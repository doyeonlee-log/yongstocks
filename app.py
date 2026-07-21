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

# 2. 사이드바 - 글로벌 옵션 설정 (금액 옵션 제거 완료)
st.sidebar.header("🛠️ 대시보드 설정")
target_subject = st.sidebar.selectbox(
    "분석할 투자 주체 선택:",
    ("외국인", "기관", "개인")
)

# 주체별 컬럼 매핑 사전
subject_col_map = {
    "외국인": "Foreigner",
    "기관": "Institution",
    "개인": "Individual"
}

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

# [데이터 엔진: 3대 주체 CSV 읽기 지원]
@st.cache_data(ttl=3600)
def get_clean_investor_data(ticker, start, end, subject_col):
    try:
        df = pd.read_csv("data/investor_data.csv", dtype={'Ticker': str})
        df['Date'] = pd.to_datetime(df['Date'])
        df['Ticker'] = df['Ticker'].astype(str).str.zfill(6)
        
        mask = (df['Ticker'] == ticker.zfill(6)) & \
               (df['Date'] >= pd.to_datetime(start)) & \
               (df['Date'] <= pd.to_datetime(end))
        df_filtered = df.loc[mask].copy()
        
        if subject_col in df_filtered.columns:
            df_filtered['일별지표'] = df_filtered[subject_col]
        else:
            df_filtered['일별지표'] = 0
            
        return df_filtered.sort_values('Date')
    except Exception as e:
        return pd.DataFrame()

# [차트 엔진: 누적선 및 5일, 10일, 20일 이동평균선 추가]
def draw_pure_zero_start_chart(df, label_name, subject_name):
    df = df.sort_values(by='Date').reset_index(drop=True)
    df['누적지표'] = df['일별지표'].cumsum()
    first_day_cum = df['누적지표'].iloc[0] if not df['누적지표'].empty else 0
    df['정렬영점누적'] = df['누적지표'] - first_day_cum

    df['MA_5'] = df['정렬영점누적'].rolling(window=5).mean()
    df['MA_10'] = df['정렬영점누적'].rolling(window=10).mean()
    df['MA_20'] = df['정렬영점누적'].rolling(window=20).mean()

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = ['red' if val >= 0 else 'blue' for val in df['일별지표']]

    fig.add_trace(go.Bar(x=df['Date'], y=df['일별지표'], marker_color=colors, name=f"{subject_name} 당일 순매수", opacity=0.4), secondary_y=False)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['정렬영점누적'], mode='lines', name=f"{subject_name} 누적 수급선", line=dict(color='#2CA02C', width=2)), secondary_y=True)

    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA_5'], mode='lines', name="5일 이평선", line=dict(color='orange', width=1.2, dash='solid')), secondary_y=True)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA_10'], mode='lines', name="10일 이평선", line=dict(color='purple', width=1.2, dash='dash')), secondary_y=True)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA_20'], mode='lines', name="20일 이평선", line=dict(color='deeppink', width=1.2, dash='dot')), secondary_y=True)

    fig.update_layout(template="plotly_white", height=480, hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig

# ==========================================
# 🔍 탭 1: 개별 종목 분석
# ==========================================
with tab1:
    st.header(f"🔍 종목별 상세 [{target_subject}] 수급 및 이동평균선 추세 분석")
    col_input1, col_input2 = st.columns([2, 2])
    with col_input1:
        selected_stock = st.selectbox("📊 분석할 종목을 입력하거나 고르세요:", stock_df['선택용_이름'], key="individual_select")
        selected_ticker = stock_df[stock_df['선택용_이름'] == selected_stock]['티커'].values[0]
        selected_name = stock_df[stock_df['선택용_이름'] == selected_stock]['종목명'].values[0]

    with col_input2:
        date_range_1 = st.date_input("📅 분석 기간을 선택하세요:", value=(datetime.date(2026, 1, 1), datetime.date.today()))

    if isinstance(date_range_1, tuple) and len(date_range_1) == 2:
        col_name = subject_col_map[target_subject]
        df_daily = get_clean_investor_data(selected_ticker, date_range_1[0], date_range_1[1], col_name)
        
        if not df_daily.empty:
            fig = draw_pure_zero_start_chart(df_daily, selected_name, target_subject)
            fig.update_layout(title=f"📊 {selected_name} [{target_subject}] 주식 수량 기준 수급 흐름 및 이동평균선")
            st.plotly_chart(fig, use_container_width=True)
            st.metric(f"기간 내 {target_subject} 누적 증감량 (주)", f"{df_daily['일별지표'].sum():,.0f}")
        else:
            st.error("데이터가 없습니다. init_data.py를 먼저 실행해 주세요.")

# ==========================================
# ⭐ 탭 2: 나의 새싹 즐겨찾기 추세 레이더
# ==========================================
with tab2:
    st.header("🌱 나의 관심 새싹 수급 추세 레이더")
    favorite_stocks = st.multiselect("📌 즐겨찾기 종목:", options=stock_df['선택용_이름'], default=default_favs, key="fav_box")
    
    if favorite_stocks:
        local_storage.setItem("my_sprout_favorites", ",".join(favorite_stocks))
        col_name = subject_col_map[target_subject]
        
        for stock_name in favorite_stocks:
            ticker = stock_df[stock_df['선택용_이름'] == stock_name]['티커'].values[0]
            name = stock_df[stock_df['선택용_이름'] == stock_name]['종목명'].values[0]
            df_fav = get_clean_investor_data(ticker, datetime.date(2026, 1, 1), datetime.date.today(), col_name)
            
            if not df_fav.empty:
                fig = draw_pure_zero_start_chart(df_fav, name, target_subject)
                fig.update_layout(title=f"📈 {name} [{target_subject}] 수급 및 이동평균선", height=400)
                st.plotly_chart(fig, use_container_width=True)
