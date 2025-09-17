import streamlit as st
import pandas as pd
import google.generativeai as genai
from langchain.chains import LLMChain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
import plotly.graph_objects as go
import plotly.express as px # 引入 Express 以使用更豐富的顏色主題
import json
from datetime import datetime
import re
import os
import time

# --- 導入專案模組 ---
from update_database import main as run_db_update
from etf_rules import ETF_PROMPT_FRAMEWORK
from prompts import get_data_driven_prompt_templates, STOCK_PROMPT_FRAMEWORK
from data_loader import load_and_merge_data
from screener import screen_stocks

# --- 專案說明 ---
st.set_page_config(page_title="台股分析引擎 (yfinance 穩定版)", layout="wide")
st.title("📊 高效台股分析引擎 (yfinance 穩定版)")
st.markdown("本系統採用 **yfinance** 作為核心數據源，結合本地數據庫進行高效分析。數據可手動更新，提供您閃電般的篩選速度與穩定可靠的數據品質。")

# --- Google API 金鑰設定 ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except (KeyError, Exception) as e:
    st.error("錯誤：請確認你的 Google API 金鑰已在 Streamlit Secrets 中正確設定。")
    st.info("若在本機端開發，請建立 `.streamlit/secrets.toml` 檔案並設定金鑰。")
    st.stop()

# --- 資料庫檢查與數據載入 ---
DB_PATH = "tw_stock_data.db"
if not os.path.exists(DB_PATH):
    st.warning(f"警告：找不到本地資料庫檔案 '{DB_PATH}'。")
    st.info("請點擊下方按鈕來下載最新的市場數據並建立本地資料庫。")
    if st.button("建立/更新本地市場資料庫", type="primary", use_container_width=True):
        with st.spinner("正在執行數據庫更新程序，請稍候..."):
            run_db_update()
        st.success("資料庫建立成功！應用程式將在 3 秒後自動重新載入。")
        time.sleep(3)
        st.rerun()
    st.stop()
    
market_data = load_and_merge_data()

# --- RAG 核心邏輯 ---
def get_llm_chain(prompt_template):
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.2, model_kwargs={"response_format": {"type": "json_object"}})
    prompt = PromptTemplate.from_template(prompt_template)
    return LLMChain(llm=model, prompt=prompt)

def _clean_and_parse_json(raw_text: str):
    match = re.search(r"```(json)?\s*({.*?})\s*```", raw_text, re.DOTALL)
    clean_text = match.group(2) if match else raw_text[raw_text.find('{'):raw_text.rfind('}')+1]
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError as e:
        st.error("JSON 解析失敗。")
        st.code(raw_text, language="text")
        raise e

# --- 報告生成 ---
def generate_portfolio(portfolio_type, risk_profile, investment_amount):
    if portfolio_type in ["純個股", "混合型"]:
        with st.spinner("步驟 1/2: 正在從本地資料庫進行量化篩選..."):
            if market_data.empty:
                st.error("市場數據為空，無法進行篩選。")
                return None
            candidate_df = screen_stocks(market_data, risk_profile)
            if candidate_df.empty:
                st.warning(f"根據您的 '{risk_profile}' 規則，找不到滿足所有條件的股票。")
                return None
            csv_columns = ['stock_id', 'stock_name', 'industry_category', 'pe_ratio', 'pb_ratio', 'yield', 'close_price', 'Positive', 'Negative', 'headline']
            candidate_data_for_llm = candidate_df[csv_columns].to_csv(index=False)

        with st.spinner("步驟 2/2: 已完成量化篩選！正在將候選名單交由 AI 進行最終質化分析..."):
            prompt_templates = get_data_driven_prompt_templates()
            chain = get_llm_chain(prompt_templates[portfolio_type])
            input_data = {
                "stock_rules": STOCK_PROMPT_FRAMEWORK, "etf_rules": ETF_PROMPT_FRAMEWORK,
                "risk_profile": risk_profile, "investment_amount": f"{investment_amount:,.0f}",
                "current_date": datetime.now().strftime("%Y年%m月%d日"),
                "candidate_stocks_csv": candidate_data_for_llm
            }
            response = chain.invoke(input_data)
            return _clean_and_parse_json(response['text'])
    else:
        with st.spinner("正在為您建構純 ETF 投資組合..."):
            prompt_templates = get_data_driven_prompt_templates()
            chain = get_llm_chain(prompt_templates[portfolio_type])
            input_data = {
                "etf_rules": ETF_PROMPT_FRAMEWORK, "risk_profile": risk_profile,
                "investment_amount": f"{investment_amount:,.0f}",
                "current_date": datetime.now().strftime("%Y年%m月%d日")
            }
            response = chain.invoke(input_data)
            return _clean_and_parse_json(response['text'])

