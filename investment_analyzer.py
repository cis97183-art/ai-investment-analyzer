import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from langchain.chains import LLMChain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
import os
from urllib.parse import quote

# --- 專案說明 ---
# 這個應用程式是一個AI驅動的個人化投資建議分析報告系統。
# 核心功能是利用RAG（Retrieval-Augmented Generation）技術，
# 結合即時的股價資訊和市場新聞，為使用者提供針對其風險偏好的投資分析。

# --- Google API 金鑰設定 ---
try:
    # 使用 Streamlit secrets 來安全地讀取金鑰
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except (KeyError, Exception) as e:
    st.error("錯誤：請確認你的 Google API 金鑰已在 `.streamlit/secrets.toml` 中正確設定。")
    st.info("設定教學：在專案資料夾中建立 `.streamlit` 資料夾，並在其中新增 `secrets.toml` 檔案，內容為：`GOOGLE_API_KEY = \"你的金鑰\"`")
    st.stop() # 如果金鑰設定失敗，則停止執行

# --- 第二步：資料擷取模組 ---

@st.cache_data(ttl=600) # 快取10分鐘，避免重複請求
def get_stock_data(ticker):
    """使用 yfinance 獲取指定股票的資料。"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        # 驗證 yfinance 是否回傳了有效的資料
        if not info or info.get('regularMarketPrice') is None:
            long_name = info.get('longName', ticker) # 嘗試獲取公司名稱
            st.error(f"無法從 yfinance 獲取 '{long_name}' ({ticker}) 的完整即時資訊，請確認股票代碼是否正確（台股上市請輸入如 2330）。")
            return None, None
        hist = stock.history(period="1y")
        return info, hist
    except Exception as e:
        st.error(f"抓取股票資料時發生錯誤：{e}")
        return None, None

@st.cache_data(ttl=1800) # 快取30分鐘
def get_market_news(query):
    """從鉅亨網爬取與指定公司相關的新聞標題。"""
    try:
        encoded_query = quote(query)
        url = f"https://news.cnyes.com/search?keyword={encoded_query}"
        # 使用 headers 模擬瀏覽器行為，增加成功率
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10) # 設定10秒超時
        response.raise_for_status() # 如果請求失敗，會拋出異常
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 尋找新聞連結的 'a' 標籤
        news_items = soup.find_all('a', href=lambda href: href and href.startswith('/news/id/'), limit=5)
        
        news_list = []
        for item in news_items:
            # 在 'a' 標籤下尋找標題 'h3'
            title_tag = item.find('h3')
            if title_tag:
                title = title_tag.text.strip()
                news_list.append(f"標題：{title}\n摘要：(請AI自行根據標題總結內容)\n")
        
        return "\n".join(news_list) if news_list else "找不到相關新聞。"
    except Exception as e:
        st.warning(f"爬取市場新聞時發生錯誤，將僅根據股價數據分析：{e}")
        return "無法獲取市場新聞。"

# --- RAG 核心邏輯 ---

def get_llm_chain():
    """建立一個 LLMChain 來處理我們的請求。"""
    prompt_template = """
    你是一位專業的台股投資顧問。請根據以下提供的上下文資訊，以繁體中文回答問題。
    你的分析需要嚴謹、客觀，並且要明確地結合使用者的風險偏好。

    上下文資訊:
    1. **公司基本資料與股價**: 
    {context}
    2. **相關市場新聞**: 
    {news}

    使用者的問題:
    - **投資標的**: {ticker}
    - **風險偏好**: {risk_profile}
    - **具體問題**: {question}

    你的任務是生成一份包含以下部分的個人化投資分析報告：
    1.  **公司前景分析**：根據公司資料和最新新聞，分析公司的未來潛力。
    2.  **股價趨勢評估**：簡要評論目前的股價位置（例如：相對高點、低點、盤整）。
    3.  **風險評估**：指出潛在的投資風險，特別是新聞中可能隱含的利空消息。
    4.  **個人化投資建議**：根據使用者的「{risk_profile}」風險偏好，給出明確、可操作的投資策略建議。
    
    請以專業、條理分明的格式呈現報告。
    """
    
    # --- *** 使用最穩定通用的 gemini-1.0-pro 模型 *** ---
    model = ChatGoogleGenerativeAI(model="gemini-1.0-pro", temperature=0.3)
    
    prompt = PromptTemplate(template=prompt_template, 
                            input_variables=["context", "news", "ticker", "risk_profile", "question"])
    chain = LLMChain(llm=model, prompt=prompt)
    return chain

# --- 第五步：報告生成與可視化 ---

def generate_report(ticker, risk_profile, info, hist, news):
    """生成完整的分析報告。"""
    st.subheader(f"📈 對 {info.get('longName', ticker)} 的投資分析報告")

    question = f"請為一位「{risk_profile}」的投資者，分析 {info.get('longName', ticker)} 是否值得投資，並提供具體建議。"
    
    context_str = f"""
    公司名稱: {info.get('longName', 'N/A')}
    產業: {info.get('industry', 'N/A')}
    市值: {info.get('marketCap', 'N/A')}
    目前股價: {info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))}
    52週高點: {info.get('fiftyTwoWeekHigh', 'N/A')}
    52週低點: {info.get('fiftyTwoWeekLow', 'N/A')}
    P/E Ratio (本益比): {info.get('trailingPE', 'N/A')}
    股息殖利率: {info.get('dividendYield', 'N/A')}
    """

    chain = get_llm_chain()
    
    input_data = {
        'context': context_str,
        'news': news,
        'ticker': ticker,
        'risk_profile': risk_profile,
        'question': question
    }
    
    # 呼叫 LLMChain
    response = chain.invoke(input_data)
    
    st.write("---")
    st.subheader("🤖 AI 智能分析")
    st.write(response['text'])
    st.write("---")

    st.subheader("📊 關鍵財務數據")
    current_price = info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))
    key_data = {
        "指標": ["目前價格", "52週高點", "52週低點", "市值", "本益比(P/E)", "股息殖利率"],
        "數值": [
            current_price,
            info.get('fiftyTwoWeekHigh', 'N/A'),
            info.get('fiftyTwoWeekLow', 'N/A'),
            f"{info.get('marketCap', 0)/1e8:.2f} 億" if info.get('marketCap') else 'N/A',
            f"{info.get('trailingPE', 'N/A'):.2f}" if isinstance(info.get('trailingPE'), float) else 'N/A',
            f"{info.get('dividendYield', 0)*100:.2f}%" if isinstance(info.get('dividendYield'), float) else 'N/A'
        ]
    }
    st.dataframe(pd.DataFrame(key_data), use_container_width=True)

    st.subheader("📉 近一年股價走勢圖")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(hist.index, hist['Close'], label='收盤價')
    ax.set_title(f'{info.get("longName", ticker)} Price History')
    ax.set_xlabel('日期')
    ax.set_ylabel('股價 (TWD)')
    ax.grid(True)
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)

# --- 第六步：建立使用者介面 (UI) ---

st.set_page_config(page_title="AI 投資分析報告系統", layout="wide")
st.title("💡 AI 個人化投資建議分析報告系統")
st.markdown("本系統使用 RAG 技術，結合即時股價與新聞數據，為您生成個人化的投資分析報告。")

col1, col2 = st.columns([1, 2])

with col1:
    st.header("請輸入您的需求")
    ticker_input = st.text_input("請輸入台股代碼 (例如: 2330)", "2330")
    risk_profile_input = st.selectbox("請選擇您的風險偏好", ('保守型', '穩健型', '積極型'))
    analyze_button = st.button("🚀 生成分析報告")

with col2:
    if analyze_button:
        if not ticker_input:
            st.warning("請輸入股票代碼。")
        else:
            with st.spinner(f"正在分析 {ticker_input}，請稍候..."):
                try:
                    # 自動為台股代碼加上後綴 .TW
                    ticker_to_fetch = ticker_input.strip()
                    # 判斷是否為台灣上市股票代碼 (4位數字)，並自動加上 .TW 後綴
                    if ticker_to_fetch.isdigit() and len(ticker_to_fetch) == 4:
                        ticker_to_fetch += ".TW"
                        st.info(f"偵測到台股上市代碼，自動轉換為 yfinance 格式: {ticker_to_fetch}")

                    # 使用處理過的代碼抓取資料
                    stock_info, stock_hist = get_stock_data(ticker_to_fetch)
                    
                    if stock_info and not stock_hist.empty:
                        market_news = get_market_news(stock_info.get('longName', ticker_input))
                        # 將原始輸入的代碼傳遞給報告函式，以維持顯示一致性
                        generate_report(ticker_input, risk_profile_input, stock_info, stock_hist, market_news)
                except Exception as e:
                    # 在網頁上顯示更詳細的錯誤，方便除錯
                    st.error(f"分析過程中發生未預期的錯誤！")
                    st.exception(e)

st.sidebar.info("免責聲明：本系統僅為AI輔助分析工具，所有資訊與建議僅供參考，不構成任何投資決策的依據。投資有風險，請謹慎評估。")

