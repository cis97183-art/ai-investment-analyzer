# app.py (最終修正版)

import streamlit as st
import config
import data_loader
import screener
import investment_analyzer

# --- Streamlit App 介面設定 ---

st.set_page_config(
    page_title="AI 投資組合分析師",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AI 投資組合分析師")
st.write("根據您的風險偏好，從台股市場中篩選標的並建立客製化投資組合。")

# --- 側邊欄，讓使用者輸入選項 ---
st.sidebar.header("請選擇您的偏好")

risk_profile = st.sidebar.selectbox(
    "1. 您的風險偏好是？",
    ("保守型", "穩健型", "積極型"),
    index=1
)

portfolio_type = st.sidebar.selectbox(
    "2. 您想建立的組合類型是？",
    ("純個股", "純 ETF", "混合型"),
    index=0
)

# *** 新增點：讓使用者選擇優化策略 ***
# 這個選項只在選擇「純個股」時出現
optimization_strategy = "平均權重" # 預設值
if portfolio_type == '純個股':
    optimization_strategy = st.sidebar.selectbox(
        "3. 請選擇個股優化策略",
        ("平均權重", "夏普比率優化", "因子加權")
    )

# --- 觸發分析的按鈕 ---
if st.sidebar.button("🚀 開始分析"):
    
    with st.spinner("正在讀取與清理最新市場資料..."):
        master_df = data_loader.load_and_prepare_data(
            listed_path=config.LISTED_STOCK_PATH,
            otc_path=config.OTC_STOCK_PATH,
            etf_path=config.ETF_PATH
        )
    
    if master_df is None:
        st.error("資料載入失敗，請檢查檔案路徑或檔案內容。")
    else:
        st.success("資料準備完成！")

        with st.spinner(f"正在為您篩選【{risk_profile}】的標的..."):
            screened_pool = screener.screen_assets(
                data_df=master_df,
                risk_profile=risk_profile,
                target_count=config.TARGET_ASSET_COUNT
            )
        
        if screened_pool.empty:
            st.warning(f"在【{risk_profile}】的篩選條件下，找不到足夠的標的。")
        else:
            st.subheader(f"【{risk_profile}】標的池 (已依輔助指標排序)")
            st.dataframe(screened_pool[['代號', '名稱', '產業別', '市值(億)', '一年(β)', '一年(σ年)']].head(20))
            
            with st.spinner(f"正在為您建構【{portfolio_type} / {optimization_strategy}】投資組合..."):
                # *** 修正點：將 optimization_strategy 參數傳入函式中 ***
                final_portfolio = investment_analyzer.build_portfolio(
                    screened_assets=screened_pool,
                    portfolio_type=portfolio_type,
                    optimization_strategy=optimization_strategy, # <--- 新增的參數
                    master_df=master_df
                )

            if final_portfolio is not None:
                st.subheader(f"✅ 您的【{risk_profile} - {portfolio_type} ({optimization_strategy})】投資組合建議")
                st.dataframe(final_portfolio)
                
                @st.cache_data
                def convert_df_to_csv(df):
                    return df.to_csv(index=False).encode('utf_8_sig')

                csv_data = convert_df_to_csv(final_portfolio)
                st.download_button(
                    label="📥 下載投資組合 (CSV)",
                    data=csv_data,
                    file_name=f"{risk_profile}_{portfolio_type}_{optimization_strategy}_portfolio.csv",
                    mime='text/csv',
                )
            else:
                st.error(f"無法建構【{portfolio_type}】投資組合，可能是標的池中符合條件的資產不足。")

else:
    st.info("請在左方側邊欄選擇您的偏好，然後點擊「開始分析」。")