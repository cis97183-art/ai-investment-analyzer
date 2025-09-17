import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import os

# --- 專案模組 ---
from config import FINMIND_API_TOKEN
from news_fetcher import update_news_sentiment_for_stocks

# --- 全域設定 ---
DB_PATH = "tw_stock_data.db"
# 為了演示，我們選取台灣50指數 + 部分中小型潛力股作為基礎股票池
# 在真實應用中，這個列表可以擴展到台股全市場
TICKER_LIST = [
    "2330", "2317", "2454", "2412", "2881", "2882", "2886", "1301", "1303", "1326",
    "2002", "2207", "2303", "2308", "2382", "2891", "2912", "3008", "3045", "3711",
    "4904", "5871", "5880", "6505", "9910", "2379", "2395", "2884", "1216", "1101",
    "2357", "2603", "2609", "2615", "2880", "2883", "2885", "2892", "4938", "6415",
    "1590", "3661", "8069", "6669", "3529", "3034", "3443", "2458", "5269", "2377"
]


def setup_database():
    """
    [Phase 1] 建立資料庫與所需的表格 (daily_metrics, news_sentiment)。
    """
    print("正在設定資料庫結構...")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # 1. 建立每日財務指標表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            stock_id TEXT NOT NULL,
            date DATE NOT NULL,
            stock_name TEXT,
            industry_category TEXT,
            pe_ratio REAL,
            pb_ratio REAL,
            yield REAL,
            close_price REAL,
            PRIMARY KEY (stock_id, date)
        )
        """)
        # 2. 建立新聞情緒表 (來自藍圖)
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

def fetch_finmind_data(stock_ids: list, start_date: str, end_date: str) -> pd.DataFrame:
    """
    [Phase 1] 從 FinMind API 獲取指定股票列表的每日指標。
    """
    base_url = "https://api.finmindtrade.com/api/v4/data"
    all_data = []
    
    print(f"正在從 FinMind 下載 {len(stock_ids)} 支股票的數據...")
    
    for i, stock_id in enumerate(stock_ids):
        params = {
            "dataset": "TaiwanStockPriceAndPER",
            "data_id": stock_id,
            "start_date": start_date,
            "end_date": end_date,
            "token": FINMIND_API_TOKEN,
        }
        
        try:
            res = requests.get(base_url, params=params)
            res.raise_for_status()
            data = res.json()

            if data['msg'] == 'success' and data['data']:
                df = pd.DataFrame(data['data'])
                # 欄位重新命名以符合我們的資料庫結構
                df.rename(columns={
                    'stock_id': 'stock_id',
                    'date': 'date',
                    'PBR': 'pb_ratio',
                    'PER': 'pe_ratio',
                    'yield': 'yield',
                    'close': 'close_price'
                }, inplace=True)
                # 確保欄位齊全
                df = df[['stock_id', 'date', 'pb_ratio', 'pe_ratio', 'yield', 'close_price']]
                all_data.append(df)
            else:
                 print(f"警告: FinMind API 未回傳有效數據 (股票代碼: {stock_id}, 訊息: {data.get('msg', 'N/A')})")
        
        except requests.exceptions.RequestException as e:
            print(f"錯誤: 請求 FinMind API 失敗 (股票代碼: {stock_id}): {e}")
        except Exception as e:
            print(f"錯誤: 處理 FinMind 數據時發生預期外的錯誤 (股票代碼: {stock_id}): {e}")

        # API 呼叫之間加入延遲以避免觸發速率限制
        time.sleep(1) 
        print(f"  進度: {i+1}/{len(stock_ids)}")

    if not all_data:
        print("警告: 未能從 FinMind 下載任何數據。")
        return pd.DataFrame()
        
    return pd.concat(all_data, ignore_index=True)

def get_stock_info(stock_ids: list) -> pd.DataFrame:
    """
    獲取股票的基本資訊 (公司簡稱, 產業類別)。
    """
    base_url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockInfo",
        "token": FINMIND_API_TOKEN,
    }
    try:
        res = requests.get(base_url, params=params)
        res.raise_for_status()
        data = res.json()
        if data['msg'] == 'success':
            df = pd.DataFrame(data['data'])
            df = df[df['stock_id'].isin(stock_ids)]
            return df[['stock_id', 'stock_name', 'industry_category']]
    except Exception as e:
        print(f"錯誤: 獲取股票基本資訊失敗: {e}")
    return pd.DataFrame()


def update_financial_data():
    """
    主函數：更新所有股票的最新財務數據到資料庫。
    """
    print("\n--- 開始更新每日財務指標 ---")
    # [最終優化] 將結束日期設定為昨天，確保能抓取到已收盤的完整數據
    end_date_dt = datetime.now() - timedelta(days=1)
    start_date_dt = end_date_dt - timedelta(days=7) # 將時間窗口擴大到7天，增加數據獲取成功率

    end_date = end_date_dt.strftime('%Y-%m-%d')
    start_date = start_date_dt.strftime('%Y-%m-%d')

    print(f"數據抓取區間: {start_date} 至 {end_date}")

    # 1. 抓取財務數據
    financial_df = fetch_finmind_data(TICKER_LIST, start_date, end_date)
    if financial_df.empty:
        print("警告：在指定日期區間內未獲取任何財務數據。將保留資料庫中現有數據。")
        return

    # 2. 抓取公司基本資訊
    info_df = get_stock_info(TICKER_LIST)
    if not info_df.empty:
        financial_df = pd.merge(financial_df, info_df, on='stock_id', how='left')

    # 3. 數據清洗
    financial_df['date'] = pd.to_datetime(financial_df['date']).dt.date
    numeric_cols = ['pe_ratio', 'pb_ratio', 'yield', 'close_price']
    for col in numeric_cols:
        financial_df[col] = pd.to_numeric(financial_df[col], errors='coerce')
    
    # 只保留最新的數據
    financial_df.dropna(subset=numeric_cols, inplace=True) # 移除關鍵數據為空值的行
    financial_df = financial_df.sort_values('date').groupby('stock_id').last().reset_index()

    # 4. 寫入資料庫 (增加保護機制)
    if not financial_df.empty:
        with sqlite3.connect(DB_PATH) as conn:
            # 使用 'replace' if_exists 策略，這裡需要先讀取舊數據，再合併新數據
            try:
                old_df = pd.read_sql("SELECT * FROM daily_metrics", conn)
                # 將新舊數據合併，並移除重複項，保留最新的
                combined_df = pd.concat([old_df, financial_df]).drop_duplicates(subset=['stock_id'], keep='last')
            except pd.io.sql.DatabaseError:
                # 如果表格不存在，直接使用新數據
                combined_df = financial_df

            combined_df.to_sql('daily_metrics', conn, if_exists='replace', index=False)

        print(f"成功更新/寫入 {len(financial_df)} 筆最新的財務數據。資料庫總計 {len(combined_df)} 筆記錄。")
    else:
        print("警告：經過清洗後，沒有有效的財務數據可供更新。")

def main():
    """
    執行整個數據更新流程的主函數。
    """
    print(f"--- 數據庫更新程序啟動 ({datetime.now()}) ---")
    
    # 步驟 1: 確保資料庫與表格存在
    setup_database()
    
    # 步驟 2: 更新財務數據 (核心)
    update_financial_data()
    
    # 步驟 3: 更新新聞情緒數據 (衛星)
    update_news_sentiment_for_stocks(TICKER_LIST, DB_PATH)
    
    print(f"--- 所有數據更新完畢 ({datetime.now()}) ---")


if __name__ == "__main__":
    # 讓此腳本可以獨立執行
    if not FINMIND_API_TOKEN or FINMIND_API_TOKEN == "YOUR_FINMIND_API_TOKEN":
        print("錯誤：請在 config.py 中設定您有效的 FinMind API Token。")
    else:
        main()

