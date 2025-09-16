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

# --- 導入新的模組 ---
from etf_rules import ETF_PROMPT_FRAMEWORK
# [BUG FIX] 修正導入的函式名稱，並移除不再需要單獨導入的 STOCK_PROMPT_FRAMEWORK
from prompts import get_data_driven_prompt_templates
from data_fetcher import get_stock_data
from screener import screen_stocks

# --- 專案說明 ---
st.set_page_config(page_title="數據驅動 AI 投資組合系統", layout="wide")
st.title("💡 數據驅動 AI 投資組合建構系統 (V2)")
st.markdown("本系統結合 `yfinance` **即時市場數據**進行量化預篩選，再由 AI 根據專業風險框架，從高品質候選名單中為您打造專屬投資組合。")


# --- Google API 金鑰設定 ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except (KeyError, Exception) as e:
    st.error("錯誤：請確認你的 Google API 金鑰已在 `.streamlit/secrets.toml` 中正確設定。")
    st.info("設定教學：在專案資料夾中建立 `.streamlit` 資料夾，並在其中新增 `secrets.toml` 檔案，內容為：`GOOGLE_API_KEY = \"你的金鑰\"`")
    st.stop()


# --- RAG 核心邏輯 ---
def get_llm_chain(prompt_template):
    """
    Initializes and returns a LangChain LLMChain.
    Specifies the model to use Gemini-1.5-Flash for speed and cost-effectiveness,
    and sets the response format to JSON.
    """
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest",
                                 temperature=0.2,
                                 # Enforce JSON output format
                                 model_kwargs={"response_format": {"type": "json_object"}})
    prompt = PromptTemplate.from_template(prompt_template)
    chain = LLMChain(llm=model, prompt=prompt)
    return chain

def _clean_and_parse_json(raw_text: str):
    """
    Cleans and parses a JSON string from the LLM's raw output.
    Handles cases where the JSON is wrapped in markdown code blocks.
    """
    # Use regex to find JSON within markdown code blocks (```json ... ```)
    match = re.search(r"```(json)?\s*({.*?})\s*```", raw_text, re.DOTALL)
    if match:
        clean_text = match.group(2)
    else:
        # Fallback for cases where JSON is not in a markdown block
        start_index = raw_text.find('{')
        end_index = raw_text.rfind('}')
        if start_index != -1 and end_index != -1 and end_index > start_index:
            clean_text = raw_text[start_index:end_index+1]
        else:
            clean_text = raw_text # Assume it's already a clean JSON
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError as e:
        st.error("JSON 解析失敗，即使在清理後也是如此。")
        st.write("以下是 AI 回傳的原始文字，這可能不是有效的 JSON：")
        st.code(raw_text, language="text")
        # Re-raise the exception to stop execution if parsing fails
        raise e


