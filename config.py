# config.py

# --- 檔案路徑設定 ---
ETF_FILE = 'ETFALL.xlsx'
LISTED_STOCK_FILE = 'listed stock. without etf.csv'
OTC_STOCK_FILE = 'OTC without etf.csv'

# --- API 金鑰設定 ---
# !! 重要 !!: 請將 'YOUR_API_KEY' 替換成你自己的 Google AI (Gemini) API 金鑰
# 你可以從 Google AI Studio 免費取得: https://aistudio.google.com/app/apikey
GEMINI_API_KEY = 'AIzaSyC5t0uo2iJK-dFRZ1JG4bX9eYuVO8Roi0Y'

# --- 投資策略參數設定 ---
# 規則零
MIN_MARKET_CAP_BILLIONS = 50
MIN_LISTING_DAYS = 365

# 純個股投資組合
CONSERVATIVE_STOCK_COUNT = (8, 10)
MODERATE_STOCK_COUNT = (5, 8)
AGGRESSIVE_STOCK_COUNT = (5, 7)
MAX_INDUSTRY_CONCENTRATION = 2
HHI_CONSERVATIVE_MAX = 0.20
HHI_MODERATE_MAX = 0.25
HHI_AGGRESSIVE_MAX = 0.35

# ETF 資產配置藍圖 (%)
CONSERVATIVE_ETF_ALLOC = {'stocks': 30, 'bonds': 70}
MODERATE_ETF_ALLOC = {'stocks': 60, 'bonds': 40}
AGGRESSIVE_ETF_ALLOC = {'stocks': 90, 'bonds': 10}

# 混合型投資組合核心與衛星配置比例 (%)
CONSERVATIVE_HYBRID_ALLOC = {'core': 70, 'satellite': 30}
MODERATE_HYBRID_ALLOC = {'core': 60, 'satellite': 40}
AGGRESSIVE_HYBRID_ALLOC = {'core': 50, 'satellite': 50}