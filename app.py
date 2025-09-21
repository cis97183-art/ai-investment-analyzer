# app.py (整合新聞摘要功能版)

import streamlit as st
import pandas as pd
import plotly.express as px
import re
import numpy as np

# 導入自訂模組
import config
from data_loader import load_and_preprocess_data
from investment_analyzer import run_rule_zero, create_stock_pools, create_etf_pools, build_portfolio
# ▼▼▼ [修改] 從 ai_helper 導入我們需要的 get_realtime_market_news 函式 ▼▼▼
from ai_helper import generate_rag_report, get_chat_response, get_realtime_market_news

# --- 頁面設定 ---
st.set_page_config(layout="wide", page_title="AI 個人化投資組合分析")

# --- 初始化 session_state ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame()
if 'hhi' not in st.session_state:
    st.session_state.hhi = 0
if 'report' not in st.session_state:
    st.session_state.report = ""
# ▼▼▼ [新增] 初始化用來存放新聞摘要的 session_state ▼▼▼
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
                st.session_state.last_inputs = {
                    'risk': risk_profile, 'type': portfolio_type, 'amount': total_amount
                }
                
                # ... (篩選與建池邏輯保持不變) ...
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
                    # ▼▼▼ [新增] 呼叫新聞函式並儲存結果 ▼▼▼
                    st.session_state.news_summary = get_realtime_market_news(st.session_state.portfolio)
                    
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
                    st.session_state.news_summary = "" # 清空
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

    # 視覺化圖表 (保持不變)
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

    # ▼▼▼ [新增] 即時新聞摘要的完整UI區塊 ▼▼▼
    st.header("📰 成分股即時新聞摘要")
    with st.expander("點擊展開或收合新聞摘要", expanded=True):
        if st.session_state.news_summary:
            st.markdown(st.session_state.news_summary)
        else:
            st.info("目前無法獲取相關新聞。")
    # ▲▲▲ 新增區塊結束 ▲▲▲

    st.header("📝 AI 深度分析報告")
    if st.session_state.report:
        st.markdown(st.session_state.report)
    else:
        st.warning("無法生成AI報告。")

    st.header("🔬 標的池檢視器 (Pool Viewer)")
    # ... (標的池檢視器程式碼保持不變) ...
    
    st.header("💬 AI 互動問答")
    # ... (聊天機器人程式碼保持不變) ...

else:
    st.info("請在左側選擇您的偏好，然後點擊按鈕開始分析。")