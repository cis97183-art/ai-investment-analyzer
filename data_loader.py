# data_loader.py (已修正)

import pandas as pd
import numpy as np
import io
import csv
from config import LISTED_STOCK_PATH, OTC_STOCK_PATH, ETF_PATH

def _read_and_manually_clean_csv(file_path: str, encoding: str = 'cp950') -> pd.DataFrame:
    """
    一個極度強健的 CSV 讀取函式，能預先處理檔案中的 NULL byte 和結構性錯誤。
    """
    print(f"--- 正在以強健模式讀取並清理 CSV 檔案: {file_path} ---")
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        cleaned_content = content.replace(b'\x00', b'')
        
        string_data = cleaned_content.decode(encoding, errors='replace')
        string_io_obj = io.StringIO(string_data)
        
        reader = csv.reader(string_io_obj)
        data = list(reader)
        
        if not data:
            return pd.DataFrame()
            
        header = data[0]
        rows = data[1:]
        
        header_len = len(header)
        cleaned_rows = [row for row in rows if len(row) == header_len]
        
        if not cleaned_rows:
             print(f"警告：在 {file_path} 中找不到格式正確的資料行。")
             return pd.DataFrame(columns=header)

        df = pd.DataFrame(cleaned_rows, columns=header)
        print(f"強健模式讀取成功！共讀取 {len(df)} 筆資料。")
        return df
        
    except Exception as e:
        print(f"在讀取並清理檔案 {file_path} 時發生嚴重錯誤: {e}")
        raise

def _clean_stock_data(df: pd.DataFrame, asset_type: str) -> pd.DataFrame:
    """清理上市/上櫃股票資料的輔助函式"""
    if df.empty: return df
    df['資產類別'] = asset_type
    df.rename(columns={'代號': '代碼'}, inplace=True)
    df.replace('--', np.nan, inplace=True)
    return df

def _clean_etf_data(df: pd.DataFrame) -> pd.DataFrame:
    """清理 ETF 資料的輔-助函式，並統一規模與代碼欄位"""
    if df.empty: return df
    df['資產類別'] = 'ETF'
    # 檢查 '代碼.y' 是否存在，若否，則嘗試使用 '代碼'
    if '代碼.y' in df.columns:
        df.rename(columns={'代碼.y': '代碼'}, inplace=True)
    
    df.replace('--', np.nan, inplace=True)
    
    df['市值(億)'] = pd.to_numeric(df.get('資產規模.億.'), errors='coerce')
    df['市值(億)'].fillna(pd.to_numeric(df.get('市值.億.'), errors='coerce'), inplace=True)
    
    cols_to_drop = [col for col in ['市值.億.', '資產規模.億.', '代碼.x'] if col in df.columns]
    if cols_to_drop:
        df.drop(columns=cols_to_drop, inplace=True)
    
    return df

def load_and_prepare_data(listed_path: str, otc_path: str, etf_path: str) -> pd.DataFrame:
    """
    載入、清理並合併所有資料來源，回傳一個標準化後的 master DataFrame。
    """
    try:
        # --- 【核心修正】---
        # 針對 .xlsx 檔案，我們必須使用 pandas.read_excel()
        print(f"--- 正在讀取 Excel 檔案: {etf_path} ---")
        df_etf_raw = pd.read_excel(etf_path)
        df_etf = _clean_etf_data(df_etf_raw)
        
        # 對於 CSV 檔案，繼續使用我們強大的自訂讀取函式
        df_listed = _clean_stock_data(_read_and_manually_clean_csv(listed_path), '上市')
        df_otc = _clean_stock_data(_read_and_manually_clean_csv(otc_path), '上櫃')

        # 合併三個 DataFrame
        master_df = pd.concat([df_etf, df_listed, df_otc], ignore_index=True, sort=False)
        
        print("資料載入與標準化完成！")
        return master_df

    except Exception as e:
        print(f"在 load_and_prepare_data 中發生錯誤: {e}")
        raise e