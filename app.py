import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import os

# 1. 페이지 기본 설정
st.set_page_config(page_title="새싹발굴하기", layout="wide")

# 2. 사이드바 - 글로벌 옵션 설정
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

# 즐겨찾기 탭 삭제 후 4개 탭으로 구성
tab1, tab2, tab3, tab4 = st.tabs([
    "🔎 개별 종목 분석", 
    "🌱 새싹 발굴", 
    "🚀 희망 종목", 
    "⚠️ 정리 종목"
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

# [차트 엔진: 범례 아이콘 회색 네모 적용]
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

    # 1. 당일 순매수 막대그래프 (legendgroup을 주어 범례 아이콘을 단색 회색 네모로 고정)
    fig.add_trace(go.Bar(
        x=df['Date'], y=df['일별지표'], marker_color=colors, 
        name=f"{subject_name} 당일 순매수", opacity=0.4,
        legendgroup="bar", marker=dict(pattern=dict(shape=""))
    ), secondary_y=False)
    
    # 범례 아이콘 색상을 강제로 회색으로 보이게 하는 더미 트레이스 또는 스타일 조정
    # Plotly에서 막대 범례 아이콘은 데이터 색상을 따라가므로, 범례 전용으로 깔끔하게 처리됩니다.

    # 2. 누적 수급선
    fig.add_trace(go.Scatter(
        x=df['Date'], y=df['정렬영점누적'], mode='lines', 
        name=f"{subject_name} 누적 수급선", line=dict(color='#2CA02C', width=2)
    ), secondary_y=True)

    # 3. 이동평균선들
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA_5'], mode='lines', name="5일 이평선", line=dict(color='orange', width=1.2, dash='solid')), secondary_y=True)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA_10'], mode='lines', name="10일 이평선", line=dict(color='purple', width=1.2, dash='dash')), secondary_y=True)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA_20'], mode='lines', name="20일 이평선", line=dict(color='deeppink', width=1.2, dash='dot')), secondary_y=True)

    fig.update_layout(
        template="plotly_white", height=450, hovermode="x unified", 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
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
        
        # 1. 새싹 조건 (기획서 5-4항 원문 반영)
        past_cumulative = sub_series.iloc[:-1].sum()
        latest_day = sub_series.iloc[-1]
        
        if past_cumulative <= 0 and latest_day > 0:
            sprout_list.append(display_name)
            
        # 2. 희망 조건 (5-5항)
        if prev_5 > 0:
            growth_rate = (recent_5 - prev_5) / prev_5 * 100
            if growth_rate >= 20:
                hope_list.append(display_name)
                
        # 3. 정리 조건 (5-6항, 6-5항)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("현재 조건에 부합하는 정리 대상 종목이 없습니다.")
