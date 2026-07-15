import pandas as pd
import requests
from io import StringIO
import os
import time

DATA_DIR = "data"
FILE_PATH = os.path.join(DATA_DIR, "investor_data.csv")
STOCK_LIST_PATH = os.path.join(DATA_DIR, "stock_list.csv")

def get_naver_investor_data(session, ticker):
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = f"https://finance.naver.com/item/frgn.naver?code={ticker}&page=1"
    try:
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return pd.DataFrame()
        dfs = pd.read_html(StringIO(response.text), header=None, encoding='euc-kr')
        target_df = next((df for df in dfs if df.shape[1] >= 9), None)
        if target_df is None: return pd.DataFrame()

        data = target_df.iloc[2:, [0, 6]].copy()
        data.columns = ['Date', 'NetBuying']
        data['Date'] = pd.to_datetime(data['Date'].astype(str).str.replace(r'[^\d.]', '', regex=True), format='%Y.%m.%d', errors='coerce')
        data['NetBuying'] = pd.to_numeric(data['NetBuying'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        data = data.dropna(subset=['Date'])
        data['Ticker'] = ticker
        return data[['Date', 'NetBuying', 'Ticker']]
    except: return pd.DataFrame()

def run_update():
    df_existing = pd.read_csv(FILE_PATH, dtype={'Ticker': str}) if os.path.exists(FILE_PATH) else pd.DataFrame()
    df_existing['Date'] = pd.to_datetime(df_existing['Date'])
    
    stock_df = pd.read_csv(STOCK_LIST_PATH)
    session = requests.Session()
    new_data = []
    
    for _, row in stock_df.iterrows():
        df_new = get_naver_investor_data(session, str(row['티커']).zfill(6))
        if not df_new.empty: new_data.append(df_new)
        time.sleep(0.3)
    
    if new_data:
        df_final = pd.concat([df_existing, pd.concat(new_data)]).drop_duplicates(subset=['Date', 'Ticker'], keep='last')
        df_final.sort_values(['Ticker', 'Date'], inplace=True)
        df_final.to_csv(FILE_PATH, index=False)
        print("업데이트 완료.")

if __name__ == "__main__":
    run_update()
