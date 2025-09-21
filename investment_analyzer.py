# investment_analyzer.py (最終版)

import pandas as pd
import numpy as np
from portfolio_rules import PORTFOLIO_CONSTRUCTION_RULES

def _to_numeric(series):
    """輔助函式：將 Series 轉換為數值型態，錯誤則轉為 NaN"""
    return pd.to_numeric(series, errors='coerce')

def build_portfolio(asset_pools: dict, risk_preference: str, portfolio_type: str) -> (pd.DataFrame, dict):
    """
    根據使用者偏好與規則庫，從候選標的池中建立最終的投資組合。
    
    返回:
        - portfolio_df: 最終的投資組合 DataFrame (包含代碼、名稱、權重等)
        - candidate_pools: 用於建構此組合的候選標的池 (字典)
    """
    print(f"\n--- 步驟 3: 建構 「{risk_preference} - {portfolio_type}」 投資組合 ---")
    
    try:
        rules = PORTFOLIO_CONSTRUCTION_RULES[portfolio_type][risk_preference]
    except KeyError:
        print(f"錯誤: 在 portfolio_rules.py 中找不到對應 '{portfolio_type}' -> '{risk_preference}' 的建構規則。")
        return pd.DataFrame(), {}

    portfolio_df = pd.DataFrame()
    candidate_pools = {}
    
    # --- 策略一：純個股組合 ---
    if portfolio_type == '純個股':
        source_pool_name = rules['source_pool']
        source_pool = asset_pools.get(source_pool_name, pd.DataFrame())
        candidate_pools[source_pool_name] = source_pool
        
        if source_pool.empty:
            print(f"警告: '{source_pool_name}' 標的池為空，無法建立投資組合。")
            return pd.DataFrame(), candidate_pools
            
        num_assets = rules['num_assets'][1] # 取數量上限
        max_per_industry = rules['diversification'].get('max_per_industry', num_assets)
        
        selected_stocks = []
        industry_counts = {}
        for _, stock in source_pool.iterrows():
            if len(selected_stocks) >= num_assets: break
            industry = stock['產業別']
            if industry_counts.get(industry, 0) < max_per_industry:
                selected_stocks.append(stock)
                industry_counts[industry] = industry_counts.get(industry, 0) + 1
        
        portfolio_df = pd.DataFrame(selected_stocks)
        
        if not portfolio_df.empty:
            weight_factor = rules.get('weighting_factor')
            portfolio_df[weight_factor] = _to_numeric(portfolio_df[weight_factor])
            # 因子加權：將因子值標準化為權重
            factor_values = portfolio_df[weight_factor].fillna(0.0001)
            factor_values[factor_values <= 0] = 0.0001
            portfolio_df['權重(%)'] = (factor_values / factor_values.sum() * 100).round(2)

    # --- 策略二：純ETF組合 ---
    elif portfolio_type == '純ETF':
        selected_etfs_list = []
        num_per_cat = rules['num_assets_per_category']

        # 處理股票型ETF
        stock_alloc = rules['asset_allocation']['Stocks']
        if stock_alloc > 0:
            stock_pool_names = rules['stock_source_pools']
            all_stock_etfs = pd.concat([asset_pools.get(p, pd.DataFrame()) for p in stock_pool_names]).drop_duplicates(subset=['代碼'])
            candidate_pools['股票型ETF'] = all_stock_etfs
            selected_etfs_list.extend(all_stock_etfs.head(num_per_cat).to_dict('records'))

        # 處理債券型ETF
        bond_alloc = rules['asset_allocation']['Bonds']
        if bond_alloc > 0:
            bond_pool_names = rules['bond_source_pools']
            all_bond_etfs = pd.concat([asset_pools.get(p, pd.DataFrame()) for p in bond_pool_names]).drop_duplicates(subset=['代碼'])
            candidate_pools['債券型ETF'] = all_bond_etfs
            selected_etfs_list.extend(all_bond_etfs.head(num_per_cat).to_dict('records'))

        if not selected_etfs_list:
            return pd.DataFrame(), candidate_pools

        portfolio_df = pd.DataFrame(selected_etfs_list).drop_duplicates(subset=['代碼'])
        # 股債比例加權
        num_stock_etfs = sum(1 for etf in selected_etfs_list if etf['代碼'] in all_stock_etfs['代碼'].values)
        num_bond_etfs = len(selected_etfs_list) - num_stock_etfs
        
        if num_stock_etfs > 0:
            portfolio_df.loc[portfolio_df['代碼'].isin(all_stock_etfs['代碼']), '權重(%)'] = (stock_alloc * 100 / num_stock_etfs).round(2)
        if num_bond_etfs > 0:
            portfolio_df.loc[portfolio_df['代碼'].isin(all_bond_etfs['代碼']), '權重(%)'] = (bond_alloc * 100 / num_bond_etfs).round(2)

    # --- 策略三：混合型組合 ---
    elif portfolio_type == '混合型':
        # 核心部分 (Core) - 通常是穩健的ETF
        core_alloc = rules['core_satellite_split']['core']
        core_etf_pools_names = rules['core_etf_pools']
        all_core_etfs = pd.concat([asset_pools.get(p, pd.DataFrame()) for p in core_etf_pools_names]).drop_duplicates(subset=['代碼'])
        candidate_pools['核心ETF'] = all_core_etfs
        core_selection = candidate_pools['核心ETF'].head(rules['num_core_etfs'])

        # 衛星部分 (Satellite) - 通常是積極的個股
        satellite_alloc = rules['core_satellite_split']['satellite']
        satellite_pool_name = rules['satellite_stock_pool']
        satellite_pool = asset_pools.get(satellite_pool_name, pd.DataFrame())
        candidate_pools['衛星個股'] = satellite_pool
        num_satellite = rules['num_satellite_stocks'][1]
        satellite_selection = candidate_pools['衛星個股'].head(num_satellite)

        portfolio_df = pd.concat([core_selection, satellite_selection])
        
        if not portfolio_df.empty:
            # 分別給予核心與衛星部位權重
            if not core_selection.empty:
                portfolio_df.loc[core_selection.index, '權重(%)'] = (core_alloc * 100 / len(core_selection)).round(2)
            if not satellite_selection.empty:
                portfolio_df.loc[satellite_selection.index, '權重(%)'] = (satellite_alloc * 100 / len(satellite_selection)).round(2)
    
    # --- 最後的權重調整 ---
    if not portfolio_df.empty:
        portfolio_df['權重(%)'].fillna(0, inplace=True)
        # 確保總權重為 100%
        diff = 100 - portfolio_df['權重(%)'].sum()
        if diff != 0 and not portfolio_df.empty:
            portfolio_df.iloc[0, portfolio_df.columns.get_loc('權重(%)')] += diff
        
        print(f"投資組合建構完成，共 {len(portfolio_df)} 筆標的。")
        return portfolio_df.reset_index(drop=True), candidate_pools

    return pd.DataFrame(), candidate_pools
