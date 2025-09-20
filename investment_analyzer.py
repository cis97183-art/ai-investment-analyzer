import streamlit as st
import pandas as pd
import numpy as np
import google.generativeai as genai
from langchain.chains import LLMChain
from langchain_google_genai import ChatGoogleGenerativeAI
import plotly.graph_objects as go
import json
import re
import os
import time

# --- 導入專案模組 ---
from prompts import get_data_driven_prompt_templates
from data_loader import load_all_data_from_csvs
from screener import screen_stocks, screen_etfs

# --- 專案說明 ---
st.set_page_config(page_title="投資總監AI助理", layout="wide")
st.title("📊 投資總監AI助理")
st.markdown(f"本系統根據您提供的數據檔案，結合投資總監定義的嚴謹規則，為您建構專業的客製化投資組合。")

# --- Google API 金鑰設定 ---
try:
    # 為了部署方便，優先從 Streamlit Secrets 讀取
    GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        # 如果找不到，則嘗試從環境變數讀取 (本地開發常用)
        GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    
    if not GOOGLE_API_KEY:
        st.error("請設定您的 GOOGLE_API_KEY 環境變數或在 Streamlit Secrets 中設定。")
        st.stop()
        
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error(f"API 金鑰設定失敗: {e}")
    st.stop()

# --- 初始化 LangChain & Google AI 模型 ---
try:
    llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0.2, google_api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error(f"初始化語言模型失敗: {e}")
    st.stop()

# --- 初始化會話狀態 (Session State) ---
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'portfolio_generated' not in st.session_state:
    st.session_state.portfolio_generated = False
if 'report_data' not in st.session_state:
    st.session_state.report_data = None
if 'stocks_df' not in st.session_state or 'etfs_df' not in st.session_state:
    st.session_state.stocks_df, st.session_state.etfs_df = load_all_data_from_csvs()

# --- 報告生成與顯示函數 ---
def parse_llm_response(response_text):
    """從LLM的回應中解析出JSON內容"""
    # 找到第一個 '{' 和最後一個 '}'
    start_index = response_text.find('{')
    end_index = response_text.rfind('}')
    
    if start_index != -1 and end_index != -1 and start_index < end_index:
        json_string = response_text[start_index:end_index+1]
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            st.error(f"無法解析AI回傳的JSON格式: {e}")
            st.text_area("原始回應內容", response_text, height=200)
            return None
    else:
        st.error("在AI的回應中找不到有效的JSON物件。")
        st.text_area("原始回應內容", response_text, height=200)
        return None

def display_report(report_data, investment_amount, portfolio_type):
    """根據生成的報告數據，在UI上顯示結果"""
    if not report_data or 'summary' not in report_data or 'portfolio' not in report_data:
        st.error("報告資料結構不完整，無法顯示。")
        return

    st.header(f"您的客製化【{portfolio_type}】投資組合")
    st.markdown(f"**風險屬性：{report_data.get('summary', {}).get('risk_profile', 'N/A')} | 總投入資金：${investment_amount:,.0f} TWD**")
    
    st.info(f"**投資組合總覽:** {report_data.get('summary', {}).get('overview', 'N/A')}")

    # 圓餅圖
    labels = [item.get('stock_name', 'N/A') for item in report_data['portfolio']]
    values = [item.get('weight', 0) for item in report_data['portfolio']]
    
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.3, 
                                 textinfo='label+percent', 
                                 hovertemplate='%{label}: %{value:.1f}%<extra></extra>')])
    fig.update_layout(
        title_text='資產配置比例',
        annotations=[dict(text='配置比例', x=0.5, y=0.5, font_size=20, showarrow=False)]
    )
    st.plotly_chart(fig, use_container_width=True)

    # 詳細配置表格
    st.subheader("投資組合詳細配置")
    portfolio_df = pd.DataFrame(report_data['portfolio'])
    portfolio_df['invested_amount'] = (portfolio_df['weight'] / 100) * investment_amount
    
    # 格式化顯示
    portfolio_df_display = portfolio_df.copy()
    portfolio_df_display['weight'] = portfolio_df_display['weight'].map('{:.2f}%'.format)
    portfolio_df_display['invested_amount'] = portfolio_df_display['invested_amount'].map('${:,.0f}'.format)
    
    st.dataframe(portfolio_df_display[['stock_id', 'stock_name', 'asset_type', 'weight', 'invested_amount', 'reasoning']])

