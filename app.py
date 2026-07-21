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

# [개선] 5번 항목에 맞춰 단일 선택 대신 다중 주체 선택(멀티셀렉터) 지원
target_subjects = st.sidebar.multiselect(
    "비교할 투자 주체 선택 (다중 선택 가능):",
    ["외국인", "기관", "개인"],
    default=["외국인"]
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

# [데이터 엔진: 3대 주체 데이터를 한번에 로드]
@st.cache_data(ttl=3600)
def get_all_investor_data(ticker, start, end):
    try:
        df = pd.read_csv("data/investor_data.csv", dtype={'Ticker': str})
        df['Date'] = pd.to_datetime(df['Date'])
        df['Ticker'] = df['Ticker'].astype(str).str.zfill(6)
        
        mask = (df['Ticker'] == ticker.zfill(6)) & \
               (df['Date'] >= pd.to_datetime(start)) & \
               (df['Date'] <= pd.to_datetime(end))
        df_filtered = df.loc[mask].copy()
        return df_filtered.sort_values('Date')
    except Exception as e:
        return pd.DataFrame()

# [차트 엔진: 멀티 주체 비교 차트 구현]
def draw_multi_subject_chart(df, label_name, selected_subs):
    df = df.sort_values(by='Date').reset_index(drop=True)
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # 주체별 고유 색상 지정
    color_map = {
        "외국인": "#1f77b4",  # 파랑
        "기관": "#ff7f0e",    # 주황
        "개인": "#d62728"     # 빨강
    }
    
    for sub in selected_subs:
        col_name = subject_col_map[sub]
        if col_name in df.columns:
            # 영점 기준 누적 수급선 계산
            series = df[col_name].fillna(0)
            cum_series = series.cumsum()
            first_val = cum_series.iloc[0] if not cum_series.empty else 0
            aligned_cum = cum_series - first_val
            
            # 주체별 누적 수급선 추가
            fig.add_trace(go.Scatter(
                x=df['Date'], y=aligned_cum, mode='lines', 
                name=f"{sub} 누적 수급선", 
                line=dict(color=color_map.get(sub, 'gray'), width=2)
            ), secondary_y=True)

    fig.update_layout(
        template="plotly_white", height=480, hovermode="x unified", 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title=f"📈 {label_name} - 멀티 투자 주체 누적 수급 비교"
    )
    return fig

# [기존 단일 차트 엔진 (새싹/희망/정리 탭용)]
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

    fig.add_trace(go.Bar(
        x=df['Date'], y=[0] * len(df), 
        name=f"{subject_name} 당일 순매수", 
        marker_color='lightgray',
        showlegend=True,
        hoverinfo='skip'
    ), secondary_y=False)

    fig.add_trace(go.Bar(
        x=df['Date'], y=df['일별지표'], 
        marker_color=colors, 
        name="", 
        showlegend=False, 
        opacity=0.5,
        width=24 * 3600 * 1000 * 0.7
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=df['Date'], y=df['정렬영점누적'], mode='lines', 
        name=f"{subject_name} 누적 수급선", line=dict(color='#2CA02C', width=2.5)
    ), secondary_y=True)

    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA_5'], mode='lines', name="5일 이평선", line=dict(color='orange', width=1.5, dash='solid')), secondary_y=True)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA_10'], mode='lines', name="10일 이평선", line=dict(color='purple', width=1.5, dash='dash')), secondary_y=True)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA_20'], mode='lines', name="20일 이평선", line=dict(color='deeppink', width=1.5, dash='dot')), secondary_y=True)

    fig.update_layout(
        template="plotly_white", height=450, hovermode="x unified", 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# [분류 알고리즘 (대표 기준 주체인 외국인 기준 스크리닝 유지)]
@st.cache_data(ttl=3600)
def classify_stock_groups(subject_col):
    if not os.path.exists("data/investor_data.csv"):
        return [], [], []
    
    df_all = pd.read_csv("data/investor_data.csv", dtype={'Ticker': str})
    df_all['Date'] = pd.to_datetime(df_all['Date'])
    df_all['Ticker'] = df_all['Ticker'].astype(str).str.zfill(6)
    
    sprout_list, hope_list, clean_list = [], [], []
    grouped = df_all.groupby('Ticker')
    
    for ticker, group in grouped:
        group = group.sort_values('Date')
        if len(group) < 10: continue
            
        sub_series = group[subject_col].fillna(0)
        recent_5 = sub_series.iloc[-5:].sum()
        prev_5 = sub_series.iloc[-10:-5].sum()
        
        matched_row = stock_df[stock_df['티커'] == ticker]
        if matched_row.empty: continue
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
# 🔍 탭 1: 개별 종목 분석 (멀티 주체 비교 적용)
# ==========================================
with tab1:
    st.header("🔍 종목별 상세 통합 멀티 수급 비교 분석")
    col_input1, col_input2 = st.columns([2, 2])
    with col_input1:
        selected_stock = st.selectbox("📊 분석할 종목을 입력하거나 고르세요:", stock_df['선택용_이름'], key="individual_select")
        selected_ticker = stock_df[stock_df['선택용_이름'] == selected_stock]['티커'].values[0]
        selected_name = stock_df[stock_df['선택용_이름'] == selected_stock]['종목명'].values[0]

    with col_input2:
        date_range_1 = st.date_input("📅 분석 기간을 선택하세요:", value=(datetime.date(2026, 1, 1), datetime.date.today()))

    if isinstance(date_range_1, tuple) and len(date_range_1) == 2:
        df_all_data = get_all_investor_data(selected_ticker, date_range_1[0], date_range_1[1])
        
        if not df_all_data.empty and target_subjects:
            fig_multi = draw_multi_subject_chart(df_all_data, selected_name, target_subjects)
            st.plotly_chart(fig_multi, use_container_width=True)
        else:
            st.warning("비교할 주체를 사이드바에서 선택해 주시거나 데이터가 있는지 확인해 주세요.")

# 스크리닝 기준은 기본 외국인(Foreigner)으로 수행
sprouts, hopes, cleans = classify_stock_groups("Foreigner")

# ==========================================
# 🌱 탭 2: 새싹 발굴
# ==========================================
with tab2:
    st.header("🌱 새싹 발굴 종목 리스트 (외국인 기준)")
    st.info("최초로 순매수가 유입되기 시작한(과거 무매수/매도 상태에서 전환된) 기업들입니다.")
    if sprouts:
        selected_sprout = st.selectbox("발굴된 새싹 종목 선택:", sprouts, key="sprout_sel")
        s_ticker = selected_sprout.split("(")[-1].replace(")", "").strip()
        s_name = selected_sprout.split("(")[0].strip()
        
        df_sprout = get_all_investor_data(s_ticker, datetime.date(2026, 1, 1), datetime.date.today())
        if not df_sprout.empty:
            df_sprout['일별지표'] = df_sprout['Foreigner']
            fig = draw_pure_zero_start_chart(df_sprout, s_name, "외국인")
            fig.update_layout(title=f"🌱 [새싹] {selected_sprout} 수급 흐름", height=450)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("현재 조건에 부합하는 새싹 종목이 없습니다.")

# ==========================================
# 🚀 탭 3: 희망 종목
# ==========================================
with tab3:
    st.header("🚀 희망 종목 리스트 (외국인 기준)")
    st.info("5일 수급 추세가 직전 5일 대비 20% 이상 증가하여 탄력을 받은 기업들입니다.")
    if hopes:
        selected_hope = st.selectbox("희망 종목 선택:", hopes, key="hope_sel")
        h_ticker = selected_hope.split("(")[-1].replace(")", "").strip()
        h_name = selected_hope.split("(")[0].strip()
        
        df_hope = get_all_investor_data(h_ticker, datetime.date(2026, 1, 1), datetime.date.today())
        if not df_hope.empty:
            df_hope['일별지표'] = df_hope['Foreigner']
            fig = draw_pure_zero_start_chart(df_hope, h_name, "외국인")
            fig.update_layout(title=f"🚀 [희망] {selected_hope} 수급 흐름", height=450)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("현재 조건에 부합하는 희망 종목이 없습니다.")

# ==========================================
# ⚠️ 탭 4: 정리 종목
# ==========================================
with tab4:
    st.header("⚠️ 정리 대상 종목 리스트 (외국인 기준)")
    st.info("5일 추세가 10% 이상 하락한 종목입니다. (단, 하락률 30% 초과 종목은 정리 그룹에서 자동 퇴출됩니다.)")
    if cleans:
        selected_clean = st.selectbox("정리 종목 선택:", cleans, key="clean_sel")
        c_ticker = selected_clean.split("(")[-1].replace(")", "").strip()
        c_name = selected_clean.split("(")[0].strip()
        
        df_clean = get_all_investor_data(c_ticker, datetime.date(2026, 1, 1), datetime.date.today())
        if not df_clean.empty:
            df_clean['일별지표'] = df_clean['Foreigner']
            fig = draw_pure_zero_start_chart(df_clean, c_name, "외국인")
            fig.update_layout(title=f"⚠️ [정리] {selected_clean} 수급 흐름", height=450)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("현재 조건에 부합하는 정리 대상 종목이 없습니다.")

# ==========================================
# ⭐ 탭 5: 나의 새싹 즐겨찾기
# ==========================================
with tab5:
    st.header("⭐ 나의 관심 새싹 즐겨찾기 수급 추세 레이더")
    favorite_stocks = st.multiselect("📌 즐겨찾기 종목 선택:", options=stock_df['선택용_이름'], default=default_favs, key="fav_box")
    
    if favorite_stocks:
        local_storage.setItem("my_sprout_favorites", ",".join(favorite_stocks))
        
        for stock_name in favorite_stocks:
            ticker = stock_df[stock_df['선택용_이름'] == stock_name]['티커'].values[0]
            name = stock_df[stock_df['선택용_이름'] == stock_name]['종목명'].values[0]
            df_fav = get_all_investor_data(ticker, datetime.date(2026, 1, 1), datetime.date.today())
            
            if not df_fav.empty:
                df_fav['일별지표'] = df_fav['Foreigner']
                fig = draw_pure_zero_start_chart(df_fav, name, "외국인")
                fig.update_layout(title=f"📈 {name} [외국인] 수급 및 이동평균선", height=400)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("즐겨찾기할 종목을 위에서 선택해 주세요.")
