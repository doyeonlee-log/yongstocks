import FinanceDataReader as fdr
import pandas as pd

# 데이터 수집
df = fdr.StockListing('KRX')
# 저장 (이 파일이 깃허브에 남음)
df.to_csv('data/stock_list.csv', index=False)
