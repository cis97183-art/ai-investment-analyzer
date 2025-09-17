import streamlit as st
import pandas as pd
import google.generativeai as genai
from langchain.chains import LLMChain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
import plotly.graph_objects as go
import json
from datetime import datetime
import re
import yfinance as yf

# --- 導入專案模組 ---
from etf_rules import ETF_PROMPT_FRAMEWORK
from prompts import get_data_driven_prompt_templates, STOCK_PROMPT_FRAMEWORK
# [新] 導入 API 篩選器，取代舊的 data_fetcher 和 screener
from api_screener import screen_stocks_api

# --- 專案說明 ---
st.set_page_config(page_title="即時規則驅動 AI 投資組合系統", layout="wide")
st.title("🚀 即時規則驅動 AI 投資組合建構系統 (V3 API)")
st.markdown("本系統採用**即時規則驅動篩選 (Real-time Rule-Driven Screening)**。當您點擊生成按鈕時，系統會**即時調用外部的「股票篩選器 API」**，將您的風險偏好轉換為具體參數發送，直接獲取符合當下市場條件的股票代碼列表，再交由 AI 進行質化分析與組合建構。")


# --- Google API 金鑰設定 ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except (KeyError, Exception) as e:
    st.error("錯誤：請確認你的 Google API 金鑰已在 `.streamlit/secrets.toml` 中正確設定。")
    st.info("設定教學：在專案資料夾中建立 `.streamlit` 資料夾，並在其中新增 `secrets.toml` 檔案，內容為：`GOOGLE_API_KEY = \"你的金鑰\"`")
    st.stop()


# --- RAG 核心邏輯 ---
def get_llm_chain(prompt_template):
    """初始化並回傳一個 LangChain LLMChain。"""
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest",
                                 temperature=0.2,
                                 model_kwargs={"response_format": {"type": "json_object"}})
    prompt = PromptTemplate.from_template(prompt_template)
    chain = LLMChain(llm=model, prompt=prompt)
    return chain

def _clean_and_parse_json(raw_text: str):
    """清理並解析 LLM 原始輸出中的 JSON 字串。"""
    match = re.search(r"```(json)?\s*({.*?})\s*```", raw_text, re.DOTALL)
    if match:
        clean_text = match.group(2)
    else:
        start_index = raw_text.find('{')
        end_index = raw_text.rfind('}')
        if start_index != -1 and end_index != -1 and end_index > start_index:
            clean_text = raw_text[start_index:end_index+1]
        else:
            clean_text = raw_text
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError as e:
        st.error("JSON 解析失敗。")
        st.code(raw_text, language="text")
        raise e

@st.cache_data(ttl=1800) # 快取數據 30 分鐘
def get_stock_details(tickers: list[str]) -> pd.DataFrame:
    """
    [新] 根據 API 回傳的 ticker 列表，使用 yfinance 獲取詳細數據。
    """
    all_info = []
    progress_bar = st.progress(0, text="正在下載 API 篩選結果的詳細股票數據...")
    
    for i, ticker_id in enumerate(tickers):
        try:
            ticker_obj = yf.Ticker(ticker_id)
            info = ticker_obj.info
            
            if not info or info.get('marketCap') is None:
                raise ValueError(f"缺少 {ticker_id} 的關鍵數據。")

            filtered_info = {
                'tickerId': ticker_id,
                'shortName': info.get('shortName'),
                'industry': info.get('industry'),
                'marketCap': info.get('marketCap'),
                'beta': info.get('beta'),
                'averageVolume': info.get('averageVolume10day'),
                'trailingPE': info.get('trailingPE'),
                'dividendYield': info.get('dividendYield'),
            }
            all_info.append(filtered_info)
        except Exception as e:
            st.warning(f"下載 {ticker_id} 數據時出錯: {e}")
        
        progress_bar.progress((i + 1) / len(tickers), text=f"正在下載 {i+1}/{len(tickers)}: {ticker_id} ...")

    progress_bar.empty()
    
    if not all_info:
        return pd.DataFrame()

    df = pd.DataFrame(all_info).set_index('tickerId')
    df.dropna(subset=['marketCap', 'beta', 'shortName'], inplace=True)
    return df

