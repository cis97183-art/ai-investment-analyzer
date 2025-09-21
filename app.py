import streamlit as st
import pandas as pd
import plotly.express as px

# 匯入您專案的其他模組
import data_loader
import screener
import investment_analyzer
import ai_helper
import config  # 【修正點 1】匯入 config 模組以讀取檔案路徑

# --- 1. 頁面設定 (Page Configuration) ---
st.set_page_config(
    page_title="機構級投資組合建構器",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 資料載入與快取 (Data Loading & Caching) ---
@st.cache_data(show_spinner="正在載入市場資料...")
def load_data():
    """
    載入並準備所有市場資料，利用 Streamlit 快取避免重複讀取。
    """
    try:
        # 【修正點 1】將 config 中的檔案路徑傳入函式
        master_df = data_loader.load_and_prepare_data(
            config.LISTED_STOCK_PATH,
            config.OTC_STOCK_PATH,
            config.ETF_PATH
        )
        return master_df
    except FileNotFoundError as e:
        st.error(f"錯誤：找不到資料檔案 {e.filename}。請確認 config.py 中的路徑設定是否正確。")
        return None
    except Exception as e:
        st.error(f"載入資料時發生未知錯誤: {e}")
        return None

# --- 3. 初始化 Session State ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = load_data()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "portfolio_df" not in st.session_state:
    st.session_state.portfolio_df = None
if "candidate_pools" not in st.session_state:
    st.session_state.candidate_pools = None
if "hhi" not in st.session_state:
    st.session_state.hhi = 0.0

# --- 4. 側邊欄使用者輸入 (Sidebar for User Inputs) ---
with st.sidebar:
    st.image("https://storage.googleapis.com/gweb-uniblog-publish-prod/images/gemini_update_blog_announcement_animation_2.gif", use_column_width=True)
    st.title("投資策略參數")
    
    # 【修正點 2】建立選項的顯示名稱與內部鍵值的對照字典
    RISK_OPTIONS = {"保守型": "Conservative", "穩健型": "Moderate", "積極型": "Aggressive"}
    TYPE_OPTIONS = {"純個股": "Stocks", "純ETF": "ETF", "混合型": "Hybrid"}

    # 【修正點 2】移除 'keys' 參數，並使用 .keys() 取得顯示選項
    selected_risk_display = st.selectbox(
        label="1. 選擇您的風險偏好",
        options=RISK_OPTIONS.keys(),
        index=1,
        help="決定了篩選標的與資產配置的核心邏輯。"
    )
    # 根據選擇的中文顯示名稱，取得對應的英文鍵值
    risk_preference = RISK_OPTIONS[selected_risk_display]

    selected_type_display = st.selectbox(
        label="2. 選擇組合類型",
        options=TYPE_OPTIONS.keys(),
        index=2,
        help="決定了投資組合中包含的資產類型。"
    )
    # 根據選擇的中文顯示名稱，取得對應的英文鍵值
    portfolio_type = TYPE_OPTIONS[selected_type_display]

    analyze_button = st.button("🚀 開始建構投資組合", type="primary", use_container_width=True)

# --- 5. 主面板 (Main Panel) ---
st.title("📈 機構級投資組合建構與優化策略")
st.markdown("---")

if st.session_state.master_df is None:
    st.warning("資料未能成功載入，請檢查設定後重試。")
else:
    # --- 6. 核心邏輯執行 ---
    if analyze_button:
        with st.spinner("正在執行機構級篩選與建構策略..."):
            asset_pools = screener.generate_asset_pools(st.session_state.master_df)
            portfolio_df, candidate_pools = investment_analyzer.build_portfolio(
                asset_pools, 
                risk_preference, 
                portfolio_type
            )
            if not portfolio_df.empty:
                weights = portfolio_df['權重(%)'].values / 100
                st.session_state.hhi = sum([w**2 for w in weights])
            st.session_state.portfolio_df = portfolio_df
            st.session_state.candidate_pools = candidate_pools
        st.success("投資組合建構完成！")

    # --- 7. 結果顯示 ---
    if st.session_state.portfolio_df is not None and not st.session_state.portfolio_df.empty:
        # 使用中文顯示名稱
        st.subheader(f"您的客製化「{selected_risk_display} - {selected_type_display}」投資組合")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            st.metric(label="標的數量", value=f"{len(st.session_state.portfolio_df)} 支")
        with col2:
            st.metric(label="HHI 集中度指數", value=f"{st.session_state.hhi:.4f}", 
                      help="指數越低代表越分散。通常低於 0.25 被認為是分散的。")
        
        fig = px.pie(st.session_state.portfolio_df, values='權重(%)', names='名稱', title='投資組合權重分配', hole=.3)
        fig.update_traces(textposition='inside', textinfo='percent+label')
        with col3:
            st.plotly_chart(fig, use_container_width=True)
            
        st.dataframe(st.session_state.portfolio_df[['代碼', '名稱', '產業別', '權重(%)', '資產類別']])

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
            api_key = st.secrets["GOOGLE_API_KEY"]
            ai_helper.initialize_gemini(api_key)
            
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if prompt := st.chat_input("對這個投資組合有什麼問題嗎？"):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    with st.spinner("AI 正在思考中..."):
                        response = ai_helper.get_ai_response(
                            portfolio_df=st.session_state.portfolio_df,
                            user_query=prompt,
                            chat_history=st.session_state.messages
                        )
                        st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

    elif analyze_button and (st.session_state.portfolio_df is None or st.session_state.portfolio_df.empty):
        st.error("篩選條件過於嚴格，或市場上暫無符合所有規則的標的，無法建立投資組合。請嘗試調整風險偏好或組合類型。")
