# ai_helper.py (最終完整版)

import google.generativeai as genai
import config
import pandas as pd
import streamlit as st
import requests 
from datetime import datetime

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

# --- Real-time News Function ---
def get_realtime_market_news(portfolio_df):
    """
    使用 MarketAux API 獲取投資組合中相關標的的即時新聞。
    """
    try:
        # 從 Streamlit Secrets 或本地 config 讀取新聞 API 金鑰
        if 'MARKETAUX_API_TOKEN' in st.secrets:
            news_api_token = st.secrets['MARKETAUX_API_TOKEN']
        else:
            # 你也可以在 config.py 中新增 MARKETAUX_API_TOKEN = "YOUR_TOKEN"
            news_api_token = config.MARKETAUX_API_TOKEN 
        
        # 從投資組合中提取股票代碼 (只處理台股)
        symbols = [f"{sid}.TW" for sid in portfolio_df.index if portfolio_df.loc[sid, 'AssetType'] == '個股']
        
        if not symbols:
            return "本次投資組合未包含個股，無特定標的即時新聞。"

        # 建立 API 請求 URL
        url = (
            f"https://api.marketaux.com/v1/news/all"
            f"?symbols={','.join(symbols)}"
            f"&filter_entities=true&language=zh&api_token={news_api_token}"
        )
        
        response = requests.get(url, timeout=10) # 設定10秒超時
        response.raise_for_status() # 如果請求失敗 (如 401, 404), 會拋出異常

        data = response.json()
        news_items = data.get('data', [])

        if not news_items:
            return "未找到與您投資組合相關的即時新聞。"

        # 格式化新聞輸出，只取前三條
        formatted_news = "\n".join(
            [f"- **{item['title']}**: {item['snippet']}" for item in news_items[:3]]
        )
        return f"以下是與您投資組合相關的最新市場動態：\n{formatted_news}"

    except Exception as e:
        print(f"獲取即時新聞失敗: {e}")
        # 如果 API 失敗，返回一個通用的市場評論，確保報告能繼續生成
        return "即時新聞API暫時無法連線。根據市場普遍看法，近期市場關注焦點仍在通膨數據與主要央行的利率政策走向。"

# --- RAG Report Generator ---
def generate_rag_report(risk_profile, portfolio_type, portfolio_df, master_df, hhi_value):
    """模組五：RAG文字報告生成器 (整合即時新聞API)"""
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
    
    # (B) 從外部 API 檢索即時新聞
    realtime_news_str = get_realtime_market_news(portfolio_df)
    
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

    # RAG 系統檢索到的即時市場資訊 (來自新聞 API)
    {realtime_news_str}

    # 報告生成指令
    請根據以上所有資訊，為客戶撰寫一份包含以下部分的完整、客觀的投資分析報告：

    1.  **總體策略評述**: 總結此組合如何符合客戶的風險偏好。
    2.  **核心標的分析**: 挑選2-3個權重最高的標的進行深入分析，需結合本地數據與即時新聞。
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