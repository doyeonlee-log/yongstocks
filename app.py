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

# 3. 상장 종목 리스트 불러오기 함수
@st.cache_data
def load_stock_list():
    if not os.path.exists("data"):
        os.makedirs("data")
    if os.path.exists("data/stock_list.csv"):
        return pd.read_csv("data/stock_list.csv")
    else:
        try:
            df = fdr.StockListing('KRX')
            df_filtered = df[df['Market'].isin(['KOSPI', 'KOSDAQ'])][['Code', 'Name', 'Market']]
            df_filtered.columns = ['티커', '종목명', '시장']
            df_filtered.to_csv("data/stock_list.csv", index=False)
            return df_filtered
        except:
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

# 공통 기준 정의
END_DATE = datetime.datetime.now().strftime("%Y-%m-%d")

@st.cache_data(ttl=3600)
def get_clean_foreigner_data(ticker, start, end):
    try:
        df = fdr.DataReader(ticker, start, end)
        return df
    except:
        return pd.DataFrame()

# 💡 [영점 고정 엔진] 디자인 및 로직 변화 없이 안정성만 확보
def draw_pure_zero_start_chart(df, label_name, unit_label):
    df = df.sort_values(by='Date').reset_index(drop=True)

    # 누적지표 계산 후 첫날 데이터 기준으로 0점 오프셋 연산
    df['누적지표'] = df['일별지표'].cumsum()
    first_day_cum = df['누적지표'].iloc[0] if not df['누적지표'].empty else 0
    df['정렬영점누적'] = df['누적지표'] - first_day_cum

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 1. 당일 순매수/순매도 막대그래프
    colors = ['red' if val >= 0 else 'blue' for val in df['일별지표']]
    fig.add_trace(
        go.Bar(
            x=df['Date'], y=df['일별지표'], marker_color=colors,
            name="당일 외국인 순매매", showlegend=True, opacity=0.55,
            hovertemplate=f"<b>당일 순매매:</b> %{{y:,.2f}} {unit_label}<extra></extra>"
        ), secondary_y=False
    )

    # 2. 외국인 장기 누적 수급선 (정렬영점누적 사용)
    fig.add_trace(
        go.Scatter(
            x=df['Date'], y=df['정렬영점누적'], mode='lines',
            name="외국인 누적 수급선", showlegend=True,
            line=dict(color='#2CA02C', width=1.6),
            hovertemplate=f"<b>외인 누적:</b> %{{y:,.2f}} {unit_label}<extra></extra>"
        ), secondary_y=True
    )

    # 0선 기준 대칭 스케일링 (범위를 명확하게 고정하여 Autoscale 흔들림 방지)
    max_bar = max(abs(df['일별지표'].max()), abs(df['일별지표'].min())) * 1.15
    max_line = max(abs(df['정렬영점누적'].max()), abs(df['정렬영점누적'].min())) * 1.15
    if max_bar == 0: max_bar = 1.0
    if max_line == 0: max_line = 1.0

    fig.update_yaxes(range=[-max_bar, max_bar], secondary_y=False, showgrid=False, title_text=f"당일 수급 ({unit_label})")
    fig.update_yaxes(range=[-max_line, max_line], secondary_y=True, showgrid=True, title_text=f"누적 수급 흐름 ({unit_label})")

    fig.update_layout(
        template="plotly_white",
        height=450,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(tickformat="%Y-%m-%d", range=[df['Date'].min(), df['Date'].max()]),
        shapes=[dict(type="line", yref="y2", y0=0, y1=0, xref="paper", x0=0, x1=1, line=dict(color="black", width=1.5))]
    )
    return fig

