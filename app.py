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
display_option = st.sidebar.radio(
    "데이터 보기 방식 선택:",
    ("수량 기준 (만 주)", "금액 기준 (억 원)")
)

# 3. 상장 종목 리스트 불러오기 함수 (배포 안정화 버전)
@st.cache_data
def load_stock_list():
    # 데이터 폴더가 없으면 생성
    if not os.path.exists("data"):
        os.makedirs("data")
        
    # 저장된 파일이 있으면 읽고, 없으면 생성
    file_path = "data/stock_list.csv"
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    else:
        try:
            df = fdr.StockListing('KRX')
            df_filtered = df[df['Market'].isin(['KOSPI', 'KOSDAQ'])][['Code', 'Name', 'Market']]
            df_filtered.columns = ['티커', '종목명', '시장']
            df_filtered.to_csv(file_path, index=False)
            return df_filtered
        except Exception as e:
            st.error(f"종목 리스트 초기화 실패: {e}")
            return pd.DataFrame(columns=['티커', '종목명', '시장'])

stock_df = load_stock_list()
stock_df['티커'] = stock_df['티커'].astype(str).str.zfill(6)
stock_df['선택용_이름'] = stock_df['종목명'] + " (" + stock_df['티커'] + ")"

# 즐겨찾기 목록 로컬 스토리지 동기화
saved_favs = local_storage.getItem("my_sprout_favorites")
if saved_favs is None:
    default_favs = [stock_df['선택용_이름'].iloc[100], stock_df['선택용_이름'].iloc[120]] if len(stock_df) > 130 else []
else:
    default_favs = [x.strip() for x in saved_favs.split(",") if x.strip() in stock_df['선택용_이름'].values]

# 탭 구성
tab1, tab2 = st.tabs(["🔎 개별 종목 분석", "🌱 나의 새싹 즐겨찾기"])

# 공통 데이터 로딩 함수
@st.cache_data(ttl=3600)
def get_clean_foreigner_data(ticker, start, end):
    try:
        df = fdr.DataReader(ticker, start, end)
        return df
    except:
        return pd.DataFrame()

# 차트 시각화 엔진
def draw_pure_zero_start_chart(df, label_name, unit_label):
    df = df.sort_values(by='Date').reset_index(drop=True)
    df['누적지표'] = df['일별지표'].cumsum()
    first_day_cum = df['누적지표'].iloc[0] if not df['누적지표'].empty else 0
    df['정렬영점누적'] = df['누적지표'] - first_day_cum

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = ['red' if val >= 0 else 'blue' for val in df['일별지표']]

    fig.add_trace(go.Bar(x=df['Date'], y=df['일별지표'], marker_color=colors, name="당일 외국인 순매매", showlegend=True, opacity=0.55), secondary_y=False)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['정렬영점누적'], mode='lines', name="외국인 누적 수급선", showlegend=True, line=dict(color='#2CA02C', width=1.6)), secondary_y=True)

    fig.update_layout(template="plotly_white", height=450, hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig

# 🔍 탭 1: 개별 종목 분석
with tab1:
    st.header("🔍 종목별 상세 외국인 수급 추세 분석")
    col_input1, col_input2 = st.columns([2, 2])
    with col_input1:
        selected_stock = st.selectbox("📊 분석할 종목 선택:", stock_df['선택용_이름'], key="individual_select")
        selected_ticker = stock_df[stock_df['선택용_이름'] == selected_stock]['티커'].values[0]
        selected_name = stock_df[stock_df['선택용_이름'] == selected_stock]['종목명'].values[0]
    with col_input2:
        date_range_1 = st.date_input("📅 분석 기간:", value=(datetime.date(2026, 1, 1), datetime.date.today()), key="ind_date")

    if isinstance(date_range_1, tuple) and len(date_range_1) == 2:
        df_daily = get_clean_foreigner_data(selected_ticker, date_range_1[0].strftime("%Y-%m-%d"), date_range_1[1].strftime("%Y-%m-%d"))
        if not df_daily.empty:
            df_daily = df_daily.reset_index()
            hover_unit = "억 원" if display_option == "금액 기준 (억 원)" else "만 주"
            df_daily['일별지표'] = (df_daily['Close'] * df_daily['Volume'] * df_daily['Change']) / 100000000 if display_option == "금액 기준 (억 원)" else (df_daily['Volume'] * df_daily['Change']) / 10000
            
            fig = draw_pure_zero_start_chart(df_daily, selected_name, hover_unit)
            st.plotly_chart(fig, use_container_width=True)

# ⭐ 탭 2: 즐겨찾기
with tab2:
    st.header("🌱 나의 관심 새싹 즐겨찾기")
    favorite_stocks = st.multiselect("📌 즐겨찾기 종목:", options=stock_df['선택용_이름'], default=default_favs, key="fav_box")
    if favorite_stocks:
        local_storage.setItem("my_sprout_favorites", ",".join(favorite_stocks))
        for stock_name in favorite_stocks:
            ticker = stock_df[stock_df['선택용_이름'] == stock_name]['티커'].values[0]
            st.write(f"### {stock_name} 분석 중...")
            df_fav = get_clean_foreigner_data(ticker, "2026-01-01", datetime.date.today().strftime("%Y-%m-%d"))
            if not df_fav.empty:
                df_fav = df_fav.reset_index()
                df_fav['일별지표'] = (df_fav['Volume'] * df_fav['Change']) / 10000
                st.plotly_chart(draw_pure_zero_start_chart(df_fav, stock_name, "만 주"), use_container_width=True)
