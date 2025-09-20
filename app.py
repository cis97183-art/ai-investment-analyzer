# app.py (最終功能整合版)

import streamlit as st
import pandas as pd
import plotly.express as px  # 匯入 plotly
import config
import data_loader
import screener
import investment_analyzer
import ai_helper

# --- 頁面設定 ---
st.set_page_config(page_title="AI 投資組合分析師", page_icon="🤖", layout="wide")

st.title("🤖 AI 投資組合分析師")
st.write("根據您的風險偏好，從台股市場中篩選標的並建立客製化投資組合。")

# --- 側邊欄 ---
st.sidebar.header("請選擇您的偏好")

# *** 修正點 1: 調整側邊欄輸入順序 ***
risk_profile = st.sidebar.selectbox("1. 您的風險偏好是？", ("保守型", "穩健型", "積極型"), index=1)
portfolio_type = st.sidebar.selectbox("2. 您想建立的組合類型是？", ("純個股", "純 ETF", "混合型"), index=0)
total_investment = st.sidebar.number_input(
    "3. 請輸入您的總投資金額 (元)", 
    min_value=10000, 
    value=1000000, 
    step=10000,
    help="輸入您預計投入的總金額，報告將會計算每項資產的配置金額。"
)

if st.sidebar.button("🚀 開始分析"):
    # ... (資料讀取和篩選邏輯不變) ...
    with st.spinner("正在讀取與清理最新市場資料..."):
        master_df = data_loader.load_and_prepare_data(
            listed_path=config.LISTED_STOCK_PATH,
            otc_path=config.OTC_STOCK_PATH,
            etf_path=config.ETF_PATH
        )
    if master_df is None: st.error("資料載入失敗，請檢查檔案路徑或檔案內容。")
    else:
        st.success("資料準備完成！")
        with st.spinner(f"正在為您篩選【{risk_profile}】的標的..."):
            screened_pool = screener.screen_assets(data_df=master_df, risk_profile=risk_profile, target_count=config.TARGET_ASSET_COUNT)
        
        if screened_pool.empty:
            st.warning(f"在【{risk_profile}】的篩選條件下，找不到足夠的標的。")
        else:
            st.subheader(f"【{risk_profile}】階層式篩選標的池 (共 {len(screened_pool)} 支)")
            st.dataframe(screened_pool[['代號', '名稱', '產業別', '篩選層級', '市值(億)', '一年(β)', '一年(σ年)']].head(20))
            
            st.session_state.portfolios = {}
            strategies_to_run = ['平均權重', '夏普比率優化', '排名加權'] if portfolio_type == '純個股' else ['平均權重']
            
            for strategy in strategies_to_run:
                with st.spinner(f"正在為您建構【{strategy}】投資組合..."):
                    final_portfolio = investment_analyzer.build_portfolio(
                        screened_assets=screened_pool, portfolio_type=portfolio_type,
                        optimization_strategy=strategy, master_df=master_df
                    )
                if final_portfolio is not None:
                    final_portfolio['權重數值'] = final_portfolio['建議權重'].str.replace('%', '', regex=False).astype(float) / 100
                    final_portfolio['配置金額(元)'] = (total_investment * final_portfolio['權重數值']).map('{:,.0f}'.format)
                    
                    st.subheader(f"✅ 您的【{portfolio_type} ({strategy})】投資組合建議")
                    st.dataframe(final_portfolio[['代號', '名稱', '資產類別', '建議權重', '配置金額(元)']])
                    
                    # *** 新增點 2: 視覺化圖表 ***
                    col1, col2 = st.columns(2)
                    with col1:
                        fig_pie = px.pie(final_portfolio, values='權重數值', names='名稱', title='資產配置圓餅圖')
                        st.plotly_chart(fig_pie, use_container_width=True)
                    with col2:
                        # 計算各產業的權重總和
                        industry_weights = final_portfolio.groupby('產業別')['權重數值'].sum().reset_index()
                        fig_bar = px.bar(industry_weights, x='產業別', y='權重數值', title='產業配置直方圖', labels={'權重數值':'權重總和'})
                        st.plotly_chart(fig_bar, use_container_width=True)

                    st.session_state.portfolios[strategy] = final_portfolio

# --- 開放式 AI 問答區塊 ---
if 'portfolios' in st.session_state and st.session_state.portfolios:
    st.divider()
    st.subheader("🤖 AI 投資組合問答")
    
    # *** 修正點 2: 移除策略選擇，改為開放式提問 ***
    user_question = st.text_input("針對以上所有生成的投資組合，有什麼想問的嗎？ (例如：比較一下排名加權和平均權重組合的產業集中度。)")

    if user_question:
        with st.spinner("AI 正在思考中..."):
            # 將所有 portfolio 傳遞給 AI
            ai_response = ai_helper.get_ai_response(st.session_state.portfolios, user_question)
            
            if ai_response:
                st.markdown(ai_response)