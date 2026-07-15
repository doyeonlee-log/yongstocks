import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import os

# 데이터 폴더 확인
if not os.path.exists('data'): os.makedirs('data')

# 1. 종목 리스트 업데이트
df_list = fdr.StockListing('KRX')
df_filtered = df_list[df_list['Market'].isin(['KOSPI', 'KOSDAQ'])][['Code', 'Name', 'Market']]
df_filtered.columns = ['티커', '종목명', '시장']
df_filtered.to_csv('data/stock_list.csv', index=False)

# 2. [핵심] 대표 종목 수급 데이터 미리 저장 (여기서는 예시로 삼성전자)
# 만약 더 많은 종목이 필요하면 리스트로 만들어 반복문을 돌리면 됩니다.
ticker = '005930' # 삼성전자
start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
df_foreigner = fdr.DataReader(ticker, start_date, data_source='naver')

# 수급 데이터만 따로 저장
df_foreigner.to_csv('data/foreigner_data_005930.csv')
