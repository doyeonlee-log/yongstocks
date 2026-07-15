import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import os
from streamlit_local_storage import LocalStorage

# 1. 페이지 기본 설정 및 로컬 스토리지 초기화
st.set_page_config(page_title="새싹발굴하기", layout="wide")
local_storage = LocalStorage()

# 2. 사이드바 - 글로벌 옵션 설정
st.sidebar.header("🛠️ 대시보드 설정")
display_option = st.sidebar.radio("데이터 보기 방식 선택:", ("수량 기준 (만 주)", "금액 기준 (억 원)"))

# 3. 상장 종목 리스트 불러오기 함수
@st.cache_data
def load_stock_list():
    if not os.path.exists("data"): os.makedirs("data")
    if os.path.exists("data/stock_list.csv"): return pd.read_csv("data/stock_list.csv")
    else:
        try:
            df = fdr.StockListing('KRX')
            df_filtered = df[df['Market'].isin(['KOSPI', 'KOSDAQ'])][['Code', 'Name', 'Market']]
            df_filtered.columns = ['티커', '종목명', '시장']
            df_filtered.to_csv("data/stock_list.csv", index=False)
            return df_filtered
        except: return pd.DataFrame(columns=['티커', '종목명', '시장'])

stock_df = load_stock_list()
stock_df['티커'] = stock_df['티커'].astype(str).str.zfill(6)
stock_df['선택용_이름'] = stock_df['종목명'] + " (" + stock_df['티커'] + ")"

saved_favs = local_storage.getItem("my_sprout_favorites")
default_favs = [x.strip() for x in saved_favs.split(",")] if saved_favs else []

tab1, tab2 = st.tabs(["🔎 개별 종목 분석", "🌱 나의 새싹 즐겨찾기"])

@st.cache_data(ttl=3600)
def get_clean_foreigner_data(ticker, start, end):
    try:
        # 팩트 데이터: 네이버 금융 기반 데이터 호출
        df = fdr.DataReader(ticker, start, end, data_source='naver')
        return df
    except: return pd.DataFrame()

# 💡 0점 고정 차트 엔진 (데이터 없으면 0으로 처리)
def draw_pure_zero_start_chart(df, unit_label):
    # Foreigner 컬럼이 없으면 0으로 채우기 (절대 추정치 사용 안 함)
    if 'Foreigner' not in df.columns:
        df['Foreigner'] = 0
    else:
        df['Foreigner'] = df['Foreigner'].fillna(0)

    df = df.sort_values(by='Date').reset_index(drop=True)
    df['일별지표'] = df['Foreigner'] # 실제 Foreigner 데이터만 사용
    df['누적지표'] = df['일별지표'].cumsum()
    
    first_day_cum = df['누적지표'].iloc[0] if not df['누적지표'].empty else 0
    df['정렬영점누적'] = df['누적지표'] - first_day_cum

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = ['red' if val >= 0 else 'blue' for val in df['일별지표']]
    
    fig.add_trace(go.Bar(x=df['Date'], y=df['일별지표'], marker_color=colors, name="당일 외국인 순매매", opacity=0.55), secondary_y=False)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['정렬영점누적'], mode='lines', name="외국인 누적 수급선", line=dict(color='#2CA02C', width=2)), secondary_y=True)
    
    # Y축 범위 고정
    max_bar = max(abs(df['일별지표'].max()), abs(df['일별지표'].min())) * 1.2
    max_line = max(abs(df['정렬영점누적'].max()), abs(df['정렬영점누적'].min())) * 1.2
    fig.update_yaxes(range=[-max_bar, max_bar], secondary_y=False, zeroline=True)
    fig.update_yaxes(range=[-max_line, max_line], secondary_y=True, zeroline=True, zerolinecolor='black')
    
    fig.update_layout(template="plotly_white", height=450, hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig

# 🔍 탭 1
with tab1:
    col1, col2 = st.columns([2, 2])
    with col1:
        selected_stock = st.selectbox("📊 분석할 종목:", stock_df['선택용_이름'], key="ind_select")
        ticker = stock_df[stock_df['선택용_이름'] == selected_stock]['티커'].values[0]
    with col2:
        date_range = st.date_input("📅 기간:", value=(datetime.date(2026, 1, 1), datetime.date.today()))
    
    if len(date_range) == 2:
        df = get_clean_foreigner_data(ticker, date_range[0].strftime("%Y-%m-%d"), date_range[1].strftime("%Y-%m-%d"))
        if not df.empty:
            # 금액 기준일 때만 Close 사용, 나머지는 Foreigner 데이터 그대로 사용
            if display_option == "금액 기준 (억 원)":
                df['Foreigner'] = (df['Foreigner'].fillna(0) * df['Close']) / 100000000
            else:
                df['Foreigner'] = df['Foreigner'].fillna(0) / 10000
            st.plotly_chart(draw_pure_zero_start_chart(df, display_option), use_container_width=True)
        else: st.error("데이터를 가져올 수 없습니다.")

# ⭐ 탭 2
with tab2:
    favorite_stocks = st.multiselect("📌 즐겨찾기:", options=stock_df['선택용_이름'], default=default_favs, key="fav_box")
    local_storage.setItem("my_sprout_favorites", ",".join(favorite_stocks))
    for stock_name in favorite_stocks:
        ticker = stock_df[stock_df['선택용_이름'] == stock_name]['티커'].values[0]
        df = get_clean_foreigner_data(ticker, "2026-01-01", datetime.date.today().strftime("%Y-%m-%d"))
        if not df.empty:
            df['Foreigner'] = df['Foreigner'].fillna(0) / 10000
            st.plotly_chart(draw_pure_zero_start_chart(df, "만 주"), use_container_width=True)
            st.markdown("---")
