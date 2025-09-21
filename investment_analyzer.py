# investment_analysis.py

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import config

def calculate_hhi(weights):
    """計算 HHI 指數"""
    return np.sum(np.square(weights))

def apply_factor_weighting(df, factor_column):
    """應用因子加權"""
    # 處理負數或零因子值，給予一個極小的權重
    weights = df[factor_column].clip(lower=0.0001)
    return weights / weights.sum()

# 修改後 (請改成這樣)

def run_rule_zero(df):
    """執行基礎排雷篩選"""
    df_filtered = df[~df['名稱'].str.contains('槓桿|反向|正2|反1', na=False)]
    df_filtered = df_filtered[df_filtered['MarketCap_Billions'] >= config.MIN_MARKET_CAP_BILLIONS]
    
    # vvvv 修改後的篩選邏輯 vvvv
    # 排除上市/成立未滿一年 (直接檢查 Age_Years 欄位是否 >= 1)
    df_filtered = df_filtered[df_filtered['Age_Years'] >= 1]
    # ^^^^ 修改後的篩選邏輯 ^^^^

    stock_mask = (df_filtered['AssetType'] == '個股') & (df_filtered['FCFPS_Last_4Q'] < 0)
    df_filtered = df_filtered[~stock_mask]
    return df_filtered

def create_stock_pools(df_stocks):
    """建立個股標的池"""
    pools = {}
    low_vol_threshold = df_stocks['StdDev_1Y'].quantile(0.30)
    high_vol_threshold = df_stocks['StdDev_1Y'].quantile(0.70)

    pools['conservative'] = df_stocks[
        (df_stocks['StdDev_1Y'] <= low_vol_threshold) & (df_stocks['Beta_1Y'] < 1.0) &
        (df_stocks['Dividend_Consecutive_Years'] > 10) & (df_stocks['FCFPS_Last_4Q'] > 0)
    ].sort_values(by=['Dividend_Yield', 'MarketCap_Billions'], ascending=[False, False])

    pools['moderate'] = df_stocks[
        (df_stocks['StdDev_1Y'].between(low_vol_threshold, high_vol_threshold)) &
        (df_stocks['ROE_Avg_3Y'] > 5) & (df_stocks['Revenue_YoY_Accumulated'] > 0)
    ].sort_values(by=['ROE_Avg_3Y', 'MarketCap_Billions'], ascending=[False, False])
    
    pools['aggressive'] = df_stocks[
        (df_stocks['StdDev_1Y'] > high_vol_threshold) & (df_stocks['Beta_1Y'] > 1.1) &
        (df_stocks['Revenue_YoY_Accumulated'] > 15)
    ].sort_values(by=['Revenue_YoY_Accumulated', 'ROE_Latest_Quarter'], ascending=[False, False])
    return pools

def create_etf_pools(df_etf):
    """建立ETF標的池"""
    pools = {}
    pools['market_cap'] = df_etf[df_etf['名稱'].str.contains('台灣50|公司治理|S&P 500|市值', na=False)]
    pools['high_dividend'] = df_etf[df_etf['名稱'].str.contains('高股息|高息', na=False)]
    pools['theme'] = df_etf[df_etf['名稱'].str.contains('半導體|科技|AI|電動車|綠能', na=False)]
    pools['gov_bond'] = df_etf[df_etf['名稱'].str.contains('公債|政府債', na=False)]
    pools['corp_bond'] = df_etf[df_etf['名稱'].str.contains('公司債|投資級', na=False)]
    return pools

