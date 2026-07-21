import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import os
from streamlit_local_storage import LocalStorage

# 1. 페이지 기본 설정 및 레이아웃 최적화
st.set_page_config(
    page_title="새싹발굴하기 - Pro Dashboard", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# [UI/UX 고도화] 탭 선택 디자인 개선 (거슬리는 기본 주황색 배경 제거 및 깔끔한 상단 포인트 라인 적용)
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    
    /* 탭 전체 영역 간격 */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 2px solid #e9ecef; }
    
    /* 개별 탭 기본 스타일 */
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
    
    /* 선택된 탭 스타일 (거슬리는 주황색 배경 대신 상단 포인트 라인과 깔끔한 텍스트 강조) */
    .stTabs [aria-selected="true"] { 
        background-color: #ffffff !important; 
        color: #0047AB !important; /* 선명한 블루 포인트 텍스트 */
        border-top: 3px solid #0047AB !important; /* 상단 포인트 강조선 */
        border-bottom: 2px solid #ffffff !important;
        font-weight: 700;
    }

    div.stExpander { border-radius: 8px; border: 1px solid #e0e0e0; background-color: white; }
    
    .hot-badge {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
        padding: 10px 15px;
        border-radius: 6px;
        font-weight: bold;
        margin-bottom: 15px;
    }
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; letter-spacing: -0.5px; }
    </style>
""", unsafe_allow_html=True)

local_storage = LocalStorage()

# 2. 사이드바 - 제어판
st.sidebar.header("🛠️ 대시보드 제어판")
st.sidebar.markdown("---")

subject_configs = {}
subjects_meta = {
    "외국인": {
        "color": "#FF7F0E", 
        "pos_bar": "#FF4500", "neg_bar": "#FFD700", 
        "default_bar": True, "default_cum": True, "default_ma5": True, "default_ma10": False, "default_ma20": False
    },
    "기관": {
        "color": "#1F77B4", 
        "pos_bar": "#1E90FF", "neg_bar": "#B0C4DE", 
        "default_bar": False, "default_cum": True, "default_ma5": False, "default_ma10": False, "default_ma20": False
    },
    "개인": {
        "color": "#2CA02C", 
        "pos_bar": "#32CD32", "neg_bar": "#8FBC8F", 
        "default_bar": False, "default_cum": False, "default_ma5": False, "default_ma10": False, "default_ma20": False
    }
}

for sub, meta in subjects_meta.items():
    with st.sidebar.expander(f"📌 [{sub}] 상세 수급 설정", expanded=(sub == "외국인")):
        show_bar = st.checkbox("당일 순매수 바(Bar)", value=meta["default_bar"], key=f"chk_bar_{sub}")
        show_cum = st.checkbox("누적 수급선", value=meta["default_cum"], key=f"chk_cum_{sub}")
        show_ma5 = st.checkbox("5일 이동평균선", value=meta["default_ma5"], key=f"chk_ma5_{sub}")
        show_ma10 = st.checkbox("10일 이동평균선", value=meta["default_ma10"], key=f"chk_ma10_{sub}")
        show_ma20 = st.checkbox("20일 이동평균선", value=meta["default_ma20"], key=f"chk_ma20_{sub}")
        
        is_active = show_bar or show_cum or show_ma5 or show_ma10 or show_ma20
        
        subject_configs[sub] = {
            "active": is_active,
            "bar": show_bar,
            "cum": show_cum,
            "ma5": show_ma5,
            "ma10": show_ma10,
            "ma20": show_ma20,
            "color": meta["color"],
            "pos_bar": meta["pos_bar"],
            "neg_bar": meta["neg_bar"]
        }

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
    "🚨 정리 종목",
    "⭐ 나의 새싹 즐겨찾기"
])

# [데이터 엔진]
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

# [차트 엔진]
def draw_custom_multi_chart(df, label_name, configs):
    df = df.sort_values(by='Date').reset_index(drop=True)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    for sub, conf in configs.items():
        if not conf["active"]:
            continue
            
        col_name = subject_col_map[sub]
        if col_name not in df.columns:
            continue
            
        series = df[col_name].fillna(0)
        base_color = conf["color"]
        
        if conf["bar"]:
            bar_colors = [conf["pos_bar"] if val >= 0 else conf["neg_bar"] for val in series]
            fig.add_trace(go.Bar(
                x=df['Date'], y=series, marker_color=bar_colors,
                name=f"{sub} 당일 순매수", opacity=0.5, width=24*3600*1000*0.6
            ), secondary_y=False)
            
        cum_series = series.cumsum()
        first_val = cum_series.iloc[0] if not cum_series.empty else 0
        aligned_cum = cum_series - first_val
        
        if conf["cum"]:
            fig.add_trace(go.Scatter(
                x=df['Date'], y=aligned_cum, mode='lines',
                name=f"{sub} 누적 수급선", line=dict(color=base_color, width=2.5, dash='solid')
            ), secondary_y=True)
            
        if conf["ma5"]:
            ma_5 = aligned_cum.rolling(window=5).mean()
            fig.add_trace(go.Scatter(
                x=df['Date'], y=ma_5, mode='lines',
                name=f"{sub} 5일 이평선", line=dict(color=base_color, width=1.5, dash='solid')
            ), secondary_y=True)
            
        if conf["ma10"]:
            ma_10 = aligned_cum.rolling(window=10).mean()
            fig.add_trace(go.Scatter(
                x=df['Date'], y=ma_10, mode='lines',
                name=f"{sub} 10일 이평선", line=dict(color=base_color, width=1.5, dash='dash')
            ), secondary_y=True)
            
        if conf["ma20"]:
            ma_20 = aligned_cum.rolling(window=20).mean()
            fig.add_trace(go.Scatter(
                x=df['Date'], y=ma_20, mode='lines',
                name=f"{sub} 20일 이평선", line=dict(color=base_color, width=1.5, dash='dot')
            ), secondary_y=True)

    fig.update_layout(
        template="plotly_white", height=500, hovermode="x unified", 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title=f"📈 {label_name} - 주체별 맞춤 수급 및 이평선 비교 분석",
        dragmode="zoom",
        uirevision="constant"
    )
    return fig

# [분류 알고리즘]
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
        if len(group) < 15: continue
            
        sub_series = group[subject_col].fillna(0)
        recent_5 = sub_series.iloc[-5:].sum()
        prev_5 = sub_series.iloc[-10:-5].sum()
        prev_prev_5 = sub_series.iloc[-15:-10].sum()
        
        matched_row = stock_df[stock_df['티커'] == ticker]
        if matched_row.empty: continue
        stock_name = matched_row['종목명'].values[0]
        
        # 1. 🌱 새싹 탭 로직
        jan_to_jun_mask = (group['Date'] >= '2026-01-01') & (group['Date'] <= '2026-06-30')
        jan_to_jun_data = group.loc[jan_to_jun_mask, subject_col].fillna(0)
        if not jan_to_jun_data.empty and (jan_to_jun_data > 0).any():
            is_sprout = False
        else:
            recent_days = sub_series.iloc[-5:]
            history_before_recent = sub_series.iloc[:-5]
            is_sprout = (history_before_recent.sum() <= 0 and recent_days.sum() > 0 and (recent_days > 0).any())
            
        if is_sprout:
            is_recent_5d = recent_days.iloc[-1] > 0 and sub_series.iloc[-6:-1].sum() <= 0
            prefix = "🌱 " if is_recent_5d else ""
            sprout_list.append(f"{prefix}{stock_name} ({ticker})")
            
        # 2. 🚀 희망 탭 로직
        if prev_5 > 0:
            growth_rate = (recent_5 - prev_5) / prev_5 * 100
            if growth_rate >= 20:
                prev_growth_rate = (prev_5 - prev_prev_5) / abs(prev_prev_5) * 100 if prev_prev_5 != 0 else 0
                is_recent_hot = (growth_rate >= 20 and prev_growth_rate < 20)
                prefix = "🔥 " if is_recent_hot else ""
                hope_list.append(f"{prefix}{stock_name} ({ticker})")
                
        # 3. 🚨 정리 탭 로직
        if prev_5 > 0 and recent_5 < prev_5:
            drop_rate = (prev_5 - recent_5) / prev_5 * 100
            if drop_rate > 10:
                prev_drop_rate = (prev_prev_5 - prev_5) / abs(prev_prev_5) * 100 if prev_prev_5 != 0 else 0
                is_recent_warning = (drop_rate > 10 and prev_drop_rate <= 10)
                prefix = "🚨 " if is_recent_warning else ""
                clean_list.append(f"{prefix}{stock_name} ({ticker})")
            
    return sprout_list, hope_list, clean_list

active_subs = [s for s, c in subject_configs.items() if c["active"]]
primary_subject = active_subs[0] if active_subs else "외국인"
primary_col = subject_col_map[primary_subject]

# ==========================================
# 🔍 탭 1: 개별 종목 분석
# ==========================================
with tab1:
    st.markdown("### 🔍 종목별 상세 맞춤 수급 및 이평선 비교 분석")
    with st.container():
        col_input1, col_input2 = st.columns([2, 2])
        with col_input1:
            selected_stock = st.selectbox("📊 분석할 종목을 입력하거나 고르세요:", stock_df['선택용_이름'], key="individual_select")
            selected_ticker = stock_df[stock_df['선택용_이름'] == selected_stock]['티커'].values[0]
            selected_name = stock_df[stock_df['선택용_이름'] == selected_stock]['종목명'].values[0]

        with col_input2:
            date_range_1 = st.date_input("📅 분석 기간을 선택하세요:", value=(datetime.date(2026, 1, 1), datetime.date.today()), key="date_input_tab1")

    if isinstance(date_range_1, tuple) and len(date_range_1) == 2:
        df_all_data = get_all_investor_data(selected_ticker, date_range_1[0], date_range_1[1])
        
        if not df_all_data.empty:
            fig_custom = draw_custom_multi_chart(df_all_data, selected_name, subject_configs)
            st.plotly_chart(fig_custom, use_container_width=True, key="chart_tab1", config={"scrollZoom": True, "displayModeBar": True})
        else:
            st.warning("데이터가 없습니다. 사이드바 설정을 확인해 주세요.")

sprouts, hopes, cleans = classify_stock_groups(primary_col)

# 텍스트 정제 헬퍼 함수
def clean_sel_name(val):
    return val.split("(")[-1].replace(")", "").replace("🌱 ", "").replace("🔥 ", "").replace("🚨 ", "").strip()

def clean_pure_name(val):
    return val.split("(")[0].replace("🌱 ", "").replace("🔥 ", "").replace("🚨 ", "").strip()

# ==========================================
# 🌱 탭 2: 새싹 발굴
# ==========================================
with tab2:
    st.markdown(f"### 🌱 새싹 발굴 종목 리스트 ([{primary_subject}] 기준)")
    st.markdown('<div class="hot-badge">💡 최근 생애 최초로 외국인 수급이 유입된 기업들입니다. (🌱 표시는 최근 5일 내 신규 진입 종목)</div>', unsafe_allow_html=True)
    if sprouts:
        selected_sprout = st.selectbox("발굴된 새싹 종목 선택:", sprouts, key="sprout_sel")
        s_ticker = clean_sel_name(selected_sprout)
        s_name = clean_pure_name(selected_sprout)
        
        df_sprout = get_all_investor_data(s_ticker, datetime.date(2026, 1, 1), datetime.date.today())
        if not df_sprout.empty:
            fig = draw_custom_multi_chart(df_sprout, s_name, subject_configs)
            st.plotly_chart(fig, use_container_width=True, key="chart_tab2_sprout", config={"scrollZoom": True, "displayModeBar": True})
    else:
        st.warning(f"현재 [{primary_subject}] 기준 조건에 부합하는 새싹 종목이 없습니다.")

# ==========================================
# 🚀 탭 3: 희망 종목
# ==========================================
with tab3:
    st.markdown(f"### 🚀 희망 종목 리스트 ([{primary_subject}] 기준)")
    st.markdown('<div class="hot-badge">💡 전 5일 대비 금번 5일 수급 증가율이 20% 이상인 종목들입니다. (🔥 표시는 최근 5일 내 신규 진입)</div>', unsafe_allow_html=True)
    if hopes:
        selected_hope = st.selectbox("희망 종목 선택:", hopes, key="hope_sel")
        h_ticker = clean_sel_name(selected_hope)
        h_name = clean_pure_name(selected_hope)
        
        df_hope = get_all_investor_data(h_ticker, datetime.date(2026, 1, 1), datetime.date.today())
        if not df_hope.empty:
            fig = draw_custom_multi_chart(df_hope, h_name, subject_configs)
            st.plotly_chart(fig, use_container_width=True, key="chart_tab3_hope", config={"scrollZoom": True, "displayModeBar": True})
    else:
        st.warning(f"현재 [{primary_subject}] 기준 조건에 부합하는 희망 종목이 없습니다.")

# ==========================================
# 🚨 탭 4: 정리 종목
# ==========================================
with tab4:
    st.markdown(f"### 🚨 정리 대상 종목 리스트 ([{primary_subject}] 기준)")
    st.markdown('<div class="hot-badge">💡 전 5일 대비 금번 5일 수급 하락률이 10%를 초과하는 종목들입니다. (🚨 표시는 최근 5일 내 급하락 진입)</div>', unsafe_allow_html=True)
    if cleans:
        selected_clean = st.selectbox("정리 종목 선택:", cleans, key="clean_sel")
        c_ticker = clean_sel_name(selected_clean)
        c_name = clean_pure_name(selected_clean)
        
        df_clean = get_all_investor_data(c_ticker, datetime.date(2026, 1, 1), datetime.date.today())
        if not df_clean.empty:
            fig = draw_custom_multi_chart(df_clean, c_name, subject_configs)
            st.plotly_chart(fig, use_container_width=True, key="chart_tab4_clean", config={"scrollZoom": True, "displayModeBar": True})
    else:
        st.warning(f"현재 [{primary_subject}] 기준 조건에 부합하는 정리 대상 종목이 없습니다.")

# ==========================================
# ⭐ 탭 5: 나의 새싹 즐겨찾기
# ==========================================
with tab5:
    st.markdown(f"### ⭐ 나의 관심 새싹 즐겨찾기 수급 추세 레이더")
    favorite_stocks = st.multiselect("📌 즐겨찾기 종목 선택:", options=stock_df['선택용_이름'], default=default_favs, key="fav_box")
    
    if favorite_stocks:
        local_storage.setItem("my_sprout_favorites", ",".join(favorite_stocks))
        
        for idx, stock_name in enumerate(favorite_stocks):
            ticker = stock_df[stock_df['선택용_이름'] == stock_name]['티커'].values[0]
            name = stock_df[stock_df['선택용_이름'] == stock_name]['종목명'].values[0]
            df_fav = get_all_investor_data(ticker, datetime.date(2026, 1, 1), datetime.date.today())
            
            if not df_fav.empty:
                fig = draw_custom_multi_chart(df_fav, name, subject_configs)
                st.plotly_chart(fig, use_container_width=True, key=f"chart_tab5_fav_{ticker}_{idx}", config={"scrollZoom": True, "displayModeBar": True})
    else:
        st.info("즐겨찾기할 종목을 위에서 선택해 주세요.")
