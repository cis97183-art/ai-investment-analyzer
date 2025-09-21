# investment_analyzer.py (規則精煉最終版)

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import config

# --- Helper Functions ---
def calculate_hhi(weights):
    """計算 HHI 指數"""
    return np.sum(np.square(weights))

def apply_factor_weighting(df, factor_column):
    """應用因子加權"""
    # 確保因子欄位存在且為數值型態
    if factor_column in df.columns and pd.api.types.is_numeric_dtype(df[factor_column]):
        weights = df[factor_column].clip(lower=0.0001)
        if weights.sum() > 0:
            return weights / weights.sum()
    # 如果因子不存在或總和為0，則返回均等權重
    return pd.Series([1 / len(df)] * len(df), index=df.index)

# --- Core Logic Functions ---
def run_rule_zero(df):
    """執行基礎排雷篩選"""
    df_filtered = df.copy()
    # 排除槓桿型、反向型ETF
    if '名稱' in df_filtered.columns:
        df_filtered = df_filtered[~df_filtered['名稱'].str.contains('槓桿|反向|正2|反1', na=False)]
    # 排除規模小於50億的標的
    if 'MarketCap_Billions' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['MarketCap_Billions'] >= config.MIN_MARKET_CAP_BILLIONS]
    # 排除上市/成立未滿一年
    if 'Age_Years' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Age_Years'] >= 1]
    # 排除最新近4季自由現金流為負的個股
    if 'FCFPS_Last_4Q' in df_filtered.columns:
        stock_mask = (df_filtered['AssetType'] == '個股') & (df_filtered['FCFPS_Last_4Q'] < 0)
        df_filtered = df_filtered[~stock_mask]
    return df_filtered

def create_stock_pools(df_stocks):
    """建立個股標的池"""
    pools = {}
    # 確保欄位存在以避免錯誤
    if 'StdDev_1Y' not in df_stocks.columns:
        return {'conservative': pd.DataFrame(), 'moderate': pd.DataFrame(), 'aggressive': pd.DataFrame()}
        
    low_vol_threshold = df_stocks['StdDev_1Y'].quantile(0.30)
    high_vol_threshold = df_stocks['StdDev_1Y'].quantile(0.70)

    # 確保篩選所需的所有欄位都存在
    cons_cols = ['StdDev_1Y', 'Beta_1Y', 'Dividend_Consecutive_Years', 'FCFPS_Last_4Q', 'Dividend_Yield', 'MarketCap_Billions']
    mod_cols = ['StdDev_1Y', 'ROE_Avg_3Y', 'Revenue_YoY_Accumulated', 'MarketCap_Billions']
    agg_cols = ['StdDev_1Y', 'Beta_1Y', 'Revenue_YoY_Accumulated', 'ROE_Latest_Quarter']

    if all(col in df_stocks.columns for col in cons_cols):
        pools['conservative'] = df_stocks[(df_stocks['StdDev_1Y'] <= low_vol_threshold) & (df_stocks['Beta_1Y'] < 1.0) & (df_stocks['Dividend_Consecutive_Years'] > 10) & (df_stocks['FCFPS_Last_4Q'] > 0)].sort_values(by=['Dividend_Yield', 'MarketCap_Billions'], ascending=[False, False])
    else:
        pools['conservative'] = pd.DataFrame()

    if all(col in df_stocks.columns for col in mod_cols):
        pools['moderate'] = df_stocks[(df_stocks['StdDev_1Y'].between(low_vol_threshold, high_vol_threshold)) & (df_stocks['ROE_Avg_3Y'] > 5) & (df_stocks['Revenue_YoY_Accumulated'] > 0)].sort_values(by=['ROE_Avg_3Y', 'MarketCap_Billions'], ascending=[False, False])
    else:
        pools['moderate'] = pd.DataFrame()

    if all(col in df_stocks.columns for col in agg_cols):
        pools['aggressive'] = df_stocks[(df_stocks['StdDev_1Y'] > high_vol_threshold) & (df_stocks['Beta_1Y'] > 1.1) & (df_stocks['Revenue_YoY_Accumulated'] > 15)].sort_values(by=['Revenue_YoY_Accumulated', 'ROE_Latest_Quarter'], ascending=[False, False])
    else:
        pools['aggressive'] = pd.DataFrame()
        
    return pools

