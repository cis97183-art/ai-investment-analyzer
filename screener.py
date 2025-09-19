import pandas as pd
import streamlit as st

def screen_stocks(stocks_df: pd.DataFrame, risk_profile: str) -> pd.DataFrame:
    """
    【V4.0 - 專業診斷版】優先進行硬性指標篩選，若無完美標的，則自動進入診斷模式，找出最接近的潛力股。
    """
    if stocks_df.empty:
        return pd.DataFrame()

    df = stocks_df.copy()
    
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
    
    rules = {}
    sort_by_col = ''

    if risk_profile == '保守型':
        rules = {
            "Beta < 0.8": df['beta'] < 0.8,
            "市值 > 500億": df['market_cap_billions'] > 500,
            "現金股利連配 > 15年": df['dividend_consecutive_years'] > 15,
            "現金殖利率 > 4%": df['yield'] > 4,
            "年化標準差 < 20%": df['std_dev_1y'] < 20,
            "近3年平均ROE > 8%": df['roe_avg_3y'] > 8
        }
        sort_by_col = 'yield'

    elif risk_profile == '穩健型':
        rules = {
            "Beta 介於 0.8 ~ 1.2": (df['beta'] >= 0.8) & (df['beta'] <= 1.2),
            "市值 > 100億": df['market_cap_billions'] > 100,
            "近3年平均ROE > 12%": df['roe_avg_3y'] > 12,
            "本益比 < 20": df['pe_ratio'] < 20,
            "累月營收年增 > 0%": df['acc_rev_yoy'] > 0,
            "近4Q每股自由現金流 > 0元": df['fcf_per_share_4q'] > 0
        }
        sort_by_col = 'roe_avg_3y'

    elif risk_profile == '積極型':
        rules = {
            "Beta > 1.2": df['beta'] > 1.2,
            "累月營收年增 > 15%": df['acc_rev_yoy'] > 15,
            "近3年加權平均ROE > 15%": df['roe_wavg_3y'] > 15,
        }
        sort_by_col = 'acc_rev_yoy'
    
    if not rules:
        return pd.DataFrame()

    rules_text = "<ul>" + "".join([f"<li>{rule}</li>" for rule in rules.keys()]) + "</ul>"
    
    # --- [階段一] 執行最嚴格的「完美標準」篩選 ---
    st.info(f"**篩選模式 ({risk_profile}):**\n\n- **第一階段 (完美標準):** 正在尋找**「同時滿足」**以下所有 **{len(rules)}** 項條件的頂級標的...")
    st.markdown(rules_text, unsafe_allow_html=True)
    
    all_conditions = pd.concat(rules.values(), axis=1).all(axis=1)
    strict_results_df = df[all_conditions]

    if not strict_results_df.empty:
        st.success(f"**分析結果：** 成功找到 **{len(strict_results_df)}** 檔完全符合所有條件的頂級個股！")
        result_df = strict_results_df.sort_values(by=sort_by_col, ascending=False).head(50)
        result_df['match_count'] = len(rules)
    else:
        # --- [階段二] 若無完美標的，自動進入「診斷模式」 ---
        st.warning(f"**第一階段分析報告：** 市場上目前 **沒有任何一檔個股** 能「同時滿足」您設定的所有 {len(rules)} 項嚴格條件。")
        
        fallback_threshold = max(1, len(rules) - 2)
        st.info(f"**第二階段 (診斷模式):**\n\n- **分析：** 系統已自動放寬標準，為您找出最接近條件、至少滿足 **{fallback_threshold}** 項指標的「潛力股」清單。")

        df['match_count'] = sum(rule.astype(int) for rule in rules.values())
        
        diagnostic_df = df[df['match_count'] >= fallback_threshold].sort_values(
            by=['match_count', sort_by_col], ascending=[False, False]
        ).head(50)

        if diagnostic_df.empty:
            st.error("**最終診斷報告：** 市場數據極端，甚至無法找到滿足大部分條件的個股。建議您調整篩選標準或等候市況改變。")
            return pd.DataFrame()
        else:
            st.success(f"**診斷完成：** 為您找出 **{len(diagnostic_df)}** 檔最接近您理想條件的潛力個股。")
            result_df = diagnostic_df

    display_cols = [
        'stock_id', 'stock_name', 'industry_category', 'match_count',
        'beta', 'market_cap_billions', 'dividend_consecutive_years', 'yield',
        'std_dev_1y', 'roe_avg_3y', 'pe_ratio', 'acc_rev_yoy', 'fcf_per_share_4q', 'roe_wavg_3y'
    ]
    final_cols = [col for col in display_cols if col in result_df.columns]
    
    return result_df[final_cols]


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