# --- UI 輸入區塊 ---
with st.sidebar:
    st.header("Step 1: 設定您的投資參數")
    
    risk_profile_input = st.selectbox(
        '您的風險偏好',
        ('保守型', '穩健型', '積極型'),
        index=1
    )
    
    investment_amount_input = st.number_input(
        '預計投入資金 (TWD)',
        min_value=10000,
        max_value=100000000,
        value=500000,
        step=10000
    )
    
    portfolio_type_input = st.selectbox(
        '選擇投資組合類型',
        ('純個股', '純ETF', '混合型'),
        index=2
    )
    
    st.markdown("---")
    st.header("Step 2: 產生投資建議")
    if st.button("生成報告", type="primary"):
        with st.spinner('正在根據您的設定，進行標的篩選與分析...'):
            # 1. 執行篩選
            st.session_state.candidate_stocks = screen_stocks(
                st.session_state.stocks_df,
                risk_profile_input
            )
            st.session_state.candidate_etfs = screen_etfs(
                st.session_state.etfs_df,
                risk_profile_input
            )
            
            # --- V2.0 新增：顯示篩選結果 ---
            st.subheader("第一階段：量化篩選結果")
            with st.expander("📌 點此查看篩選出的候選個股清單", expanded=False):
                if not st.session_state.candidate_stocks.empty:
                    st.dataframe(st.session_state.candidate_stocks)
                else:
                    st.warning("根據您的篩選條件，找不到合適的個股。")

            with st.expander("📌 點此查看篩選出的候選ETF清單", expanded=False):
                if not st.session_state.candidate_etfs.empty:
                    st.dataframe(st.session_state.candidate_etfs)
                else:
                    st.warning("根據您的篩選條件，找不到合適的ETF。")
            
            st.info("AI 將從以上清單中，根據質化規則挑選最終標的並建立投資組合。")
            time.sleep(2) # 讓使用者有時間看到篩選結果
            # --- 新增結束 ---

            # 2. 準備 Prompt
            prompt_template = get_data_driven_prompt_templates().get(portfolio_type_input)
            if not prompt_template:
                st.error("無效的投資組合類型")
                st.stop()
            
            llm_chain = LLMChain(prompt=prompt_template, llm=llm)

            # 3. 呼叫 LLM
            try:
                response = llm_chain.invoke({
                    "risk_profile": risk_profile_input,
                    "investment_amount": f"{investment_amount_input:,.0f}",
                    "candidate_stocks_csv": st.session_state.candidate_stocks.to_csv(index=False),
                    "candidate_etfs_csv": st.session_state.candidate_etfs.to_csv(index=False)
                })
                
                # 4. 解析與儲存結果
                st.session_state.report_data = parse_llm_response(response['text'])
                st.session_state.portfolio_generated = True
                st.session_state.investment_amount = investment_amount_input
                st.session_state.portfolio_type = portfolio_type_input
                st.rerun()

            except Exception as e:
                st.error(f"生成報告時發生錯誤: {e}")

    st.markdown("---")
    st.markdown("數據來源: 使用者提供之CSV檔案")

# --- 主畫面顯示邏輯 ---
if st.session_state.portfolio_generated and st.session_state.report_data:
    display_report(st.session_state.report_data, st.session_state.investment_amount, st.session_state.portfolio_type)
    
    st.subheader("💬 與AI互動調整")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    if prompt := st.chat_input("對這個投資組合有任何疑問嗎？"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.spinner("AI 正在思考中..."):
            # 建立一個包含原始報告和新問題的上下文
            context = f"""
            這是剛才生成的投資組合報告:
            {json.dumps(st.session_state.report_data, ensure_ascii=False)}

            現在客戶有一個新的問題: {prompt}
            
            請根據報告內容和你的金融知識，用繁體中文回答這個問題。
            """
            response = llm.invoke(context)
            
            with st.chat_message("assistant"):
                st.markdown(response.content)
            st.session_state.messages.append({"role": "assistant", "content": response.content})
