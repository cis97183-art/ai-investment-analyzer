# app.py (修正函式名稱版)

import streamlit as st
import pandas as pd
import plotly.express as px
import re
import numpy as np

# 導入自訂模組
import config
from data_loader import load_and_preprocess_data
from investment_analyzer import run_rule_zero, create_stock_pools, create_etf_pools, build_portfolio
# ▼▼▼ [修改] 從 ai_helper 導入正確的新函式名稱 ▼▼▼
from ai_helper import generate_rag_report, get_chat_response, get_yfinance_news_summary

# --- 頁面設定 ---
st.set_page_config(layout="wide", page_title="AI 個人化投資組合分析")

# --- 初始化 session_state ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame()
if 'hhi' not in st.session_state:
    st.session_state.hhi = 0
if 'report' not in st.session_state:
    st.session_state.report = ""
if 'news_summary' not in st.session_state:
    st.session_state.news_summary = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if 'last_inputs' not in st.session_state:
    st.session_state.last_inputs = {}
if 'data_pools' not in st.session_state:
    st.session_state.data_pools = {}


# --- 數據載入 (加入快取) ---
@st.cache_data(ttl=3600)
def load_data():
    master_df = load_and_preprocess_data()
    return master_df

master_df = load_data()

# --- 主應用程式介面 ---
st.title("🤖 AI 個人化投資組合分析報告")
st.markdown("遵循「結構優先，紀律至上」的理念，為您量身打造專業級的投資組合。")

# --- 使用者輸入介面 (側邊欄) ---
with st.sidebar:
    st.header("Step 1: 定義您的投資偏好")
    risk_profile = st.selectbox('風險偏好:', ('保守型', '穩健型', '積極型'), index=1)
    portfolio_type = st.selectbox('組合類型:', ('純個股', '純ETF', '混合型'), index=0)
    total_amount = st.number_input('總投資金額 (TWD):', min_value=10000, value=100000, step=10000)

    if st.button('🚀 開始建構 & AI分析', use_container_width=True, type="primary"):
        if master_df is not None:
            with st.spinner('AI 引擎正在為您建構組合並撰寫報告...'):
                st.session_state.last_inputs = {
                    'risk': risk_profile, 'type': portfolio_type, 'amount': total_amount
                }
                
                df_filtered = run_rule_zero(master_df)
                df_stocks = df_filtered[df_filtered['AssetType'] == '個股'].copy()
                df_etf = df_filtered[df_filtered['AssetType'] == 'ETF'].copy()
                stock_pools = create_stock_pools(df_stocks)
                etf_pools = create_etf_pools(df_etf)
                
                st.session_state.data_pools = {
                    '篩選前的所有名單': master_df,
                    '規則零篩選完的名單': df_filtered,
                    '保守型個股池': stock_pools.get('conservative', pd.DataFrame()),
                    '穩健型個股池': stock_pools.get('moderate', pd.DataFrame()),
                    '積極型個股池': stock_pools.get('aggressive', pd.DataFrame()),
                    '市值型ETF池': etf_pools.get('market_cap', pd.DataFrame()),
                    '高股息ETF池': etf_pools.get('high_dividend', pd.DataFrame()),
                    '主題/產業型ETF池': etf_pools.get('theme', pd.DataFrame()),
                    '公債ETF池': etf_pools.get('gov_bond', pd.DataFrame()),
                    '投資級公司債ETF池': etf_pools.get('corp_bond', pd.DataFrame())
                }
                
                st.session_state.portfolio, st.session_state.hhi = build_portfolio(
                    risk_profile, portfolio_type, stock_pools, etf_pools
                )

                if not st.session_state.portfolio.empty:
                    # ▼▼▼ [修改] 呼叫正確的新函式名稱 ▼▼▼
                    st.session_state.news_summary = get_yfinance_news_summary(st.session_state.portfolio, master_df)
                    
                    st.session_state.report = generate_rag_report(
                        risk_profile, 
                        portfolio_type, 
                        st.session_state.portfolio, 
                        master_df, 
                        st.session_state.hhi
                    )
                else:
                    st.session_state.report = ""
                    st.session_state.hhi = 0
                    st.session_state.news_summary = ""
                st.session_state.messages = []
        else:
            st.error("數據載入失敗，無法執行分析。")