# --- 報告生成與可視化 ---
def generate_portfolio(portfolio_type, risk_profile, investment_amount):
    """[V2] 根據即時數據篩選並生成投資報告"""

    # For portfolios containing stocks, first get data and screen it
    if portfolio_type in ["純個股", "混合型"]:
        with st.spinner("步驟 1/2: 正在從 yfinance 獲取即時市場數據並進行量化篩選..."):
            all_stock_data = get_stock_data()
            if all_stock_data.empty:
                st.error("無法獲取股票數據，請檢查網路連線或稍後再試。")
                return None
            
            candidate_df = screen_stocks(all_stock_data, risk_profile)
            
            if candidate_df.empty:
                st.warning(f"根據您的 '{risk_profile}' 規則，找不到同時滿足所有條件的股票。請嘗試放寬條件或更換風險偏好。")
                return None
            
            # Prepare the screened data as a CSV string for the LLM
            candidate_data_for_llm = candidate_df[['shortName', 'marketCap', 'beta', 'averageVolume', 'trailingPE', 'dividendYield']].to_csv(index=True)

        with st.spinner("步驟 2/2: 已完成量化篩選！正在將候選名單交由 AI 進行最終組合分析..."):
            prompt_templates = get_data_driven_prompt_templates()
            prompt_template = prompt_templates[portfolio_type]
            chain = get_llm_chain(prompt_template)
            
            # The 'stock_rules' are now implicitly part of the template, so we don't need to pass them here
            # But the prompt template expects it, so we need to get it.
            # A better approach would be to refactor prompts.py to not require this.
            # For now, let's re-import it just for this call.
            from prompts import STOCK_PROMPT_FRAMEWORK
            
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

    else: # ETF-only portfolio flow
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
        # Format HHI index as an integer
        if key == 'hhi_index':
            try:
                value = f"{float(value):.0f}"
            except (ValueError, TypeError):
                value = str(value)
        cols[i].metric(label, value)

    st.write("---")

    # Handle different portfolio structures (mixed vs. single-type)
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

    # --- WEIGHT NORMALIZATION FIX ---
    # Ensure 'weight' column is numeric, coercing errors to NaN
    df['weight'] = pd.to_numeric(df['weight'], errors='coerce')
    # Drop rows where weight conversion failed
    df.dropna(subset=['weight'], inplace=True)
    # Re-normalize weights to ensure they sum to 1 (100%)
    if not df.empty and df['weight'].sum() > 0:
        df['weight'] = df['weight'] / df['weight'].sum()
    # --- END FIX ---

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
        # Determine the grouping column for the bar chart
        if 'industry' in df.columns and df['industry'].notna().any():
            group_col = 'industry'
            chart_title = '產業權重分佈'
        elif 'etf_type' in df.columns and df['etf_type'].notna().any():
            group_col = 'etf_type'
            chart_title = 'ETF 類型分佈'
        else:
            group_col = None

        if group_col:
            grouped = df.groupby(group_col)['weight'].sum().reset_index()
            fig_bar = go.Figure(data=[go.Bar(
                x=grouped[group_col], y=grouped['weight'],
                text=(grouped['weight']*100).apply(lambda x: f'{x:.1f}%'),
                textposition='auto',
            )])
            fig_bar.update_layout(title_text=chart_title, xaxis_title=None, yaxis_title="權重", yaxis_tickformat='.0%', margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("此投資組合無適用的分類可供繪製長條圖。")

    st.write("---")
    st.subheader("📝 詳細持股與資金計畫")

    # Dynamically build the list of columns to display
    display_cols = ['ticker', 'name']
    if 'industry' in df.columns and df['industry'].notna().any(): display_cols.append('industry')
    if 'etf_type' in df.columns and df['etf_type'].notna().any(): display_cols.append('etf_type')
    display_cols.extend(['權重 (%)', '資金分配 (TWD)', 'rationale'])
    # Ensure we only try to display columns that actually exist in the DataFrame
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
# Initialize session state variables
if 'portfolio_generated' not in st.session_state: st.session_state.portfolio_generated = False
if 'report_data' not in st.session_state: st.session_state.report_data = None
if 'messages' not in st.session_state: st.session_state.messages = []

with st.sidebar:
    st.header("👤 您的投資設定")
    portfolio_type_input = st.radio("1. 請選擇投資組合類型", ("純個股", "純 ETF", "混合型"), index=0, captions=("僅含個股", "僅含 ETF", "ETF 為核心，個股為衛星"))
    risk_profile_input = st.selectbox("2. 請選擇您的風險偏好", ('積極型', '穩健型', '保守型'), index=0, help="積極型追求高回報；穩健型平衡風險與回報；保守型注重資本保值。")
    investment_amount_input = st.number_input("3. 請輸入您預計投入的總資金 (新台幣)", min_value=10000, value=100000, step=10000)
    analyze_button = st.button("🚀 生成我的投資組合", type="primary", use_container_width=True)
    st.info("免責聲明：本系統僅為AI輔助分析工具，所有資訊與建議僅供參考，不構成任何投資決策的依據。投資有風險，請謹慎評估。")

if analyze_button:
    # Clear previous chat history and report data on new generation
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
    st.info("對這個投資組合有任何疑問嗎？或者想做些微調？請在下方提出您的問題。")
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])
        
    # Handle new chat input
    if prompt := st.chat_input("例如：為什麼選擇 0050？ 或者 可以把半導體個股換成別的嗎？"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.spinner("AI 正在思考中..."):
            response = handle_follow_up_question(prompt, st.session_state.report_data)
            st.session_state.messages.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"): st.markdown(response)
else:
    # Initial message when the app loads
    st.info("請在左側側邊欄設定您的投資偏好與資金，然後點擊按鈕開始。")
