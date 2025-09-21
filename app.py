# app.py

import streamlit as st
import pandas as pd
import plotly.express as px
import re
import numpy as np

# 導入自訂模組
import config
from data_loader import load_and_preprocess_data
from investment_analyzer import run_rule_zero, create_stock_pools, create_etf_pools, build_portfolio, classify_etf_category
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

# --- 數據載入 (加入快取) ---
@st.cache_data(ttl=3600) # 快取數據1小時
def load_data():
    master_df = load_and_preprocess_data()
    if master_df is not None:
        df_filtered = run_rule_zero(master_df)
        df_stocks = df_filtered[df_filtered['AssetType'] == '個股'].copy()
        df_etf = df_filtered[df_filtered['AssetType'] == 'ETF'].copy()
        stock_pools = create_stock_pools(df_stocks)
        df_etf_classified = classify_etf_category(df_etf)
        etf_pools = create_etf_pools(df_etf_classified)
        return master_df, stock_pools, etf_pools
    return None, None, None

master_df, stock_pools, etf_pools = load_data()

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
    if 'Close' in portfolio_with_amount.columns:
        portfolio_with_amount['Shares_To_Buy (est.)'] = np.floor(portfolio_with_amount['Investment_Amount'] / portfolio_with_amount['Close'])

    st.header("📈 您的個人化投資組合")
    st.dataframe(portfolio_with_amount[['名稱', 'AssetType', 'Industry', 'Weight', 'Investment_Amount', 'Shares_To_Buy (est.)']].style.format({
        'Weight': '{:.2%}', 'Investment_Amount': '{:,.0f} 元'
    }))

    # 視覺化圖表
    # app.py -> 視覺化圖表區塊

    col1, col2 = st.columns(2)
    with col1:
    # ... (圓餅圖的程式碼保留不變) ...
        fig_pie = px.pie(portfolio_with_amount, values='Weight', names='名稱', title='權重分佈', hole=.3)
        st.plotly_chart(fig_pie, use_container_width=True)

# ▼▼▼ 用這段程式碼，完整替換掉你舊的 with col2: 區塊 ▼▼▼
    with col2:
        st.subheader("結構分佈")

    # 如果是純ETF組合，顯示ETF類型分佈
        if portfolio_type == '純ETF':
        # 確保 ETF_Category 欄位存在
            if 'ETF_Category' in portfolio_with_amount.columns:
                etf_summary = portfolio_with_amount.groupby('ETF_Category')['Weight'].sum().reset_index()
                fig_bar = px.bar(etf_summary, 
                             x='ETF_Category', 
                             y='Weight', 
                             title='ETF 類型資產分佈',
                             labels={'Weight': '總權重', 'ETF_Category': 'ETF 類型'})
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.warning("無法生成ETF類型分佈圖，缺少分類資料。")

    # 如果是純個股或混合型，且組合中有個股，則顯示產業分佈
        elif 'Industry' in portfolio_with_amount.columns and not portfolio_with_amount[portfolio_with_amount['AssetType']=='個股'].empty:
            stock_data = portfolio_with_amount[portfolio_with_amount['AssetType']=='個股']
            industry_summary = stock_data.groupby('Industry')['Weight'].sum().reset_index()
            fig_bar = px.bar(industry_summary, 
                         x='Industry', 
                         y='Weight', 
                         title='個股部位產業分佈',
                         labels={'Weight': '總權重', 'Industry': '產業別'})
            st.plotly_chart(fig_bar, use_container_width=True)

    # 都不滿足時的預設情況
        else:
            st.info("此組合無個股部位，無產業分佈圖可顯示。")
    # ▲▲▲ 替換結束 ▲▲▲

    st.header("📝 AI 深度分析報告")
    if st.session_state.report:
        st.markdown(st.session_state.report)
    else:
        st.warning("無法生成AI報告。")

    # --- 互動式AI聊天機器人 ---
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
                # 動態調整功能觸發
                match = re.search(r"(加入|納入|增加)\s*(\w+)\s*\(?(\d{4,6})\)?", prompt)
                if match:
                    stock_name, stock_id = match.group(2), match.group(3)
                    if stock_id in master_df.index:
                        st.info(f"偵測到動態調整指令：正在嘗試將 **{stock_name}({stock_id})** 加入組合中...")
                        stock_to_add = master_df.loc[stock_id]
                        # 使用最後一次的輸入參數重新建構
                        inputs = st.session_state.last_inputs
                        new_portfolio = build_portfolio(
                            inputs['risk'], inputs['type'], stock_pools, etf_pools, forced_include=stock_to_add
                        )
                        # 更新 state
                        st.session_state.portfolio = new_portfolio
                        st.session_state.report = generate_rag_report(inputs['risk'], inputs['type'], new_portfolio, master_df)
                        st.session_state.messages = [] # 清空對話以反映新組合
                        st.success("投資組合已動態調整！頁面將會刷新以顯示最新結果。")
                        st.rerun() # 重新整理頁面
                    else:
                        response = f"抱歉，在我的資料庫中找不到股票代碼為 {stock_id} 的資料。"
                else:
                    response = get_chat_response(st.session_state.messages, prompt, st.session_state.portfolio, master_df)
                
                st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

else:
    st.info("請在左側選擇您的偏好，點擊按鈕開始建構您的投資組合。")