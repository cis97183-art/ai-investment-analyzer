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
from update_database import main as run_db_update
from etf_rules import ETF_PROMPT_FRAMEWORK
from prompts import get_data_driven_prompt_templates, STOCK_PROMPT_FRAMEWORK
from data_loader import load_and_merge_data
from screener import screen_stocks

# --- 專案說明 ---
st.set_page_config(page_title="台股分析引擎 (V3 修正版)", layout="wide")
st.title("📊 高效台股分析引擎 (V3 修正版)")
st.markdown("本系統採用 **yfinance** 作為核心數據源，結合本地數據庫進行高效分析。數據可手動更新，提供您閃電般的篩選速度與穩定可靠的數據品質。")

# --- Google API 金鑰設定 ---
try:
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
    model = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash-latest",
        temperature=0.2,
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    prompt = PromptTemplate.from_template(prompt_template)
    return LLMChain(llm=model, prompt=prompt)

def _clean_and_parse_json(raw_text: str):
    match = re.search(r"```(json)?\s*({.*?})\s*```", raw_text, re.DOTALL)
    if match:
        clean_text = match.group(2)
    else:
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
    # ... (此函數邏輯不變，省略以保持簡潔)
    if portfolio_type in ["純個股", "混合型"]:
        with st.spinner("步驟 1/2: 正在從本地資料庫進行量化篩選..."):
            if market_data.empty:
                st.error("市場數據為空，無法進行篩選。")
                return None
            candidate_df = screen_stocks(market_data, risk_profile)
            if candidate_df.empty:
                st.warning(f"根據您的 '{risk_profile}' 規則，找不到滿足所有條件的股票。請嘗試放寬條件或更新市場數據。")
                return None
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


