# data_loader.py

import pandas as pd
import numpy as np
import config # 導入設定檔

def clean_numeric_column(series):
    """將欄位轉換為數值型態，處理 '--', 'NA' 等無效值"""
    return pd.to_numeric(series.astype(str).str.replace(',', '').replace('--', np.nan), errors='coerce')

def load_and_preprocess_data():
    """模組一：數據整合與預處理引擎"""
    try:
        df_etf = pd.read_excel(config.ETF_FILE)
        df_listed = pd.read_csv(config.LISTED_STOCK_FILE)
        df_otc = pd.read_csv(config.OTC_STOCK_FILE)

        # ETF 資料處理
        df_etf = df_etf.rename(columns={'代碼.y': 'StockID', '名稱.y': '名稱'})
        df_etf = df_etf.drop(columns=['代碼.x', '名稱.x'], errors='ignore')
        df_etf['AssetType'] = 'ETF'

        # 個股資料處理
        df_stocks = pd.concat([df_listed, df_otc], ignore_index=True)
        df_stocks = df_stocks.rename(columns={'代號': 'StockID'})
        df_stocks['AssetType'] = '個股'

        # 合併資料
        master_df = pd.concat([df_etf, df_stocks], ignore_index=True)
        master_df['StockID'] = master_df['StockID'].astype(str).str.strip()
        master_df = master_df.drop_duplicates(subset='StockID', keep='first')

        # ▼▼▼ 加入這行偵錯程式碼 ▼▼▼
        print("資料合併後的原始欄位名稱：", master_df.columns.tolist())
        
        # !! 重要 !!: 請根據你實際的 Excel/CSV 欄位名稱微調這裡的 key
        column_mapping = {
        # 你的資料有兩種命名風格，我們全部對應起來
        '市值.億.': 'MarketCap_Billions',
        '市值(億)': 'MarketCap_Billions',
        '一年.β.': 'Beta_1Y',
        '一年(β)': 'Beta_1Y',
        '一年(σ年)': 'StdDev_1Y',
        '現金股利連配次數': 'Dividend_Consecutive_Years',
        '最新近4Q每股自由金流( 元)': 'FCFPS_Last_4Q', # 注意 '元' 前面有個空格
        '成交價現金殖利率': 'Dividend_Yield',
        '近3年平均ROE(%)': 'ROE_Avg_3Y',
        '累月營收年增(%)': 'Revenue_YoY_Accumulated',
        '最新單季ROE(%)': 'ROE_Latest_Quarter',
        '產業別': 'Industry',
        '市價': 'Close', # 假設 '市價' 就是收盤價
        '成立年齡': 'Age_Years', # 這是我們要用來取代 ListingDate 的欄位
        '成立年數': 'Age_Years'  # 這是我們要用來取代 ListingDate 的欄位
    }
        master_df = master_df.rename(columns=column_mapping)
        
        # ▼▼▼ 在這裡貼上新的程式碼 ▼▼▼
        # --- 新增：合併由 rename 產生的重複欄位的程式碼 ---
        cols_to_check = ['MarketCap_Billions', 'Beta_1Y', 'Age_Years', 'StdDev_1Y', 'Close']

        for col in cols_to_check:
        # 如果某個欄位名稱在 DataFrame 中實際代表了多個欄位
            if isinstance(master_df.get(col), pd.DataFrame):
                print(f"偵測到重複欄位 '{col}'，進行智慧合併...")
                # 我們使用 bfill + ffill 策略來合併
                # 這會優先使用第一個欄位的值，如果是空的，就用第二、三個...欄位的值來填補
                merged_series = master_df[col].bfill(axis=1).iloc[:, 0]

        # 刪除舊的、重複的欄位群
        master_df = master_df.drop(columns=col)

        # 將合併後的新欄位加回來
        master_df[col] = merged_series
# --- 合併程式碼結束 ---
# ▲▲▲ 貼上到這裡為止 ▲▲▲

        numeric_cols = [
            'MarketCap_Billions', 'StdDev_1Y', 'Beta_1Y', 'Dividend_Consecutive_Years',
            'FCFPS_Last_4Q', 'Dividend_Yield', 'ROE_Avg_3Y', 'Revenue_YoY_Accumulated',
            'ROE_Latest_Quarter', 'Close'
        ]
        
        for col in numeric_cols:
            if col in master_df.columns:
                master_df[col] = clean_numeric_column(master_df[col])
        
        if 'ListingDate' in master_df.columns:
            master_df['ListingDate'] = pd.to_datetime(master_df['ListingDate'], errors='coerce')

        master_df = master_df.set_index('StockID', drop=False)
        print("數據整合與清洗完成。")
        return master_df

    except FileNotFoundError as e:
        print(f"錯誤：找不到檔案 {e.filename}。")
        return None
    except Exception as e:
        print(f"處理數據時發生未預期的錯誤: {e}")
        return None