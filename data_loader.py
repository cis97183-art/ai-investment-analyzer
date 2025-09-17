import pandas as pd
import sqlite3
import streamlit as st
import os

DB_PATH = "tw_stock_data.db"

@st.cache_data(ttl=3600) # 快取數據一小時
def load_and_merge_data():
    """
    [yfinance 版] 從本地 SQLite 資料庫讀取財務數據和新聞情緒數據，然後將它們融合在一起。
    """
    if not os.path.exists(DB_PATH):
        st.error(f"錯誤：找不到資料庫檔案 '{DB_PATH}'。請先執行 'update_database.py' 來生成資料庫。")
        return pd.DataFrame()
        
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # 讀取最新的財務數據快照
            financial_df = pd.read_sql("SELECT * FROM daily_metrics", conn)
            # 讀取新聞情緒數據
            news_df = pd.read_sql("SELECT stock_id, headline, sentiment_category FROM news_sentiment", conn)
        
        if financial_df.empty:
            st.warning("資料庫中的財務數據為空。請先執行 'update_database.py'。")
            return pd.DataFrame()

        # 數據融合：計算每支股票的正面/負面新聞數量
        news_summary = news_df.groupby('stock_id')['sentiment_category'].value_counts().unstack(fill_value=0)
        # 確保 'Positive' 和 'Negative' 欄位存在
        if 'Positive' not in news_summary: news_summary['Positive'] = 0
        if 'Negative' not in news_summary: news_summary['Negative'] = 0
        
        # 將新聞統計與財務數據合併
        merged_df = pd.merge(financial_df, news_summary[['Positive', 'Negative']], on='stock_id', how='left')
        # 填充沒有新聞的股票
        merged_df[['Positive', 'Negative']] = merged_df[['Positive', 'Negative']].fillna(0)

        # 將最新的新聞標題附加到每一行，以便後續分析
        latest_headlines = news_df.groupby('stock_id')['headline'].apply(lambda x: ' | '.join(x)).reset_index()
        final_df = pd.merge(merged_df, latest_headlines, on='stock_id', how='left')
        final_df['headline'].fillna("無", inplace=True)
        
        st.success(f"成功從 '{DB_PATH}' 載入並融合了 {len(final_df)} 筆最新市場數據。")
        return final_df

    except Exception as e:
        st.error(f"從資料庫讀取或融合數據失敗: {e}")
        return pd.DataFrame()

