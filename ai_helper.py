# ai_helper.py (TEJ API 最終整合版)

import google.generativeai as genai
import config
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import tejapi # 導入 tejapi
import yfinance as yf # 導入 yfinance

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

# ▼▼▼ [重大修改] 增強 get_yfinance_news_summary 函式的穩定性 ▼▼▼
def get_yfinance_news_summary(portfolio_df, master_df):
    """
    完全使用 yfinance 獲取新聞摘要。
    增加了對新聞項目格式的檢查，使其更穩定。
    """
    INDUSTRY_ETF_MAP = {
        "半導體業": "00891.TW",
        "金融保險業": "0055.TW",
        "電腦及週邊設備業": "00899.TW",
        "通信網路業": "00881.TW",
        "航運業": "0056.TW"
    }
    NEWS_THRESHOLD = 2
    all_news_extracts = []
    
    stock_tickers = {sid: master_df.loc[sid, '名稱'] 
                     for sid in portfolio_df.index 
                     if portfolio_df.loc[sid, 'AssetType'] == '個股'}

    if not stock_tickers:
        return "本次投資組合未包含個股，無特定標的近期資訊。"

    for ticker_id, stock_name in stock_tickers.items():
        news_found_for_stock = False
        try:
            # --- 優先策略: yfinance 抓取個股新聞 ---
            print(f"Fetching yfinance news for {ticker_id}.TW ({stock_name})...")
            ticker_obj = yf.Ticker(f"{ticker_id}.TW")
            news = ticker_obj.news
            
            # [修改] 先過濾出確定有 'title' 欄位的新聞
            news_with_titles = [item for item in news if 'title' in item]
            
            if len(news_with_titles) >= NEWS_THRESHOLD:
                print(f"  -> Found {len(news_with_titles)} valid articles. Using stock-specific news.")
                # 使用過濾後的 news_with_titles 來格式化
                formatted_news = [f"- (個股新聞) **{stock_name}**: {item['title']}" for item in news_with_titles[:2]]
                all_news_extracts.extend(formatted_news)
                news_found_for_stock = True

            # --- 備用策略: 降級為抓取產業ETF新聞 ---
            if not news_found_for_stock:
                print(f"  -> Found only {len(news_with_titles)} valid articles. Falling back to industry ETF news.")
                industry = master_df.loc[ticker_id, 'Industry']
                
                if pd.notna(industry) and industry in INDUSTRY_ETF_MAP:
                    etf_ticker = INDUSTRY_ETF_MAP[industry]
                    print(f"  -> Industry '{industry}' maps to ETF {etf_ticker}. Fetching news...")
                    etf_obj = yf.Ticker(etf_ticker)
                    etf_news = etf_obj.news
                    
                    # [修改] 同樣先過濾出確定有 'title' 欄位的新聞
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

    if not all_news_extracts:
        return "未能獲取與您投資組合相關的近期市場新聞。"
    
    final_news_string = "\n".join(sorted(list(set(all_news_extracts))))
    return f"以下是與您投資組合相關的最新市場動態摘要：\n{final_news_string}"
# ▲▲▲ 函式修改結束 ▲▲▲

# --- RAG Report Generator (同步修改) ---
def generate_rag_report(risk_profile, portfolio_type, portfolio_df, master_df, hhi_value):
    if llm is None: return "AI 模型未成功初始化，無法生成報告。"
    
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
    
    # [修改] 從 yfinance 智慧策略中檢索新聞
    realtime_info_str = get_yfinance_news_summary(portfolio_df, master_df)
    
    current_date = datetime.now().strftime("%Y年%m月%d日")
    hhi_calculation_str = ' + '.join([f"({w:.2%})²" for w in portfolio_df['Weight']])

    prompt_template = f"""
    # 角色扮演...
    # 客戶背景與報告資訊...
    # 系統生成的投資組合建議...
    # RAG 系統檢索到的詳細數據 (來自本地數據庫)
    {retrieved_data_str}
    # RAG 系統檢索到的即時資訊 (來自 yfinance)
    {realtime_info_str}

    # 報告生成指令
    請根據以上所有資訊，為客戶撰寫一份包含以下部分的完整、客觀的投資分析報告：

    1.  **總體策略評述**: 總結此組合如何符合客戶的風險偏好。
    2.  **核心標的分析**: 挑選2-3個權重最高的標的進行深入分析，需結合本地數據與TEJ的近期資訊。
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