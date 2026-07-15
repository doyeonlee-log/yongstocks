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

# 3. 상장 종목 리스트 불러오기 (로컬 파일 우선 방식 - 에러 방지)
@st.cache_data
def load_stock_list():
    # 먼저 로컬에 있는지 확인
    if os.path.exists("data/stock_list.csv"):
        return pd.read_csv("data/stock_list.csv")
    else:
        # 없으면 한 번 가져와서 저장
        try:
            df = fdr.StockListing('KRX')
            df_filtered = df[df['Market'].isin(['KOSPI', 'KOSDAQ'])][['Code', 'Name', 'Market']]
            df_filtered.columns = ['티커', '종목명', '시장']
            if not os.path.exists("data"): os.makedirs("data")
            df_filtered.to_csv("data/stock_list.csv", index=False)
            return df_filtered
        except:
            st.error("종목 리스트를 가져오는데 실패했습니다. data/stock_list.csv 파일이 필요합니다.")
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

# 4. 데이터 로드 엔진 (이제 로컬 파일에서 읽음)
@st.cache_data(ttl=3600)
def get_clean_foreigner_data(ticker, start, end):
    try:
        # GitHub Actions가 쌓아둔 실제 데이터 파일 읽기
        df_all = pd.read_csv("data/investor_data.csv")
        df_all['Date'] = pd.to_datetime(df_all['Date'])
        
        # 해당 티커와 기간 필터링
        mask = (df_all['Ticker'].astype(str).str.zfill(6) == ticker.zfill(6)) & \
               (df_all['Date'] >= pd.to_datetime(start)) & \
               (df_all['Date'] <= pd.to_datetime(end))
        df = df_all.loc[mask].copy()
        
        # 'NetBuying' 컬럼을 차트용 '일별지표'로 이름 변경
        df = df.rename(columns={'NetBuying': '일별지표'})
        return df
    except Exception as e:
        st.write(f"데이터 로드 오류: {e}")
        return pd.DataFrame()

# 5. 차트 엔진
def draw_pure_zero_start_chart(df, label_name, unit_label):
    if df.empty: return go.Figure()
    
    df = df.sort_values(by='Date').reset_index(drop=True)
    df['누적지표'] = df['일별지표'].cumsum()
    first_day_cum = df['누적지표'].iloc[0]
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
        selected_stock = st.selectbox("📊 분석할 종목을 선택하세요:", stock_df['선택용_이름'], key="individual_select")
        selected_ticker = stock_df[stock_df['선택용_이름'] == selected_stock]['티커'].values[0]
    
    with col_input2:
        date_range_1 = st.date_input("📅 분석 기간:", value=(datetime.date(2026, 1, 1), datetime.date.today()))

    if isinstance(date_range_1, tuple) and len(date_range_1) == 2:
        df_daily = get_clean_foreigner_data(selected_ticker, date_range_1[0], date_range_1[1])
        
        if not df_daily.empty:
            hover_unit = "억 원" if display_option == "금액 기준 (억 원)" else "만 주"
            fig = draw_pure_zero_start_chart(df_daily, selected_stock, hover_unit)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("데이터가 없습니다. CSV 파일 경로와 데이터를 확인하세요.")

# ==========================================
# ⭐ 탭 2: 나의 새싹 즐겨찾기
# ==========================================
with tab2:
    st.header("🌱 나의 관심 새싹 외국인 누적 추세")
    favorite_stocks = st.multiselect("📌 즐겨찾기 종목:", options=stock_df['선택용_이름'], default=default_favs)
    
    if favorite_stocks:
        local_storage.setItem("my_sprout_favorites", ",".join(favorite_stocks))
        for stock_name in favorite_stocks:
            ticker = stock_df[stock_df['선택용_이름'] == stock_name]['티커'].values[0]
            df_fav = get_clean_foreigner_data(ticker, datetime.date(2026, 1, 1), datetime.date.today())
            
            if not df_fav.empty:
                fig = draw_pure_zero_start_chart(df_fav, stock_name, "수급량")
                fig.update_layout(title=f"📈 {stock_name}")
                st.plotly_chart(fig, use_container_width=True)
