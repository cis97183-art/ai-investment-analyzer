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
        
        # !! 重要 !!: 請根據你實際的 Excel/CSV 欄位名稱微調這裡的 key
        column_mapping = {
            '市值(億)': 'MarketCap_Billions', '一年標準差': 'StdDev_1Y',
            '一年Beta': 'Beta_1Y', '現金股利連續發放次數': 'Dividend_Consecutive_Years',
            '最新近4季每股自由現金流(元)': 'FCFPS_Last_4Q', '成交價現金殖利率': 'Dividend_Yield',
            '近3年平均ROE(%)': 'ROE_Avg_3Y', '累月營收年增(%)': 'Revenue_YoY_Accumulated',
            '最新單季ROE(%)': 'ROE_Latest_Quarter', '產業別': 'Industry',
            '上市/上櫃日期': 'ListingDate', '收盤價': 'Close'
        }
        master_df = master_df.rename(columns=column_mapping)
        
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