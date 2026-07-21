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

# 5번 항목: 멀티 주체 비교 선택 (다중 선택)
target_subjects = st.sidebar.multiselect(
    "분석할 투자 주체 선택 (다중 선택 가능):",
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

# [탭1 전용: 멀티 주체 비교 차트 엔진]
def draw_multi_subject_chart(df, label_name, selected_subs):
    df = df.sort_values(by='Date').reset_index(drop=True)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    color_map = {
        "외국인": "#1f77b4",  # 파랑
        "기관": "#ff7f0e",    # 주황
        "개인": "#d62728"     # 빨강
    }
    
    for sub in selected_subs:
        col_name = subject_col_map[sub]
        if col_name in df.columns:
            series = df[col_name].fillna(0)
            cum_series = series.cumsum()
            first_val = cum_series.iloc[0] if not cum_series.empty else 0
            aligned_cum = cum_series - first_val
            
            # 당일 순매수 막대 (선택된 주체가 1개일 때만 가시적으로 표시하거나 투명도 조절)
            colors = ['red' if val >= 0 else 'blue' for val in series]
            fig.add_trace(go.Bar(
                x=df['Date'], y=series, marker_color=colors,
                name=f"{sub} 당일 순매수", opacity=0.3, showlegend=True
            ), secondary_y=False)
            
            # 누적 수급선
            fig.add_trace(go.Scatter(
                x=df['Date'], y=aligned_cum, mode='lines', 
                name=f"{sub} 누적 수급선", 
                line=dict(color=color_map.get(sub, 'gray'), width=2.5)
            ), secondary_y=True)

    fig.update_layout(
        template="plotly_white", height=500, hovermode="x unified", 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title=f"📈 {label_name} - 선택 주체 수급 비교 분석"
    )
    return fig

# [기타 탭 전용: 단일 주체 상세 차트 (이동평균선 포함)]
def draw_single_subject_chart(df, label_name, subject_name, col_name):
    df = df.sort_values(by='Date').reset_index(drop=True)
    df['일별지표'] = df[col_name].fillna(0)
    df['누적지표'] = df['일별지표'].cumsum()
    first_day_cum = df['누적지표'].iloc[0] if not df['누적지표'].empty else 0
    df['정렬영점누적'] = df['누적지표'] - first_day_cum

    df['MA_5'] = df['정렬영점누적'].rolling(window=5).mean()
    df['MA_10'] = df['정렬영점누적'].rolling(window=10).mean()
    df['MA_20'] = df['정렬영점누적'].rolling(window=20).mean()

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = ['red' if val >= 0 else 'blue' for val in df['일별지표']]

    fig.add_trace(go.Bar(
        x=df['Date'], y=[0] * len(df), name=f"{subject_name} 당일 순매수", 
        marker_color='lightgray', showlegend=True, hoverinfo='skip'
    ), secondary_y=False)

    fig.add_trace(go.Bar(
        x=df['Date'], y=df['일별지표'], marker_color=colors, 
        name="", showlegend=False, opacity=0.5,
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

# [분류 알고리즘 (선택한 주체 기준 동적 스크리닝)]
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

# 대표 주체 설정 (다중 선택 중 첫 번째 주체 또는 기본값)
primary_subject = target_subjects[0] if target_subjects else "외국인"
primary_col = subject_col_map[primary_subject]

# ==========================================
# 🔍 탭 1: 개별 종목 분석 (멀티 비교)
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
            st.warning("사이드바에서 비교할 주체를 최소 1개 이상 선택해 주세요.")

# 스크리닝 실행 (사이드바에서 선택한 첫 번째 주체 기준)
sprouts, hopes, cleans = classify_stock_groups(primary_col)

# ==========================================
# 🌱 탭 2: 새싹 발굴
# ==========================================
with tab2:
    st.header(f"🌱 새싹 발굴 종목 리스트 ([{primary_subject}] 기준)")
    st.info(f"최근 [{primary_subject}]의 순매수가 유입되기 시작한(과거 무매수/매도 상태에서 전환된) 기업들입니다.")
    if sprouts:
        selected_sprout = st.selectbox("발굴된 새싹 종목 선택:", sprouts, key="sprout_sel")
        s_ticker = selected_sprout.split("(")[-1].replace(")", "").strip()
        s_name = selected_sprout.split("(")[0].strip()
        
        df_sprout = get_all_investor_data(s_ticker, datetime.date(2026, 1, 1), datetime.date.today())
        if not df_sprout.empty:
            fig = draw_single_subject_chart(df_sprout, s_name, primary_subject, primary_col)
            fig.update_layout(title=f"🌱 [새싹] {selected_sprout} [{primary_subject}] 수급 흐름", height=450)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"현재 [{primary_subject}] 기준 조건에 부합하는 새싹 종목이 없습니다.")

# ==========================================
# 🚀 탭 3: 희망 종목
# ==========================================
with tab3:
    st.header(f"🚀 희망 종목 리스트 ([{primary_subject}] 기준)")
    st.info(f"5일 [{primary_subject}] 수급 추세가 직전 5일 대비 20% 이상 증가하여 탄력을 받은 기업들입니다.")
    if hopes:
        selected_hope = st.selectbox("희망 종목 선택:", hopes, key="hope_sel")
        h_ticker = selected_hope.split("(")[-1].replace(")", "").strip()
        h_name = selected_hope.split("(")[0].strip()
        
        df_hope = get_all_investor_data(h_ticker, datetime.date(2026, 1, 1), datetime.date.today())
        if not df_hope.empty:
            fig = draw_single_subject_chart(df_hope, h_name, primary_subject, primary_col)
            fig.update_layout(title=f"🚀 [희망] {selected_hope} [{primary_subject}] 수급 흐름", height=450)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"현재 [{primary_subject}] 기준 조건에 부합하는 희망 종목이 없습니다.")

# ==========================================
# ⚠️ 탭 4: 정리 종목
# ==========================================
with tab4:
    st.header(f"⚠️ 정리 대상 종목 리스트 ([{primary_subject}] 기준)")
    st.info(f"5일 [{primary_subject}] 추세가 10% 이상 하락한 종목입니다. (하락률 30% 초과 시 자동 퇴출)")
    if cleans:
        selected_clean = st.selectbox("정리 종목 선택:", cleans, key="clean_sel")
        c_ticker = selected_clean.split("(")[-1].replace(")", "").strip()
        c_name = selected_clean.split("(")[0].strip()
        
        df_clean = get_all_investor_data(c_ticker, datetime.date(2026, 1, 1), datetime.date.today())
        if not df_clean.empty:
            fig = draw_single_subject_chart(df_clean, c_name, primary_subject, primary_col)
            fig.update_layout(title=f"⚠️ [정리] {selected_clean} [{primary_subject}] 수급 흐름", height=450)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"현재 [{primary_subject}] 기준 조건에 부합하는 정리 대상 종목이 없습니다.")

# ==========================================
# ⭐ 탭 5: 나의 새싹 즐겨찾기
# ==========================================
with tab5:
    st.header(f"⭐ 나의 관심 새싹 즐겨찾기 ([{primary_subject}] 기준)")
    favorite_stocks = st.multiselect("📌 즐겨찾기 종목 선택:", options=stock_df['선택용_이름'], default=default_favs, key="fav_box")
    
    if favorite_stocks:
        local_storage.setItem("my_sprout_favorites", ",".join(favorite_stocks))
        
        for stock_name in favorite_stocks:
            ticker = stock_df[stock_df['선택용_이름'] == stock_name]['티커'].values[0]
            name = stock_df[stock_df['선택용_이름'] == stock_name]['종목명'].values[0]
            df_fav = get_all_investor_data(ticker, datetime.date(2026, 1, 1), datetime.date.today())
            
            if not df_fav.empty:
                fig = draw_single_subject_chart(df_fav, name, primary_subject, primary_col)
                fig.update_layout(title=f"📈 {name} [{primary_subject}] 수급 및 이동평균선", height=400)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("즐겨찾기할 종목을 위에서 선택해 주세요.")
