import pandas as pd
import sqlite3
import streamlit as st
import os

DB_PATH = "tw_stock_data.db"
TABLE_NAME = "daily_metrics"

@st.cache_data(ttl=3600) # 快取數據一小時
def load_data_from_db():
    """
    從本地 SQLite 資料庫讀取所有股票數據。
    使用 Streamlit 快取來優化效能。
    """
    if not os.path.exists(DB_PATH):
        st.error(f"錯誤：找不到資料庫檔案 '{DB_PATH}'。請先執行 'update_database.py' 來生成資料庫。")
        return pd.DataFrame()
        
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql(f"SELECT * FROM {TABLE_NAME}", conn)
        st.success(f"成功從 '{DB_PATH}' 載入 {len(df)} 筆最新市場數據。")
        return df
    except Exception as e:
        st.error(f"從資料庫讀取數據失敗: {e}")
        return pd.DataFrame()
