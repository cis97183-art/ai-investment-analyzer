# ai_helper.py (升級版)

import streamlit as st
import google.generativeai as genai
from prompts import get_system_prompt

# 【修正點】接收 chat_history 參數
def get_ai_response(portfolios_dict, user_question, chat_history):
    """
    呼叫 Gemini API 來獲取 AI 的回答。
    現在接收一個包含所有 portfolio 的字典，並支援對話歷史。
    """
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
        genai.configure(api_key=api_key)
        
        # 為了實現多輪對話，我們需要從 GenerativeModel 初始化一個 chat session
        model = genai.GenerativeModel('gemini-1.5-flash')
        chat = model.start_chat(history=[]) # 每次都用新的 history 開始，以 prompt 為主

        # 組合包含 portfolio 上下文的提示語
        # 讓 AI 知道它的角色和目前的資料
        system_prompt = get_system_prompt(portfolios_dict, user_question)
        
        response = chat.send_message(system_prompt) # 使用 send_message 而非 generate_content
        return response.text
    except Exception as e:
        error_message = f"呼叫 AI 時發生錯誤：{e} \n\n請確認：\n1. `.streamlit/secrets.toml` 檔案已建立。\n2. `GOOGLE_API_KEY` 已正確設定。"
        st.error(error_message)
        return "抱歉，AI助理目前無法回應。"