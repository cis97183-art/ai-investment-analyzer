# data_loader.py

import pandas as pd
import numpy as np
import config # 導入設定檔

def clean_numeric_column(series):
    """將欄位轉換為數值型態，處理 '--', 'NA' 等無效值"""
    return pd.to_numeric(series.astype(str).str.replace(',', '').replace('--', np.nan), errors='coerce')

# data_loader.py

# (上面的 import 和 clean_numeric_column 函式不用變)

def load_and_preprocess_data():
    """模組一：數據整合與預處理引擎 (升級版)"""
    try:
        df_etf = pd.read_excel(config.ETF_FILE)
        df_listed = pd.read_csv(config.LISTED_STOCK_FILE)
        df_otc = pd.read_csv(config.OTC_STOCK_FILE)

        # --- 資料整合 ---
        df_etf = df_etf.rename(columns={'代碼.y': 'StockID', '名稱.y': '名稱'}).drop(columns=['代碼.x', '名稱.x'], errors='ignore')
        df_etf['AssetType'] = 'ETF'
        df_stocks = pd.concat([df_listed, df_otc], ignore_index=True).rename(columns={'代號': 'StockID'})
        df_stocks['AssetType'] = '個股'
        master_df = pd.concat([df_etf, df_stocks], ignore_index=True)
        master_df['StockID'] = master_df['StockID'].astype(str).str.strip()
        master_df = master_df.drop_duplicates(subset='StockID', keep='first')

        # --- 欄位重新命名 ---
        # (這一段 mapping 保持不變)
        column_mapping = {
            '市值.億.': 'MarketCap_Billions', '市值(億)': 'MarketCap_Billions',
            '一年.β.': 'Beta_1Y', '一年(β)': 'Beta_1Y',
            '一年(σ年)': 'StdDev_1Y',
            '現金股利連配次數': 'Dividend_Consecutive_Years',
            '最新近4Q每股自由金流( 元)': 'FCFPS_Last_4Q',
            '成交價現金殖利率': 'Dividend_Yield',
            '近3年平均ROE(%)': 'ROE_Avg_3Y',
            '累月營收年增(%)': 'Revenue_YoY_Accumulated',
            '最新單季ROE(%)': 'ROE_Latest_Quarter',
            '產業別': 'Industry',
            '市價': 'Close',
            '成立年齡': 'Age_Years',
            '成立年數': 'Age_Years'
        }
        master_df = master_df.rename(columns=column_mapping)

        # ▼▼▼ 升級版的合併邏輯 ▼▼▼
        # --- 自動偵測並合併所有因 rename 產生的重複欄位 ---
        # 找出所有重複的欄位名稱
        duplicated_cols = master_df.columns[master_df.columns.duplicated(keep=False)].unique()

        if not duplicated_cols.empty:
            print(f"偵測到重複欄位: {duplicated_cols.tolist()}，將進行智慧合併...")
            for col_name in duplicated_cols:
                # 使用 bfill + ffill 策略來合併 (優先使用前面欄位的值，空值則由後面補上)
                merged_series = master_df[col_name].bfill(axis=1).iloc[:, 0]
                # 刪除舊的、重複的欄位群
                master_df = master_df.drop(columns=col_name)
                # 將合併後的新欄位加回來
                master_df[col_name] = merged_series
            print("重複欄位合併完成。")
        # --- 升級結束 ---

        # --- 數據清洗 (這一段保持不變) ---
        numeric_cols = [
            'MarketCap_Billions', 'StdDev_1Y', 'Beta_1Y', 'Dividend_Consecutive_Years',
            'FCFPS_Last_4Q', 'Dividend_Yield', 'ROE_Avg_3Y', 'Revenue_YoY_Accumulated',
            'ROE_Latest_Quarter', 'Close', 'Age_Years'
        ]

        for col in numeric_cols:
            if col in master_df.columns:
                master_df[col] = clean_numeric_column(master_df[col])

        master_df = master_df.set_index('StockID', drop=False)
        print("數據整合與清洗完成。")
        return master_df

    except Exception as e:
        print(f"處理數據時發生未預期的錯誤: {e}")
        # 為了偵錯，我們印出更詳細的錯誤資訊
        import traceback
        traceback.print_exc()
        return None