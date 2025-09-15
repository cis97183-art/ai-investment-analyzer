import streamlit as st
import pandas as pd
import google.generativeai as genai
from langchain.chains import LLMChain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
import plotly.graph_objects as go
import json
from datetime import datetime
import re # 新增 re 模組

# --- 專案說明 ---
# 這個應用程式是一個 AI 驅動的個人化投資組合建構與分析系統。
# 核心功能是利用一個詳細的「台股投資組合風險偏好定義規則」框架，
# 結合大型語言模型 (LLM)，為使用者生成符合其風險偏好與投資目標的台股投資組合建議。

# --- Google API 金鑰設定 ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except (KeyError, Exception) as e:
    st.error("錯誤：請確認你的 Google API 金鑰已在 `.streamlit/secrets.toml` 中正確設定。")
    st.info("設定教學：在專案資料夾中建立 `.streamlit` 資料夾，並在其中新增 `secrets.toml` 檔案，內容為：`GOOGLE_API_KEY = \"你的金鑰\"`")
    st.stop()

# --- AI Prompt 框架 (核心規則) ---
# 將使用者提供的規則框架直接整合到 Prompt 中
PROMPT_FRAMEWORK = """
### 台股投資組合風險偏好定義規則 (AI Prompt Framework for Taiwan Market)

這是一套清晰、量化的規則，您必須嚴格遵守以根據三種核心投資者風險偏好（保守型、穩健型、積極型）生成或評估純台股投資組合。

| 規則維度 (Rule Dimension)      | 保守型 (Conservative)                                     | 穩健型 (Balanced)                                   | 積極型 (Aggressive)                                           | 規則說明 (Rule Description)                                                                          |
| ------------------------------ | --------------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **1. 主要投資目標** | 資本保值，追求穩定股利現金流與絕對報酬。                  | 追求資本長期溫和增值，兼顧風險控制。                | 追求資本最大化增長，願意承受較大波動以換取高額回報。          | 定義投資組合的最終目的，影響所有決策。                                                                 |
| **2. 投資組合 Beta 值** | 0.5 - 0.8                                                 | 0.8 - 1.1                                           | > 1.1                                                         | 相對於台灣加權指數 (TAIEX) 的波動性。這是衡量市場風險的核心指標。                                      |
| **3. 預期年化波動率 (標準差)** | 8% - 13%                                                  | 13% - 20%                                           | > 20%                                                         | 投資組合的總風險，衡量其淨值波動的劇烈程度 (台股波動性普遍高於美股)。                                    |
| **4. 目標夏普比率 (Sharpe Ratio)**| > 1.0                                                     | > 0.7                                               | > 0.5                                                         | 衡量「每一單位總風險，能換取多少超額報酬」，是評估投資組合效率的黃金標準。                             |
| **5. 分散化程度** |                                                           |                                                     |                                                               | 用以控制非系統性風險。                                                                                 |
| &nbsp;&nbsp;&nbsp; a) 投資組合集中度 (HHI) | < 500                                                     | 500 - 800                                           | > 800                                                         | 赫芬達爾-赫希曼指數 (HHI)。計算方式為組合中每支股票權重的平方總和 (權重以 % 為單位)。數值越低，代表持股越分散。 |
| &nbsp;&nbsp;&nbsp; b) 單一產業權重上限 | < 20%                                                     | < 30%                                               | < 40%                                                         | HHI 無法衡量產業集中度，此規則仍須保留。考量台股電子產業的高權重特性，適度放寬限制。                 |
| **6. 持股風格與特徵** |                                                           |                                                     |                                                               |                                                                                                        |
| &nbsp;&nbsp;&nbsp; a) 公司規模  | 大型股為主 (市值 > 2000億新台幣，如台灣50成分股)          | 大型、中型股為主 (市值 > 500億新台幣)               | 可包含中小型股與新創公司                                      | 大型公司通常經營較穩定、波動較低。                                                                     |
| &nbsp;&nbsp;&nbsp; b) 產業風格  | 側重防禦型產業 (如：金融、電信、公用事業、必需消費)       | 均衡配置核心電子股與傳產龍頭股。                    | 側重高成長電子股 (如：半導體、AI、IC設計) 與利基型傳產股。      | 產業的內在屬性決定了其在不同經濟週期下的表現。                                                         |
| &nbsp;&nbsp;&nbsp; c) 財務品質  | 高殖利率、低負債、穩定現金流的公司。                      | 兼具穩定盈利與營收成長潛力的公司。                  | 高營收增長、高毛利、願意為未來研發投入而犧牲短期利潤的公司。  | 財務指標直接反映了公司的健康狀況與經營策略。                                                           |
| **7. 市場板塊配置** | 以**集中市場(上市)**的台灣50、中型100成分股為主。         | 可適度納入**櫃買中心(上櫃)**的績優龍頭股。          | 可提高櫃買中心(上櫃)及創新板個股比重，捕捉更高成長潛力。      | 不同市場板塊代表不同的風險與成長機會。                                                                 |
"""

# --- RAG 核心邏輯 ---

