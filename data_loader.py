import pandas as pd
import streamlit as st
import os

# --- 常數設定 ---
LISTED_STOCKS_PATH = 'listed stock. without etfcsv.csv'
OTC_STOCKS_PATH = 'OTC without etf.csv'
ETF_PATH = 'ETFALL.xlsx' 

# --- 核心數據清理與轉換函數 ---
def clean_numeric_column(series: pd.Series) -> pd.Series:
    """
    【V8.0 終極版】將欄位轉換為數值型態，並處理無效值 (如逗號、百分比、前後空格)。
    這是解決「中砂」等股票無法被正確篩選的最終修正。
    """
    # 關鍵修正: 新增 .str.replace('%', '') 來移除百分比符號，並用 .str.strip() 移除潛在空格
    cleaned_series = series.astype(str).str.replace(',', '').str.replace('%', '').str.strip()
    return pd.to_numeric(cleaned_series, errors='coerce')

def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """標準化欄位名稱，移除特殊字元並統一命名"""
    df.columns = df.columns.str.strip()
    
    rename_map = {
        '代號': 'stock_id',
        '代碼.y': 'stock_id',
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
        '最新季度負債總額佔比(%)': 'debt_ratio_latest_q',
        '現金股利連配次數': 'dividend_consecutive_years',
        '成交價現金殖利率': 'yield',
        '一年(σ年)': 'std_dev_1y',
        '三年.σ年.': 'std_dev_3y',
        '僑外投資持股(%)': 'foreign_holding_pct',
        '本國法人持股(%)': 'local_corp_holding_pct',
        '最新近4Q每股自由金流(元)': 'fcf_per_share_4q',
        '市價': 'price',
        '漲跌...': 'price_change',
        '折溢價...': 'premium_discount_pct',
        '年報酬率.含息.': 'annual_return_incl_div',
        '內扣費用.保管.管理.': 'expense_ratio',
    }
    
    df.rename(columns=rename_map, inplace=True)
    return df

# --- 主要數據加載與整合函數 ---
@st.cache_data
def load_all_data_from_csvs():
    """從多個CSV/Excel檔案加載、清理並整合所有數據"""
    try:
        listed_df = pd.read_csv(LISTED_STOCKS_PATH, encoding='utf-8')
        otc_df = pd.read_csv(OTC_STOCKS_PATH, encoding='utf-8')
        stocks_df = pd.concat([listed_df, otc_df], ignore_index=True)
        stocks_df = standardize_column_names(stocks_df)
        
        numeric_cols_stock = [
            'beta', 'market_cap_billions', 'years_since_listing', 'roe_avg_3y',
            'roe_latest_q', 'pe_ratio', 'acc_rev_yoy', 'debt_ratio_latest_q',
            'dividend_consecutive_years', 'yield', 'std_dev_1y', 
            'foreign_holding_pct', 'local_corp_holding_pct',
            'fcf_per_share_4q', 'roe_wavg_3y'
        ]
        for col in numeric_cols_stock:
            if col in stocks_df.columns:
                stocks_df[col] = clean_numeric_column(stocks_df[col])
        
        if 'stock_id' in stocks_df.columns:
            stocks_df['stock_id'] = stocks_df['stock_id'].astype(str)

        etfs_df = pd.read_excel(ETF_PATH)
        etfs_df = standardize_column_names(etfs_df)
        
        numeric_cols_etf = [
            'beta', 'std_dev_3y', 'annual_return_incl_div', 'yield',
            'expense_ratio', 'price', 'price_change', 'premium_discount_pct'
        ]
        for col in numeric_cols_etf:
            if col in etfs_df.columns:
                 etfs_df[col] = clean_numeric_column(etfs_df[col])

        if 'stock_id' in etfs_df.columns:
            etfs_df['stock_id'] = etfs_df['stock_id'].astype(str)

        return stocks_df, etfs_df
    
    except FileNotFoundError as e:
        st.error(f"錯誤：找不到必要的資料檔案 '{e.filename}'。請確認檔案是否已上傳且位於正確的路徑。")
        return pd.DataFrame(), pd.DataFrame()
    except Exception as e:
        st.error(f"讀取資料時發生未預期的錯誤: {e}")
        return pd.DataFrame(), pd.DataFrame()

