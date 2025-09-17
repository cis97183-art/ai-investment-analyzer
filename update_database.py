import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from FinMind.data import DataLoader
from config import FINMIND_API_TOKEN

# --- 全域設定 ---
DB_PATH = "tw_stock_data.db"
TABLE_NAME = "daily_metrics"
API = DataLoader()

def login_finmind():
    """登入 FinMind API"""
    if not FINMIND_API_TOKEN or FINMIND_API_TOKEN == "在此貼上您從 FinMind 網站獲取的 API Token":
        print("錯誤：請在 config.py 中設定您的 FINMIND_API_TOKEN。")
        return False
    API.login_by_token(api_token=FINMIND_API_TOKEN)
    print("FinMind API 登入成功。")
    return True

def get_all_stock_ids():
    """獲取所有上市上櫃的普通股股票代碼列表"""
    print("正在從 FinMind 獲取所有台股基本資訊...")
    stock_list = API.taiwan_stock_info()
    
    if stock_list.empty:
        print("錯誤：從 API 獲取的股票列表為空。")
        return []

    print(f"已獲取 {len(stock_list)} 筆市場標的總數。開始篩選普通股...")
    
    # [修正] 更新篩選邏輯，以 'industry_category' 是否存在作為主要判斷依據
    # 這樣可以更可靠地過濾掉指數、ETF、DR 等非普通股標的
    filtered_stocks = stock_list[
        stock_list['industry_category'].notna() &
        (stock_list['industry_category'] != "") &
        (~stock_list['stock_name'].str.contains('DR|ES|CA|ETF'))
    ].copy() # 使用 .copy() 避免 SettingWithCopyWarning
    
    return filtered_stocks['stock_id'].tolist()

def get_stock_metrics(stock_ids, date_str):
    """批次獲取多支股票的 PER, PBR, Yield 等指標"""
    try:
        # FinMind API 限制單次查詢的股票數量，這裡進行分批處理
        batch_size = 100
        all_metrics = []
        
        for i in range(0, len(stock_ids), batch_size):
            batch = stock_ids[i:i + batch_size]
            print(f"正在獲取第 {i+1} 到 {i+len(batch)} 支股票的數據...")
            # [修正] 根據 FinMind API 的最新版本，將參數 'date' 修改為 'start_date'
            df_batch = API.taiwan_stock_per_pbr(
                stock_id=batch,
                start_date=date_str
            )
            if not df_batch.empty:
                all_metrics.append(df_batch)
        
        if not all_metrics:
            return pd.DataFrame()
            
        return pd.concat(all_metrics, ignore_index=True)
        
    except Exception as e:
        print(f"獲取 PER/PBR 時發生錯誤: {e}")
        return pd.DataFrame()

def save_to_db(df, db_path, table_name):
    """將 DataFrame 存入 SQLite 資料庫"""
    if df.empty:
        print("沒有數據可儲存。")
        return
    
    with sqlite3.connect(db_path) as conn:
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        print(f"成功將 {len(df)} 筆資料寫入資料庫 '{db_path}' 的 '{table_name}' 表中。")

def main():
    """主執行流程"""
    if not login_finmind():
        return
    
    target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"目標資料日期: {target_date}")

    # 1. 獲取所有股票代碼
    print("步驟 1/3: 正在獲取所有股票代碼...")
    stock_ids = get_all_stock_ids()
    
    if not stock_ids:
        print("未能獲取到任何有效的股票代碼，程序終止。請檢查 get_all_stock_ids 函式的篩選邏輯或 API 連線。")
        return

    print(f"篩選後，獲取到 {len(stock_ids)} 支上市上櫃普通股代碼。")

    # 2. 批次獲取所有股票的關鍵指標
    print(f"步驟 2/3: 正在為 {len(stock_ids)} 支股票獲取 {target_date} 的指標數據...")
    all_metrics_df = get_stock_metrics(stock_ids, target_date)
    
    # 3. 數據清洗與整理
    if not all_metrics_df.empty:
        print("步驟 3/3: 正在進行數據清洗與整理...")

        # [修正] 增加欄位名稱的穩健性處理，以應對 API 可能的大小寫變動
        rename_map = {
            'dividend_yield': 'yield',
            'PE': 'pe_ratio',      # 原始預期大寫
            'pe': 'pe_ratio',      # 備用小寫
            'PB': 'pb_ratio',      # 原始預期大寫
            'pb': 'pb_ratio'       # 備用小寫
        }
        
        # 篩選出 DataFrame 中實際存在的欄位進行重新命名
        existing_rename_map = {k: v for k, v in rename_map.items() if k in all_metrics_df.columns}
        all_metrics_df.rename(columns=existing_rename_map, inplace=True)

        # 確保必要的欄位存在，若不存在則給予預設值 (e.g., NA)
        required_cols = ['pe_ratio', 'pb_ratio', 'yield']
        for col in required_cols:
            if col not in all_metrics_df.columns:
                all_metrics_df[col] = pd.NA
                print(f"警告：資料來源缺少 '{col}' 欄位，已自動補上 NA 值。")

        print("正在儲存數據至本地資料庫...")
        save_to_db(all_metrics_df, DB_PATH, TABLE_NAME)
    else:
        print("未能獲取任何指標數據，程序終止。")

    print("數據更新流程完成。")

if __name__ == "__main__":
    main()