def get_llm_chain(prompt_template):
    """建立一個 LLMChain 來處理我們的請求。"""
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest",
                                 temperature=0.2,
                                 model_kwargs={"response_format": {"type": "json_object"}}) # 要求模型回傳 JSON
    prompt = PromptTemplate.from_template(prompt_template)
    chain = LLMChain(llm=model, prompt=prompt)
    return chain

# --- 新增：更穩健的 JSON 解析函式 ---
def _clean_and_parse_json(raw_text: str):
    """
    清理從 LLM 獲得的原始文字輸出並將其解析為 JSON。
    此函式能處理常見的格式問題，例如 Markdown 程式碼區塊。
    """
    # 尋找被 ```json ... ``` 包圍的 JSON 內容
    match = re.search(r"```(json)?\s*({.*?})\s*```", raw_text, re.DOTALL)
    if match:
        clean_text = match.group(2)
    else:
        # 如果沒有找到 Markdown 區塊，則假設整個文字是一個類似 JSON 的字串
        # 並嘗試找到第一個 '{' 和最後一個 '}'
        start_index = raw_text.find('{')
        end_index = raw_text.rfind('}')
        if start_index != -1 and end_index != -1 and end_index > start_index:
            clean_text = raw_text[start_index:end_index+1]
        else:
            # 如果找不到清晰的 JSON 結構，則回退到原始文字
            clean_text = raw_text

    try:
        return json.loads(clean_text)
    except json.JSONDecodeError as e:
        # 如果解析仍然失敗，則在 Streamlit 介面提供更詳細的除錯資訊
        st.error("JSON 解析失敗，即使在清理後也是如此。")
        st.write("以下是 AI 回傳的原始文字，這可能不是有效的 JSON：")
        st.code(raw_text, language="text")
        # 重新引發異常，讓主流程可以捕獲它
        raise e

# --- 報告生成與可視化 ---

