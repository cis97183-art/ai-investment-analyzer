import pandas as pd
import streamlit as st
import os

# --- 常數設定 ---
LISTED_STOCKS_PATH = 'listed stock. without etfcsv.csv'
OTC_STOCKS_PATH = 'OTC without etf.csv'
ETF_PATH = 'ETFALL.xlsx'

# --- 核心數據清理與轉換函數 ---
def clean_numeric_column(series: pd.Series) -> pd.Series:
    """將欄位轉換為數值型態，並處理無效值"""
    return pd.to_numeric(series.astype(str).str.replace(',', ''), errors='coerce')

def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """標準化欄位名稱，移除特殊字元並統一命名"""
    df.columns = df.columns.str.strip()
    
    rename_map = {
        '代號': 'stock_id',
        '名稱': 'stock_name',
        '市場': 'market',
        '產業別': 'industry_category',
        '一年(β)': 'beta',
        '一年.β.': 'beta',
        '市值(億)': 'market_cap_billions',
        '市值.億.': 'market_cap_billions',
        '成立年數': 'years_since_listing',
        '近3年平均ROE(%)': 'roe_avg_3y',
        '近3年加權平均ROE(%)': 'roe_wavg_3y',
        '最新單季ROE(%)': 'roe_latest_q',
        'PER': 'pe_ratio',
        '累月營收年增(%)': 'acc_rev_yoy',
        '最新季度負債總額佔比(%)': 'debt_ratio',
        '現金股利連配次數': 'dividend_consecutive_years',
        '成交價現金殖利率': 'yield',
        '一年(σ年)': 'std_dev_1y',
        '僑外投資持股(%)': 'foreign_holding_pct',
        '本國法人持股(%)': 'local_corp_holding_pct',
        '最新近4Q每股自由金流(元)': 'fcf_per_share_4q',
        '代碼.y': 'stock_id', 
        '三年.σ年.': 'std_dev_3y',
        '五年.σ年.': 'std_dev_5y',
        '市價': 'close_price',
        '資產規模.億.': 'asset_size_billions',
        '近四季殖利率': 'yield_4q',
        '年報酬率.含息.': 'annual_return_incl_div',
        '內扣費用.保管.管理.': 'expense_ratio',
        '受益人數': 'num_of_beneficiaries',
        '成立年齡': 'etf_age'
    }
    
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    return df

# --- 數據載入與快取 ---
@st.cache_data(ttl=3600)
def load_all_data_from_csvs():
    """
    從三個指定的檔案載入、清理、標準化並合併上市櫃公司與ETF的數據。
    返回兩個獨立的DataFrame: 一個給個股，一個給ETF。
    """
    if not all(os.path.exists(p) for p in [LISTED_STOCKS_PATH, OTC_STOCKS_PATH, ETF_PATH]):
        st.error("錯誤：缺少必要的數據檔案 (上市、上櫃或ETF)。請確保檔案都存在於專案目錄中。")
        return pd.DataFrame(), pd.DataFrame()

    try:
        listed_df = pd.read_csv(LISTED_STOCKS_PATH, encoding='cp950', encoding_errors='ignore')
        otc_df = pd.read_csv(OTC_STOCKS_PATH, encoding='cp950', encoding_errors='ignore')
        stocks_df = pd.concat([listed_df, otc_df], ignore_index=True)
        stocks_df = standardize_column_names(stocks_df)
        
        # [修正] 新增 roe_wavg_3y 至數值轉換列表
        numeric_cols_stock = [
            'beta', 'market_cap_billions', 'roe_avg_3y', 'pe_ratio', 
            'acc_rev_yoy', 'dividend_consecutive_years', 'yield', 
            'std_dev_1y', 'fcf_per_share_4q', 'roe_wavg_3y'
        ]
        for col in numeric_cols_stock:
            if col in stocks_df.columns:
                stocks_df[col] = clean_numeric_column(stocks_df[col])
        
        if 'stock_id' in stocks_df.columns:
            stocks_df['stock_id'] = stocks_df['stock_id'].astype(str)

        etfs_df = pd.read_excel(ETF_PATH)
        etfs_df = standardize_column_names(etfs_df)
        
        numeric_cols_etf = [
            'beta', 'std_dev_3y', 'annual_return_incl_div', 
            'expense_ratio', 'yield'
        ]
        for col in numeric_cols_etf:
            if col in etfs_df.columns:
                 if col == 'yield' and '成交價現金殖利率' in etfs_df.columns:
                     etfs_df[col] = clean_numeric_column(etfs_df['成交價現金殖利率'])
                 else:
                    etfs_df[col] = clean_numeric_column(etfs_df[col])

        if 'stock_id' in etfs_df.columns:
            etfs_df['stock_id'] = etfs_df['stock_id'].astype(str)
        
        if 'stock_id' in stocks_df.columns:
            stocks_df.drop_duplicates(subset=['stock_id'], inplace=True)
        if 'stock_id' in etfs_df.columns:
            etfs_df.drop_duplicates(subset=['stock_id'], inplace=True)

        return stocks_df, etfs_df

    except Exception as e:
        st.error(f"處理數據時發生預期外的錯誤: {e}")
        return pd.DataFrame(), pd.DataFrame()

