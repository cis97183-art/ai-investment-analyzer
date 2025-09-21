# ai_helper.py

import google.generativeai as genai
import config
import pandas as pd
import streamlit as st # <-- 新增導入 streamlit

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

# ai_helper.py

# ▼▼▼ 用這個新版本完整替換掉舊的 generate_rag_report 函式 ▼▼▼
def generate_rag_report(risk_profile, portfolio_type, portfolio_df, master_df, hhi_value): # <-- [修改] 新增 hhi_value 參數
    """模組五：RAG文字報告生成器 (HHI 增強版)"""
    if llm is None:
        return "AI 模型未成功初始化，無法生成報告。"

    # 1. 檢索 (Retrieve) - 從主資料表提取更詳細的數據 (邏輯不變)
    retrieved_data_str = ""
    for stock_id, row in portfolio_df.iterrows():
        detail = master_df.loc[stock_id]
        retrieved_data_str += f"""
        - **{detail['名稱']} ({stock_id})**:
          - 類型: {detail['AssetType']}
          - 產業: {detail.get('Industry', 'N/A')}
          - 市值: {detail.get('MarketCap_Billions', 'N/A')} 億
          - Beta: {detail.get('Beta_1Y', 'N/A')}
          - 近3年平均ROE: {detail.get('ROE_Avg_3Y', 'N/A')}%
          - 累月營收年增: {detail.get('Revenue_YoY_Accumulated', 'N/A')}%
          - 現金殖利率: {detail.get('Dividend_Yield', 'N/A')}%
        """

    # ▼▼▼ [新增] 產生 HHI 計算過程的字串 ▼▼▼
    hhi_calculation_str = ' + '.join([f"({w:.2%})²" for w in portfolio_df['Weight']])

    # 2. 增強 (Augment) - 建立詳細的提示工程 (Prompt Engineering) 模板
    prompt_template = f"""
    # 角色扮演
    你是一位專業、資深的投資組合分析師。你的任務是根據以下提供的數據，為一位客戶生成一份個人化的投資分析報告。你的語氣應該客觀、嚴謹且富有洞察力，並以繁體中文撰寫。

    # 客戶背景
    - 風險偏好: **{risk_profile}**
    - 選擇的投資組合類型: **{portfolio_type}**

    # 系統生成的投資組合建議
    {portfolio_df[['名稱', 'Weight']].to_markdown()}

    # RAG 系統檢索到的詳細數據 (模擬自本地數據庫)
    {retrieved_data_str}

    # RAG 系統檢索到的即時市場資訊 (模擬自財經API)
    - 市場情緒：近期市場因預期利率政策可能轉向，風險性資產情緒普遍樂觀，但科技股估值偏高，需留意回檔風險。
    - 產業動態：AI與半導體產業鏈仍是市場焦點，相關主題ETF持續吸引資金流入。高股息產品因其防禦性，在市場不確定性高時仍受青睞。

    # 報告生成指令
    請根據以上所有資訊，撰寫一份包含以下部分的完整分析報告：

    1.  **總體策略評述**:
        - 開頭先總結這個投資組合的核心策略，點出它如何符合客戶的 **{risk_profile}** 風險偏好與 **{portfolio_type}** 選擇。
        - 評論整體資產配置的股債比例或核心-衛星思想。

    2.  **核心標的分析**:
        - 從組合中挑選2-3個權重最高的標的進行深入分析。
        - 結合 RAG 檢索到的詳細數據（如ROE、Beta、營收成長）和市場資訊，解釋為什麼這些標的適合被納入此策略中。

    3.  **HHI 指數集中度分析**:  <-- [新增] 要求 AI 撰寫 HHI 分析段落
        - **這必須是一個獨立的段落。**
        - **第一部分：定義與公式**。解釋 HHI 指數 (Herfindahl-Hirschman Index) 是衡量投資組合集中度的重要指標，並展示其計算公式：HHI = Σ (個股權重)²。
        - **第二部分：計算過程**。明確列出本次投資組合的詳細計算過程。格式為：「HHI = {hhi_calculation_str}」。
        - **第三部分：專業解讀**。根據計算出的最終 HHI 指數 **{hhi_value:.4f}**，給出專業解讀。你需要判斷這個數值代表的是「高度分散」、「適度分散」還是「高度集中」，並解釋這對應到客戶的風險偏好是否合適。
          - (參考標準：HHI < 0.15 為高度分散，0.15 <= HHI <= 0.25 為適度分散/集中，HHI > 0.25 為高度集中)

    4.  **潛在風險與建議**:
        - 客觀地指出此投資組合可能面臨的潛在風險（例如：產業集中度、利率敏感性、市場波動風險等）。
        - 提供具體的後續觀察建議。

    5.  **結語**:
        - 用一段話總結這份報告，重申此組合的長期投資價值，並鼓勵客戶保持紀律。

    請以 Markdown 格式輸出報告。
    """

    try:
        response = llm.generate_content(prompt_template)
        return response.text
    except Exception as e:
        return f"生成 AI 報告時發生錯誤: {e}"

def get_chat_response(chat_history, user_query, portfolio_df, master_df):
    """模組六：互動式AI聊天機器人"""
    if llm is None:
        return "AI 模型未成功初始化，無法回應。"
    
    # 建立上下文
    context = f"""
    這是目前的對話紀錄:
    {chat_history}

    這是目前畫面上的投資組合:
    {portfolio_df[['名稱', 'Weight']].to_markdown()}

    這是使用者的最新問題:
    "{user_query}"
    """
    
    prompt = f"""
    # 角色
    你是一位友善且專業的AI投資顧問。

    # 任務
    根據提供的對話紀錄和當前的投資組合資訊，簡潔地回答使用者的問題。

    # 指導原則
    - 如果問題是關於投資組合中的某個標的，請利用投資組合的數據來回答。
    - 如果是一般的金融問題（例如 "什麼是Beta值？"），請提供清晰的解釋。
    - 保持回答簡潔、切題。

    # 上下文
    {context}

    請生成你的回答：
    """
    
    try:
        response = llm.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"生成 AI 回應時發生錯誤: {e}"