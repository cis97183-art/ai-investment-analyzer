import streamlit as st
import pandas as pd
import numpy as np
import google.generativeai as genai
from langchain.chains import LLMChain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
import plotly.graph_objects as go
import plotly.express as px
import json
from datetime import datetime
import re
import os
import time

# --- 導入專案模組 ---
# 假設 update_database, etf_rules, prompts, data_loader, screener 都在同級目錄
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
    # 為了方便部署，我們優先從 Streamlit Secrets 讀取金鑰
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except (KeyError, Exception):
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
    """初始化並返回一個配置好的 LangChain LLMChain。"""
    model = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash-latest",
        temperature=0.2,
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    prompt = PromptTemplate.from_template(prompt_template)
    return LLMChain(llm=model, prompt=prompt)

def _clean_and_parse_json(raw_text: str):
    """從 LLM 的原始輸出中清理並解析 JSON。"""
    # 使用 정규 표현식 尋找被 ```json ... ``` 包裹的內容
    match = re.search(r"```(json)?\s*({.*?})\s*```", raw_text, re.DOTALL)
    if match:
        clean_text = match.group(2)
    else:
        # 如果沒有找到 markdown 區塊，則嘗試找到最外層的大括號
        start_index = raw_text.find('{')
        end_index = raw_text.rfind('}')
        if start_index != -1 and end_index != -1:
            clean_text = raw_text[start_index:end_index+1]
        else:
            raise ValueError("在 LLM 的回應中找不到有效的 JSON 物件。")
            
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError as e:
        st.error(f"JSON 解析失敗，請檢查 LLM 的輸出格式。錯誤訊息: {e}")
        st.code(raw_text, language="text")
        raise

# --- 報告生成 ---
def generate_portfolio(portfolio_type, risk_profile, investment_amount):
    """根據使用者輸入生成投資組合報告。"""
    if portfolio_type in ["純個股", "混合型"]:
        with st.spinner("步驟 1/2: 正在從本地資料庫進行量化篩選..."):
            if market_data.empty:
                st.error("市場數據為空，無法進行篩選。")
                return None
            candidate_df = screen_stocks(market_data, risk_profile)
            if candidate_df.empty:
                st.warning(f"根據您的 '{risk_profile}' 規則，找不到滿足所有條件的股票。請嘗試放寬條件或更新市場數據。")
                return None
            # 限制候選名單的大小，避免 Prompt 過長
            candidate_df = candidate_df.head(50)
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
    else: # 純 ETF
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

