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

# 3. 상장 종목 리스트 불러오기
@st.cache_data
def load_stock_list():
    if os.path.exists("data/stock_list.csv"):
        return pd.read_csv("data/stock_list.csv")
    else:
        df = fdr.StockListing('KRX')
        df_filtered = df[df['Market'].isin(['KOSPI', 'KOSDAQ'])][['Code', 'Name', 'Market']]
        df_filtered.columns = ['티커', '종목명', '시장']
        if not os.path.exists("data"): os.makedirs("data")
        df_filtered.to_csv("data/stock_list.csv", index=False)
        return df_filtered

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

# [데이터 엔진: 계산식 제거 -> CSV 읽기]
@st.cache_data(ttl=3600)
def get_clean_foreigner_data(ticker, start, end):
    try:
        # 1. 파일 읽기 (Ticker를 문자열로 명시하여 005930 등이 5930으로 변하는 것 방지)
        df = pd.read_csv("data/investor_data.csv", dtype={'Ticker': str}) 
        
        # 2. 날짜 컬럼 변환
        df['Date'] = pd.to_datetime(df['Date'])
        
        # 3. Ticker 형식 통일 (혹시 모를 공백이나 형식을 zfill로 맞춤)
        df['Ticker'] = df['Ticker'].astype(str).str.zfill(6)
        
        # 4. 필터링
        mask = (df['Ticker'] == ticker.zfill(6)) & \
               (df['Date'] >= pd.to_datetime(start)) & \
               (df['Date'] <= pd.to_datetime(end))
        df_filtered = df.loc[mask].copy()
        
        # 5. 시각화 함수가 읽기 좋게 이름 변경
        df_filtered = df_filtered.rename(columns={'NetBuying': '일별지표'})
        
        # 6. 날짜순 정렬 (차트가 꼬이지 않게)
        return df_filtered.sort_values('Date')
        
    except Exception as e:
        # 에러가 나면 화면에 붉은색으로 띄우지 않고, 빈 데이터프레임 반환
        return pd.DataFrame()

# [차트 엔진: 그대로 유지]
def draw_pure_zero_start_chart(df, label_name, unit_label):
    df = df.sort_values(by='Date').reset_index(drop=True)
    df['누적지표'] = df['일별지표'].cumsum()
    first_day_cum = df['누적지표'].iloc[0] if not df['누적지표'].empty else 0
    df['정렬영점누적'] = df['누적지표'] - first_day_cum

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = ['red' if val >= 0 else 'blue' for val in df['일별지표']]

    fig.add_trace(go.Bar(x=df['Date'], y=df['일별지표'], marker_color=colors, name="당일 외국인 순매매", opacity=0.55), secondary_y=False)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['정렬영점누적'], mode='lines', name="외국인 누적 수급선", line=dict(color='#2CA02C', width=1.6)), secondary_y=True)

    fig.update_layout(template="plotly_white", height=450, hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig

# ==========================================
# 🔍 탭 1: 개별 종목 분석
# ==========================================
with tab1:
    st.header("🔍 종목별 상세 외국인 수급 추세 분석")
    col_input1, col_input2 = st.columns([2, 2])
    with col_input1:
        selected_stock = st.selectbox("📊 분석할 종목을 입력하거나 고르세요:", stock_df['선택용_이름'], key="individual_select")
        selected_ticker = stock_df[stock_df['선택용_이름'] == selected_stock]['티커'].values[0]
        selected_name = stock_df[stock_df['선택용_이름'] == selected_stock]['종목명'].values[0]

    with col_input2:
        date_range_1 = st.date_input("📅 분석 기간을 선택하세요:", value=(datetime.date(2026, 1, 1), datetime.date.today()))

    if isinstance(date_range_1, tuple) and len(date_range_1) == 2:
        df_daily = get_clean_foreigner_data(selected_ticker, date_range_1[0], date_range_1[1])
        if not df_daily.empty:
            hover_unit = "단위(수량)" # CSV 데이터의 단위에 맞춤
            fig = draw_pure_zero_start_chart(df_daily, selected_name, hover_unit)
            fig.update_layout(title=f"📊 {selected_name} 외국인 당일/누적 수급 흐름")
            st.plotly_chart(fig, use_container_width=True)
            st.metric("기간 내 외인 누적 증감량", f"{df_daily['일별지표'].sum():,.0f}")
        else:
            st.error("데이터가 없습니다. update_data.py를 실행하세요.")

# ==========================================
# ⭐ 탭 2: 나의 새싹 즐겨찾기 추세 레이더
# ==========================================
with tab2:
    st.header("🌱 나의 관심 새싹 외국인 누적 추세 레이더")
    favorite_stocks = st.multiselect("📌 즐겨찾기 종목:", options=stock_df['선택용_이름'], default=default_favs, key="fav_box")
    
    if favorite_stocks:
        local_storage.setItem("my_sprout_favorites", ",".join(favorite_stocks))
        for stock_name in favorite_stocks:
            ticker = stock_df[stock_df['선택용_이름'] == stock_name]['티커'].values[0]
            name = stock_df[stock_df['선택용_이름'] == stock_name]['종목명'].values[0]
            df_fav = get_clean_foreigner_data(ticker, datetime.date(2026, 1, 1), datetime.date.today())
            
            if not df_fav.empty:
                fig = draw_pure_zero_start_chart(df_fav, name, "수량")
                fig.update_layout(title=f"📈 {name} 외국인 당일/누적 수급 흐름", height=400)
                st.plotly_chart(fig, use_container_width=True)
