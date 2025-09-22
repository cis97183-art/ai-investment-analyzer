# ai_helper.py (最終韌性增強版)

import google.generativeai as genai
import config
import pandas as pd
import streamlit as st
from datetime import datetime
import yfinance as yf

# --- AI 模型初始化 ---
try:
    # 優先從 Streamlit 的 Secrets 讀取 API 金鑰 (用於雲端部署)
    if 'GEMINI_API_KEY' in st.secrets:
        api_key = st.secrets['GEMINI_API_KEY']
        print("Gemini API Key loaded from Streamlit Secrets.")
    # 如果 Secrets 中沒有，則從本地的 config.py 讀取 (用於本機開發)
    else:
        api_key = config.GEMINI_API_KEY
        print("Gemini API Key loaded from local config.py.")
    
    genai.configure(api_key=api_key)
    llm = genai.GenerativeModel('gemini-1.5-flash')
    print("Gemini AI 模型初始化成功。")

except Exception as e:
    print(f"AI 模型初始化失敗: {e}")
    # 在 Streamlit 介面上顯示錯誤，方便除錯
    st.error(f"AI 模型初始化失敗，請檢查 API 金鑰是否已正確設定在 Streamlit Secrets 中。錯誤訊息: {e}")
    llm = None

# --- yfinance News Summary Function ---
def get_yfinance_news_summary(portfolio_df, master_df):
    """
    完全使用 yfinance 獲取新聞摘要，並具備兩層備用方案：
    1. 個股 -> 產業ETF
    2. 如果最終無新聞 -> 整體市場ETF (0050)
    """
    # [擴充版] 產業名稱到代表性ETF的對照表
    INDUSTRY_ETF_MAP = {
        "半導體業": "00891.TW",          # 中信關鍵半導體
        "金融保險業": "0055.TW",          # 元大MSCI金融
        "電腦及週邊設備業": "00929.TW",  # 復華台灣科技優息
        "通信網路業": "00881.TW",          # 國泰台灣5G+
        "航運業": "2603.TW",               # 以長榮作為航運業新聞代理
        "生技醫療業": "00692.TW",          # 富邦臺灣生技
        "其他電子業": "00929.TW",          # 範疇較廣，同樣用科技ETF代替
        "文化創意業": "0050.TW"             # 無直接對應ETF，使用大盤作為代理
    }
    NEWS_THRESHOLD = 2 # 設定新聞數量的門檻值 (少於2條則觸發降級)
    all_news_extracts = []
    
    stock_tickers = {sid: master_df.loc[sid, '名稱'] 
                     for sid in portfolio_df.index 
                     if portfolio_df.loc[sid, 'AssetType'] == '個股'}

    if not stock_tickers:
        return "本次投資組合未包含個股，無特定標的近期資訊。"

    for ticker_id, stock_name in stock_tickers.items():
        news_found_for_stock = False
        try:
            # 優先策略: yfinance 抓取個股新聞
            print(f"Fetching yfinance news for {ticker_id}.TW ({stock_name})...")
            ticker_obj = yf.Ticker(f"{ticker_id}.TW")
            news = ticker_obj.news
            news_with_titles = [item for item in news if 'title' in item]
            
            if len(news_with_titles) >= NEWS_THRESHOLD:
                print(f"  -> Found {len(news_with_titles)} valid articles. Using stock-specific news.")
                formatted_news = [f"- (個股新聞) **{stock_name}**: {item['title']}" for item in news_with_titles[:2]]
                all_news_extracts.extend(formatted_news)
                news_found_for_stock = True

            # 備用策略: 降級為抓取產業ETF新聞
            if not news_found_for_stock:
                print(f"  -> Found only {len(news_with_titles)} valid articles. Falling back to industry ETF news.")
                industry = master_df.loc[ticker_id, 'Industry']
                
                if pd.notna(industry) and industry in INDUSTRY_ETF_MAP:
                    etf_ticker = INDUSTRY_ETF_MAP[industry]
                    print(f"  -> Industry '{industry}' maps to ETF {etf_ticker}. Fetching news...")
                    etf_obj = yf.Ticker(etf_ticker)
                    etf_news = etf_obj.news
                    etf_news_with_titles = [item for item in etf_news if 'title' in item]

                    if etf_news_with_titles:
                        formatted_news = [f"- (產業新聞) **{industry}**: {item['title']}" for item in etf_news_with_titles[:2]]
                        all_news_extracts.extend(formatted_news)
                else:
                    print(f"  -> No representative ETF found for industry: '{industry}'.")
                    if news_with_titles:
                        formatted_news = [f"- (個股新聞) **{stock_name}**: {item['title']}" for item in news_with_titles[:1]]
                        all_news_extracts.extend(formatted_news)

        except Exception as e:
            print(f"Error fetching yfinance news for {ticker_id}: {e}")
            continue

    # 最終備用方案：如果遍歷完所有股票後仍然沒有任何新聞，就抓取大盤新聞
    if not all_news_extracts:
        print("  -> No specific news found. Falling back to broad market news (0050.TW)...")
        try:
            market_obj = yf.Ticker("0050.TW")
            market_news = market_obj.news
            market_news_with_titles = [item for item in market_news if 'title' in item]
            if market_news_with_titles:
                formatted_news = [f"- (整體市場新聞) **台灣50**: {item['title']}" for item in market_news_with_titles[:3]]
                all_news_extracts.extend(formatted_news)
        except Exception as e:
            print(f"Error fetching broad market news: {e}")

    if not all_news_extracts:
        return "未能獲取與您投資組合相關的近期市場新聞。"
    
    final_news_string = "\n".join(sorted(list(set(all_news_extracts))))
    return f"以下是與您投資組合相關的最新市場動態摘要：\n{final_news_string}"

