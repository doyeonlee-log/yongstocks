import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import os
import requests
from io import StringIO
from streamlit_local_storage import LocalStorage

st.set_page_config(page_title="새싹발굴하기", layout="wide")
local_storage = LocalStorage()

st.sidebar.header("🛠️ 대시보드 설정")
display_option = st.sidebar.radio("데이터 보기 방식 선택:", ("수량 기준 (만 주)", "금액 기준 (억 원)"))

@st.cache_data
def load_stock_list():
    if os.path.exists("data/stock_list.csv"): return pd.read_csv("data/stock_list.csv")
    else: return pd.DataFrame(columns=['티커', '종목명', '시장'])

stock_df = load_stock_list()
stock_df['티커'] = stock_df['티커'].astype(str).str.zfill(6)
stock_df['선택용_이름'] = stock_df['종목명'] + " (" + stock_df['티커'] + ")"

saved_favs = local_storage.getItem("my_sprout_favorites")
default_favs = [x.strip() for x in saved_favs.split(",")] if saved_favs else []

# 💡 [팩트 추출 엔진] 네이버 금융 직접 파싱 (모든 종목 대응)
@st.cache_data(ttl=3600)
def get_real_foreigner_data(ticker, start_date):
    try:
        url = f"https://finance.naver.com/item/frgn.naver?code={ticker}&page=1"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df = pd.read_html(StringIO(res.text))[1].dropna(how='all')
        df = df.iloc[2:].copy()
        df.columns = ['Date', 'Close', 'Diff', 'Change', 'Foreigner', 'Agency', 'Individual', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        df['Foreigner'] = pd.to_numeric(df['Foreigner'], errors='coerce').fillna(0)
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        return df.sort_values('Date')
    except: return pd.DataFrame()

def draw_pure_zero_start_chart(df, unit_label):
    df = df.sort_values(by='Date').reset_index(drop=True)
    df['일별지표'] = df['Foreigner']
    df['누적지표'] = df['일별지표'].cumsum()
    df['정렬영점누적'] = df['누적지표'] - df['누적지표'].iloc[0]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = ['red' if val >= 0 else 'blue' for val in df['일별지표']]
    
    fig.add_trace(go.Bar(x=df['Date'], y=df['일별지표'], marker_color=colors, name="당일 외국인 순매매"), secondary_y=False)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['정렬영점누적'], mode='lines', name="외국인 누적 수급선", line=dict(color='#2CA02C', width=2)), secondary_y=True)
    
    max_bar = max(abs(df['일별지표'].max()), abs(df['일별지표'].min())) * 1.2
    max_line = max(abs(df['정렬영점누적'].max()), abs(df['정렬영점누적'].min())) * 1.2
    fig.update_yaxes(range=[-max_bar, max_bar], secondary_y=False, zeroline=True)
    fig.update_yaxes(range=[-max_line, max_line], secondary_y=True, zeroline=True, zerolinecolor='black')
    fig.update_layout(template="plotly_white", height=450, hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig

tab1, tab2 = st.tabs(["🔎 개별 종목 분석", "🌱 나의 새싹 즐겨찾기"])

with tab1:
    col1, col2 = st.columns([2, 2])
    with col1:
        selected_stock = st.selectbox("📊 분석할 종목:", stock_df['선택용_이름'], key="ind_select")
        ticker = stock_df[stock_df['선택용_이름'] == selected_stock]['티커'].values[0]
    with col2:
        date_range = st.date_input("📅 기간:", value=(datetime.date(2026, 1, 1), datetime.date.today()))
    
    df = get_real_foreigner_data(ticker, date_range[0])
    if not df.empty:
        if display_option == "금액 기준 (억 원)": df['Foreigner'] = (df['Foreigner'] * df['Close']) / 100000000
        else: df['Foreigner'] = df['Foreigner'] / 10000
        st.plotly_chart(draw_pure_zero_start_chart(df, "만 주"), use_container_width=True)

with tab2:
    favorite_stocks = st.multiselect("📌 즐겨찾기:", options=stock_df['선택용_이름'], default=default_favs, key="fav_box")
    local_storage.setItem("my_sprout_favorites", ",".join(favorite_stocks))
    for stock_name in favorite_stocks:
        ticker = stock_df[stock_df['선택용_이름'] == stock_name]['티커'].values[0]
        df = get_real_foreigner_data(ticker, "2026-01-01")
        if not df.empty:
            df['Foreigner'] = df['Foreigner'] / 10000
            st.plotly_chart(draw_pure_zero_start_chart(df, "만 주"), use_container_width=True)
            st.markdown("---")