# --- 報告生成與可視化 ---
def generate_portfolio(portfolio_type, risk_profile, investment_amount):
    """[V3 API] 根據 API 篩選結果生成投資報告"""

    if portfolio_type in ["純個股", "混合型"]:
        # --- 步驟 1: 調用 API 取得股票列表 ---
        candidate_tickers = screen_stocks_api(risk_profile)
        
        if not candidate_tickers:
            st.error("API 未回傳任何符合條件的股票，無法生成投資組合。")
            return None

        # --- 步驟 2: 獲取這些股票的詳細數據 ---
        with st.spinner("步驟 2/3: 正在從 yfinance 獲取 API 篩選結果的詳細數據..."):
            candidate_df = get_stock_details(candidate_tickers)
            if candidate_df.empty:
                st.error("無法為 API 回傳的股票獲取詳細數據。")
                return None
            
            candidate_data_for_llm = candidate_df[['shortName', 'marketCap', 'beta', 'trailingPE', 'dividendYield']].to_csv(index=True)

        # --- 步驟 3: 將結果交給 AI 分析 ---
        with st.spinner("步驟 3/3: 已獲取數據！正在將候選名單交由 AI 進行最終質化分析..."):
            prompt_templates = get_data_driven_prompt_templates()
            prompt_template = prompt_templates[portfolio_type]
            chain = get_llm_chain(prompt_template)
            
            input_data = {
                "stock_rules": STOCK_PROMPT_FRAMEWORK,
                "etf_rules": ETF_PROMPT_FRAMEWORK,
                "risk_profile": risk_profile,
                "investment_amount": f"{investment_amount:,.0f}",
                "current_date": datetime.now().strftime("%Y年%m月%d日"),
                "candidate_stocks_csv": candidate_data_for_llm
            }
            response = chain.invoke(input_data)
            return _clean_and_parse_json(response['text'])

    else: # 純 ETF 流程 (不需經過個股 API)
        with st.spinner("正在為您建構純 ETF 投資組合..."):
            prompt_templates = get_data_driven_prompt_templates()
            prompt_template = prompt_templates[portfolio_type]
            chain = get_llm_chain(prompt_template)
            input_data = {
                "etf_rules": ETF_PROMPT_FRAMEWORK,
                "risk_profile": risk_profile,
                "investment_amount": f"{investment_amount:,.0f}",
                "current_date": datetime.now().strftime("%Y年%m月%d日")
            }
            response = chain.invoke(input_data)
            return _clean_and_parse_json(response['text'])


