import FinanceDataReader as fdr
import pandas as pd
import os

if not os.path.exists('data'): os.makedirs('data')

# 종목 리스트 업데이트
df = fdr.StockListing('KRX')
df_filtered = df[df['Market'].isin(['KOSPI', 'KOSDAQ'])][['Code', 'Name', 'Market']]
df_filtered.columns = ['티커', '종목명', '시장']
df_filtered.to_csv('data/stock_list.csv', index=False)
