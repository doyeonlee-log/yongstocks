import pandas as pd
import FinanceDataReader as fdr
import os

# 데이터 저장 경로
DATA_DIR = "data"
FILE_PATH = os.path.join(DATA_DIR, "investor_data.csv")

# 추적할 종목 리스트 (필요할 때 여기에 티커를 추가하세요)
TARGET_TICKERS = ["005930", "000660", "005380"] 

def update_stock_data():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    # 1. 기존 파일이 있으면 불러오기
    if os.path.exists(FILE_PATH):
        df_existing = pd.read_csv(FILE_PATH)
        df_existing['Date'] = pd.to_datetime(df_existing['Date'])
    else:
        df_existing = pd.DataFrame()

    new_data_list = []

    # 2. 각 종목별로 데이터 업데이트
    for ticker in TARGET_TICKERS:
        print(f"{ticker} 데이터 가져오는 중...")
        # 2026-01-01부터 최신까지 다시 가져오기 (데이터 정합성을 위해 전체를 다시 읽는 게 가장 안전합니다)
        df_new = fdr.DataReader(ticker, '2026-01-01')
        df_new = df_new.reset_index()
        
        # [중요] '일별지표' 계산 (나중에 실제 수급 데이터로 크롤링하면 이 부분만 바꾸면 됨)
        df_new['Ticker'] = ticker
        df_new['NetBuying'] = (df_new['Volume'] * df_new['Change']) / 10000 
        
        new_data_list.append(df_new[['Date', 'Ticker', 'NetBuying', 'Close', 'Change']])

    # 3. 새로운 데이터 합치기
    df_new_all = pd.concat(new_data_list)
    
    # 4. 기존 데이터와 합치고 중복 제거 (날짜와 종목이 같으면 최신 데이터로 유지)
    if not df_existing.empty:
        df_final = pd.concat([df_existing, df_new_all]).drop_duplicates(subset=['Date', 'Ticker'], keep='last')
    else:
        df_final = df_new_all

    # 5. 정렬 후 저장
    df_final = df_final.sort_values(by=['Ticker', 'Date'])
    df_final.to_csv(FILE_PATH, index=False)
    print(f"데이터가 {FILE_PATH}에 안전하게 업데이트되었습니다.")

if __name__ == "__main__":
    update_stock_data()
