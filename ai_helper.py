# ai_helper.py

import streamlit as st
import google.generativeai as genai
from prompts import get_system_prompt

def get_ai_response(portfolio_df, user_question):
    """
    呼叫 Gemini API 來獲取 AI 的回答。
    """
    try:
        # 從 Streamlit secrets 中讀取 API 金鑰並設定
        api_key = st.secrets["GOOGLE_API_KEY"]
        genai.configure(api_key=api_key)

        # 建立模型
        model = genai.GenerativeModel('gemini-1.5-flash')

        # 組合完整的提示語 (包含上下文和使用者問題)
        prompt = get_system_prompt(portfolio_df, user_question)

        # 呼叫 API 並返回結果
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        error_message = f"呼叫 AI 時發生錯誤：{e}\n\n請確認：\n1. `.streamlit/secrets.toml` 檔案已建立且位置正確。\n2. `GOOGLE_API_KEY` 已正確設定。"
        st.error(error_message)
        return None