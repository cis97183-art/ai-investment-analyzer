import sqlite3
import pandas as pd
from datetime import datetime, timedelta

def simple_sentiment_analysis(headline: str) -> tuple[str, float]:
    """
    [Phase 2] 簡易的情緒分析實作 (關鍵字法)。
    返回 (情緒類別, 分數)。
    """
    positive_keywords = ['創高', '利多', '成長', '優於預期', '上修', '強勁', '大漲', '擴廠', '報喜']
    negative_keywords = ['衰退', '利空', '虧損', '低於預期', '下修', '疲軟', '大跌', '裁員', '警訊']
    
    score = 0
    for p_word in positive_keywords:
        if p_word in headline:
            score += 1
    for n_word in negative_keywords:
        if n_word in headline:
            score -= 1
    
    if score > 0:
        return '正面', 1.0
    elif score < 0:
        return '負面', -1.0
    else:
        return '中性', 0.0

def fetch_mock_news(stock_id: str) -> list[dict]:
    """
    模擬新聞 API 的行為。
    在真實應用中，這裡會是對外部新聞 API (如 Google News) 的 HTTP 請求。
    """
    # 模擬一些可能的新聞標題
    mock_headlines = {
        "2330": [
            f"台積電 CoWoS 產能吃緊，獲利成長優於預期",
            f"外資上修台積電目標價，看好 AI 強勁需求",
            f"地緣政治風險影響，台積電供應鏈面臨挑戰"
        ],
        "2317": [
            f"鴻海電動車業務報喜，Q3 營收有望創高",
            f"蘋果新機銷售疲軟，鴻海面臨訂單下修壓力"
        ],
        "2881": [
            f"富邦金控獲利穩健成長，蟬聯金控獲利王",
            f"央行升息恐衝擊銀行利差，金融股前景轉趨保守"
        ],
        "2603": [
            f"貨櫃航運景氣觸底？長榮海運靜待需求回溫",
            f"運價指數持續破底，長榮營收面臨衰退"
        ]
    }
    
    today = datetime.now()
    if stock_id in mock_headlines:
        return [
            {
                "stock_id": stock_id,
                "news_date": (today - timedelta(days=i)).strftime('%Y-%m-%d'),
                "headline": headline,
                "source": "模擬新聞網"
            }
            for i, headline in enumerate(mock_headlines[stock_id])
        ]
    return []

def update_news_sentiment_for_stocks(stock_ids: list, db_path: str):
    """
    [Phase 2] 針對給定的股票列表，更新新聞與情緒分析結果到資料庫。
    """
    print("\n--- 開始更新新聞情緒數據 ---")
    all_news = []
    for i, stock_id in enumerate(stock_ids):
        # 1. 抓取新聞 (目前為模擬)
        news_items = fetch_mock_news(stock_id)
        
        for item in news_items:
            # 2. 進行情緒分析
            sentiment_category, sentiment_score = simple_sentiment_analysis(item['headline'])
            item['sentiment_category'] = sentiment_category
            item['sentiment_score'] = sentiment_score
            all_news.append(item)
        print(f"  進度: {i+1}/{len(stock_ids)} (找到 {len(news_items)} 則 '{stock_id}' 的新聞)")

    if not all_news:
        print("未發現任何新新聞。")
        return

    # 3. 將結果寫入資料庫
    news_df = pd.DataFrame(all_news)
    with sqlite3.connect(db_path) as conn:
        # 使用 'OR IGNORE' 來處理 UNIQUE 限制，避免因重複新聞而導致整個交易失敗
        news_df.to_sql('news_sentiment', conn, if_exists='append', index=False)
    
    print(f"成功處理 {len(news_df)} 則新聞並更新至資料庫。")
