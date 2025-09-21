# config.py (最終版)

# --- 檔案路徑設定 ---
# 請確保這三個檔案與你的 Python 執行檔位於同一個資料夾下
LISTED_STOCK_PATH = 'listed stock. without etfcsv.csv'
OTC_STOCK_PATH = 'OTC without etf.csv'
ETF_PATH = 'ETFALL.xlsx' # 確保這是 Excel 檔案路徑

# --- 可調整參數 ---
# 無風險利率 (未來可用於夏普比率計算)
RISK_FREE_RATE = 0.0137
