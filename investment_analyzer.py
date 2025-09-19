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

# --- 初始化 Session State ---
if 'portfolio_generated' not in st.session_state:
    st.session_state.portfolio_generated = False
if 'report_data' not in st.session_state:
    st.session_state.report_data = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'stocks_df' not in st.session_state or 'etfs_df' not in st.session_state:
    # 載入數據並存儲在 session state 中
    st.session_state.stocks_df, st.session_state.etfs_df = load_all_data_from_csvs()

# --- 全局數據載入 ---
stocks_df = st.session_state.stocks_df
etfs_df = st.session_state.etfs_df

# --- LLM 初始化 ---
@st.cache_resource
def get_llm():
    return ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.5)

llm = get_llm()
prompt_templates = get_data_driven_prompt_templates()

# --- 核心功能函數 ---
def clean_json_string(s):
    """清理LLM回傳的，可能包含非標準JSON字元的字串"""
    s = re.sub(r'```json\s*', '', s)
    s = re.sub(r'```', '', s)
    s = s.strip()
    return s

def generate_portfolio(portfolio_type, risk_profile, investment_amount):
    """根據使用者輸入，執行篩選並調用LLM生成投資組合"""
    with st.spinner('AI 正在為您建構投資組合，請稍候...'):
        start_time = time.time()
        
        candidate_stocks_df = pd.DataFrame()
        candidate_etfs_df = pd.DataFrame()
        prompt_template = prompt_templates.get(portfolio_type)
        
        if not prompt_template:
            st.error("選擇的投資組合類型無效。")
            return None

        # --- 根據組合類型，執行不同的篩選邏輯 ---
        if portfolio_type in ["純個股投資組合", "混合型投資組合"]:
            candidate_stocks_df = screen_stocks(stocks_df, risk_profile)
            if candidate_stocks_df.empty:
                st.warning(f"在目前的市場數據中，找不到符合「{risk_profile}」個股篩選條件的標的。請嘗試調整條件或更新數據。")
                if portfolio_type == "純個股投資組合": return None
        
        if portfolio_type in ["純ETF投資組合", "混合型投資組合"]:
            candidate_etfs_df = screen_etfs(etfs_df, risk_profile)
            if candidate_etfs_df.empty:
                st.warning(f"在目前的市場數據中，找不到符合「{risk_profile}」ETF篩選條件的標的。請嘗試調整條件或更新數據。")
                if portfolio_type == "純ETF投資組合": return None

        # --- 準備 Prompt 的輸入 ---
        input_data = {
            "risk_profile": risk_profile,
            "investment_amount": f"{investment_amount:,.0f}"
        }
        if not candidate_stocks_df.empty:
            input_data["candidate_stocks_csv"] = candidate_stocks_df.to_csv(index=False)
        if not candidate_etfs_df.empty:
            input_data["candidate_etfs_csv"] = candidate_etfs_df.to_csv(index=False)

        # --- 調用 LLM ---
        try:
            chain = LLMChain(llm=llm, prompt=prompt_template)
            raw_response = chain.run(input_data)
            
            # --- 解析回應 ---
            cleaned_response = clean_json_string(raw_response)
            report_json = json.loads(cleaned_response)
            
            end_time = time.time()
            st.success(f"投資組合建構完成！耗時 {end_time - start_time:.2f} 秒。")
            return report_json

        except json.JSONDecodeError:
            st.error("AI回傳的格式有誤，無法解析。請稍後重試。")
            st.text_area("AI原始回傳內容", raw_response, height=200)
            return None
        except Exception as e:
            st.error(f"生成報告時發生錯誤: {e}")
            return None

def display_report(report_data, investment_amount, portfolio_type):
    """將生成的報告數據以美觀的格式顯示在Streamlit介面上"""
    try:
        summary = report_data.get('summary', {})
        composition = report_data.get('portfolio_composition', {})
        holdings = composition.get('holdings', [])

        st.header(summary.get('title', "您的客製化投資組合"))
        st.markdown(f"**投資組合類型：** `{portfolio_type}`")
        st.info(f"**策略總覽：** {summary.get('overview', 'N/A')}")

        if not holdings:
            st.warning("AI未能根據篩選結果提出具體持股建議。")
            return

        holdings_df = pd.DataFrame(holdings)
        holdings_df['allocated_value'] = holdings_df['weight'] * investment_amount
        holdings_df['weight_pct'] = (holdings_df['weight'] * 100).map('{:,.2f}%'.format)

        col1, col2 = st.columns([0.4, 0.6])
        with col1:
            st.subheader("資產配置圓餅圖")
            fig = go.Figure(data=[go.Pie(
                labels=holdings_df['stock_name'], 
                values=holdings_df['weight'], 
                hole=.3,
                textinfo='label+percent',
                insidetextorientation='radial'
            )])
            fig.update_layout(showlegend=False, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("投資組合明細")
            display_df = holdings_df[['stock_id', 'stock_name', 'industry', 'weight_pct', 'allocated_value']]
            display_df.columns = ['標的代號', '標的名稱', '類型/產業', '配置權重', '投入金額(TWD)']
            st.dataframe(display_df.style.format({'投入金額(TWD)': '{:,.0f}'}), use_container_width=True)

        st.subheader("標的選擇理由")
        for _, row in holdings_df.iterrows():
            with st.expander(f"**{row['stock_name']} ({row['stock_id']})** - 權重: {row['weight_pct']}"):
                st.markdown(row['reason'])

    except Exception as e:
        st.error(f"顯示報告時發生錯誤: {e}")
        st.json(report_data)

# --- 使用者介面 ---
with st.sidebar:
    st.header("投資組合參數設定")
    
    portfolio_type_input = st.selectbox(
        "1. 選擇投資組合類型",
        ("純個股投資組合", "純ETF投資組合", "混合型投資組合"),
        key="portfolio_type_selector"
    )

    risk_profile_input = st.selectbox(
        "2. 選擇您的風險偏好",
        ("保守型", "穩健型", "積極型"),
        key="risk_profile_selector"
    )

    investment_amount_input = st.number_input(
        "3. 請輸入預計投資金額 (新台幣)",
        min_value=100000,
        max_value=100000000,
        value=1000000,
        step=100000,
        format="%d",
        key="investment_amount_input"
    )
    
    if st.button("🚀 開始建構投資組合", key="generate_button", use_container_width=True):
        if stocks_df.empty or etfs_df.empty:
            st.error("數據載入失敗，無法生成報告。請檢查數據文件。")
        else:
            st.session_state.messages = [] # 清空歷史對話
            report = generate_portfolio(portfolio_type_input, risk_profile_input, investment_amount_input)
            if report:
                st.session_state.report_data = report
                st.session_state.portfolio_generated = True
                st.session_state.investment_amount = investment_amount_input
                st.session_state.portfolio_type = portfolio_type_input
                st.rerun()

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
else:
    st.info("請在左側側邊欄設定您的投資偏好，然後點擊「開始建構投資組合」。")
