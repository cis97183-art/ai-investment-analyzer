# config.py (修正版)

# --- 檔案路徑設定 ---
LISTED_STOCK_PATH = 'listed stock. without etfcsv.csv'
OTC_STOCK_PATH = 'OTC without etf.csv'
ETF_PATH = 'ETFALL.xlsx' # 確保這是你正確的 Excel 檔名

# --- 可調整參數 ---
TARGET_ASSET_COUNT = 10 # 篩選標的時的目標數量

# *** 新增：無風險利率 (用於夏普比率計算) ***
# 根據你的文件，設定為 1.37%
RISK_FREE_RATE = 0.0137