# --- [V2 版] 報告可視化 (已修復四大問題) ---
def display_report(report_data, investment_amount, portfolio_type):
    # 【問題一：解決方案】擴充產業中英對照表，涵蓋更多可能性
    INDUSTRY_MAP = {
        'Semiconductors': '半導體', 'Computer Hardware': '電腦硬體',
        'Financial Services': '金融服務', 'Conglomerates': '綜合企業',
        'Shipping & Ports': '航運與港口', 'Telecom Services': '電信服務',
        'Electronic Components': '電子零組件', 'Plastics': '塑膠',
        'Cement': '水泥', 'Retail': '零售', 'Textiles': '紡織',
        'Food & Beverages': '食品飲料', 'Construction': '營建',
        'Biotechnology': '生物科技', 'Other': '其他'
    }

    st.header(report_data['summary']['title'])
    st.info(f"報告生成日期：{report_data['summary']['generated_date']}")
    st.subheader("📈 投資組合總覽")
    st.write(report_data['summary']['overview'])
    
    st.subheader("📊 核心風險指標 (AI 估算)")
    metrics = report_data.get('portfolio_metrics', {})
    metric_labels = {'beta': "Beta 值", 'annual_volatility': "年化波動率", 'sharpe_ratio': "夏普比率"}
    cols = st.columns(len(metrics))
    for i, (key, value) in enumerate(metrics.items()):
        cols[i].metric(metric_labels.get(key, key), value)

    st.write("---")

    # --- 數據準備與清洗 ---
    core_df = pd.DataFrame(report_data.get('core_holdings', []))
    sat_df = pd.DataFrame(report_data.get('satellite_holdings', []))
    # 'holdings' 是為了兼容純個股/純ETF的情況
    holdings_df = pd.DataFrame(report_data.get('holdings', []))
    
    # 整合所有持股到一個 DataFrame
    df = pd.concat([core_df, sat_df, holdings_df], ignore_index=True)

    # 確保 'weight' 欄位為數值型態，並移除無效權重
    df['weight'] = pd.to_numeric(df['weight'], errors='coerce')
    df.dropna(subset=['weight'], inplace=True)
    df = df[df['weight'] > 0].copy()

    if df.empty:
        st.warning("AI 生成的投資組合中沒有有效的持股資訊。")
        return
        
    # 【問題三：解決方案】標準化權重，確保總和為 100%
    # 這個步驟可以修正 AI 給出的權重總和不完全等於 1 或 100 的情況
    total_weight = df['weight'].sum()
    if total_weight > 0:
        df['weight_normalized'] = df['weight'] / total_weight
    else:
        df['weight_normalized'] = 0

    df.sort_values(by='weight_normalized', ascending=False, inplace=True)
    
    # 【問題四：解決方案】修正資金分配邏輯，避免因四捨五入產生驚嘆號
    df['資金分配 (TWD)'] = (df['weight_normalized'] * investment_amount).apply(np.floor).astype(int)
    remainder = investment_amount - df['資金分配 (TWD)'].sum()
    # 將餘額加到權重最高的持股上，確保資金完全分配
    if not df.empty:
        df.iloc[0, df.columns.get_loc('資金分配 (TWD)')] += remainder

    df['權重 (%)'] = (df['weight_normalized'] * 100)
    
    # 【問題一：解決方案】確保中文產業欄位存在
    if 'industry' in df.columns:
        df['industry_zh'] = df['industry'].map(INDUSTRY_MAP).fillna(df['industry'])

    # --- 圖表繪製 ---
    st.subheader("視覺化分析")
    chart1, chart2 = st.columns(2)

    with chart1:
        fig_pie = px.pie(df, values='weight_normalized', names='name', hole=.3,
                         title='持股權重分配',
                         color_discrete_sequence=px.colors.qualitative.Plotly)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label',
                              hovertemplate='%{label}<br>權重: %{percent:.2%}')
        fig_pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    with chart2:
        # 【問題二：解決方案】修正混合型圖表分類邏輯，使其更穩健
        chart_title = "資產分佈"
        if portfolio_type == "混合型":
            # 為 ETF 標記為 'ETF 核心'，個股使用中文產業別
            df['chart_category'] = np.where(df['ticker'].str.match(r'^\d{4,6}$'), 
                                           df.get('industry_zh', '其他個股'), 
                                           'ETF 核心')
            # 針對 ETF ticker 通常是數字的特性來區分
            is_etf = df['ticker'].str.match(r'^\d{4,6}$') & ('etf_type' in df.columns)
            df['chart_category'] = np.where(is_etf, 'ETF 核心', df.get('industry_zh', '其他個股'))

            grouped = df.groupby('chart_category')['weight_normalized'].sum().reset_index()
            chart_title, x_col, y_col = '資產類別分佈 (混合型)', 'chart_category', 'weight_normalized'
        
        elif 'industry_zh' in df.columns and df['industry_zh'].notna().any():
            grouped = df.groupby('industry_zh')['weight_normalized'].sum().reset_index()
            chart_title, x_col, y_col = '產業權重分佈', 'industry_zh', 'weight_normalized'
        
        elif 'etf_type' in df.columns and df['etf_type'].notna().any():
            grouped = df.groupby('etf_type')['weight_normalized'].sum().reset_index()
            chart_title, x_col, y_col = 'ETF 類型分佈', 'etf_type', 'weight_normalized'
        else:
            grouped = None

        if grouped is not None and not grouped.empty:
            fig_bar = go.Figure(data=[go.Bar(
                x=grouped[x_col], y=grouped[y_col],
                text=(grouped[y_col]*100).apply(lambda x: f'{x:.1f}%'), 
                textposition='auto',
                marker_color=px.colors.qualitative.Plotly
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
    
    # 為了顯示美觀，重新命名欄位
    df_display = df.rename(columns={'ticker': '代碼', 'name': '名稱', 'industry_zh': '產業類別', 'etf_type': 'ETF類型', 'rationale': '簡要理由'})
    
    # 確保要顯示的欄位都存在於 DataFrame 中
    final_cols_renamed = [col for col in ['代碼', '名稱', '產業類別', 'ETF類型', '權重 (%)', '資金分配 (TWD)', '簡要理由'] if col in df_display.columns]

    st.dataframe(df_display[final_cols_renamed], use_container_width=True, hide_index=True,
        column_config={
            "權重 (%)": st.column_config.ProgressColumn("權重 (%)", format="%.2f%%", min_value=0, max_value=df_display['權重 (%)'].max()),
            "資金分配 (TWD)": st.column_config.NumberColumn("資金分配 (TWD)", format="NT$ %'d"),
            "簡要理由": st.column_config.TextColumn("簡要理由", width="large")
        })

def handle_follow_up_question(question, context):
    """處理後續的問答。"""
    prompt_template = """
    你是一位專業的台灣股市投資組合經理。使用者已經收到你先前建立的投資組合報告，現在他有後續問題。
    請根據你先前提供的報告內容，以及使用者的問題，提供簡潔、專業的回答。
    **先前報告的內容摘要 (JSON):** {context}
    **使用者的問題:** {question}
    請直接回答使用者的問題，使用繁體中文。
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
    portfolio_type_input = st.radio("1. 請選擇投資組合類型", ("純個股", "純 ETF", "混合型"), index=2) # 預設改為混合型，方便測試
    risk_profile_input = st.selectbox("2. 請選擇您的風險偏好", ('積極型', '穩健型', '保守型'), index=1) # 預設改為穩健型
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
        st.error("無法生成報告，因為市場數據庫是空的。請先更新市場數據。")
        st.stop()

    report = generate_portfolio(portfolio_type_input, risk_profile_input, investment_amount_input)
    if report:
        st.session_state.report_data = report
        st.session_state.portfolio_generated = True
        st.session_state.investment_amount = investment_amount_input # 保存當時的投資金額
        st.session_state.portfolio_type = portfolio_type_input # 保存當時的類型

# 如果已經生成報告，則顯示它
if st.session_state.portfolio_generated and st.session_state.report_data:
    # 從 session_state 讀取，確保頁面刷新後資訊依然存在
    display_report(st.session_state.report_data, st.session_state.investment_amount, st.session_state.portfolio_type)
    
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
    st.info("請在左側側邊欄設定您的投資偏好與資金，然後點擊「生成投資組合」按鈕開始分析。")