def generate_portfolio(risk_profile, investment_amount):
    """生成投資組合報告"""
    
    prompt_template = """
    你是一位專業的台灣股市投資組合經理。你的任務是根據我提供的「台股投資組合風險偏好定義規則」以及使用者的個人情況，為他量身打造一個純台股的投資組合。

    **你的工作流程:**
    1.  **嚴格遵守規則**: 詳細閱讀並嚴格遵循下方提供的「台股投資組合風險偏好定義規則」中關於 "{risk_profile}" 的所有量化與質化指標。
    2.  **建立投資組合**: 根據規則，挑選 5 到 8 支符合條件的台股（上市或上櫃公司），並為它們分配投資權重(權重總和必須為 100%)。
    3.  **計算與評估**: 估算你所建立的投資組合的整體 Beta 值、預期年化波動率、夏普比率及 HHI 指數。
    4.  **提供分析**: 撰寫一段簡潔的投資組合概述，說明此組合如何符合使用者的風險偏好。
    5.  **格式化輸出**: 將所有結果以指定的 JSON 格式回傳。你的輸出必須是"純粹"的 JSON 物件，不包含任何 Markdown 標記 (例如 ```json) 或其他說明文字。直接以 '{{' 開始，以 '}}' 結束。

    ---
    {rules}
    ---

    **使用者資訊:**
    - **風險偏好**: {risk_profile}
    - **預計投入資金 (新台幣)**: {investment_amount}

    **你的輸出必須是純粹的 JSON 格式，結構如下:**
    {{
      "summary": {{
        "title": "為{risk_profile}投資者設計的投資組合",
        "overview": "一段 150 字以內的投資組合概述，解釋這個組合的建構理念，以及它如何符合使用者的風險偏好。",
        "generated_date": "{current_date}"
      }},
      "portfolio_metrics": {{
        "beta": "<估算的整體 Beta 值，數字>",
        "annual_volatility": "<估算的預期年化波動率，字串，例如 '18%' 或 '> 20%'>",
        "sharpe_ratio": "<估算的夏普比率，數字>",
        "hhi_index": "<計算出的 HHI 指數，數字>"
      }},
      "holdings": [
        {{
          "ticker": "<股票代碼>",
          "name": "<公司名稱>",
          "industry": "<產業類別>",
          "weight": <投資權重，數字，例如 0.25 代表 25%>,
          "rationale": "<選擇這支股票的簡要理由 (50字以內)>"
        }},
        {{
          "ticker": "<股票代碼>",
          "name": "<公司名稱>",
          "industry": "<產業類別>",
          "weight": <投資權重，數字，例如 0.15 代表 15%>,
          "rationale": "<選擇這支股票的簡要理由 (50字以內)>"
        }}
      ]
    }}
    """
    
    chain = get_llm_chain(prompt_template)
    today_str = datetime.now().strftime("%Y年%m月%d日")
    
    input_data = {
        "rules": PROMPT_FRAMEWORK,
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
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("整體 Beta 值", metrics['beta'])
    col2.metric("預期年化波動率", metrics['annual_volatility'])
    col3.metric("目標夏普比率", metrics['sharpe_ratio'])
    col4.metric("持股集中度 (HHI)", f"{metrics['hhi_index']:.0f}")

    st.write("---")

    # 建立 DataFrame 並計算資金分配
    df = pd.DataFrame(report_data['holdings'])
    df['資金分配 (TWD)'] = (df['weight'] * investment_amount).round(0)
    df['權重 (%)'] = (df['weight'] * 100).round(2)
    
    # 圖表區
    st.subheader("視覺化分析")
    
    # 權重分配圖 (圓餅圖)
    fig_pie = go.Figure(data=[go.Pie(
        labels=df['name'], 
        values=df['weight'], 
        hole=.3,
        textinfo='percent+label',
        hoverinfo='label+percent+value',
        texttemplate='%{label}<br>%{percent:.1%}',
    )])
    fig_pie.update_layout(
        title_text='持股權重分配',
        showlegend=False
    )

    # 產業分佈圖 (長條圖)
    industry_grouped = df.groupby('industry')['weight'].sum().reset_index()
    fig_bar = go.Figure(data=[go.Bar(
        x=industry_grouped['industry'],
        y=industry_grouped['weight'],
        text=(industry_grouped['weight']*100).apply(lambda x: f'{x:.1f}%'),
        textposition='auto',
    )])
    fig_bar.update_layout(
        title_text='產業權重分佈',
        xaxis_title="產業類別",
        yaxis_title="權重",
        yaxis_tickformat='.0%'
    )

    chart1, chart2 = st.columns(2)
    with chart1:
        st.plotly_chart(fig_pie, use_container_width=True)
    with chart2:
        st.plotly_chart(fig_bar, use_container_width=True)

    st.write("---")
    
    # 詳細持股表格
    st.subheader("📝 詳細持股與資金計畫")
    st.dataframe(
        df[['ticker', 'name', 'industry', '權重 (%)', '資金分配 (TWD)', 'rationale']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "權重 (%)": st.column_config.ProgressColumn(
                "權重 (%)",
                format="%.2f%%",
                min_value=0,
                max_value=df['權重 (%)'].max(),
            ),
            "資金分配 (TWD)": st.column_config.NumberColumn(
                "資金分配 (TWD)",
                format="NT$ %'d"
            )
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
    # 移除 response_format for conversational text
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.5)
    prompt = PromptTemplate.from_template(prompt_template)
    chain = LLMChain(llm=model, prompt=prompt)

    response = chain.invoke({"context": json.dumps(context, ensure_ascii=False), "question": question})
    return response['text']


# --- 建立使用者介面 (UI) ---

st.set_page_config(page_title="AI 投資組合建構系統", layout="wide")
st.title("💡 AI 個人化投資組合建構與分析系統 (V4)")
st.markdown("本系統採用專業的風險偏好框架，由 AI 為您量身打造專屬的台股投資組合。")

# 初始化 session state
if 'portfolio_generated' not in st.session_state:
    st.session_state.portfolio_generated = False
if 'report_data' not in st.session_state:
    st.session_state.report_data = None
if 'messages' not in st.session_state:
    st.session_state.messages = []

# --- 輸入介面 ---
with st.sidebar:
    st.header("👤 您的投資設定")
    risk_profile_input = st.selectbox(
        "請選擇您的風險偏好", 
        ('積極型', '穩健型', '保守型'), 
        index=0, 
        help="積極型追求高回報；穩健型平衡風險與回報；保守型注重資本保值。"
    )
    investment_amount_input = st.number_input(
        "請輸入您預計投入的總資金 (新台幣)", 
        min_value=10000, 
        max_value=100000000, 
        value=100000, 
        step=10000,
        help="AI 將根據此金額計算每支股票的資金分配。"
    )
    analyze_button = st.button("🚀 生成我的投資組合", type="primary", use_container_width=True)
    st.info("免責聲明：本系統僅為AI輔助分析工具，所有資訊與建議僅供參考，不構成任何投資決策的依據。投資有風險，請謹慎評估。")

# --- 主畫面顯示區 ---
if analyze_button:
    st.session_state.messages = [] # 重置對話紀錄
    with st.spinner(f"正在為您這位「{risk_profile_input}」投資者建構專屬投資組合，請稍候..."):
        try:
            report = generate_portfolio(risk_profile_input, investment_amount_input)
            st.session_state.report_data = report
            st.session_state.portfolio_generated = True
        except json.JSONDecodeError:
            # 現在錯誤訊息主要由 _clean_and_parse_json 函式顯示，這裡可以顯示一個簡短的提示
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

    # 顯示對話紀錄
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 使用者輸入
    if prompt := st.chat_input("例如：為什麼選擇台積電？ 或者 可以把金融股換成別的嗎？"):
        # 將使用者問題加入對話紀錄
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 獲取 AI 回應
        with st.spinner("AI 正在思考中..."):
            response = handle_follow_up_question(prompt, st.session_state.report_data)
            # 將 AI 回應加入對話紀錄
            st.session_state.messages.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                st.markdown(response)

else:
    st.info("請在左側側邊欄設定您的投資偏好與資金，然後點擊按鈕開始。")


