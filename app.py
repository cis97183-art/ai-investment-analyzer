# app.py

import streamlit as st
import pandas as pd
import plotly.express as px
import re
import numpy as np

# 導入自訂模組
import config
from data_loader import load_and_preprocess_data
from investment_analyzer import run_rule_zero, create_stock_pools, create_etf_pools, build_portfolio
from ai_helper import generate_rag_report, get_chat_response

# --- 頁面設定 ---
st.set_page_config(layout="wide", page_title="AI 個人化投資組合分析")

# --- 初始化 session_state ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame()
if 'report' not in st.session_state:
    st.session_state.report = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if 'last_inputs' not in st.session_state:
    st.session_state.last_inputs = {}
# ▼▼▼ [新增] 初始化用來存放標的池的 session_state ▼▼▼
if 'data_pools' not in st.session_state:
    st.session_state.data_pools = {}


# --- 數據載入 (加入快取) ---
@st.cache_data(ttl=3600) # 快取數據1小時
def load_data():
    master_df = load_and_preprocess_data()
    # 我們不再在這裡執行篩選，將篩選步驟移到按鈕點擊事件中
    return master_df

master_df = load_data()

# --- 主應用程式介面 ---
st.title("🤖 AI 個人化投資組合分析報告 (v2.0)")
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
                # 儲存本次輸入
                st.session_state.last_inputs = {
                    'risk': risk_profile, 'type': portfolio_type, 'amount': total_amount
                }
                
                # --- 執行篩選與建池邏輯 ---
                df_filtered = run_rule_zero(master_df)
                df_stocks = df_filtered[df_filtered['AssetType'] == '個股'].copy()
                df_etf = df_filtered[df_filtered['AssetType'] == 'ETF'].copy()
                stock_pools = create_stock_pools(df_stocks)
                etf_pools = create_etf_pools(df_etf)
                
                # ▼▼▼ [新增] 將所有中間過程的數據儲存到 session_state 中 ▼▼▼
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
                
                # 建構投資組合
                st.session_state.portfolio = build_portfolio(risk_profile, portfolio_type, stock_pools, etf_pools)
                if not st.session_state.portfolio.empty:
                    # 生成AI報告
                    st.session_state.report = generate_rag_report(risk_profile, portfolio_type, st.session_state.portfolio, master_df)
                else:
                    st.session_state.report = ""
                # 清空聊天紀錄
                st.session_state.messages = []
        else:
            st.error("數據載入失敗，無法執行分析。")

# --- 結果展示區 ---
if not st.session_state.portfolio.empty:
    portfolio_with_amount = st.session_state.portfolio.copy()
    portfolio_with_amount['Investment_Amount'] = portfolio_with_amount['Weight'] * total_amount
    # if 'Close' in portfolio_with_amount.columns:
    #     portfolio_with_amount['Shares_To_Buy (est.)'] = np.floor(portfolio_with_amount['Investment_Amount'] / portfolio_with_amount['Close'])

    st.header("📈 您的個人化投資組合")
    st.dataframe(portfolio_with_amount[['名稱', 'AssetType', 'Industry', 'Weight', 'Investment_Amount']].style.format({
        'Weight': '{:.2%}', 'Investment_Amount': '{:,.0f} 元'
    }))

    # 視覺化圖表
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

    st.header("📝 AI 深度分析報告")
    if st.session_state.report:
        st.markdown(st.session_state.report)
    else:
        st.warning("無法生成AI報告。")

    # ▼▼▼ [新增] 標的池檢視器 (Pool Viewer) 的完整UI區塊 ▼▼▼
    st.header("🔬 標的池檢視器 (Pool Viewer)")
    st.markdown("在這裡，您可以檢視投資策略在各個篩選階段的結果，深入了解標的入選的過程。")
    
    with st.expander("點擊展開或收合標的池檢視器", expanded=False):
        # 建立下拉選單，選項來自我們儲存在 session_state 中的字典的鍵 (keys)
        pool_options = list(st.session_state.data_pools.keys())
        selected_pool_name = st.selectbox("請選擇您想檢視的標的池：", options=pool_options)

        # 根據使用者的選擇，從 session_state 中取出對應的 DataFrame
        pool_to_display = st.session_state.data_pools.get(selected_pool_name)

        if pool_to_display is not None and not pool_to_display.empty:
            st.write(f"### {selected_pool_name} ({len(pool_to_display)} 檔標的)")
            
            # 為了讓表格更具可讀性，我們只顯示最重要的欄位
            # 並確保這些欄位真的存在於該標的池中
            display_cols = [
                'StockID', '名稱', 'AssetType', 'Industry', 'MarketCap_Billions',
                'Close', 'StdDev_1Y', 'Beta_1Y', 'Dividend_Yield',
                'Dividend_Consecutive_Years', 'ROE_Avg_3Y',
                'Revenue_YoY_Accumulated', 'FCFPS_Last_4Q', 'Age_Years'
            ]
            
            existing_cols_to_display = [col for col in display_cols if col in pool_to_display.columns]
            
            st.dataframe(pool_to_display[existing_cols_to_display])
        else:
            st.warning(f"「{selected_pool_name}」是空的，沒有任何標的。")

    # --- 互動式AI聊天機器人 ---
    st.header("💬 AI 互動問答")
    # ... (聊天機器人程式碼保持不變) ...

else:
    st.info("請在左側選擇您的偏好，然後點擊按鈕開始分析。")