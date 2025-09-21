import pandas as pd
import numpy as np
from config import LISTED_STOCK_PATH, OTC_STOCK_PATH, ETF_PATH

def _clean_stock_data(df: pd.DataFrame, asset_type: str) -> pd.DataFrame:
    """清理上市/上櫃股票資料的輔助函式"""
    df['資產類別'] = asset_type
    df.rename(columns={'代號': '代碼'}, inplace=True)
    df.replace('--', np.nan, inplace=True)
    return df

def _clean_etf_data(df: pd.DataFrame) -> pd.DataFrame:
    """清理 ETF 資料的輔助函式，並統一規模與代碼欄位"""
    df['資產類別'] = 'ETF'
    
    # 【核心修正】將 '代碼.y' 重新命名為 '代碼'
    df.rename(columns={'代碼.y': '代碼'}, inplace=True)
    df.replace('--', np.nan, inplace=True)
    
    # 建立統一的 '市值(億)' 欄位
    # 優先使用 '資產規模.億.'，如果該值為空，則使用 '市值.億.'
    df['市值(億)'] = pd.to_numeric(df['資產規模.億.'], errors='coerce')
    df['市值(億)'].fillna(pd.to_numeric(df['市值.億.'], errors='coerce'), inplace=True)
    
    # 刪除舊的、不統一或不再需要的欄位
    df.drop(columns=['市值.億.', '資產規模.億.', '代碼.x'], inplace=True, errors='ignore')
    
    return df

def load_and_prepare_data(listed_path: str, otc_path: str, etf_path: str) -> pd.DataFrame:
    """
    載入、清理並合併所有資料來源，回傳一個標準化後的 master DataFrame。
    """
    try:
        # 讀取並清理各個檔案
        df_etf = _clean_etf_data(pd.read_csv(etf_path))
        df_listed = _clean_stock_data(pd.read_csv(listed_path), '上市')
        df_otc = _clean_stock_data(pd.read_csv(otc_path), '上櫃')

        # 合併三個 DataFrame
        master_df = pd.concat([df_etf, df_listed, df_otc], ignore_index=True, sort=False)
        
        print("資料載入與標準化完成！")
        return master_df

    except FileNotFoundError as e:
        print(f"錯誤：找不到檔案 {e.filename}。")
        raise e
    except Exception as e:
        print(f"處理資料時發生錯誤: {e}")
        raise e