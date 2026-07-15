import pandas as pd
import requests
from io import StringIO
import os
import time

DATA_DIR = "data"
FILE_PATH = os.path.join(DATA_DIR, "investor_data.csv")
# 분석할 종목 리스트 (필요하면 여기서 관리하세요)
TARGET_TICKERS = ["005930", "000660", "005380"] 

def get_naver_investor_data(session, ticker):
    """우리가 검증한 위치 기반 수집 로직 적용"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'}
    url = f"https://finance.naver.com/item/frgn.naver?code={ticker}&page=1"
    
    try:
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return pd.DataFrame()

        # 표 읽기
        dfs = pd.read_html(StringIO(response.text), header=None, encoding='euc-kr')
        target_df = None
        for df in dfs:
            if df.shape[1] >= 9:
                target_df = df
                break
        if target_df is None: return pd.DataFrame()

        # 위치 기반 추출 (0:날짜, 6:외국인 순매매량)
        data = target_df.iloc[2:, [0, 6]].copy()
        data.columns = ['Date', 'NetBuying']
        
        # 데이터 정제 (가장 중요한 부분!)
        data['Date'] = data['Date'].astype(str).str.replace(r'[^\d.]', '', regex=True)
        data['Date'] = pd.to_datetime(data['Date'], format='%Y.%m.%d', errors='coerce')
        data['NetBuying'] = pd.to_numeric(data['NetBuying'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        data = data.dropna(subset=['Date'])
        data['Ticker'] = ticker
        
        return data[['Date', 'NetBuying', 'Ticker']]
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return pd.DataFrame()

def run_update():
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    
    # 1. 기존 데이터 불러오기
    if os.path.exists(FILE_PATH):
        df_existing = pd.read_csv(FILE_PATH, dtype={'Ticker': str})
        df_existing['Date'] = pd.to_datetime(df_existing['Date'])
    else:
        df_existing = pd.DataFrame()

    # 2. 새로운 데이터 수집
    session = requests.Session()
    new_data = []
    for ticker in TARGET_TICKERS:
        print(f"Updating {ticker}...")
        df_new = get_naver_investor_data(session, ticker)
        if not df_new.empty:
            new_data.append(df_new)
        time.sleep(0.5)
    
    # 3. 병합 및 중복 제거
    if new_data:
        df_new_all = pd.concat(new_data)
        df_final = pd.concat([df_existing, df_new_all]).drop_duplicates(subset=['Date', 'Ticker'], keep='last')
        df_final.sort_values(['Ticker', 'Date'], inplace=True)
        df_final.to_csv(FILE_PATH, index=False)
        print("업데이트 완료.")

if __name__ == "__main__":
    run_update()
