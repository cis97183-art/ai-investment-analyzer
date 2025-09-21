# ai_helper.py (最終版 - 已整合 prompt)

import streamlit as st
import google.generativeai as genai

def get_system_prompt(portfolios_dict, user_question):
    """
    動態產生一個精簡、高效的提示語 (Prompt) 給 AI 模型。
    """
    context_str = "目前尚未生成任何投資組合。"
    if portfolios_dict:
        context_str = ""
        for strategy_name, df in portfolios_dict.items():
            if df is not None and not df.empty:
                context_str += f"--- 投資組合策略: {strategy_name} ---\n"
                # 只選擇最重要的欄位給 AI，減少 token 消耗
                display_cols = ['代碼', '名稱', '產業別', '權重(%)', '資產類別']
                existing_display_cols = [col for col in display_cols if col in df.columns]
                context_str += df[existing_display_cols].to_string(index=False)
                context_str += "\n\n"

    # 這是一個 Prompt Engineering 的範例，告訴 AI 它的角色、能力、規則和當前資料。
    prompt = f"""
    你是一位專業、友善且客觀的AI投資組合分析助理。

    # 你的能力
    1.  **報告分析模式**：當使用者問題與下方提供的「當前投資組合數據」相關時，你的任務是根據這些數據進行分析和回答。例如「分析一下這個組合的產業分佈」、「這個組合的集中度如何？」。
    2.  **投資知識庫模式**：當使用者問題是關於一般性的投資觀念時（例如「什麼是本益比？」、「解釋一下什麼是 HHI」），請從你的知識庫中提供準確、客觀的定義與解釋。

    # 規則與限制
    -   **絕不**提供任何未來的預測或直接的買賣建議 (例如 "我覺得 XX 會漲")。所有回答都應保持中立客觀。
    -   在「報告分析模式」下，回答必須嚴格基於下方提供的數據。
    -   請用繁體中文回答。

    ---
    **當前投資組合數據:**
    {context_str}
    ---

    **使用者問題:**
    {user_question}

    **你的回答:**
    """
    return prompt

def get_ai_response(portfolios_dict, user_question, chat_history):
    """
    呼叫 Gemini API 來獲取 AI 的回答，並支援多輪對話。
    """
    try:
        # 從 Streamlit secrets 讀取 API Key
        api_key = st.secrets["GOOGLE_API_KEY"]
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 將過去的對話歷史傳給模型，讓 AI 有上下文記憶
        chat = model.start_chat(history=chat_history)
        
        # 產生包含當前 portfolio 資訊的完整 prompt
        full_prompt = get_system_prompt(portfolios_dict, user_question)
        
        response = chat.send_message(full_prompt)
        return response.text
    except Exception as e:
        error_message = f"呼叫 AI 時發生錯誤：{e} \n\n請確認：\n1. `.streamlit/secrets.toml` 檔案已建立。\n2. `GOOGLE_API_KEY` 已正確設定。"
        st.error(error_message)
        return "抱歉，AI助理目前無法回應。"
