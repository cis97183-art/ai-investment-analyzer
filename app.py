# app.py (最終整合版)

import streamlit as st
import pandas as pd
import plotly.express as px

# 匯入專案的核心模組
import data_loader
import screener
import investment_analyzer
import ai_helper
import config

# --- 1. 頁面設定 (Page Configuration) ---
# 設定瀏覽器頁籤的標題、圖示，並採用寬版佈局
st.set_page_config(
    page_title="機構級投資組合建構器",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 資料載入與快取 (Data Loading & Caching) ---
# @st.cache_data 是 Streamlit 的一個強大功能，它會將函式回傳的結果快取起來。
# 只要輸入參數不變，下次執行時會直接讀取快取，避免耗時的重複資料載入。
@st.cache_data(show_spinner="正在載入市場資料...")
def load_data():
    """
    載入並準備所有市場資料。
    """
    try:
        master_df = data_loader.load_and_prepare_data(
            config.LISTED_STOCK_PATH,
            config.OTC_STOCK_PATH,
            config.ETF_PATH
        )
        return master_df
    except Exception as e:
        # 如果載入過程中發生任何錯誤，顯示錯誤訊息並回傳 None
        st.error(f"載入資料時發生錯誤: {e}")
        return None

# --- 3. 初始化 Session State ---
# Session State 是 Streamlit 用來在使用者互動之間保存變數的地方。
# 例如，使用者點擊按鈕後，計算出來的投資組合會被存放在 st.session_state 中。
if 'master_df' not in st.session_state:
    st.session_state.master_df = load_data()
if "messages" not in st.session_state:
    st.session_state.messages = [] # 儲存 AI 聊天紀錄
if "portfolio_df" not in st.session_state:
    st.session_state.portfolio_df = None # 儲存計算出的投資組合
if "candidate_pools" not in st.session_state:
    st.session_state.candidate_pools = None # 儲存候選標的池
if "hhi" not in st.session_state:
    st.session_state.hhi = 0.0 # 儲存 HHI 指數

# --- 4. 側邊欄使用者輸入 (Sidebar for User Inputs) ---
with st.sidebar:
    st.image("https://storage.googleapis.com/gweb-uniblog-publish-prod/images/gemini_update_blog_announcement_animation_2.gif", use_column_width=True)
    st.title("投資策略參數")
    
    # 【核心簡化】直接使用中文作為選項，因為 portfolio_rules.py 也已更新為使用中文鍵值
    risk_preference = st.selectbox(
        label="1. 選擇您的風險偏好",
        options=["保守型", "穩健型", "積極型"],
        index=1, # 預設選項為 "穩健型"
        help="決定了篩選標的與資產配置的核心邏輯。"
    )

    portfolio_type = st.selectbox(
        label="2. 選擇組合類型",
        options=["純個股", "純ETF", "混合型"],
        index=2, # 預設選項為 "混合型"
        help="決定了投資組合中包含的資產類型。"
    )

    analyze_button = st.button("🚀 開始建構投資組合", type="primary", use_container_width=True)

# --- 5. 主面板 (Main Panel) ---
st.title("📈 機構級投資組合建構與優化策略")
st.markdown("---")

# 檢查資料是否成功載入
if st.session_state.master_df is None:
    st.warning("資料未能成功載入，請檢查 `config.py` 中的檔案路徑設定後重試。")
else:
    # --- 6. 核心邏輯執行 ---
    # 當使用者點擊按鈕時，才執行分析
    if analyze_button:
        with st.spinner("正在執行機構級篩選與建構策略..."):
            # 步驟一：呼叫 screener 產生所有可能的標的池
            asset_pools = screener.generate_asset_pools(st.session_state.master_df)
            # 步驟二：呼叫 investment_analyzer 根據使用者選擇建立最終組合
            portfolio_df, candidate_pools = investment_analyzer.build_portfolio(
                asset_pools, 
                risk_preference, 
                portfolio_type
            )
            
            # 儲存計算結果到 Session State
            st.session_state.portfolio_df = portfolio_df
            st.session_state.candidate_pools = candidate_pools
            
            # 計算 HHI 指數
            if portfolio_df is not None and not portfolio_df.empty:
                weights = portfolio_df['權重(%)'].values / 100
                st.session_state.hhi = sum([w**2 for w in weights])
            else:
                st.session_state.hhi = 0.0
        
        st.success("投資組合建構完成！")

    # --- 7. 結果顯示 ---
    # 只有在 portfolio_df 存在且不為空時，才顯示結果區塊
    if st.session_state.portfolio_df is not None and not st.session_state.portfolio_df.empty:
        st.subheader(f"您的客製化「{risk_preference} - {portfolio_type}」投資組合")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            st.metric(label="標的數量", value=f"{len(st.session_state.portfolio_df)} 支")
        with col2:
            st.metric(label="HHI 集中度指數", value=f"{st.session_state.hhi:.4f}", 
                      help="指數越低代表越分散。通常低於 0.25 被認為是分散的。")
        
        # 繪製圓餅圖
        with col3:
            fig = px.pie(st.session_state.portfolio_df, values='權重(%)', names='名稱', 
                         title='投資組合權重分配', hole=.3)
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
            
        st.dataframe(st.session_state.portfolio_df[['代碼', '名稱', '產業別', '權重(%)', '資產類別']])

        # 顯示候選標的池
        if st.session_state.candidate_pools:
            st.markdown("---")
            st.subheader("觀察名單 (候選標的池)")
            for pool_name, pool_df in st.session_state.candidate_pools.items():
                with st.expander(f"查看完整的「{pool_name}」候選標的池 ({len(pool_df)} 筆)"):
                    st.dataframe(pool_df)

        # --- 8. AI 智慧助理 ---
        st.markdown("---")
        st.subheader("🤖 AI 智慧助理")
        
        if "GOOGLE_API_KEY" not in st.secrets or not st.secrets["GOOGLE_API_KEY"]:
            st.warning("尚未在 secrets.toml 中設定 Google API Key，AI 助理功能無法使用。")
        else:
            # 顯示歷史訊息
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
            # 接收使用者新輸入
            if prompt := st.chat_input("對這個投資組合有什麼問題嗎？"):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    with st.spinner("AI 正在思考中..."):
                        portfolio_context = {
                            f"{risk_preference} - {portfolio_type}": st.session_state.portfolio_df
                        }
                        response = ai_helper.get_ai_response(
                            portfolios_dict=portfolio_context,
                            user_question=prompt,
                            chat_history=st.session_state.messages
                        )
                        st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

    # 如果點擊按鈕後，沒有產生任何投資組合，則顯示錯誤訊息
    elif analyze_button:
        st.error("篩選條件過於嚴格，或市場上暫無符合所有規則的標的，無法建立投資組合。請嘗試調整風險偏好或組合類型。")
