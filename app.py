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

# [UI/UX 다듬기] 거슬리는 기본 주황색 탭 배경 제거 및 깔끔한 상단 포인트 라인 적용
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 2px solid #e9ecef; }
    .stTabs [data-baseweb="tab"] { 
        height: 48px; 
        white-space: pre-wrap; 
        background-color: #ffffff; 
        border-radius: 8px 8px 0px 0px; 
        font-weight: 600;
        font-size: 15px;
        color: #495057;
        border: 1px solid #dee2e6;
        border-bottom: none;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #ffffff !important; 
        color: #0047AB !important; 
        border-top: 3px solid #0047AB !important; 
        border-bottom: 2px solid #ffffff !important;
        font-weight: 700;
    }
    div.stExpander { border-radius: 8px; border: 1px solid #e0e0e0; background-color: white; }
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; letter-spacing: -0.5px; }
    </style>
""", unsafe_allow_html=True)

local_storage = LocalStorage()

# 2. 사이드바 - 글로벌 옵션 설정 (교수님 원본 구조)
st.sidebar.header("🛠️ 대시보드 설정")
target_subject = st.sidebar.selectbox(
    "분석할 투자 주체 선택:",
    ("외국인", "기관", "개인")
)

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

# 탭 5개 구성
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔎 개별 종목 분석", 
    "🌱 새싹 발굴", 
    "🚀 희망 종목", 
    "⚠️ 정리 종목",
    "⭐ 나의 새싹 즐겨찾기"
])

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

# [차트 엔진: 모바일 핀치 줌 및 PC 드래그 확대/축소 자연스럽도록 최적화 반영]
def draw_pure_zero_start_chart(df, label_name, subject_name):
    df = df.sort_values(by='Date').reset_index(drop=True)
    df['누적지표'] = df['일별지표'].cumsum()
    first_day_cum = df['누적지표'].iloc[0] if not df['누적지표'].empty else 0
    df['정렬영점누적'] = df['누적지표'] - first_day_cum

    df['MA_5'] = df['정렬영점누적'].rolling(window=5).mean()
    df['MA_10'] = df['정렬영점누적'].rolling(window=10).mean()
    df['MA_20'] = df['정렬영점누적'].rolling(window=20).mean()

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    bar_colors = ['red' if val >= 0 else 'blue' for val in df['일별지표']]

    # 범례 아이콘만 회색으로 고정하기 위한 더미 트레이스
    fig.add_trace(go.Bar(
        x=df['Date'], y=[0] * len(df), 
        name=f"{subject_name} 당일 순매수", 
        marker_color='lightgray',
        showlegend=True,
        hoverinfo='skip'
    ), secondary_y=False)

    # 실제 차트에 그려지는 컬러 막대
    fig.add_trace(go.Bar(
        x=df['Date'], y=df['일별지표'], 
        marker_color=bar_colors, 
        name="", 
        showlegend=False, 
        opacity=0.5,
        width=24 * 3600 * 1000 * 0.7
    ), secondary_y=False)

    # 누적 수급선
    fig.add_trace(go.Scatter(
        x=df['Date'], y=df['정렬영점누적'], mode='lines', 
        name=f"{subject_name} 누적 수급선", line=dict(color='#2CA02C', width=2.5)
    ), secondary_y=True)

    # 이동평균선들
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA_5'], mode='lines', name="5일 이평선", line=dict(color='orange', width=1.5, dash='solid')), secondary_y=True)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA_10'], mode='lines', name="10일 이평선", line=dict(color='purple', width=1.5, dash='dash')), secondary_y=True)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA_20'], mode='lines', name="20일 이평선", line=dict(color='deeppink', width=1.5, dash='dot')), secondary_y=True)

    fig.update_layout(
        template="plotly_white", height=450, hovermode="x unified", 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        dragmode="zoom",
        uirevision="constant"
    )
    return fig

# [기획서 원문 반영 분류 알고리즘]
@st.cache_data(ttl=3600)
def classify_stock_groups(subject_col):
    if not os.path.exists("data/investor_data.csv"):
        return [], [], []
    
    df_all = pd.read_csv("data/investor_data.csv", dtype={'Ticker': str})
    df_all['Date'] = pd.to_datetime(df_all['Date'])
    df_all['Ticker'] = df_all['Ticker'].astype(str).str.zfill(6)
    
    sprout_list = []
    hope_list = []
    clean_list = []
    
    grouped = df_all.groupby('Ticker')
    
    for ticker, group in grouped:
        group = group.sort_values('Date')
        if len(group) < 10: 
            continue
            
        sub_series = group[subject_col].fillna(0)
        
        recent_5 = sub_series.iloc[-5:].sum()
        prev_5 = sub_series.iloc[-10:-5].sum()
        
        matched_row = stock_df[stock_df['티커'] == ticker]
        if matched_row.empty:
            continue
        stock_name = matched_row['종목명'].values[0]
        display_name = f"{stock_name} ({ticker})"
        
        past_cumulative = sub_series.iloc[:-1].sum()
        latest_day = sub_series.iloc[-1]
        
        if past_cumulative <= 0 and latest_day > 0:
            sprout_list.append(display_name)
            
        if prev_5 > 0:
            growth_rate = (recent_5 - prev_5) / prev_5 * 100
            if growth_rate >= 20:
                hope_list.append(display_name)
                
        if prev_5 > 0 and recent_5 < prev_5:
            drop_rate = (prev_5 - recent_5) / prev_5 * 100
            if 10 <= drop_rate <= 30:
                clean_list.append(display_name)
            
    return sprout_list, hope_list, clean_list

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
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True})
            st.metric(f"기간 내 {target_subject} 누적 증감량 (주)", f"{df_daily['일별지표'].sum():,.0f}")
        else:
            st.error("데이터가 없습니다. init_data.py를 먼저 실행해 주세요.")

col_name = subject_col_map[target_subject]
sprouts, hopes, cleans = classify_stock_groups(col_name)

# ==========================================
# 🌱 탭 2: 새싹 발굴
# ==========================================
with tab2:
    st.header(f"🌱 [{target_subject}] 새싹 발굴 종목 리스트")
    st.info("최초로 순매수가 유입되기 시작한(과거 무매수/매도 상태에서 전환된) 기업들입니다.")
    if sprouts:
        selected_sprout = st.selectbox("발굴된 새싹 종목 선택:", sprouts, key="sprout_sel")
        s_ticker = selected_sprout.split("(")[-1].replace(")", "").strip()
        s_name = selected_sprout.split("(")[0].strip()
        
        df_sprout = get_clean_investor_data(s_ticker, datetime.date(2026, 1, 1), datetime.date.today(), col_name)
        if not df_sprout.empty:
            fig = draw_pure_zero_start_chart(df_sprout, s_name, target_subject)
            fig.update_layout(title=f"🌱 [새싹] {selected_sprout} 수급 흐름", height=450)
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True})
    else:
        st.warning("현재 조건에 부합하는 새싹 종목이 없습니다.")

# ==========================================
# 🚀 탭 3: 희망 종목
# ==========================================
with tab3:
    st.header(f"🚀 [{target_subject}] 희망 종목 리스트")
    st.info("5일 수급 추세가 직전 5일 대비 20% 이상 증가하여 탄력을 받은 기업들입니다.")
    if hopes:
        selected_hope = st.selectbox("희망 종목 선택:", hopes, key="hope_sel")
        h_ticker = selected_hope.split("(")[-1].replace(")", "").strip()
        h_name = selected_hope.split("(")[0].strip()
        
        df_hope = get_clean_investor_data(h_ticker, datetime.date(2026, 1, 1), datetime.date.today(), col_name)
        if not df_hope.empty:
            fig = draw_pure_zero_start_chart(df_hope, h_name, target_subject)
            fig.update_layout(title=f"🚀 [희망] {selected_hope} 수급 흐름", height=450)
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True})
    else:
        st.warning("현재 조건에 부합하는 희망 종목이 없습니다.")

# ==========================================
# ⚠️ 탭 4: 정리 종목
# ==========================================
with tab4:
    st.header(f"⚠️ [{target_subject}] 정리 대상 종목 리스트")
    st.info("5일 추세가 10% 이상 하락한 종목입니다. (단, 하락률 30% 초과 종목은 정리 그룹에서 자동 퇴출됩니다.)")
    if cleans:
        selected_clean = st.selectbox("정리 종목 선택:", cleans, key="clean_sel")
        c_ticker = selected_clean.split("(")[-1].replace(")", "").strip()
        c_name = selected_clean.split("(")[0].strip()
        
        df_clean = get_clean_investor_data(c_ticker, datetime.date(2026, 1, 1), datetime.date.today(), col_name)
        if not df_clean.empty:
            fig = draw_pure_zero_start_chart(df_clean, c_name, target_subject)
            fig.update_layout(title=f"⚠️ [정리] {selected_clean} 수급 흐름", height=450)
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True})
    else:
        st.warning("현재 조건에 부합하는 정리 대상 종목이 없습니다.")

# ==========================================
# ⭐ 탭 5: 나의 새싹 즐겨찾기
# ==========================================
with tab5:
    st.header(f"⭐ 나의 관심 새싹 즐겨찾기 [{target_subject}] 수급 추세 레이더")
    favorite_stocks = st.multiselect("📌 즐겨찾기 종목 선택:", options=stock_df['선택용_이름'], default=default_favs, key="fav_box")
    
    if favorite_stocks:
        local_storage.setItem("my_sprout_favorites", ",".join(favorite_stocks))
        
        for idx, stock_name in enumerate(favorite_stocks):
            ticker = stock_df[stock_df['선택용_이름'] == stock_name]['티커'].values[0]
            name = stock_df[stock_df['선택용_이름'] == stock_name]['종목명'].values[0]
            df_fav = get_clean_investor_data(ticker, datetime.date(2026, 1, 1), datetime.date.today(), col_name)
            
            if not df_fav.empty:
                fig = draw_pure_zero_start_chart(df_fav, name, target_subject)
                fig.update_layout(title=f"📈 {name} [{target_subject}] 수급 및 이동평균선", height=400)
                st.plotly_chart(fig, use_container_width=True, key=f"chart_fav_{ticker}_{idx}", config={"scrollZoom": True, "displayModeBar": True})
    else:
        st.info("즐겨찾기할 종목을 위에서 선택해 주세요.")
