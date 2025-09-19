import pandas as pd
import streamlit as st

def screen_stocks(stocks_df: pd.DataFrame, risk_profile: str) -> pd.DataFrame:
    """
    根據使用者風險偏好，從完整的個股DataFrame中篩選出符合條件的候選股票。
    """
    if stocks_df.empty:
        return pd.DataFrame()

    df = stocks_df.copy()
    
    # --- 前置處理：移除必要欄位為NA的資料 ---
    required_cols = [
        'stock_id', 'stock_name', 'industry_category', 'beta', 'market_cap_billions', 
        'dividend_consecutive_years', 'yield', 'std_dev_1y', 'roe_avg_3y', 
        'pe_ratio', 'acc_rev_yoy', 'fcf_per_share_4q', 'roe_wavg_3y'
    ]
    # 檢查欄位是否存在，不存在則填充None或0
    for col in required_cols:
        if col not in df.columns:
            df[col] = None 
    
    df.dropna(subset=[
        'beta', 'market_cap_billions', 'yield', 'roe_avg_3y', 'pe_ratio'
        ], inplace=True)
    
    st.write("---")
    st.subheader("第一步：量化指標初步篩選（個股）")

    if risk_profile == '保守型':
        rules_desc = """
        - **一年(β) (Beta):** < 0.8
        - **市值(億):** > 500億
        - **現金股利連配次數:** > 15年
        - **成交價現金殖利率:** > 4%
        - **一年(σ年) (年化標準差):** < 20%
        - **近3年平均ROE(%):** > 8%
        """
        st.info("套用「保守型」個股篩選規則：")
        st.markdown(rules_desc)
        
        result_df = df[
            (df['beta'] < 0.8) &
            (df['market_cap_billions'] > 500) &
            (df['dividend_consecutive_years'] > 15) &
            (df['yield'] > 4) &
            (df['std_dev_1y'] < 20) &
            (df['roe_avg_3y'] > 8)
        ]

    elif risk_profile == '穩健型':
        rules_desc = """
        - **一年(β) (Beta):** 0.8 ~ 1.2
        - **市值(億):** > 100億
        - **近3年平均ROE(%):** > 12%
        - **PER (本益比):** < 20
        - **累月營收年增(%):** > 0%
        - **最新近4Q每股自由金流(元):** > 0
        """
        st.info("套用「穩健型」個股篩選規則：")
        st.markdown(rules_desc)
        
        result_df = df[
            (df['beta'].between(0.8, 1.2)) &
            (df['market_cap_billions'] > 100) &
            (df['roe_avg_3y'] > 12) &
            (df['pe_ratio'] < 20) &
            (df['acc_rev_yoy'] > 0) &
            (df['fcf_per_share_4q'] > 0)
        ]

    elif risk_profile == '積極型':
        rules_desc = """
        - **一年(β) (Beta):** > 1.2
        - **累月營收年增(%):** > 15%
        - **近3年加權平均ROE(%):** > 15%
        """
        st.info("套用「積極型」個股篩選規則：")
        st.markdown(rules_desc)
        
        result_df = df[
            (df['beta'] > 1.2) &
            (df['acc_rev_yoy'] > 15) &
            (df['roe_wavg_3y'] > 15)
        ]
        
    else:
        result_df = pd.DataFrame()

    st.success(f"篩選完成！共有 {len(result_df)} 檔個股符合初步條件。")
    return result_df.head(50) # 最多取前50筆送給AI分析

def screen_etfs(etfs_df: pd.DataFrame, risk_profile: str) -> pd.DataFrame:
    """
    根據使用者風險偏好，從完整的ETF DataFrame中篩選出符合條件的候選ETF。
    """
    if etfs_df.empty:
        return pd.DataFrame()

    df = etfs_df.copy()

    # --- 前置處理 ---
    required_cols = [
        'stock_id', 'stock_name', 'industry_category', 'beta', 
        'std_dev_3y', 'expense_ratio', 'annual_return_incl_div'
    ]
    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    df.dropna(subset=['beta', 'std_dev_3y', 'expense_ratio'], inplace=True)
    
    st.write("---")
    st.subheader("第一步：量化指標初步篩選（ETF）")
    
    # --- 共通篩選：過濾掉槓桿型/反向型ETF ---
    df = df[~df['stock_name'].str.contains('正2|反1|槓桿|反向')]

    if risk_profile == '保守型':
        rules_desc = """
        - **ETF類型:** 債券ETF
        - **一年.β. (Beta):** < 0.5
        - **三年.σ年. (年化標準差):** < 10%
        - **內扣費用:** < 0.5%
        """
        st.info("套用「保守型」ETF篩選規則：")
        st.markdown(rules_desc)
        
        # 篩選債券ETF
        bond_etfs = df[df['industry_category'].str.contains('債券', na=False)]
        result_df = bond_etfs[
            (bond_etfs['beta'] < 0.5) &
            (bond_etfs['std_dev_3y'] < 10) &
            (bond_etfs['expense_ratio'] < 0.5)
        ]
        
        # 額外加入高股息低波動ETF作為衛星選項
        high_div_etfs = df[
            (df['stock_name'].str.contains('高息|優息', na=False)) &
            (df['beta'] < 0.8) # 放寬beta限制
        ]
        result_df = pd.concat([result_df, high_div_etfs], ignore_index=True).drop_duplicates(subset=['stock_id'])


    elif risk_profile == '穩健型':
        rules_desc = """
        - **ETF類型:** 國內外大盤指數型 & 投資級債券ETF
        """
        st.info("套用「穩健型」ETF篩選規則：")
        st.markdown(rules_desc)

        # 篩選大盤指數型
        stock_index_etfs = df[
            df['industry_category'].str.contains('國內成分股|國外成分股', na=False) &
            (df['stock_name'].str.contains('台灣50|臺灣50|S&P 500|MSCI', na=False))
        ]
        # 篩選投資級債券
        bond_etfs = df[
            df['industry_category'].str.contains('債券', na=False) &
            (df['std_dev_3y'] < 15)
        ]
        result_df = pd.concat([stock_index_etfs, bond_etfs], ignore_index=True).drop_duplicates(subset=['stock_id'])

    elif risk_profile == '積極型':
        rules_desc = """
        - **ETF類型:** 特定產業、主題或國家型ETF (如科技、半導體、美股)
        - **年報酬率.含息.:** 具有高增長潛力
        """
        st.info("套用「積極型」ETF篩選規則：")
        st.markdown(rules_desc)

        result_df = df[
            (df['industry_category'].str.contains('國內成分股|國外成分股', na=False)) &
            (df['stock_name'].str.contains('科技|半導體|Nasdaq|費城|越南|印度|AI|5G', na=False))
        ].sort_values(by='annual_return_incl_div', ascending=False)

    else:
        result_df = pd.DataFrame()

    st.success(f"篩選完成！共有 {len(result_df)} 檔ETF符合初步條件。")
    return result_df.head(50) # 最多取前50筆送給AI分析
