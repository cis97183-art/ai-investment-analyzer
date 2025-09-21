# data_loader.py (最終版 - 處理 Excel + CSV 混合檔案)

import pandas as pd
import numpy as np
import io
import csv

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
        df.columns = df.columns.str.strip()
        print(f"強健模式讀取成功！共讀取 {len(df)} 筆資料。")
        return df
        
    except Exception as e:
        print(f"在讀取並清理檔案 {file_path} 時發生嚴重錯誤: {e}")
        raise

def _clean_stock_data(df: pd.DataFrame, asset_type: str) -> pd.DataFrame:
    """
    清理上市/上櫃股票資料的輔助函式。
    核心任務：將 '代號' 欄位統一為 '代碼'。
    """
    if df.empty: return df
    
    df['資產類別'] = asset_type
    
    if '代號' in df.columns:
        df.rename(columns={'代號': '代碼'}, inplace=True)
    
    df.replace('--', np.nan, inplace=True)
    
    return df

def _clean_etf_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    清理 ETF 資料的輔助函式。
    核心任務：
    1. 將 '代碼.y' (正確的ID) 統一為 '代碼'。
    2. 將 '資產規模.億.' 統一為 '市值(億)'。
    3. 移除混淆的 '代碼.x' 欄位。
    """
    if df.empty: return df
    
    df['資產類別'] = 'ETF'
    
    if '代碼.y' in df.columns:
        df.rename(columns={'代碼.y': '代碼'}, inplace=True)
    
    if '資產規模.億.' in df.columns:
        df['市值(億)'] = pd.to_numeric(df['資產規模.億.'], errors='coerce')
    elif '市值.億.' in df.columns:
        df['市值(億)'] = pd.to_numeric(df['市值.億.'], errors='coerce')

    cols_to_drop = ['代碼.x', '市值.億.', '資產規模.億.']
    existing_cols_to_drop = [col for col in cols_to_drop if col in df.columns]
    if existing_cols_to_drop:
        df.drop(columns=existing_cols_to_drop, inplace=True)

    df.replace('--', np.nan, inplace=True)
    
    return df

def load_and_prepare_data(listed_path: str, otc_path: str, etf_path: str) -> pd.DataFrame:
    """
    載入、清理並合併所有資料來源，回傳一個標準化後的 master DataFrame。
    """
    try:
        # 1. 使用 pandas.read_excel 來讀取 ETFALL.xlsx 檔案
        print(f"--- 正在讀取 Excel 檔案: {etf_path} ---")
        df_etf_raw = pd.read_excel(etf_path)
        df_etf = _clean_etf_data(df_etf_raw)
        
        # 2. 對於 CSV 檔案，繼續使用強健的自訂讀取函式
        df_listed = _clean_stock_data(_read_and_manually_clean_csv(listed_path), '上市')
        df_otc = _clean_stock_data(_read_and_manually_clean_csv(otc_path), '上櫃')

        # 合併三個 DataFrame
        master_df = pd.concat([df_etf, df_listed, df_otc], ignore_index=True, sort=False)
        
        print("\n所有資料載入與標準化完成！最終 Master DataFrame 資訊：")
        master_df.info(verbose=False)
        return master_df

    except FileNotFoundError as e:
        print(f"錯誤：找不到檔案 {e.filename}。請確認 config.py 中的路徑設定是否正確。")
        return None
    except Exception as e:
        print(f"在 load_and_prepare_data 中發生錯誤: {e}")
        return None
