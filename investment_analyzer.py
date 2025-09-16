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

# --- 從獨立檔案導入規則與 Prompt 框架 ---
# [修正] 確保從 prompts.py 和 etf_rules.py 導入最新的變數
from etf_rules import ETF_PROMPT_FRAMEWORK
from prompts import STOCK_PROMPT_FRAMEWORK, get_prompt_templates

# --- 專案說明 ---
# 這個應用程式是一個 AI 驅動的個人化投資組合建構與分析系統。
# 核心功能是利用一個詳細的「台股投資組合風險偏好定義規則」框架，
# 結合大型語言模型 (LLM)，為使用者生成符合其風險偏好與投資目標的台股投資組合建議，
# 支援純個股、純 ETF 以及混合型投資組合。

# --- Google API 金鑰設定 ---
try:
    # 這是從 Streamlit Secrets 讀取金鑰的安全作法
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except (KeyError, Exception) as e:
    st.error("錯誤：請確認你的 Google API 金鑰已在 `.streamlit/secrets.toml` 中正確設定。")
    st.info("設定教學：在專案資料夾中建立 `.streamlit` 資料夾，並在其中新增 `secrets.toml` 檔案，內容為：`GOOGLE_API_KEY = \"你的金鑰\"`")
    st.stop()

# --- RAG 核心邏輯 ---

def get_llm_chain(prompt_template):
    """建立一個 LLMChain 來處理我們的請求。"""
    # 設定模型，並指定回傳格式為 JSON
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest",
                                 temperature=0.2,
                                 model_kwargs={"response_format": {"type": "json_object"}})
    prompt = PromptTemplate.from_template(prompt_template)
    chain = LLMChain(llm=model, prompt=prompt)
    return chain

def _clean_and_parse_json(raw_text: str):
    """清理並解析 LLM 的 JSON 輸出，增強穩定性。"""
    # 優先使用正規表達式尋找被 ```json ... ``` 包裹的區塊
    match = re.search(r"```(json)?\s*({.*?})\s*```", raw_text, re.DOTALL)
    if match:
        clean_text = match.group(2)
    else:
        # 如果找不到，則退回使用大括號尋找 JSON 物件
        start_index = raw_text.find('{')
        end_index = raw_text.rfind('}')
        if start_index != -1 and end_index != -1 and end_index > start_index:
            clean_text = raw_text[start_index:end_index+1]
        else:
            # 如果連大括號都找不到，就直接使用原始文字
            clean_text = raw_text
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError as e:
        st.error("JSON 解析失敗，即使在清理後也是如此。")
        st.write("以下是 AI 回傳的原始文字，這可能不是有效的 JSON：")
        st.code(raw_text, language="text")
        raise e

# --- 報告生成與可視化 ---

def generate_portfolio(portfolio_type, risk_profile, investment_amount):
    """根據組合類型生成投資報告"""
    
    # [修正] 從 prompts.py 檔案動態獲取模板，保持主程式乾淨
    prompt_templates = get_prompt_templates()
    prompt_template = prompt_templates[portfolio_type]
    chain = get_llm_chain(prompt_template)
    today_str = datetime.now().strftime("%Y年%m月%d日")
    
    input_data = {
        "stock_rules": STOCK_PROMPT_FRAMEWORK,
        "etf_rules": ETF_PROMPT_FRAMEWORK, 
        "risk_profile": risk_profile,
        "investment_amount": f"{investment_amount:,.0f}",
        "current_date": today_str
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
    
    metric_labels = {
        'beta': "Beta 值",
        'annual_volatility': "年化波動率",
        'sharpe_ratio': "夏普比率",
        'hhi_index': "HHI 集中度"
    }
    
    cols = st.columns(len(metrics))
    for i, (key, value) in enumerate(metrics.items()):
        label = metric_labels.get(key, key.replace('_', ' ').title())
        # 確保 HHI 指數顯示為整數
        if key == 'hhi_index':
            try:
                value = f"{float(value):.0f}"
            except (ValueError, TypeError):
                value = str(value)
        cols[i].metric(label, value)

    st.write("---")

    # 根據報告類型，準備 DataFrame
    if 'core_holdings' in report_data: # 混合型
        core_df = pd.DataFrame(report_data['core_holdings'])
        core_df['類型'] = '核心 (ETF)'
        sat_df = pd.DataFrame(report_data['satellite_holdings'])
        sat_df['類型'] = '衛星 (個股)'
        df = pd.concat([core_df, sat_df], ignore_index=True)
        st.subheader("視覺化分析：整體資產配置")
    else: # 純個股或純 ETF
        df = pd.DataFrame(report_data['holdings'])
        st.subheader("視覺化分析")

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
        # 智慧判斷要用哪個欄位來畫長條圖
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
                x=grouped[group_col],
                y=grouped['weight'],
                text=(grouped['weight']*100).apply(lambda x: f'{x:.1f}%'),
                textposition='auto',
            )])
            fig_bar.update_layout(
                title_text=chart_title,
                xaxis_title=None,
                yaxis_title="權重",
                yaxis_tickformat='.0%',
                margin=dict(l=0, r=0, t=40, b=0)
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("此投資組合無適用的分類可供繪製長條圖。")

    st.write("---")
    
    st.subheader("📝 詳細持股與資金計畫")

    display_cols = ['ticker', 'name']
    if 'industry' in df.columns and df['industry'].notna().any():
        display_cols.append('industry')
    if 'etf_type' in df.columns and df['etf_type'].notna().any():
        display_cols.append('etf_type')
        
    display_cols.extend(['權重 (%)', '資金分配 (TWD)', 'rationale'])
    
    final_cols = [col for col in display_cols if col in df.columns]

    st.dataframe(
        df[final_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "權重 (%)": st.column_config.ProgressColumn(
                "權重 (%)", format="%.2f%%", min_value=0, max_value=100,
            ),
            "資金分配 (TWD)": st.column_config.NumberColumn(
                "資金分配 (TWD)", format="NT$ %'d"
            ),
            "rationale": st.column_config.TextColumn("簡要理由", width="large")
        }
    )

def handle_follow_up_question(question, context):
    """處理後續問題"""
    prompt_template = """
    你是一位專業的台灣股市投資組合經理。使用者已經收到你先前建立的投資組合報告，現在他有後續問題。
    請根據你先前提供的報告內容，以及使用者的問題，提供簡潔、專業的回答。
    **先前報告的內容摘要 (JSON):**
    {context}
    **使用者的問題:**
    {question}
    請直接回答使用者的問題。
    """
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.5)
    prompt = PromptTemplate.from_template(prompt_template)
    chain = LLMChain(llm=model, prompt=prompt)

    response = chain.invoke({"context": json.dumps(context, ensure_ascii=False), "question": question})
    return response['text']