def display_report(report_data, investment_amount):
    """以圖文並茂的方式呈現報告"""
    
    st.header(report_data['summary']['title'])
    st.info(f"報告生成日期：{report_data['summary']['generated_date']}")
    
    st.subheader("📈 投資組合總覽")
    st.write(report_data['summary']['overview'])
    
    st.subheader("📊 核心風險指標")
    metrics = report_data['portfolio_metrics']
    metric_labels = {'beta': "Beta 值", 'annual_volatility': "年化波動率", 'sharpe_ratio': "夏普比率", 'hhi_index': "HHI 集中度"}
    
    cols = st.columns(len(metrics))
    for i, (key, value) in enumerate(metrics.items()):
        label = metric_labels.get(key, key.replace('_', ' ').title())
        if key == 'hhi_index':
            try: value = f"{float(value):.0f}"
            except (ValueError, TypeError): value = str(value)
        cols[i].metric(label, value)

    st.write("---")

    if 'core_holdings' in report_data:
        core_df = pd.DataFrame(report_data['core_holdings'])
        core_df['類型'] = '核心 (ETF)'
        sat_df = pd.DataFrame(report_data['satellite_holdings'])
        sat_df['類型'] = '衛星 (個股)'
        df = pd.concat([core_df, sat_df], ignore_index=True)
        st.subheader("視覺化分析：整體資產配置")
    else:
        df = pd.DataFrame(report_data['holdings'])
        st.subheader("視覺化分析")

    df['weight'] = pd.to_numeric(df['weight'], errors='coerce')
    df.dropna(subset=['weight'], inplace=True)
    if not df.empty and df['weight'].sum() > 0:
        df['weight'] = df['weight'] / df['weight'].sum()

    df['資金分配 (TWD)'] = (df['weight'] * investment_amount).round(0)
    df['權重 (%)'] = (df['weight'] * 100).round(2)
    
    chart1, chart2 = st.columns(2)

    with chart1:
        fig_pie = go.Figure(data=[go.Pie(
            labels=df['name'], values=df['weight'], hole=.3,
            textinfo='percent+label', hoverinfo='label+percent+value',
            texttemplate='%{label}<br>%{percent:.1%}',
        )])
        fig_pie.update_layout(title_text='持股權重分配', showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    with chart2:
        group_col = None
        if 'industry' in df.columns and df['industry'].notna().any():
            group_col = 'industry'
            chart_title = '產業權重分佈'
        elif 'etf_type' in df.columns and df['etf_type'].notna().any():
            group_col = 'etf_type'
            chart_title = 'ETF 類型分佈'

        if group_col:
            grouped = df.groupby(group_col)['weight'].sum().reset_index()
            fig_bar = go.Figure(data=[go.Bar(
                x=grouped[group_col], y=grouped['weight'],
                text=(grouped['weight']*100).apply(lambda x: f'{x:.1f}%'),
                textposition='auto',
            )])
            fig_bar.update_layout(title_text=chart_title, xaxis_title=None, yaxis_title="權重", yaxis_tickformat='.0%', margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_bar, use_container_width=True)

    st.write("---")
    st.subheader("📝 詳細持股與資金計畫")
    display_cols = ['ticker', 'name']
    if 'industry' in df.columns and df['industry'].notna().any(): display_cols.append('industry')
    if 'etf_type' in df.columns and df['etf_type'].notna().any(): display_cols.append('etf_type')
    display_cols.extend(['權重 (%)', '資金分配 (TWD)', 'rationale'])
    final_cols = [col for col in display_cols if col in df.columns]

    st.dataframe(df[final_cols], use_container_width=True, hide_index=True,
        column_config={
            "權重 (%)": st.column_config.ProgressColumn("權重 (%)", format="%.2f%%", min_value=0, max_value=100),
            "資金分配 (TWD)": st.column_config.NumberColumn("資金分配 (TWD)", format="NT$ %'d"),
            "rationale": st.column_config.TextColumn("簡要理由", width="large")
        })

def handle_follow_up_question(question, context):
    """處理後續問題"""
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

# --- UI ---
if 'portfolio_generated' not in st.session_state: st.session_state.portfolio_generated = False
if 'report_data' not in st.session_state: st.session_state.report_data = None
if 'messages' not in st.session_state: st.session_state.messages = []

with st.sidebar:
    st.header("👤 您的投資設定")
    portfolio_type_input = st.radio("1. 請選擇投資組合類型", ("純個股", "純 ETF", "混合型"), index=0)
    risk_profile_input = st.selectbox("2. 請選擇您的風險偏好", ('積極型', '穩健型', '保守型'), index=0)
    investment_amount_input = st.number_input("3. 請輸入您預計投入的總資金 (新台幣)", min_value=10000, value=100000, step=10000)
    analyze_button = st.button("🚀 生成我的投資組合", type="primary", use_container_width=True)
    st.info("免責聲明：本系統僅為AI輔助分析工具，所有資訊與建議僅供參考。投資有風險，請謹慎評估。")

if analyze_button:
    st.session_state.messages = []
    st.session_state.report_data = None
    st.session_state.portfolio_generated = False
    
    report = generate_portfolio(portfolio_type_input, risk_profile_input, investment_amount_input)
    if report:
        st.session_state.report_data = report
        st.session_state.portfolio_generated = True

if st.session_state.portfolio_generated:
    display_report(st.session_state.report_data, investment_amount_input)
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
else:
    st.info("請在左側側邊欄設定您的投資偏好與資金，然後點擊按鈕開始。")
