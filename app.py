# app.py

import streamlit as st
import pandas as pd
import plotly.express as px
import config
import data_loader
import screener
import investment_analyzer
import ai_helper
import re

def add_stock_to_portfolio(stock_code, portfolio_dict, master_df):
    """將指定股票加入現有投資組合並重新計算"""
    stock_data = master_df[master_df['代號'] == stock_code]
    if stock_data.empty:
        st.warning(f"在資料庫中找不到股票代號 {stock_code}。")
        return portfolio_dict, False #回傳失敗

    updated = False
    for strategy, df in portfolio_dict.items():
        if stock_code in df['代號'].values:
            st.info(f"股票 {stock_code} 已存在於【{strategy}】組合中。")
            continue
        
        # 保留必要欄位進行合併
        cols_to_keep = [col for col in df.columns if col not in ['權重數值', '配置金額(元)', '建議權重']]
        new_df_base = pd.concat([df[cols_to_keep], stock_data], ignore_index=True)
        
        num_assets = len(new_df_base)
        weights = [1 / num_assets] * num_assets
        new_df_base['建議權重'] = [f"{w:.2%}" for w in weights]
        portfolio_dict[strategy] = new_df_base
        updated = True
    
    if updated:
        st.success(f"已將 {stock_code} 加入投資組合並重新採用平均權重計算。")
    return portfolio_dict, updated

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
            st.rerun() # 執行完分析後，刷新頁面來顯示結果
    else:
        st.error("資料載入失敗，請檢查檔案路徑或檔案內容。")

if "screened_pool" in st.session_state and not st.session_state.screened_pool.empty:
    st.success("分析完成！")
    
    with st.expander(f"查看【{risk_profile}】階層式篩選標的池 (共 {len(st.session_state.screened_pool)} 支)"):
        pool_display_cols = ['代號', '名稱', '產業別', '篩選層級', '一年(σ年)', '一年(β)', '累月營收年增(%)', '市值(億)', '最新單季ROE(%)']
        existing_cols = [col for col in pool_display_cols if col in st.session_state.screened_pool.columns]
        st.dataframe(st.session_state.screened_pool[existing_cols])

    st.markdown("---")
    
    if not st.session_state.portfolios: # 只有在 portfolio 為空時才重新生成
        final_portfolio, hhi_value = investment_analyzer.build_portfolio(
            screened_assets=st.session_state.screened_pool,
            portfolio_type=portfolio_type,
            risk_profile=risk_profile,
            master_df=st.session_state.master_df
        )
        if final_portfolio is not None:
             st.session_state.portfolios[portfolio_type] = final_portfolio
             st.session_state.hhi = hhi_value

    if st.session_state.portfolios:
        portfolio_to_display = st.session_state.portfolios[portfolio_type]
        hhi_value_to_display = st.session_state.hhi

        portfolio_to_display['權重數值'] = portfolio_to_display['建議權重'].str.replace('%', '', regex=False).astype(float) / 100
        portfolio_to_display['配置金額(元)'] = (total_investment * portfolio_to_display['權重數值']).map('{:,.0f}'.format)
        
        st.subheader(f"✅ 您的【{risk_profile} - {portfolio_type}】投資組合建議")
        
        hhi_help_text = "HHI 越低代表分散程度越高。純個股(<0.25)；混合型(<0.3)。"
        st.metric(label="投資組合 HHI 指數", value=f"{hhi_value_to_display:.4f}", help=hhi_help_text)

        display_cols = ['代號', '名稱', '產業別', '建議權重', '配置金額(元)']
        if 'sharpe_ratio' in portfolio_to_display.columns:
            portfolio_to_display['夏普比率'] = portfolio_to_display['sharpe_ratio'].map('{:.2f}'.format)
            display_cols.insert(3, '夏普比率')
        st.dataframe(portfolio_to_display[display_cols])
        
        col1, col2 = st.columns(2)
        with col1:
            fig_pie = px.pie(portfolio_to_display, values='權重數值', names='名稱', title='資產配置圓餅圖')
            st.plotly_chart(fig_pie, use_container_width=True)
        with col2:
            if '產業別' in portfolio_to_display.columns and not portfolio_to_display['產業別'].isnull().all():
                industry_weights = portfolio_to_display.groupby('產業別')['權重數值'].sum().reset_index()
                fig_bar = px.bar(industry_weights, x='產業別', y='權重數值', title='產業配置直方圖', labels={'權重數值':'權重總和'})
                st.plotly_chart(fig_bar, use_container_width=True)

        if not st.session_state.messages:
            st.session_state.messages.append({"role": "assistant", "content": "您的客製化投資組合報告已生成，請問有什麼想深入了解的嗎？"})

elif "screened_pool" in st.session_state and st.session_state.screened_pool.empty:
     st.warning(f"在【{risk_profile}】的篩選條件下，找不到任何符合的標的。")
else:
    st.info("請在左方側邊欄設定您的偏好，然後點擊「開始分析」。")

st.divider()
st.subheader("🤖 AI 投資組合問答")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("您可以問我投資相關問題，或試著說「加入 2330」"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    add_stock_match = re.search(r'(加入|add)\s*(\d{4,6})', prompt)
    
    if add_stock_match and "portfolios" in st.session_state and st.session_state.portfolios:
        stock_code_to_add = add_stock_match.group(2)
        with st.chat_message("assistant"):
            with st.spinner(f"正在將 {stock_code_to_add} 加入您的投資組合..."):
                updated_portfolios, success = add_stock_to_portfolio(
                    stock_code_to_add, st.session_state.portfolios, st.session_state.master_df
                )
                if success:
                    response = f"好的，我已經為您加入新標的 **{stock_code_to_add}** 並重新採用平均權重計算。"
                    st.session_state.portfolios = updated_portfolios
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.rerun()
                else:
                    response = f"抱歉，無法將 {stock_code_to_add} 加入投資組合。"
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

    else:
        with st.chat_message("assistant"):
            with st.spinner("AI 正在思考中..."):
                portfolios_context = st.session_state.get('portfolios', {})
                response = ai_helper.get_ai_response(portfolios_context, prompt)
                if response:
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})