import pandas as pd
import streamlit as st

def screen_stocks(stocks_df: pd.DataFrame, risk_profile: str) -> pd.DataFrame:
    """
    【V3.0 - 指標硬篩選版】根據使用者設定的風險偏好，嚴格篩選出滿足所有條件的個股。
    此版本回歸硬性指標過濾，確保只有100%符合條件的標的才會被選入。
    """
    if stocks_df.empty:
        return pd.DataFrame()

    df = stocks_df.copy()
    
    # 預先處理，確保所有用於篩選的欄位都存在且為數值
    required_cols = {
        'beta': 999, 'market_cap_billions': 0, 'dividend_consecutive_years': 0,
        'yield': 0, 'std_dev_1y': 999, 'roe_avg_3y': -999, 'pe_ratio': 999,
        'acc_rev_yoy': -999, 'fcf_per_share_4q': -999, 'roe_wavg_3y': -999
    }
    for col, fill_value in required_cols.items():
        if col not in df.columns:
            df[col] = fill_value
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(fill_value)

    st.write("---")
    
    result_df = pd.DataFrame()
    rules_text = ""

    if risk_profile == '保守型':
        rules = {
            "Beta < 0.8": df['beta'] < 0.8,
            "市值 > 500億": df['market_cap_billions'] > 500,
            "現金股利連配 > 15年": df['dividend_consecutive_years'] > 15,
            "現金殖利率 > 4%": df['yield'] > 4,
            "年化標準差 < 20%": df['std_dev_1y'] < 20,
            "近3年平均ROE > 8%": df['roe_avg_3y'] > 8
        }
        # 使用 & 符號串聯所有條件
        all_conditions = pd.concat(rules.values(), axis=1).all(axis=1)
        result_df = df[all_conditions].sort_values(by='yield', ascending=False)
        rules_text = "<ul>" + "".join([f"<li>{rule}</li>" for rule in rules.keys()]) + "</ul>"

    elif risk_profile == '穩健型':
        rules = {
            "Beta 介於 0.8 ~ 1.2": (df['beta'] >= 0.8) & (df['beta'] <= 1.2),
            "市值 > 100億": df['market_cap_billions'] > 100,
            "近3年平均ROE > 12%": df['roe_avg_3y'] > 12,
            "本益比 < 20": df['pe_ratio'] < 20,
            "累月營收年增 > 0%": df['acc_rev_yoy'] > 0,
            "近4Q每股自由現金流 > 0元": df['fcf_per_share_4q'] > 0
        }
        all_conditions = pd.concat(rules.values(), axis=1).all(axis=1)
        result_df = df[all_conditions].sort_values(by='roe_avg_3y', ascending=False)
        rules_text = "<ul>" + "".join([f"<li>{rule}</li>" for rule in rules.keys()]) + "</ul>"

    elif risk_profile == '積極型':
        rules = {
            "Beta > 1.2": df['beta'] > 1.2,
            "累月營收年增 > 15%": df['acc_rev_yoy'] > 15,
            "近3年加權平均ROE > 15%": df['roe_wavg_3y'] > 15,
        }
        all_conditions = pd.concat(rules.values(), axis=1).all(axis=1)
        result_df = df[all_conditions].sort_values(by='acc_rev_yoy', ascending=False)
        rules_text = "<ul>" + "".join([f"<li>{rule}</li>" for rule in rules.keys()]) + "</ul>"

    st.info(f"**篩選規則 ({risk_profile}):** 必須**同時滿足**以下所有條件")
    st.markdown(rules_text, unsafe_allow_html=True)
    
    st.success(f"篩選完成！共有 {len(result_df)} 檔個股完全符合條件。")
    
    # 為了保持介面欄位一致性，加入 'match_count' 欄位，值為規則數量
    if not result_df.empty:
        result_df['match_count'] = len(rules)

    display_cols = [
        'stock_id', 'stock_name', 'industry_category', 'match_count',
        'beta', 'market_cap_billions', 'dividend_consecutive_years', 'yield',
        'std_dev_1y', 'roe_avg_3y', 'pe_ratio', 'acc_rev_yoy', 'fcf_per_share_4q', 'roe_wavg_3y'
    ]
    final_cols = [col for col in display_cols if col in result_df.columns]
    
    return result_df[final_cols].head(50) # 最多顯示50檔


def screen_etfs(etfs_df: pd.DataFrame, risk_profile: str) -> pd.DataFrame:
    """
    根據使用者設定的風險偏好，篩選ETF。
    """
    if etfs_df.empty:
        return pd.DataFrame()

    df = etfs_df.copy()
    
    exclude_keywords = ['正2', '反1', '槓桿', '反向']
    for keyword in exclude_keywords:
        df = df[~df['stock_name'].str.contains(keyword, na=False)]

    required_cols = {
        'beta': 999, 'std_dev_3y': 999, 'expense_ratio': 999, 
        'annual_return_incl_div': -999, 'yield': -999
    }
    for col, fill_value in required_cols.items():
        if col not in df.columns:
            df[col] = fill_value
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(fill_value)

    st.write("---")
    result_df = pd.DataFrame()

    if risk_profile == '保守型':
        st.info("**ETF篩選規則 (保守型):**\n\n- **主要:** 尋找低Beta(<0.5)、低波動(<10%)、低費用(<0.5%)的債券型ETF。\n- **補充:** 納入高股息低波動ETF作為衛星選項。")
        bond_etfs = df[df['industry_category'].str.contains('債券', na=False)]
        cond1 = (bond_etfs['beta'] < 0.5) & (bond_etfs['std_dev_3y'] < 10) & (bond_etfs['expense_ratio'] < 0.5)
        
        high_div_etfs = df[df['stock_name'].str.contains('高股息', na=False)]
        cond2 = (high_div_etfs['beta'] < 0.8) & (high_div_etfs['yield'] > 4)

        result_df = pd.concat([bond_etfs[cond1], high_div_etfs[cond2]]).sort_values(by='beta').head(50)

    elif risk_profile == '穩健型':
        st.info("**ETF篩選規則 (穩健型):**\n\n- **主要:** 尋找追蹤大盤指數的市值型ETF。\n- **補充:** 納入綜合型投資級債券ETF以平衡風險。")
        market_etfs = df[df['stock_name'].str.contains('0050|006208|台灣50', na=False)]
        bond_etfs = df[df['industry_category'].str.contains('投資級.*債券', na=False, regex=True)]
        
        result_df = pd.concat([market_etfs, bond_etfs]).sort_values(by='expense_ratio').head(50)
        
    elif risk_profile == '積極型':
        st.info("**ETF篩選規則 (積極型):**\n\n- **主要:** 尋找科技、半導體或海外市場等主題式/產業型ETF。\n- **目標:** 追求長期較高的資本增值潛力。")
        keywords = ['科技', '半導體', '費城', '納斯達克', 'NASDAQ', 'FANG', '5G', '電動車']
        pattern = '|'.join(keywords)
        result_df = df[df['stock_name'].str.contains(pattern, na=False)].sort_values(by='annual_return_incl_div', ascending=False).head(50)

    st.success(f"篩選完成！共有 {len(result_df)} 檔ETF符合初步條件。")
    return result_df

