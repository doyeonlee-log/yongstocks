import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import os
from streamlit_local_storage import LocalStorage

st.set_page_config(page_title="새싹발굴하기", layout="wide")
local_storage = LocalStorage()

# 데이터 로드 함수 수정 (CSV 읽기 방식)
@st.cache_data(ttl=3600)
def get_clean_foreigner_data(ticker, start, end):
    try:
        # 1. 실제 데이터 파일 로드
        df_all = pd.read_csv("data/investor_data.csv")
        df_all['Date'] = pd.to_datetime(df_all['Date'])
        
        # 2. 필터링 (가져온 데이터 중 해당 종목, 해당 기간만)
        mask = (df_all['Ticker'].astype(str) == ticker) & \
               (df_all['Date'] >= pd.to_datetime(start)) & \
               (df_all['Date'] <= pd.to_datetime(end))
        df = df_all.loc[mask].copy()
        
        # 3. 차트 함수가 요구하는 '일별지표' 컬럼명으로 변경
        df = df.rename(columns={'NetBuying': '일별지표'})
        return df
    except Exception as e:
        return pd.DataFrame()

# [차트 함수 유지]
def draw_pure_zero_start_chart(df, label_name, unit_label):
    if df.empty: return go.Figure()
    df = df.sort_values(by='Date').reset_index(drop=True)
    df['누적지표'] = df['일별지표'].cumsum()
    first_day_cum = df['누적지표'].iloc[0]
    df['정렬영점누적'] = df['누적지표'] - first_day_cum

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = ['red' if val >= 0 else 'blue' for val in df['일별지표']]

    fig.add_trace(go.Bar(x=df['Date'], y=df['일별지표'], marker_color=colors, name="외인 수급", opacity=0.55), secondary_y=False)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['정렬영점누적'], mode='lines', name="누적 수급선", line=dict(color='#2CA02C', width=1.6)), secondary_y=True)

    fig.update_layout(template="plotly_white", height=450, hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig

# [메인 로직]
stock_df = fdr.StockListing('KRX')[['Code', 'Name']].rename(columns={'Code': '티커', 'Name': '종목명'})
stock_df['티커'] = stock_df['티커'].astype(str).str.zfill(6)
stock_df['선택용_이름'] = stock_df['종목명'] + " (" + stock_df['티커'] + ")"

# 화면 구현 (탭 구성)
tab1, tab2 = st.tabs(["🔎 개별 종목 분석", "🌱 나의 새싹 즐겨찾기"])

with tab1:
    st.header("🔍 종목별 외국인 수급 추세")
    selected_stock = st.selectbox("분석할 종목:", stock_df['선택용_이름'])
    selected_ticker = stock_df[stock_df['선택용_이름'] == selected_stock]['티커'].values[0]
    
    start_date = st.date_input("시작일", datetime.date(2026, 1, 1))
    
    df_daily = get_clean_foreigner_data(selected_ticker, start_date, datetime.date.today())
    
    if not df_daily.empty:
        fig = draw_pure_zero_start_chart(df_daily, selected_stock, "값")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("데이터가 없습니다. update_data.py를 먼저 실행하세요.")

with tab2:
    st.header("🌱 즐겨찾기")
    # ... (나머지 기존 코드 유지)
