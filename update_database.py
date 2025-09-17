import sqlite3
import pandas as pd
from datetime import datetime
import time
import os
import yfinance as yf

# --- 專案模組 ---
# config.py 不再需要，因為 yfinance 無需 API 金鑰
from news_fetcher import update_news_sentiment_for_stocks

# --- 全域設定 ---
DB_PATH = "tw_stock_data.db"
# [yfinance 版] 股票代碼需要加上 '.TW' 後綴
TICKER_LIST = [
    "2330.TW", "2317.TW", "2454.TW", "2412.TW", "2881.TW", "2882.TW", "2886.TW", "1301.TW", "1303.TW", "1326.TW",
    "2002.TW", "2207.TW", "2303.TW", "2308.TW", "2382.TW", "2891.TW", "2912.TW", "3008.TW", "3045.TW", "3711.TW",
    "4904.TW", "5871.TW", "5880.TW", "6505.TW", "9910.TW", "2379.TW", "2395.TW", "2884.TW", "1216.TW", "1101.TW",
    "2357.TW", "2603.TW", "2609.TW", "2615.TW", "2880.TW", "2883.TW", "2885.TW", "2892.TW", "4938.TW", "6415.TW",
    "1590.TW", "3661.TW", "8069.TW", "6669.TW", "3529.TW", "3034.TW", "3443.TW", "2458.TW", "5269.TW", "2377.TW"
]


def setup_database():
    """
    建立或驗證資料庫結構。
    """
    print("正在設定資料庫結構...")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # 建立每日財務指標表 (yfinance 版 schema)
        # 我們只儲存最新快照，因此 stock_id 是唯一的 PRIMARY KEY
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            stock_id TEXT PRIMARY KEY NOT NULL,
            stock_name TEXT,
            industry_category TEXT,
            pe_ratio REAL,
            pb_ratio REAL,
            yield REAL,
            close_price REAL
        )
        """)
        # 建立新聞情緒表 (維持不變)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_sentiment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id TEXT NOT NULL,
            news_date DATE NOT NULL,
            headline TEXT NOT NULL,
            source TEXT,
            sentiment_score REAL,
            sentiment_category TEXT,
            UNIQUE(stock_id, headline)
        )
        """)
        conn.commit()
    print("資料庫設定完成。")


def update_financial_data_with_yfinance():
    """
    使用 yfinance 套件獲取最新的股票數據快照並更新到資料庫。
    """
    print("\n--- 開始使用 yfinance 更新每日財務指標 ---")
    all_stock_data = []
    
    print(f"正在從 Yahoo Finance 下載 {len(TICKER_LIST)} 支股票的數據...")
    
    for i, stock_id in enumerate(TICKER_LIST):
        try:
            ticker = yf.Ticker(stock_id)
            info = ticker.info
            
            # 檢查是否有足夠的數據，'regularMarketPrice' 是最基本的指標
            if 'regularMarketPrice' not in info or info['regularMarketPrice'] is None:
                print(f"警告: 缺少 {stock_id} 的關鍵市場數據，將被忽略。")
                continue

            # 提取所需欄位，並使用 .get() 提供預設值 None
            stock_data = {
                'stock_id': stock_id.replace('.TW', ''), # 存入資料庫時移除後綴
                'stock_name': info.get('shortName'),
                'industry_category': info.get('industry'),
                'pe_ratio': info.get('trailingPE'),
                'pb_ratio': info.get('priceToBook'),
                'yield': info.get('dividendYield', 0) * 100, # yfinance 的殖利率是小數
                'close_price': info.get('regularMarketPrice')
            }
            all_stock_data.append(stock_data)
            
        except Exception as e:
            print(f"錯誤: 請求 yfinance API 失敗 (股票代碼: {stock_id}): {e}")
        
        time.sleep(0.5) # 友善請求，避免被封鎖
        print(f"  進度: {i+1}/{len(TICKER_LIST)}")

    if not all_stock_data:
        print("警告: 未能從 yfinance 下載任何數據。資料庫未更新。")
        return

    # 轉換為 DataFrame 並進行數據清洗
    new_df = pd.DataFrame(all_stock_data)
    numeric_cols = ['pe_ratio', 'pb_ratio', 'yield', 'close_price']
    for col in numeric_cols:
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce')
    new_df.dropna(subset=['stock_id', 'stock_name', 'close_price'], inplace=True)


    # 寫入資料庫
    with sqlite3.connect(DB_PATH) as conn:
        try:
            # 使用 'replace' if_exists 策略，這裡需要先讀取舊數據，再合併新數據
            old_df = pd.read_sql("SELECT * FROM daily_metrics", conn)
            # 將新舊數據合併，並移除重複項，保留最新的
            combined_df = pd.concat([old_df, new_df]).drop_duplicates(subset=['stock_id'], keep='last')
        except (pd.io.sql.DatabaseError, sqlite3.OperationalError):
            # 如果表格不存在或讀取失敗，直接使用新數據
            combined_df = new_df

        combined_df.to_sql('daily_metrics', conn, if_exists='replace', index=False)

    print(f"成功從 yfinance 更新/寫入 {len(new_df)} 筆最新的財務數據。資料庫總計 {len(combined_df)} 筆記錄。")


def main():
    """
    執行整個數據更新流程的主函數。
    """
    print(f"--- 數據庫更新程序啟動 ({datetime.now()}) ---")
    
    # 步驟 1: 確保資料庫與表格存在
    setup_database()
    
    # 步驟 2: 使用 yfinance 更新財務數據 (核心)
    update_financial_data_with_yfinance()
    
    # 步驟 3: 更新新聞情緒數據 (衛星，維持不變)
    # 我們傳入不含 .TW 的股票代碼列表
    stock_ids_without_suffix = [s.replace('.TW', '') for s in TICKER_LIST]
    update_news_sentiment_for_stocks(stock_ids_without_suffix, DB_PATH)
    
    print(f"--- 所有數據更新完畢 ({datetime.now()}) ---")


if __name__ == "__main__":
    # 讓此腳本可以獨立執行
    main()