# --- 建立使用者介面 (UI) ---

st.set_page_config(page_title="AI 投資組合建構系統", layout="wide")
st.title("💡 AI 個人化投資組合建構與分析系統")
st.markdown("本系統採用專業風險框架，由 AI 為您量身打造專屬的**純個股、純 ETF** 或 **核心-衛星混合型** 台股投資組合。")

if 'portfolio_generated' not in st.session_state:
    st.session_state.portfolio_generated = False
if 'report_data' not in st.session_state:
    st.session_state.report_data = None
if 'messages' not in st.session_state:
    st.session_state.messages = []

# --- 輸入介面 ---
with st.sidebar:
    st.header("👤 您的投資設定")
    portfolio_type_input = st.radio(
        "1. 請選擇投資組合類型",
        ("純個股", "純 ETF", "混合型"),
        index=0,
        captions=("僅含個股", "僅含 ETF", "ETF 為核心，個股為衛星")
    )
    risk_profile_input = st.selectbox(
        "2. 請選擇您的風險偏好", 
        ('積極型', '穩健型', '保守型'), 
        index=0, 
        help="積極型追求高回報；穩健型平衡風險與回報；保守型注重資本保值。"
    )
    investment_amount_input = st.number_input(
        "3. 請輸入您預計投入的總資金 (新台幣)", 
        min_value=10000, 
        value=100000, 
        step=10000
    )
    analyze_button = st.button("🚀 生成我的投資組合", type="primary", use_container_width=True)
    st.info("免責聲明：本系統僅為AI輔助分析工具，所有資訊與建議僅供參考，不構成任何投資決策的依據。投資有風險，請謹慎評估。")

# --- 主畫面顯示區 ---
if analyze_button:
    st.session_state.messages = []
    
    with st.spinner(f"正在為您這位「{risk_profile_input}」投資者建構專屬的【{portfolio_type_input}】投資組合..."):
        try:
            report = generate_portfolio(portfolio_type_input, risk_profile_input, investment_amount_input)
            st.session_state.report_data = report
            st.session_state.portfolio_generated = True
        except json.JSONDecodeError:
            st.error("AI 回應的格式無法被正確解析，請檢查上方由系統提供的詳細錯誤資訊。")
            st.session_state.portfolio_generated = False
        except Exception as e:
            st.error(f"分析過程中發生未預期的錯誤！")
            st.exception(e)
            st.session_state.portfolio_generated = False

if st.session_state.portfolio_generated:
    display_report(st.session_state.report_data, investment_amount_input)
    
    st.write("---")
    st.subheader("💬 提問與互動調整")
    st.info("對這個投資組合有任何疑問嗎？或者想做些微調？請在下方提出您的問題。")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("例如：為什麼選擇 0050？ 或者 可以把半導體個股換成別的嗎？"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.spinner("AI 正在思考中..."):
            response = handle_follow_up_question(prompt, st.session_state.report_data)
            st.session_state.messages.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                st.markdown(response)
else:
    st.info("請在左側側邊欄設定您的投資偏好與資金，然後點擊按鈕開始。")