# --- 結果展示區 ---
if not st.session_state.portfolio.empty:
    portfolio_with_amount = st.session_state.portfolio.copy()
    portfolio_with_amount['Investment_Amount'] = portfolio_with_amount['Weight'] * total_amount
    
    st.header("📈 您的個人化投資組合")

    st.metric(
        label="HHI 集中度指數 (越低越分散)",
        value=f"{st.session_state.hhi:.4f}"
    )

    st.dataframe(portfolio_with_amount[['名稱', 'AssetType', 'Industry', 'Weight', 'Investment_Amount']].style.format({
        'Weight': '{:.2%}', 'Investment_Amount': '{:,.0f} 元'
    }))

    col1, col2 = st.columns(2)
    with col1:
        fig_pie = px.pie(portfolio_with_amount, values='Weight', names='名稱', title='權重分佈', hole=.3)
        st.plotly_chart(fig_pie, use_container_width=True)
    with col2:
        st.subheader("結構分佈")
        if 'Industry' in portfolio_with_amount.columns:
            summary_data = portfolio_with_amount.dropna(subset=['Industry'])
            summary = summary_data.groupby('Industry')['Weight'].sum().reset_index()
            fig_bar = px.bar(summary, 
                             x='Industry', 
                             y='Weight', 
                             title='投資組合結構分佈',
                             labels={'Weight': '總權重', 'Industry': '類型 / 產業別'})
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("此組合無產業或類型分佈資料可顯示。")

    st.header("📰 成分股即時新聞摘要")
    with st.expander("點擊展開或收合新聞摘要", expanded=True):
        if st.session_state.news_summary:
            st.markdown(st.session_state.news_summary)
        else:
            st.info("目前無法獲取相關新聞。")

    st.header("📝 AI 深度分析報告")
    if st.session_state.report:
        st.markdown(st.session_state.report)
    else:
        st.warning("無法生成AI報告。")

    # ▼▼▼ 用這段程式碼，完整替換掉你舊的「標的池檢視器」區塊 ▼▼▼
    st.header("🔬 標的池檢視器 (Pool Viewer)")
    st.markdown("在這裡，您可以檢視投資策略在各個篩選階段的結果，深入了解標的入選的過程。")
    
    with st.expander("點擊展開或收合標的池檢視器", expanded=False):
        # 建立下拉選單 (邏輯不變)
        pool_options = list(st.session_state.data_pools.keys())
        selected_pool_name = st.selectbox("請選擇您想檢視的標的池：", options=pool_options)

        # 根據使用者的選擇，從 session_state 中取出對應的 DataFrame
        pool_to_display = st.session_state.data_pools.get(selected_pool_name)

        if pool_to_display is not None and not pool_to_display.empty:
            st.write(f"### {selected_pool_name} ({len(pool_to_display)} 檔標的)")
            
            # ▼▼▼ [修改] 動態決定要顯示的欄位 ▼▼▼
            # 預設的個股欄位組合
            stock_display_cols = [
                'StockID', '名稱', 'AssetType', 'Industry', 'MarketCap_Billions',
                'Close', 'StdDev_1Y', 'Beta_1Y', 'Dividend_Yield',
                'Dividend_Consecutive_Years', 'ROE_Avg_3Y',
                'Revenue_YoY_Accumulated', 'FCFPS_Last_4Q', 'Age_Years'
            ]
            
            # 為ETF優化的欄位組合
            etf_display_cols = [
                'StockID', '名稱', 'AssetType', 'Industry', 'MarketCap_Billions',
                'Close', 'Beta_1Y', 'Dividend_Yield', 'Age_Years',
                'Expense_Ratio', 'Annual_Return_Include_Dividend' # <-- 新增的兩個欄位
            ]

            # 判斷使用者選擇的是否為ETF池
            if "ETF" in selected_pool_name:
                display_cols = etf_display_cols
            else:
                display_cols = stock_display_cols
            
            # 確保要顯示的欄位真的存在於該標的池中
            existing_cols_to_display = [col for col in display_cols if col in pool_to_display.columns]
            
            st.dataframe(pool_to_display[existing_cols_to_display])
        else:
            st.warning(f"「{selected_pool_name}」是空的，沒有任何標的。")
    # ▲▲▲ 替換到此結束 ▲▲▲


    st.header("💬 AI 互動問答")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("對這個投資組合有任何問題嗎？(例：如果我想加入台積電(2330)會如何？)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("AI 正在思考中..."):
                match = re.search(r"(加入|納入|增加)\s*(\w+)\s*\(?(\d{4,6})\)?", prompt)
                if match:
                    stock_name, stock_id = match.group(2), match.group(3)
                    if master_df is not None and stock_id in master_df.index:
                        st.info(f"偵測到動態調整指令：正在嘗試將 **{stock_name}({stock_id})** 加入組合中...")
                        stock_to_add = master_df.loc[stock_id]
                        inputs = st.session_state.last_inputs
                        
                        df_filtered = run_rule_zero(master_df)
                        df_stocks = df_filtered[df_filtered['AssetType'] == '個股'].copy()
                        df_etf = df_filtered[df_filtered['AssetType'] == 'ETF'].copy()
                        stock_pools = create_stock_pools(df_stocks)
                        etf_pools = create_etf_pools(df_etf)

                        new_portfolio, new_hhi = build_portfolio(
                            inputs['risk'], inputs['type'], stock_pools, etf_pools, forced_include=stock_to_add
                        )
                        
                        st.session_state.portfolio = new_portfolio
                        st.session_state.hhi = new_hhi
                        st.session_state.report = generate_rag_report(inputs['risk'], inputs['type'], new_portfolio, master_df, new_hhi)
                        st.session_state.news_summary = get_tej_news_summary(new_portfolio)
                        st.session_state.messages = []
                        st.success("投資組合已動態調整！頁面將會刷新以顯示最新結果。")
                        st.rerun()
                    else:
                        response = f"抱歉，在我的資料庫中找不到股票代碼為 {stock_id} 的資料。"
                else:
                    response = get_chat_response(st.session_state.messages, prompt, st.session_state.portfolio, master_df)
                
                st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

else:
    st.info("請在左側選擇您的偏好，然後點擊按鈕開始分析。")