# --- RAG Report Generator ---
def generate_rag_report(risk_profile, portfolio_type, portfolio_df, master_df, hhi_value):
    """模組五：RAG文字報告生成器 (整合 yfinance 智慧策略)"""
    if llm is None:
        return "AI 模型未成功初始化，無法生成報告。"

    # 1. 檢索 (Retrieve)
    # (A) 從本地數據庫檢索詳細數據
    retrieved_data_str = ""
    for stock_id, row in portfolio_df.iterrows():
        detail = master_df.loc[stock_id]
        retrieved_data_str += f"""
        - **{detail['名稱']} ({stock_id})**:
          - 類型: {detail['AssetType']}
          - 產業: {detail.get('Industry', 'N/A')}
          - 市值: {detail.get('MarketCap_Billions', 'N/A')} 億
          - Beta: {detail.get('Beta_1Y', 'N/A')}
        """
    
    # (B) 從 yfinance 智慧策略中檢索新聞
    realtime_info_str = get_yfinance_news_summary(portfolio_df, master_df)
    
    # 2. 增強 (Augment)
    current_date = datetime.now().strftime("%Y年%m月%d日")
    hhi_calculation_str = ' + '.join([f"({w:.2%})²" for w in portfolio_df['Weight']])

    prompt_template = f"""
    # 角色扮演
    你是一位專業、資深的投資組合分析師。

    # 客戶背景與報告資訊
    - **客戶類型**: {risk_profile} 投資人
    - **報告日期**: {current_date}

    # 系統生成的投資組合建議
    {portfolio_df[['名稱', 'Weight']].to_markdown()}

    # RAG 系統檢索到的詳細數據 (來自本地數據庫)
    {retrieved_data_str}

    # RAG 系統檢索到的即時資訊 (來自 yfinance)
    {realtime_info_str}

    # 報告生成指令
    請根據以上所有資訊，為客戶撰寫一份包含以下部分的完整、客觀的投資分析報告：

    1.  **總體策略評述**: 總結此組合如何符合客戶的風險偏好。
    2.  **核心標的分析**: 挑選2-3個權重最高的標的進行深入分析，需結合本地數據與yfinance的近期資訊。
    3.  **HHI 指數集中度分析**: 
        - **必須是獨立段落。**
        - 解釋 HHI 是衡量投資組合集中度的指標，並展示公式：HHI = Σ (個股權重)²。
        - 列出計算過程：「HHI = {hhi_calculation_str}」。
        - 根據最終 HHI 指數 **{hhi_value:.4f}**，給出專業解讀 (高度分散/適度分散/高度集中)。
    4.  **潛在風險與建議**: 客觀指出此組合的潛在風險並提供後續觀察建議。
    5.  **結語**: 總結報告。

    請以 Markdown 格式輸出報告。
    """

    try:
        response = llm.generate_content(prompt_template)
        return response.text
    except Exception as e:
        return f"生成 AI 報告時發生錯誤: {e}"

# --- Chatbot Responder ---
def get_chat_response(chat_history, user_query, portfolio_df, master_df):
    """模組六：互動式AI聊天機器人"""
    if llm is None:
        return "AI 模型未成功初始化，無法回應。"
    
    context = f"""
    This is the current chat history:
    {chat_history}

    This is the current portfolio on screen:
    {portfolio_df[['名稱', 'Weight']].to_markdown()}

    This is the user's latest question:
    "{user_query}"
    """
    
    prompt = f"""
    # Role
    You are a friendly and professional AI investment advisor.

    # Task
    Based on the provided chat history and the current portfolio information, concisely answer the user's question in Traditional Chinese.

    # Guiding Principles
    - If the question is about a specific security in the portfolio, use the portfolio data to answer.
    - If it's a general financial question (e.g., "What is Beta?"), provide a clear explanation.
    - Keep the answer concise and to the point.

    # Context
    {context}

    Please generate your response:
    """
    
    try:
        response = llm.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"生成 AI 回應時發生錯誤: {e}"