def create_etf_pools(df_etf):
    """建立ETF標的池"""
    pools = {}
    if '名稱' not in df_etf.columns:
        return {
            'market_cap': pd.DataFrame(), 'high_dividend': pd.DataFrame(), 'theme': pd.DataFrame(),
            'gov_bond': pd.DataFrame(), 'corp_bond': pd.DataFrame()
        }
    pools['market_cap'] = df_etf[df_etf['名稱'].str.contains('台灣50|公司治理|S&P 500|市值', na=False)]
    pools['high_dividend'] = df_etf[df_etf['名稱'].str.contains('高股息|高息', na=False)]
    pools['theme'] = df_etf[df_etf['名稱'].str.contains('半導體|科技|AI|電動車|綠能', na=False)]
    pools['gov_bond'] = df_etf[df_etf['名稱'].str.contains('公債|政府債', na=False)]
    pools['corp_bond'] = df_etf[df_etf['名稱'].str.contains('公司債|投資級', na=False)]
    return pools

# --- Portfolio Construction Logic ---

def _build_etf_component(risk_profile, etf_pools):
    """
    [輔助函式] 根據精煉版規則，建構純ETF投資組合的核心部分。
    """
    portfolio_df = pd.DataFrame()
    sort_cols_cons_mod = ['MarketCap_Billions', 'Expense_Ratio']
    sort_ascending_cons_mod = [False, True]
    sort_cols_agg = ['MarketCap_Billions', 'Annual_Return_Include_Dividend']
    sort_ascending_agg = [False, False]

    if risk_profile == '保守型':
        alloc = config.CONSERVATIVE_ETF_ALLOC
        stock_etf = etf_pools['high_dividend'].sort_values(by=sort_cols_cons_mod, ascending=sort_ascending_cons_mod).head(1)
        bond_etfs = pd.concat([
            etf_pools['gov_bond'].sort_values(by=sort_cols_cons_mod, ascending=sort_ascending_cons_mod).head(1),
            etf_pools['corp_bond'].sort_values(by=sort_cols_cons_mod, ascending=sort_ascending_cons_mod).head(1)
        ])
        portfolio_df = pd.concat([stock_etf, bond_etfs])
        if not portfolio_df.empty:
            weights = [alloc['stocks']/100, (alloc['bonds']/100)*0.6, (alloc['bonds']/100)*0.4]
            if len(portfolio_df) == len(weights):
                portfolio_df['Weight'] = weights

    elif risk_profile == '穩健型':
        alloc = config.MODERATE_ETF_ALLOC
        core_etf = etf_pools['market_cap'].sort_values(by=sort_cols_cons_mod, ascending=sort_ascending_cons_mod).head(1)
        theme_etf = etf_pools['theme'].sort_values(by=sort_cols_cons_mod, ascending=sort_ascending_cons_mod).head(1)
        bond_etf = etf_pools['gov_bond'].sort_values(by=sort_cols_cons_mod, ascending=sort_ascending_cons_mod).head(1)
        portfolio_df = pd.concat([core_etf, theme_etf, bond_etf])
        if not portfolio_df.empty:
            stock_total_weight = alloc['stocks'] / 100
            weights = [stock_total_weight * 0.7, stock_total_weight * 0.3, alloc['bonds']/100]
            if len(portfolio_df) == len(weights):
                portfolio_df['Weight'] = weights

    elif risk_profile == '積極型':
        alloc = config.AGGRESSIVE_ETF_ALLOC
        theme_etfs = etf_pools['theme'].sort_values(by=sort_cols_agg, ascending=sort_ascending_agg).head(2)
        core_etf = etf_pools['market_cap'].sort_values(by=sort_cols_agg, ascending=sort_ascending_agg).head(1)
        bond_etf = etf_pools['gov_bond'].sort_values(by=sort_cols_agg, ascending=sort_ascending_agg).head(1)
        portfolio_df = pd.concat([theme_etfs, core_etf, bond_etf])
        if not portfolio_df.empty:
            stock_total_weight = alloc['stocks'] / 100
            theme_weight = stock_total_weight * 0.7 / len(theme_etfs) if len(theme_etfs) > 0 else 0
            weights = [theme_weight] * len(theme_etfs) + [stock_total_weight * 0.3, alloc['bonds']/100]
            if len(portfolio_df) == len(weights):
                portfolio_df['Weight'] = weights
        
    return portfolio_df.dropna(subset=['Weight'])