# --- [圖表優化最終版] 報告可視化 ---
def display_report(report_data, investment_amount, portfolio_type):
    INDUSTRY_MAP = {
        'Semiconductors': '半導體', 'Computer Hardware': '電腦硬體',
        'Financial Services': '金融服務', 'Conglomerates': '綜合企業',
        'Shipping & Ports': '航運與港口', 'Telecom Services': '電信服務',
        'Electronic Components': '電子零組件', 'Plastics': '塑膠',
        'Cement': '水泥'
    }

    st.header(report_data['summary']['title'])
    st.info(f"報告生成日期：{report_data['summary']['generated_date']}")
    st.subheader("📈 投資組合總覽")
    st.write(report_data['summary']['overview'])
    
    st.subheader("📊 核心風險指標 (AI 估算)")
    metrics = report_data['portfolio_metrics']
    metric_labels = {'beta': "Beta 值", 'annual_volatility': "年化波動率", 'sharpe_ratio': "夏普比率"}
    cols = st.columns(len(metrics))
    for i, (key, value) in enumerate(metrics.items()):
        cols[i].metric(metric_labels.get(key, key), value)

    st.write("---")

    # --- 數據準備與清洗 ---
    if 'core_holdings' in report_data:
        core_df = pd.DataFrame(report_data.get('core_holdings', []))
        sat_df = pd.DataFrame(report_data.get('satellite_holdings', []))
        df = pd.concat([core_df, sat_df], ignore_index=True)
    else:
        df = pd.DataFrame(report_data.get('holdings', []))

    df['weight'] = pd.to_numeric(df['weight'], errors='coerce')
    df.dropna(subset=['weight'], inplace=True) # 確保權重是有效數字
    df = df[df['weight'] > 0].copy()
    if not df.empty:
        df['weight'] = df['weight'] / df['weight'].sum()
    else:
        st.warning("AI 生成的投資組合中沒有有效的持股。")
        return
        
    df.sort_values(by='weight', ascending=False, inplace=True)
    df['資金分配 (TWD)'] = (df['weight'] * investment_amount).round().astype(int)
    df['權重 (%)'] = (df['weight'] * 100).round(2)
    if 'industry' in df.columns:
        df['industry_zh'] = df['industry'].map(INDUSTRY_MAP).fillna(df['industry'])

    # --- 圖表繪製 ---
    st.subheader("視覺化分析")
    chart1, chart2 = st.columns(2)

    with chart1:
        # [解決方案] 優化圓餅圖 (趴樹)
        fig_pie = px.pie(df, values='weight', names='name', hole=.3,
                         title='持股權重分配',
                         color_discrete_sequence=px.colors.qualitative.Plotly) # 使用更多樣的顏色
        fig_pie.update_traces(textposition='inside', textinfo='percent+label',
                              hovertemplate='%{label}<br>權重: %{percent:.2%}')
        fig_pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    with chart2:
        # [解決方案] 重構混合型圖表邏輯
        if portfolio_type == "混合型":
            df['chart_category'] = df.apply(
                lambda row: 'ETF 核心' if 'etf_type' in row and pd.notna(row['etf_type']) else row.get('industry_zh', '其他'),
                axis=1
            )
            # 修正 Bug：確保 industry_zh 在 lambda 函數中被正確使用
            df['chart_category'].fillna('其他', inplace=True)

            grouped = df.groupby('chart_category')['weight'].sum().reset_index()
            chart_title, x_col = '資產類別分佈', 'chart_category'
        elif 'industry_zh' in df.columns:
            grouped = df.groupby('industry_zh')['weight'].sum().reset_index()
            chart_title, x_col = '產業權重分佈 (中文)', 'industry_zh'
        elif 'etf_type' in df.columns:
            grouped = df.groupby('etf_type')['weight'].sum().reset_index()
            chart_title, x_col = 'ETF 類型分佈', 'etf_type'
        else:
            grouped = None

        if grouped is not None:
            fig_bar = go.Figure(data=[go.Bar(
                x=grouped[x_col], y=grouped['weight'],
                text=(grouped['weight']*100).apply(lambda x: f'{x:.1f}%'), textposition='auto'
            )])
            fig_bar.update_layout(title_text=chart_title, xaxis_title=None, yaxis_title="權重",
                                  yaxis_tickformat='.0%', margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_bar, use_container_width=True)

    # --- 詳細表格 ---
    st.write("---")
    st.subheader("📝 詳細持股與資金計畫")
    display_cols = ['ticker', 'name']
    if 'industry_zh' in df.columns and df['industry_zh'].notna().any():
        display_cols.append('industry_zh')
    if 'etf_type' in df.columns and df['etf_type'].notna().any():
        display_cols.append('etf_type')
    display_cols.extend(['權重 (%)', '資金分配 (TWD)', 'rationale'])
    
    df.rename(columns={'industry_zh': '產業類別'}, inplace=True)
    final_cols = [col for col in display_cols if col in df.columns]

    st.dataframe(df[final_cols], use_container_width=True, hide_index=True,
        column_config={
            "權重 (%)": st.column_config.ProgressColumn("權重 (%)", format="%.2f%%", min_value=0, max_value=100),
            "資金分配 (TWD)": st.column_config.NumberColumn("資金分配 (TWD)", format="NT$ %'d"),
            "rationale": st.column_config.TextColumn("簡要理由", width="large")
        })

