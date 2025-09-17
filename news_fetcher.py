import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import random

# --- 模擬新聞數據庫 ---
# 在真實世界中，這會由一個真正的新聞 API 取代
SIMULATED_NEWS_DATABASE = {
    "2330": [
        {"date": "2025-09-16", "headline": "台積電宣布3奈米製程取得重大突破，產能將翻倍", "source": "經濟日報"},
        {"date": "2025-09-15", "headline": "外資持續看好！高盛上調台積電目標價至900元", "source": "路透社"},
        {"date": "2025-09-12", "headline": "分析師警告：半導體產業面臨庫存調整壓力", "source": "彭博社"}
    ],
    "2317": [
        {"date": "2025-09-16", "headline": "鴻海電動車Model C正式量產，預計第四季開始交車", "source": "工商時報"},
        {"date": "2025-09-14", "headline": "鴻海集團布局東南亞，宣布在印尼設立新廠", "source": "中央社"}
    ],
    "2881": [
        {"date": "2025-09-15", "headline": "富邦金控前三季獲利創新高，EPS達8.5元", "source": "財訊快報"},
        {"date": "2025-09-13", "headline": "央行利率決策在即，金融股走勢相對穩健", "source": "鉅亨網"}
    ],
    "2603": [
        {"date": "2025-09-16", "headline": "長榮海運增開歐洲線，運價指數反彈", "source": "航運界"},
        {"date": "2025-09-11", "headline": "全球貨櫃需求放緩，BDI指數連三天下滑", "source": "國際船舶網"}
    ]
}

def get_simulated_news(stock_id: str) -> list:
    """
    模擬從 API 獲取指定股票的新聞。
    """
    # 為了演示，我們回傳資料庫中儲存的新聞，或者一個空列表
    return SIMULATED_NEWS_DATABASE.get(stock_id, [])


def analyze_sentiment(headline: str) -> tuple:
    """
    模擬對新聞標題進行情緒分析。
    """
    # 這是一個非常簡化的模型，真實世界中會使用 NLP 模型
    positive_keywords = ["突破", "上調", "創新高", "量產", "新廠", "反彈", "看好"]
    negative_keywords = ["警告", "壓力", "放緩", "下滑", "不穩"]
    
    score = 0.5 # 中性
    category = "Neutral"

    if any(keyword in headline for keyword in positive_keywords):
        score = random.uniform(0.7, 0.9)
        category = "Positive"
    elif any(keyword in headline for keyword in negative_keywords):
        score = random.uniform(0.1, 0.4)
        category = "Negative"
        
    return round(score, 2), category


def update_news_sentiment_for_stocks(stock_ids: list, db_path: str):
    """
    [防重複更新版] 更新指定股票列表的新聞與情緒分數到資料庫。
    """
    print("\n--- 開始更新新聞情緒數據 ---")
    all_news = []

    for i, stock_id in enumerate(stock_ids):
        news_items = get_simulated_news(stock_id)
        print(f"  進度: {i+1}/{len(stock_ids)} (找到 {len(news_items)} 則 '{stock_id}' 的新聞)")

        for item in news_items:
            sentiment_score, sentiment_category = analyze_sentiment(item['headline'])
            all_news.append({
                "stock_id": stock_id,
                "news_date": item['date'],
                "headline": item['headline'],
                "source": item['source'],
                "sentiment_score": sentiment_score,
                "sentiment_category": sentiment_category
            })
    
    if not all_news:
        print("未找到任何新新聞可供更新。")
        return

    news_df = pd.DataFrame(all_news)

    with sqlite3.connect(db_path) as conn:
        # --- 解決方案核心 ---
        # 1. 讀取資料庫中已有的新聞標題
        try:
            existing_headlines = pd.read_sql("SELECT stock_id, headline FROM news_sentiment", conn)
            existing_headlines_set = set(zip(existing_headlines['stock_id'], existing_headlines['headline']))
        except (pd.io.sql.DatabaseError, sqlite3.OperationalError):
            existing_headlines_set = set() # 如果表格不存在，就當作是空的

        # 2. 過濾掉重複的新聞
        # 建立一個 (stock_id, headline) 的元組欄位用於比對
        news_df['unique_key'] = list(zip(news_df['stock_id'], news_df['headline']))
        # 只保留 unique_key 不在現有集合中的新聞
        new_records_df = news_df[~news_df['unique_key'].isin(existing_headlines_set)]
        new_records_df = new_records_df.drop(columns=['unique_key']) # 移除輔助欄位

        # 3. 只將真正新的新聞寫入資料庫
        if not new_records_df.empty:
            new_records_df.to_sql('news_sentiment', conn, if_exists='append', index=False)
            print(f"成功將 {len(new_records_df)} 則新新聞寫入資料庫。")
        else:
            print("資料庫中已包含所有找到的新聞，無需更新。")

