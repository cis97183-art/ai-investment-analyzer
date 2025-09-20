# app.py (狀態管理優化版)

import streamlit as st
import pandas as pd
import plotly.express as px
import config
import data_loader
import screener
import investment_analyzer
import ai_helper

# --- 頁面設定與狀態初始化 ---
st.set_page_config(page_title="AI 投資組合分析師", page_icon="🤖", layout="wide")

# 在腳本最上方初始化 session_state，確保它們存在
if "portfolios" not in st.session_state:
    st.session_state.portfolios = {}
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 側邊欄 (使用者輸入) ---
st.sidebar.header("請選擇您的偏好")
risk_profile = st.sidebar.selectbox("1. 您的風險偏好是？", ("保守型", "穩健型", "積極型"), index=1)
portfolio_type = st.sidebar.selectbox("2. 您想建立的組合類型是？", ("純個股", "純 ETF", "混合型"), index=0)
total_investment = st.sidebar.number_input(
    "3. 請輸入您的總投資金額 (元)", 
    min_value=10000, value=1000000, step=10000
)

# --- 按鈕：只負責觸發分析與更新狀態 ---
if st.sidebar.button("🚀 開始分析"):
    # 清空舊的分析結果與聊天記錄
    st.session_state.portfolios = {}
    st.session_state.messages = []
    
    with st.spinner("正在讀取與清理最新市場資料..."):
        master_df = data_loader.load_and_prepare_data(
            listed_path=config.LISTED_STOCK_PATH,
            otc_path=config.OTC_STOCK_PATH,
            etf_path=config.ETF_PATH
        )
    
    if master_df is not None:
        st.session_state.master_df = master_df # 將 master_df 也存入 state
        with st.spinner(f"正在為您篩選【{risk_profile}】的標的..."):
            screened_pool = screener.screen_assets(
                data_df=master_df, risk_profile=risk_profile, target_count=config.TARGET_ASSET_COUNT
            )
            st.session_state.screened_pool = screened_pool # 儲存篩選結果
    else:
        st.error("資料載入失敗，請檢查檔案路徑或檔案內容。")

# --- 主頁面顯示區：根據 session_state 的內容來決定顯示什麼 ---

# 只有當 screened_pool 在 session_state 中且不為空時，才顯示報告區
if "screened_pool" in st.session_state and not st.session_state.screened_pool.empty:
    st.success("資料準備完成！")
    
    # 顯示篩選池
    st.subheader(f"【{risk_profile}】階層式篩選標的池 (共 {len(st.session_state.screened_pool)} 支)")
    st.dataframe(st.session_state.screened_pool[['代號', '名稱', '產業別', '篩選層級', '市值(億)', '一年(β)', '一年(σ年)']].head(20))
    
    # 生成並顯示投資組合報告
    strategies_to_run = ['平均權重', '夏普比率優化', '排名加權'] if portfolio_type == '純個股' else ['平均權重']
    for strategy in strategies_to_run:
        final_portfolio = investment_analyzer.build_portfolio(
            screened_assets=st.session_state.screened_pool, portfolio_type=portfolio_type,
            optimization_strategy=strategy, master_df=st.session_state.master_df
        )
        if final_portfolio is not None:
            final_portfolio['權重數值'] = final_portfolio['建議權重'].str.replace('%', '', regex=False).astype(float) / 100
            final_portfolio['配置金額(元)'] = (total_investment * final_portfolio['權重數值']).map('{:,.0f}'.format)
            
            st.subheader(f"✅ 您的【{portfolio_type} ({strategy})】投資組合建議")
            st.dataframe(final_portfolio[['代號', '名稱', '資產類別', '建議權重', '配置金額(元)']])
            
            col1, col2 = st.columns(2)
            with col1:
                fig_pie = px.pie(final_portfolio, values='權重數值', names='名稱', title='資產配置圓餅圖')
                st.plotly_chart(fig_pie, use_container_width=True)
            with col2:
                industry_weights = final_portfolio.groupby('產業別')['權重數值'].sum().reset_index()
                fig_bar = px.bar(industry_weights, x='產業別', y='權重數值', title='產業配置直方圖', labels={'權重數值':'權重總和'})
                st.plotly_chart(fig_bar, use_container_width=True)

            st.session_state.portfolios[strategy] = final_portfolio
    
    # 當報告生成後，檢查並加入 AI 的第一則歡迎訊息
    if not st.session_state.messages:
        st.session_state.messages.append({"role": "assistant", "content": "您的客製化投資組合報告已生成，請問針對這些報告內容，有什麼想深入了解的嗎？"})

# 如果沒有報告，顯示預設提示
elif "screened_pool" not in st.session_state:
    st.info("請在左方側邊欄設定您的偏好，然後點擊「開始分析」。")

st.divider()

# --- 聊天室介面 ---
st.subheader("🤖 AI 投資組合問答")

# 顯示歷史對話訊息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 使用 st.chat_input 建立固定在底部的輸入框
if prompt := st.chat_input("針對您的報告提問..."):
    if not st.session_state.portfolios:
        st.warning("請先點擊左側的「開始分析」來生成報告，才能開始問答喔！")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("AI 正在思考中..."):
                response = ai_helper.get_ai_response(st.session_state.portfolios, prompt)
                if response:
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})