def build_portfolio(risk_profile, portfolio_type, stock_pools, etf_pools, forced_include=None):
    """主函數：建構投資組合"""
    portfolio_df = pd.DataFrame()

    # --- 純個股投資組合 ---
    if portfolio_type == '純個股':
        if risk_profile == '保守型':
            pool = stock_pools['conservative']
            count = np.random.randint(*config.CONSERVATIVE_STOCK_COUNT)
            portfolio_df = pool.groupby('Industry').head(config.MAX_INDUSTRY_CONCENTRATION).head(count)
            if not portfolio_df.empty: portfolio_df['Weight'] = apply_factor_weighting(portfolio_df, 'Dividend_Yield')
        elif risk_profile == '穩健型':
            pool = stock_pools['moderate']
            count = np.random.randint(*config.MODERATE_STOCK_COUNT)
            portfolio_df = pool.groupby('Industry').head(config.MAX_INDUSTRY_CONCENTRATION).head(count)
            if not portfolio_df.empty: portfolio_df['Weight'] = apply_factor_weighting(portfolio_df, 'ROE_Avg_3Y')
        elif risk_profile == '積極型':
            pool = stock_pools['aggressive']
            count = np.random.randint(*config.AGGRESSIVE_STOCK_COUNT)
            # 積極型可集中產業
            portfolio_df = pool.head(count)
            if not portfolio_df.empty: portfolio_df['Weight'] = apply_factor_weighting(portfolio_df, 'Revenue_YoY_Accumulated')

    # --- 純ETF投資組合 ---
    elif portfolio_type == '純ETF':
        if risk_profile == '保守型':
            alloc = config.CONSERVATIVE_ETF_ALLOC
            stock_etf = etf_pools['high_dividend'].head(1)
            bond_etfs = pd.concat([etf_pools['gov_bond'].head(1), etf_pools['corp_bond'].head(1)])
            portfolio_df = pd.concat([stock_etf, bond_etfs])
            if not portfolio_df.empty: portfolio_df['Weight'] = [alloc['stocks']/100, (alloc['bonds']/100)*0.6, (alloc['bonds']/100)*0.4]
        elif risk_profile == '穩健型':
            alloc = config.MODERATE_ETF_ALLOC
            core_etf = etf_pools['market_cap'].head(1)
            theme_etf = etf_pools['theme'].head(1)
            bond_etf = etf_pools['gov_bond'].head(1)
            portfolio_df = pd.concat([core_etf, theme_etf, bond_etf])
            if not portfolio_df.empty: portfolio_df['Weight'] = [(alloc['stocks']/100)*0.7, (alloc['stocks']/100)*0.3, alloc['bonds']/100]
        elif risk_profile == '積極型':
            alloc = config.AGGRESSIVE_ETF_ALLOC
            core_etf = etf_pools['market_cap'].head(1)
            theme_etfs = etf_pools['theme'].head(2)
            bond_etf = etf_pools['gov_bond'].head(1)
            portfolio_df = pd.concat([core_etf, theme_etfs, bond_etf])
            if not portfolio_df.empty: portfolio_df['Weight'] = [(alloc['stocks']/100)*0.4, (alloc['stocks']/100)*0.25, (alloc['stocks']/100)*0.25, alloc['bonds']/100]
    
    # --- 混合型投資組合 ---
    elif portfolio_type == '混合型':
        if risk_profile == '保守型':
            alloc = config.CONSERVATIVE_HYBRID_ALLOC
            core = pd.concat([etf_pools['high_dividend'].head(1), etf_pools['gov_bond'].head(1)])
            core['Weight'] = [0.5, 0.5]
            satellite = stock_pools['conservative'].head(4)
            satellite['Weight'] = apply_factor_weighting(satellite, 'Dividend_Yield')
            portfolio_df = pd.concat([core, satellite])
            portfolio_df['Weight'] *= np.append(np.full(len(core), alloc['core']/100), np.full(len(satellite), alloc['satellite']/100))
        elif risk_profile == '穩健型':
            alloc = config.MODERATE_HYBRID_ALLOC
            core = etf_pools['market_cap'].head(1)
            core['Weight'] = 1.0
            satellite = stock_pools['moderate'].head(4)
            satellite['Weight'] = apply_factor_weighting(satellite, 'ROE_Avg_3Y')
            portfolio_df = pd.concat([core, satellite])
            portfolio_df['Weight'] *= np.append(np.full(len(core), alloc['core']/100), np.full(len(satellite), alloc['satellite']/100))
        elif risk_profile == '積極型':
            alloc = config.AGGRESSIVE_HYBRID_ALLOC
            core = etf_pools['theme'].head(2)
            core['Weight'] = [0.5, 0.5]
            satellite = stock_pools['aggressive'].head(3)
            satellite['Weight'] = apply_factor_weighting(satellite, 'Revenue_YoY_Accumulated')
            portfolio_df = pd.concat([core, satellite])
            portfolio_df['Weight'] *= np.append(np.full(len(core), alloc['core']/100), np.full(len(satellite), alloc['satellite']/100))

    if portfolio_df.empty:
        return pd.DataFrame()

    # 正規化權重，確保總和為1
    if portfolio_df['Weight'].sum() > 0:
        portfolio_df['Weight'] /= portfolio_df['Weight'].sum()

    # 動態調整邏輯：如果使用者強制加入某標的
    if forced_include is not None:
        stock_to_add = forced_include.copy()
        # 給予新加入標的 10% 基礎權重，並從其他標的等比例扣除
        new_weight = 0.10
        portfolio_df['Weight'] *= (1 - new_weight)
        stock_to_add['Weight'] = new_weight
        portfolio_df = pd.concat([portfolio_df, stock_to_add.to_frame().T])
        portfolio_df.index.name = 'StockID'
        portfolio_df = portfolio_df.reset_index().drop_duplicates(subset='StockID', keep='last').set_index('StockID')
        # 再次正規化
        portfolio_df['Weight'] /= portfolio_df['Weight'].sum()
        
    return portfolio_df.sort_values('Weight', ascending=False)