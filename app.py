# app.py (新規則最終版)

import streamlit as st
import pandas as pd
import plotly.express as px
import config
import data_loader
import screener
import investment_analyzer
import ai_helper

st.set_page_config(page_title="AI 投資組合分析師", page_icon="🤖", layout="wide")

if "portfolios" not in st.session_state: st.session_state.portfolios = {}
if "messages" not in st.session_state: st.session_state.messages = []

st.title("🤖 AI 投資組合分析師")
st.write("根據您的風險偏好，從台股市場中篩選標的並建立客製化投資組合。")

st.sidebar.header("請選擇您的偏好")
risk_profile = st.sidebar.selectbox("1. 您的風險偏好是？", ("保守型", "穩健型", "積極型"), index=1)
portfolio_type = st.sidebar.selectbox("2. 您想建立的組合類型是？", ("純個股", "純 ETF", "混合型"), index=0)
total_investment = st.sidebar.number_input("3. 請輸入您的總投資金額 (元)", min_value=10000, value=1000000, step=10000)

if st.sidebar.button("🚀 開始分析"):
    st.session_state.portfolios = {}
    st.session_state.messages = []
    
    with st.spinner("正在讀取與清理最新市場資料..."):
        master_df = data_loader.load_and_prepare_data(config.LISTED_STOCK_PATH, config.OTC_STOCK_PATH, config.ETF_PATH)
    
    if master_df is not None:
        st.session_state.master_df = master_df
        with st.spinner(f"正在為您篩選【{risk_profile}】的標的..."):
            screened_pool = screener.screen_assets(master_df, risk_profile, config.TARGET_ASSET_COUNT)
            st.session_state.screened_pool = screened_pool
    else:
        st.error("資料載入失敗，請檢查檔案路徑或檔案內容。")

if "screened_pool" in st.session_state and not st.session_state.screened_pool.empty:
    st.success("分析完成！")
    
    with st.expander(f"查看【{risk_profile}】階層式篩選標的池 (共 {len(st.session_state.screened_pool)} 支)"):
        pool_display_cols = ['代號', '名稱', '產業別', '篩選層級', '一年(σ年)', '一年(β)', '累月營收年增(%)', '市值(億)', '最新單季ROE(%)']
        existing_cols = [col for col in pool_display_cols if col in st.session_state.screened_pool.columns]
        st.dataframe(st.session_state.screened_pool[existing_cols])

    st.markdown("---")
    
    # *** 修正點：不再需要迴圈，直接呼叫一次 ***
    final_portfolio, hhi_value = investment_analyzer.build_portfolio(
        screened_assets=st.session_state.screened_pool,
        portfolio_type=portfolio_type,
        risk_profile=risk_profile,
        master_df=st.session_state.master_df
    )
    
    if final_portfolio is not None:
        # 計算金額
        final_portfolio['權重數值'] = final_portfolio['建議權重'].str.replace('%', '', regex=False).astype(float) / 100
        final_portfolio['配置金額(元)'] = (total_investment * final_portfolio['權重數值']).map('{:,.0f}'.format)
        
        st.subheader(f"✅ 您的【{risk_profile} - {portfolio_type}】投資組合建議")

        # *** 修正點：使用 st.metric 顯示 HHI ***
        hhi_help_text = "HHI 越低代表分散程度越高。純個股(<0.25)；混合型(<0.3)。"
        st.metric(label="投資組合 HHI 指數", value=f"{hhi_value:.4f}", help=hhi_help_text)

        display_cols = ['代號', '名稱', '產業別', '建議權重', '配置金額(元)']
        if 'sharpe_ratio' in final_portfolio.columns:
            final_portfolio['夏普比率'] = final_portfolio['sharpe_ratio'].map('{:.2f}'.format)
            display_cols.insert(3, '夏普比率')

        st.dataframe(final_portfolio[display_cols])
        
        # (圖表與AI邏輯不變)
        col1, col2 = st.columns(2)
        with col1:
            fig_pie = px.pie(final_portfolio, values='權重數值', names='名稱', title='資產配置圓餅圖')
            st.plotly_chart(fig_pie, use_container_width=True)
        with col2:
            industry_weights = final_portfolio.groupby('產業別')['權重數值'].sum().reset_index()
            fig_bar = px.bar(industry_weights, x='產業別', y='權重數值', title='產業配置直方圖', labels={'權重數值':'權重總和'})
            st.plotly_chart(fig_bar, use_container_width=True)

        st.session_state.portfolios[portfolio_type] = final_portfolio
        if not st.session_state.messages:
            st.session_state.messages.append({"role": "assistant", "content": "您的客製化投資組合報告已生成，請問有什麼想深入了解的嗎？"})

# ... (後續 AI 問答區塊的程式碼完全相同，此處省略) ...