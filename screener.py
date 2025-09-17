import pandas as pd

def screen_stocks(market_data_df: pd.DataFrame, risk_profile: str) -> pd.DataFrame:
    """
    [更新版] 根據財務指標與新聞情緒，從市場數據中篩選出候選股票。
    
    Args:
        market_data_df: 包含所有股票財務與新聞情緒的 DataFrame。
        risk_profile: 投資者的風險偏好 ('保守型', '穩健型', '積極型')。

    Returns:
        一個符合篩選條件的候選股票 DataFrame。
    """
    if market_data_df.empty:
        return pd.DataFrame()

    # --- 步驟 1: 建立篩選條件 ---
    conditions = []
    
    # 共通規則：排除新聞情緒為負面的股票
    conditions.append(market_data_df['sentiment_category'] != '負面')
    # 共通規則：排除沒有 P/E 或 P/B 值的股票
    conditions.append(market_data_df['pe_ratio'].notna() & (market_data_df['pe_ratio'] > 0))
    conditions.append(market_data_df['pb_ratio'].notna() & (market_data_df['pb_ratio'] > 0))

    # --- 步驟 2: 根據風險偏好添加特定規則 ---
    if risk_profile == '保守型':
        conditions.append(market_data_df['pe_ratio'] < 15)
        conditions.append(market_data_df['pb_ratio'] < 2)
        conditions.append(market_data_df['yield'] > 0.04) # 殖利率 > 4%
        
    elif risk_profile == '穩健型':
        conditions.append(market_data_df['pe_ratio'] < 25)
        conditions.append(market_data_df['pb_ratio'] < 4)
        conditions.append(market_data_df['yield'] > 0.025) # 殖利率 > 2.5%
        
    elif risk_profile == '積極型':
        conditions.append(market_data_df['pe_ratio'] < 50)
        # 對於積極型，我們可能更關注成長性，對 P/B 和殖利率的限制較寬鬆
        
    # --- 步驟 3: 應用所有篩選條件 ---
    if not conditions:
        return market_data_df # 如果沒有條件，返回全部

    # 將所有條件用 '&' 結合起來
    final_condition = pd.Series(True, index=market_data_df.index)
    for cond in conditions:
        final_condition &= cond
        
    screened_df = market_data_df[final_condition].copy()
    
    return screened_df
