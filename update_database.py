import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from FinMind.data import DataLoader
from config import FINMIND_API_TOKEN
import time
import os

# --- 全域設定 ---
DB_PATH = "tw_stock_data.db"
TABLE_NAME = "daily_metrics"
API = DataLoader()

def login_finmind():
    """登入 FinMind API"""
    if not FINMIND_API_TOKEN or FINMIND_API_TOKEN == "在此貼上您從 FinMind 網站獲取的 API Token":
        print("錯誤：請在 config.py 中設定您的 FINMIND_API_TOKEN。")
        return False
    try:
        API.login_by_token(api_token=FINMIND_API_TOKEN)
        print("FinMind API 登入成功。")
        return True
    except Exception as e:
        print(f"FinMind API 登入失敗: {e}")
        return False

def get_all_stock_ids():
    """獲取所有上市上櫃的普通股股票代碼列表"""
    stock_list = API.taiwan_stock_info()
    # 篩選出上市(listed)和上櫃(otc)的普通股，並排除特別股、DR股等
    filtered_stocks = stock_list[
        (stock_list['type'].isin(['listed', 'otc'])) &
        (~stock_list['stock_name'].str.contains('DR|ES|CA|특별|보통|보통주|公司', na=False)) &
        (stock_list['stock_id'].str.match(r'^\d{4}$'))
    ]
    return filtered_stocks[['stock_id', 'stock_name', 'industry_category']].copy()

def get_stock_metrics(stock_ids, date_str):
    """批次獲取多支股票的 PER, PBR, Yield 等指標"""
    try:
        print(f"正在為 {len(stock_ids)} 支股票獲取 {date_str} 的指標數據...")
        # FinMind API 每次調用有股票數量限制，需要分批處理
        batch_size = 100 
        all_metrics = []
        for i in range(0, len(stock_ids), batch_size):
            batch_ids = stock_ids[i:i+batch_size]
            print(f"  - 處理批次 {i//batch_size + 1}...")
            df_metrics = API.taiwan_stock_per_pbr(
                stock_id=batch_ids,
                date=date_str
            )
            all_metrics.append(df_metrics)
            time.sleep(1) # 遵守 API 使用禮儀，避免過於頻繁的請求

        if not all_metrics:
            return pd.DataFrame()
            
        final_df = pd.concat(all_metrics, ignore_index=True)
        return final_df
    except Exception as e:
        print(f"獲取 PER/PBR 時發生錯誤: {e}")
        return pd.DataFrame()

def save_to_db(df, db_path, table_name):
    """將 DataFrame 存入 SQLite 資料庫"""
    if df.empty:
        print("沒有數據可儲存。")
        return
    
    # 使用絕對路徑確保檔案位置正確
    db_abs_path = os.path.abspath(db_path)
    print(f"準備將數據寫入資料庫：{db_abs_path}")
    
    with sqlite3.connect(db_abs_path) as conn:
        # 使用 replace 策略，每次都寫入最新的完整數據
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        print(f"成功將 {len(df)} 筆資料寫入資料庫 '{db_path}' 的 '{table_name}' 表中。")

def main():
    """主執行流程"""
    if not login_finmind():
        return
    
    # 為了確保能抓到最新已收盤的數據，我們從 T-1 開始往前找最多5天
    print("正在確定最新的有效交易日期...")
    latest_date_str = None
    for i in range(1, 6):
        target_date = datetime.now() - timedelta(days=i)
        date_str = target_date.strftime('%Y-%m-%d')
        # 以台積電為樣本，測試當天是否有數據
        test_df = API.taiwan_stock_daily(stock_id="2330", start_date=date_str, end_date=date_str)
        if not test_df.empty:
            latest_date_str = date_str
            print(f"找到最新的有效交易日期: {latest_date_str}")
            break
        time.sleep(0.5)

    if not latest_date_str:
        print("錯誤：在過去5天內找不到任何有效的交易日數據。")
        return

    # 1. 獲取所有股票代碼及基本資訊
    print("\n步驟 1/3: 正在獲取所有股票代碼...")
    stock_info_df = get_all_stock_ids()
    stock_ids = stock_info_df['stock_id'].tolist()
    print(f"獲取到 {len(stock_ids)} 支上市上櫃普通股代碼。")

    # 2. 批次獲取所有股票的關鍵指標
    print("\n步驟 2/3: 正在批次獲取市場關鍵指標...")
    all_metrics_df = get_stock_metrics(stock_ids, latest_date_str)
    
    # 3. 數據合併、清洗與儲存
    if not all_metrics_df.empty:
        print("\n步驟 3/3: 正在合併、清理數據並儲存至本地資料庫...")
        
        # 將指標數據與股票基本資訊合併
        final_df = pd.merge(stock_info_df, all_metrics_df, on="stock_id")

        # 重新命名欄位以符合後續分析需求
        final_df.rename(columns={
            'dividend_yield': 'yield',
            'PE': 'pe_ratio',
            'PB': 'pb_ratio'
        }, inplace=True)
        
        # 移除 P/E 或 P/B 為 0 或負數的無效數據
        final_df = final_df[(final_df['pe_ratio'] > 0) & (final_df['pb_ratio'] > 0)]
        
        save_to_db(final_df, DB_PATH, TABLE_NAME)
    else:
        print("未能獲取任何指標數據，程序終止。")

    print("\n數據更新流程完成。")

if __name__ == "__main__":
    main()
