import pandas as pd
import streamlit as st

def screen_stocks(market_data: pd.DataFrame, risk_profile: str) -> pd.DataFrame:
    """
    [yfinance 版] 根據使用者風險偏好，從融合後的市場數據中篩選出候選股票。
    """
    if market_data.empty:
        return pd.DataFrame()

    # 複製一份數據以避免修改原始快取
    df = market_data.copy()
    
    # 基本過濾條件 (對所有類型都適用)
    # 移除 PE 或 PB 為負或空值的股票，這些通常是虧損或數據不足的公司
    df.dropna(subset=['pe_ratio', 'pb_ratio'], inplace=True)
    df = df[(df['pe_ratio'] > 0) & (df['pb_ratio'] > 0)]

    # 根據風險偏好設定不同的篩選條件
    if risk_profile == '保守型':
        st.write("篩選規則 (保守型): P/E < 20, P/B < 2, 殖利率 > 3%")
        result_df = df[
            (df['pe_ratio'] < 20) &
            (df['pb_ratio'] < 2) &
            (df['yield'] > 3)
        ].sort_values(by='yield', ascending=False)

    elif risk_profile == '穩健型':
        st.write("篩選規則 (穩健型): P/E < 25, P/B < 4")
        result_df = df[
            (df['pe_ratio'] < 25) &
            (df['pb_ratio'] < 4)
        ].sort_values(by='pe_ratio', ascending=True)

    elif risk_profile == '積極型':
        st.write("篩選規則 (積極型): P/B < 6, 優先選擇正面新聞較多的股票")
        result_df = df[
            (df['pb_ratio'] < 6)
        ].sort_values(by=['Positive', 'pe_ratio'], ascending=[False, True])
        
    else:
        result_df = df

    return result_df