def build_portfolio(risk_profile, portfolio_type, stock_pools, etf_pools, forced_include=None):
    """主函數：根據精煉版規則建構投資組合。"""
    portfolio_df = pd.DataFrame()

    # --- 純個股投資組合 ---
    if portfolio_type == '純個股':
        if risk_profile == '保守型':
            pool = stock_pools.get('conservative', pd.DataFrame())
            if not pool.empty:
                count = np.random.randint(*config.CONSERVATIVE_STOCK_COUNT)
                portfolio_df = pool.sort_values(by=['Dividend_Yield', 'MarketCap_Billions'], ascending=[False, False])
                portfolio_df = portfolio_df.groupby('Industry').head(config.MAX_INDUSTRY_CONCENTRATION).head(count).copy()
                if not portfolio_df.empty: portfolio_df['Weight'] = apply_factor_weighting(portfolio_df, 'Dividend_Yield')
        
        elif risk_profile == '穩健型':
            pool = stock_pools.get('moderate', pd.DataFrame())
            if not pool.empty:
                count = np.random.randint(*config.MODERATE_STOCK_COUNT)
                portfolio_df = pool.sort_values(by=['ROE_Avg_3Y', 'MarketCap_Billions'], ascending=[False, False])
                portfolio_df = portfolio_df.groupby('Industry').head(config.MAX_INDUSTRY_CONCENTRATION).head(count).copy()
                if not portfolio_df.empty: portfolio_df['Weight'] = apply_factor_weighting(portfolio_df, 'ROE_Avg_3Y')

        elif risk_profile == '積極型':
            pool = stock_pools.get('aggressive', pd.DataFrame())
            if not pool.empty:
                count = np.random.randint(*config.AGGRESSIVE_STOCK_COUNT)
                portfolio_df = pool.sort_values(by=['Revenue_YoY_Accumulated', 'ROE_Latest_Quarter'], ascending=[False, False]).head(count).copy()
                if not portfolio_df.empty: portfolio_df['Weight'] = apply_factor_weighting(portfolio_df, 'Revenue_YoY_Accumulated')

    # --- 純ETF投資組合 ---
    elif portfolio_type == '純ETF':
        portfolio_df = _build_etf_component(risk_profile, etf_pools)
    
    # --- 混合型投資組合 ---
    elif portfolio_type == '混合型':
        core_portfolio, satellite_portfolio = pd.DataFrame(), pd.DataFrame()
        alloc = {}
        
        if risk_profile == '保守型':
            alloc = config.CONSERVATIVE_HYBRID_ALLOC
            core_portfolio = _build_etf_component(risk_profile, etf_pools)
            satellite_pool = stock_pools.get('conservative', pd.DataFrame())
            if not satellite_pool.empty:
                count = np.random.randint(3, 6)
                satellite_portfolio = satellite_pool.sort_values(by='MarketCap_Billions', ascending=False).head(count).copy()
                if not satellite_portfolio.empty: satellite_portfolio['Weight'] = apply_factor_weighting(satellite_portfolio, 'Dividend_Yield')

        elif risk_profile == '穩健型':
            alloc = config.MODERATE_HYBRID_ALLOC
            core_portfolio = _build_etf_component(risk_profile, etf_pools)
            satellite_pool = stock_pools.get('moderate', pd.DataFrame())
            if not satellite_pool.empty:
                count = np.random.randint(3, 6)
                satellite_portfolio = satellite_pool.sort_values(by='ROE_Avg_3Y', ascending=False).head(count).copy()
                if not satellite_portfolio.empty: satellite_portfolio['Weight'] = apply_factor_weighting(satellite_portfolio, 'ROE_Avg_3Y')

        elif risk_profile == '積極型':
            alloc = config.AGGRESSIVE_HYBRID_ALLOC
            core_portfolio = _build_etf_component(risk_profile, etf_pools)
            satellite_pool = stock_pools.get('aggressive', pd.DataFrame())
            if not satellite_pool.empty:
                count = np.random.randint(2, 5)
                satellite_portfolio = satellite_pool.sort_values(by='Revenue_YoY_Accumulated', ascending=False).head(count).copy()
                if not satellite_portfolio.empty: satellite_portfolio['Weight'] = apply_factor_weighting(satellite_portfolio, 'Revenue_YoY_Accumulated')
            
        if not core_portfolio.empty and 'Weight' in core_portfolio.columns:
            core_portfolio['Weight'] *= (alloc.get('core', 0) / 100)
        if not satellite_portfolio.empty and 'Weight' in satellite_portfolio.columns:
            satellite_portfolio['Weight'] *= (alloc.get('satellite', 0) / 100)
            
        portfolio_df = pd.concat([core_portfolio, satellite_portfolio])

    # --- 後續處理 ---
    if portfolio_df.empty or 'Weight' not in portfolio_df.columns:
        return pd.DataFrame(), 0 

    # 確保權重總和為1
    if portfolio_df['Weight'].sum() > 0:
        portfolio_df['Weight'] /= portfolio_df['Weight'].sum()
    else: # 如果權重總和為0，則均等分配
        portfolio_df['Weight'] = 1 / len(portfolio_df) if len(portfolio_df) > 0 else 0

    if forced_include is not None:
        # 動態調整邏輯
        pass
    
    final_portfolio = portfolio_df.sort_values('Weight', ascending=False)
    hhi_value = calculate_hhi(final_portfolio['Weight'])
    
    return final_portfolio, hhi_value