# --- [V3 版] 報告可視化 (已整合所有問題的修正) ---
def display_report(report_data, investment_amount, portfolio_type):
    # 【問題一：解決方案】擴充產業中英對照表，並設定萬無一失的預設值
    INDUSTRY_MAP = {
        'Semiconductors': '半導體', 'Computer Hardware': '電腦硬體',
        'Financial Services': '金融服務', 'Conglomerates': '綜合企業',
        'Shipping & Ports': '航運與港口', 'Telecom Services': '電信服務',
        'Electronic Components': '電子零組件', 'Plastics': '塑膠',
        'Cement': '水泥', 'Retail': '零售', 'Textiles': '紡織',
        'Food & Beverages': '食品飲料', 'Construction': '營建',
        'Biotechnology': '生物科技', 'Insurance - Life': '人壽保險',
        'Credit Services': '信貸服務', 'Building Materials': '建材',
        'Other': '其他'
    }

    st.header(report_data.get('summary', {}).get('title', '投資組合報告'))
    st.info(f"報告生成日期：{report_data.get('summary', {}).get('generated_date', 'N/A')}")
    st.subheader("📈 投資組合總覽")
    st.write(report_data.get('summary', {}).get('overview', ''))
    
    # ... (核心風險指標部分不變)
    st.subheader("📊 核心風險指標 (AI 估算)")
    metrics = report_data.get('portfolio_metrics', {})
    metric_labels = {'beta': "Beta 值", 'annual_volatility': "年化波動率", 'sharpe_ratio': "夏普比率"}
    cols = st.columns(len(metrics))
    for i, (key, value) in enumerate(metrics.items()):
        cols[i].metric(metric_labels.get(key, key), value)

    st.write("---")

    # --- 數據準備與清洗 ---
    df = pd.concat([
        pd.DataFrame(report_data.get('core_holdings', [])),
        pd.DataFrame(report_data.get('satellite_holdings', [])),
        pd.DataFrame(report_data.get('holdings', []))
    ], ignore_index=True)

    df['weight'] = pd.to_numeric(df['weight'], errors='coerce')
    df.dropna(subset=['weight'], inplace=True)
    df = df[df['weight'] > 0].copy()

    if df.empty:
        st.warning("AI 生成的投資組合中沒有有效的持股資訊。")
        return
        
    # 【問題三：解決方案】標準化權重，確保總和為 100%
    total_weight = df['weight'].sum()
    df['weight_normalized'] = df['weight'] / total_weight if total_weight > 0 else 0
    df.sort_values(by='weight_normalized', ascending=False, inplace=True)
    
    # 【問題四：解決方案】根本修正資金分配邏輯
    df['資金分配 (TWD)'] = (df['weight_normalized'] * investment_amount).round().astype(int)
    current_sum = df['資金分配 (TWD)'].sum()
    difference = investment_amount - current_sum
    if difference != 0 and not df.empty:
        df.iloc[0, df.columns.get_loc('資金分配 (TWD)')] += difference
    
    df['權重 (%)'] = (df['weight_normalized'] * 100).round(2)
    
    # --- 圖表繪製 ---
    st.subheader("視覺化分析")
    chart1, chart2 = st.columns(2)

    with chart1:
        # ... (圓餅圖邏輯不變)
        fig_pie = px.pie(df, values='weight_normalized', names='name', hole=.3,
                         title='持股權重分配',
                         color_discrete_sequence=px.colors.qualitative.Plotly)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label',
                              hovertemplate='%{label}<br>權重: %{percent:.2%}')
        fig_pie.update_layout(showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)


    with chart2:
        # 【問題一 & 二：解決方案】重構分類邏輯
        if 'industry' in df.columns:
            df['industry_zh'] = df['industry'].map(INDUSTRY_MAP).fillna('其他產業')
        else:
            df['industry_zh'] = 'N/A' # 給個預設值以防萬一

        if portfolio_type == "混合型":
            # 【V3.1 Bug 修復】修正 'etf_type' 欄位不存在時的錯誤
            if 'etf_type' in df.columns:
                # 建立一個新欄位 'chart_category'
                # 判斷 'etf_type' 欄位是否存在且不為空，是的話就標記為 'ETF 核心'
                df['chart_category'] = np.where(df['etf_type'].notna(), 'ETF 核心', df['industry_zh'])
            else:
                # 如果沒有 etf_type 欄位，代表全都是個股
                df['chart_category'] = df['industry_zh']

            grouped = df.groupby('chart_category')['weight_normalized'].sum().reset_index()
            chart_title, x_col = '資產類別分佈 (混合型)', 'chart_category'
        else:
            # 純個股或純 ETF 的邏輯
            # 修正：確保 group_col 在 df 中存在
            if 'industry_zh' in df.columns and df['industry_zh'].nunique() > 1:
                group_col = 'industry_zh'
            elif 'etf_type' in df.columns:
                group_col = 'etf_type'
            else:
                group_col = 'name' # 最後的保險手段，按名稱分組
            
            grouped = df.groupby(group_col)['weight_normalized'].sum().reset_index()
            chart_title, x_col = f'{group_col} 權重分佈', group_col

        fig_bar = px.bar(grouped, x=x_col, y='weight_normalized',
                         text_auto='.1%', title=chart_title,
                         color_discrete_sequence=px.colors.qualitative.Plotly)
        fig_bar.update_layout(xaxis_title=None, yaxis_title="權重", yaxis_tickformat='.0%',
                              margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- 詳細表格 ---
    st.write("---")
    st.subheader("📝 詳細持股與資金計畫")
    df_display = df.rename(columns={'ticker': '代碼', 'name': '名稱', 
                                    'industry_zh': '產業類別', 'etf_type': 'ETF類型', 
                                    'rationale': '簡要理由'})
    
    final_cols = [col for col in ['代碼', '名稱', '產業類別', 'ETF類型', '權重 (%)', '資金分配 (TWD)', '簡要理由'] if col in df_display.columns]

    st.dataframe(df_display[final_cols], use_container_width=True, hide_index=True,
        column_config={
            # 【問題三 修正】max_value 應為 100，進度條才會正確顯示
            "權重 (%)": st.column_config.ProgressColumn("權重 (%)", format="%.2f%%", min_value=0, max_value=100),
            "資金分配 (TWD)": st.column_config.NumberColumn("資金分配 (TWD)", format="NT$ %'d"),
            "簡要理由": st.column_config.TextColumn("簡要理由", width="large")
        })

def handle_follow_up_question(question, context):
    # ... (此函數邏輯不變)
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
    # ... (側邊欄 UI 不變)
    st.header("👤 您的投資設定")
    portfolio_type_input = st.radio("1. 請選擇投資組合類型", ("純個股", "純 ETF", "混合型"), index=2)
    risk_profile_input = st.selectbox("2. 請選擇您的風險偏好", ('積極型', '穩健型', '保守型'), index=1)
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
    if market_data.empty:
        st.error("無法生成報告，因為市場數據庫是空的。請先更新市場數據。")
        st.stop()
    
    report = generate_portfolio(portfolio_type_input, risk_profile_input, investment_amount_input)
    if report:
        st.session_state.report_data = report
        st.session_state.portfolio_generated = True
        # 【問題四：解決方案】在生成報告的當下，鎖定當時的設定值
        st.session_state.investment_amount = investment_amount_input
        st.session_state.portfolio_type = portfolio_type_input

if st.session_state.portfolio_generated and st.session_state.report_data:
    # 【問題四：解決方案】顯示報告時，務必使用 session_state 中儲存的設定值
    display_report(st.session_state.report_data, st.session_state.investment_amount, st.session_state.portfolio_type)
    
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

