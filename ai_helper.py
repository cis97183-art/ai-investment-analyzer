# ai_helper.py (升級版)

import streamlit as st
import google.generativeai as genai
from prompts import get_system_prompt

def get_ai_response(portfolios_dict, user_question):
    """
    呼叫 Gemini API 來獲取 AI 的回答。
    現在接收一個包含所有 portfolio 的字典。
    """
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 組合包含所有 portfolio 上下文的提示語
        prompt = get_system_prompt(portfolios_dict, user_question)
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        error_message = f"呼叫 AI 時發生錯誤：{e} \n\n請確認：\n1. `.streamlit/secrets.toml` 檔案已建立。\n2. `GOOGLE_API_KEY` 已正確設定。"
        st.error(error_message)
        return None