# 🔍 탭 1
with tab1:
    st.header("🔍 종목별 상세 외국인 수급 추세 분석")
    st.markdown("당일 순매매량과 외국인 순매매량 누적 추세선 비교")
    col_input1, col_input2 = st.columns([2, 2])
    with col_input1:
        selected_stock = st.selectbox("📊 분석할 종목을 입력하거나 고르세요:", stock_df['선택용_이름'], key="individual_select")
        selected_ticker = stock_df[stock_df['선택용_이름'] == selected_stock]['티커'].values[0]
    with col_input2:
        date_range_1 = st.date_input("📅 분석 기간을 선택하세요:", value=(datetime.date(2026, 1, 1), datetime.date.today()), key="ind_date")

    if isinstance(date_range_1, tuple) and len(date_range_1) == 2:
        df_daily = get_clean_foreigner_data(selected_ticker, date_range_1[0].strftime("%Y-%m-%d"), date_range_1[1].strftime("%Y-%m-%d"))
        if not df_daily.empty and 'Foreigner' in df_daily.columns:
            df_daily = df_daily.reset_index()
            if display_option == "금액 기준 (억 원)":
                df_daily['일별지표'] = (df_daily['Foreigner'] * df_daily['Close']) / 100000000
                hover_unit = "억 원"
            else:
                df_daily['일별지표'] = df_daily['Foreigner'] / 10000
                hover_unit = "만 주"
            fig = draw_pure_zero_start_chart(df_daily, selected_stock, hover_unit)
            fig.update_layout(title=f"📊 {selected_stock} 외국인 당일/누적 수급 흐름")
            st.plotly_chart(fig, use_container_width=True)
            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                df_sorted = df_daily.sort_values(by='Date').reset_index(drop=True)
                df_sorted['누적지표'] = df_sorted['일별지표'].cumsum()
                final_zero_val = df_sorted['누적지표'].iloc[-1] - df_sorted['누적지표'].iloc[0] if not df_sorted['누적지표'].empty else 0
                st.metric("기간 내 외인 누적 증감량", f"{final_zero_val:+.2f} {hover_unit}")
            with col_stat2:
                st.metric("현재 종가 (최근 거래일)", f"{int(df_daily['Close'].iloc[-1]):,} 원", delta=f"{df_daily['Change'].iloc[-1] * 100:.2f}%")
        else:
            st.error("외국인 수급 데이터를 가져올 수 없습니다.")

# ⭐ 탭 2
with tab2:
    st.header("🌱 나의 관심 새싹 외국인 누적 추세 레이더")
    col_fav1, col_fav2 = st.columns([2, 2])
    with col_fav1:
        favorite_stocks = st.multiselect("📌 즐겨찾기하여 추적할 새싹 종목들을 등록하세요:", options=stock_df['선택용_이름'], default=default_favs, key="fav_box")
    with col_fav2:
        date_range_2 = st.date_input("📅 즐겨찾기 분석 기간을 선택하세요:", value=(datetime.date(2026, 1, 1), datetime.date.today()), key="fav_date_pick")
    
    if favorite_stocks: local_storage.setItem("my_sprout_favorites", ",".join(favorite_stocks))
    else: local_storage.setItem("my_sprout_favorites", "")

    if favorite_stocks and isinstance(date_range_2, tuple) and len(date_range_2) == 2:
        hover_unit = "만 주"
        fav_summary_list = []
        with st.spinner("수급 지도를 갱신하는 중..."):
            for stock_name in favorite_stocks:
                ticker = stock_df[stock_df['선택용_이름'] == stock_name]['티커'].values[0]
                df_fav = get_clean_foreigner_data(ticker, date_range_2[0].strftime("%Y-%m-%d"), date_range_2[1].strftime("%Y-%m-%d"))
                if not df_fav.empty and 'Foreigner' in df_fav.columns:
                    df_fav = df_fav.reset_index()
                    df_fav['일별지표'] = df_fav['Foreigner'] / 10000
                    fig = draw_pure_zero_start_chart(df_fav, stock_name, hover_unit)
                    fig.update_layout(title=f"📈 {stock_name} 외국인 당일/누적 수급 흐름", height=400)
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown("---")
                    df_fav_sorted = df_fav.sort_values(by='Date').reset_index(drop=True)
                    df_fav_sorted['누적지표'] = df_fav_fav_sum = df_fav_sorted['일별지표'].cumsum()
                    final_zero_fav = df_fav_sorted['누적지표'].iloc[-1] - df_fav_sorted['누적지표'].iloc[0]
                    fav_summary_list.append({"종목명": stock_name, f"외인 누적 증감 ({hover_unit})": round(final_zero_fav, 2)})
        if fav_summary_list:
            st.dataframe(pd.DataFrame(fav_summary_list).sort_values(by=f"외인 누적 증감 ({hover_unit})", ascending=False).reset_index(drop=True), use_container_width=True)
