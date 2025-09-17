import pandas as pd
import sqlite3
import streamlit as st
import os

DB_PATH = "tw_stock_data.db"

@st.cache_data(ttl=3600) # 快取數據一小時
def load_data_from_db():
    """
    [更新版] 從本地 SQLite 資料庫讀取數據，並將財務指標與最新的新聞情緒融合。
    """
    if not os.path.exists(DB_PATH):
        st.error(f"錯誤：找不到資料庫檔案 '{DB_PATH}'。請先執行 'update_database.py' 來生成資料庫。")
        return pd.DataFrame()
        
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # 步驟 1: 讀取主要的財務數據
            metrics_query = "SELECT * FROM daily_metrics"
            metrics_df = pd.read_sql(metrics_query, conn)

            # 步驟 2: 讀取新聞數據，並只保留每支股票「最新」的一則新聞情緒
            # 使用 ROW_NUMBER() 視窗函數來為每支股票的新聞按日期排序
            sentiment_query = """
            WITH LatestNews AS (
                SELECT
                    stock_id,
                    sentiment_category,
                    headline,
                    ROW_NUMBER() OVER(PARTITION BY stock_id ORDER BY news_date DESC) as rn
                FROM news_sentiment
            )
            SELECT
                stock_id,
                sentiment_category,
                headline as latest_news_headline
            FROM LatestNews
            WHERE rn = 1
            """
            sentiment_df = pd.read_sql(sentiment_query, conn)

            # 步驟 3: [Phase 3 - 數據融合] 將新聞情緒合併到財務數據中
            # 使用 left join，確保即使沒有新聞的股票也會被包含進來
            if not sentiment_df.empty:
                merged_df = pd.merge(metrics_df, sentiment_df, on='stock_id', how='left')
            else:
                merged_df = metrics_df
                merged_df['sentiment_category'] = None
                merged_df['latest_news_headline'] = None
            
            # 填充缺失值，將沒有新聞的股票情緒設為'中性'
            merged_df['sentiment_category'].fillna('中性', inplace=True)

        st.success(f"成功從 '{DB_PATH}' 載入並融合了 {len(merged_df)} 筆最新市場數據。")
        return merged_df
        
    except Exception as e:
        st.error(f"從資料庫讀取或融合數據失敗: {e}")
        return pd.DataFrame()
