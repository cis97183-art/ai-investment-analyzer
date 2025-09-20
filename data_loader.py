# data_loader.py (最終修正版 for Excel)

import pandas as pd
import numpy as np

def clean_stock_data(file_path, file_name):
    """
    專門讀取並清理「上市」與「上櫃」股票資料的函式。
    """
    print(f"--- 開始處理【{file_name}】---")
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
        print(f"成功讀取檔案: {file_path}")
    except FileNotFoundError:
        print(f"錯誤：找不到檔案 {file_path}，請確認檔案路徑是否正確。")
        return None
    except Exception as e:
        print(f"讀取檔案時發生錯誤: {e}")
        return None

    df.columns = df.columns.str.strip()
    
    numeric_cols = [
        '一年(β)', '市值(億)', '成立年數', '近3年平均ROE(%)', 
        '近3年加權平均ROE(%)', '最新單季ROE(%)', 'PER', '累月營收年增(%)',
        '最新季度負債總額佔比(%)', '現金股利連配次數', '成交價現金殖利率',
        '一年(σ年)', '僑外投資持股(%)', '本國法人持股(%)', '最新近4Q每股自由金流(元)'
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    print(f"【{file_name}】資料清理完成！")
    return df

def clean_etf_data(file_path):
    """
    專門讀取並清理 ETF 資料的函式 (現在使用 read_excel)。
    """
    print(f"--- 開始處理【ETF 資料】---")
    try:
        # *** 修正點：將 pd.read_csv 改為 pd.read_excel ***
        df = pd.read_excel(file_path)
        print(f"成功讀取 Excel 檔案: {file_path}")
    except FileNotFoundError:
        print(f"錯誤：找不到檔案 {file_path}，請確認檔案路徑是否正確。")
        return None
    except Exception as e:
        print(f"讀取檔案時發生錯誤: {e}")
        return None

    # Excel 讀取進來後，後續的清理流程與之前相同
    original_cols = df.columns.tolist()
    new_cols = [col.replace('...', '').replace('.張.', '').replace('.億.', '').replace('.x', '').replace('.y', '') for col in original_cols]
    df.columns = new_cols
    print("欄位名稱清理完成。")

    df.replace({'--': np.nan, 'NA': np.nan}, inplace=True)
    
    percent_cols = ['折溢價', '近四季殖利率', '年報酬率含息', '本月月增率', '成交價現金殖利率']
    for col in percent_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('%', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col] / 100

    other_numeric_cols = ['市價', '五日均量', '資產規模', '內扣費用保管管理', '受益人數', '成立年齡', '一年.β.', '三年.σ年.', '五年.σ年.']
    for col in other_numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    print("【ETF 資料】資料清理完成！")
    return df

def load_and_prepare_data(listed_path, otc_path, etf_path):
    """
    主函式：讀取、清理並整合所有資料檔案。
    """
    df_listed = clean_stock_data(listed_path, "上市股票")
    df_otc = clean_stock_data(otc_path, "上櫃股票")
    df_etf = clean_etf_data(etf_path)
    
    if df_listed is None or df_otc is None or df_etf is None:
        print("有部分資料檔案處理失敗，無法繼續。")
        return None

    df_listed['資產類別'] = '上市櫃股票'
    df_otc['資產類別'] = '上市櫃股票'
    df_etf['資產類別'] = 'ETF'
    
    df_etf.rename(columns={
        '代碼.y': '代號',
        '市值.億.': '市值(億)',
        '一年.β.': '一年(β)',
        '三年.σ年.': '一年(σ年)'
    }, inplace=True)
    
    if '代碼.x' in df_etf.columns:
        df_etf.drop(columns=['代碼.x'], inplace=True)
        print("已修正 ETF 資料：使用 '代碼.y' 作為代號，並移除 '代碼.x'。")

    master_df = pd.concat([df_listed, df_otc, df_etf], ignore_index=True)
    master_df['代號'] = master_df['代號'].astype(str)

    print("\n--- 所有資料已成功整合至 Master DataFrame ---\n")
    return master_df