import pandas as pd
import FinanceDataReader as fdr
import os
from datetime import datetime

# 데이터 저장 경로 설정
DATA_DIR = "data"
FILE_PATH = os.path.join(DATA_DIR, "investor_data.csv")

def update_stock_data():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    # 예시: 여기서는 예시로 삼성전자 데이터를 가져오지만, 
    # 실제로는 스크래핑한 외국인 순매수 데이터를 이곳에 넣어야 합니다.
    ticker = "005930" 
    df = fdr.DataReader(ticker, '2026-01-01')
    
    # [중요] 여기에서 실제 외국인 수급 데이터를 웹에서 긁어와서 DataFrame으로 만드세요.
    # 예: df['NetBuying'] = scrape_naver_finance(ticker)
    # 아래는 임시로 거래량 기반 데이터를 넣은 것입니다.
    df = df.reset_index()
    df['Ticker'] = ticker
    df['NetBuying'] = (df['Volume'] * df['Change']) / 10000 
    
    # 파일 저장 (기존 파일이 있으면 덮어쓰거나, append 하는 로직을 추가하세요)
    df[['Date', 'Ticker', 'NetBuying', 'Close', 'Change']].to_csv(FILE_PATH, index=False)
    print(f"데이터가 {FILE_PATH}에 저장되었습니다.")

if __name__ == "__main__":
    update_stock_data()
