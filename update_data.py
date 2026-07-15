import pandas as pd
import requests
import os
from datetime import datetime

DATA_DIR = "data"
FILE_PATH = os.path.join(DATA_DIR, "investor_data.csv")
TARGET_TICKERS = ["005930", "000660", "005380"] # 여기서 분석할 종목 관리

def get_naver_investor_data(ticker):
    """네이버 금융에서 외국인 순매수 데이터를 가져옵니다."""
    url = f"https://finance.naver.com/item/frgn.naver?code={ticker}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # pd.read_html로 테이블 추출 (보통 1번 인덱스에 수급 데이터 있음)
        dfs = pd.read_html(url, header=0, encoding='euc-kr')
        df = dfs[1].dropna(how='all') # 빈 행 제거
        
        # 데이터 클렌징 (날짜, 외국인순매매 추출)
        df = df[['날짜', '외국인']]
        df.columns = ['Date', 'NetBuying']
        df['Date'] = pd.to_datetime(df['Date'])
        df['Ticker'] = ticker
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return pd.DataFrame()

def run_update():
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    
    # 1. 기존 데이터 불러오기
    if os.path.exists(FILE_PATH):
        df_existing = pd.read_csv(FILE_PATH)
        df_existing['Date'] = pd.to_datetime(df_existing['Date'])
    else:
        df_existing = pd.DataFrame()

    # 2. 새로운 데이터 수집
    new_data = []
    for ticker in TARGET_TICKERS:
        print(f"Updating {ticker}...")
        df_new = get_naver_investor_data(ticker)
        new_data.append(df_new)
    
    if new_data:
        df_new_all = pd.concat(new_data)
        # 3. 병합 및 중복 제거
        df_final = pd.concat([df_existing, df_new_all]).drop_duplicates(subset=['Date', 'Ticker'], keep='last')
        df_final.sort_values(['Ticker', 'Date'], inplace=True)
        df_final.to_csv(FILE_PATH, index=False)
        print("업데이트 완료.")

if __name__ == "__main__":
    run_update()