def handle_follow_up_question(question, context):
    prompt_template = """
    你是一位專業的台灣股市投資組合經理。使用者已經收到你先前建立的投資組合報告，現在他有後續問題。
    請根據你先前提供的報告內容，以及使用者的問題，提供簡潔、專業的回答。
    **先前報告的內容摘要 (JSON):** {context}
    **使用者的問題:** {question}
    請直接回答使用者的問題。
    """
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.5)
    prompt = PromptTemplate.from_template(prompt_template)
    chain = LLMChain(llm=model, prompt=prompt)
    response = chain.invoke({"context": json.dumps(context, ensure_ascii=False), "question": question})
    return response['text']

# --- UI 主流程 ---
if 'portfolio_generated' not in st.session_state: st.session_state.portfolio_generated = False
if 'report_data' not in st.session_state: st.session_state.report_data = None
if 'messages' not in st.session_state: st.session_state.messages = []

with st.sidebar:
    st.header("👤 您的投資設定")
    portfolio_type_input = st.radio("1. 請選擇投資組合類型", ("純個股", "純 ETF", "混合型"), index=0)
    risk_profile_input = st.selectbox("2. 請選擇您的風險偏好", ('積極型', '穩健型', '保守型'), index=0)
    investment_amount_input = st.number_input("3. 請輸入您預計投入的總資金 (新台幣)", min_value=10000, value=500000, step=50000)
    
    col1, col2 = st.columns(2)
    with col1:
        analyze_button = st.button("🚀 生成投資組合", type="primary", use_container_width=True)
    with col2:
        if st.button("🔄 更新市場數據", use_container_width=True):
            with st.spinner("正在執行數據庫更新程序，請稍候..."):
                run_db_update()
            st.success("數據庫更新成功！")
            st.rerun()

    st.info("免責聲明：本系統僅為AI輔助分析工具，所有建議僅供參考，不構成任何投資決策之依據。")

if analyze_button:
    st.session_state.messages = []
    st.session_state.report_data = None
    st.session_state.portfolio_generated = False
    
    if market_data.empty:
        st.stop()

    report = generate_portfolio(portfolio_type_input, risk_profile_input, investment_amount_input)
    if report:
        st.session_state.report_data = report
        st.session_state.portfolio_generated = True

if st.session_state.portfolio_generated and st.session_state.report_data:
    display_report(st.session_state.report_data, investment_amount_input, portfolio_type_input)
    
    st.write("---")
    st.subheader("💬 提問與互動調整")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])
        
    if prompt := st.chat_input("對這個投資組合有任何疑問嗎？"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.spinner("AI 正在思考中..."):
            response = handle_follow_up_question(prompt, st.session_state.report_data)
            st.session_state.messages.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"): st.markdown(response)

elif not market_data.empty:
    st.info("請在左側側邊欄設定您的投資偏好與資金，然後點擊按鈕開始分析。")

