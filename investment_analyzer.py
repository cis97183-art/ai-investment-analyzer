# investment_analyzer.py

import pandas as pd
import numpy as np
from portfolio_rules import PORTFOLIO_CONSTRUCTION_RULES

def _calculate_hhi(weights: list) -> float:
    """計算 HHI 集中度指數"""
    return sum([w**2 for w in weights])

def _to_numeric(series):
    """輔助函式：將 Series 轉換為數值型態，錯誤則轉為 NaN"""
    return pd.to_numeric(series, errors='coerce')

def build_portfolio(asset_pools: dict, risk_preference: str, portfolio_type: str) -> (pd.DataFrame, dict):
    """
    根據使用者偏好與規則建構投資組合。
    
    返回:
        - portfolio_df: 最終的投資組合 DataFrame (包含代碼、名稱、權重等)
        - candidate_pools: 用於建構此組合的候選標的池 (字典)
    """
    print(f"\n--- 步驟 3: 建構 {risk_preference} 型 {portfolio_type} 投資組合 ---")
    
    rules = PORTFOLIO_CONSTRUCTION_RULES.get(portfolio_type, {}).get(risk_preference)
    if not rules:
        raise ValueError("找不到對應的投資組合建構規則。")

    portfolio_df = pd.DataFrame()
    candidate_pools = {}
    
    # --- 策略一：純個股組合 ---
    if portfolio_type == 'Stocks':
        source_pool_name = rules['source_pool']
        source_pool = asset_pools.get(source_pool_name, pd.DataFrame())
        candidate_pools[source_pool_name] = source_pool
        
        if source_pool.empty:
            print(f"警告: '{source_pool_name}' 標的池為空，無法建立投資組合。")
            return pd.DataFrame(), candidate_pools
            
        # 依產業分散原則挑選標的
        num_assets = rules['num_assets'][1] # 取數量上限
        max_per_industry = rules['diversification'].get('max_per_industry', num_assets)
        
        selected_stocks = []
        industry_counts = {}
        for _, stock in source_pool.iterrows():
            if len(selected_stocks) >= num_assets:
                break
            industry = stock['產業別']
            if industry_counts.get(industry, 0) < max_per_industry:
                selected_stocks.append(stock)
                industry_counts[industry] = industry_counts.get(industry, 0) + 1
        
        portfolio_df = pd.DataFrame(selected_stocks)
        
        # 分配權重
        weight_factor = rules.get('weighting_factor')
        portfolio_df[weight_factor] = _to_numeric(portfolio_df[weight_factor])
        
        # 因子加權，若因子數值<=0或為NaN，給予極小權重
        factor_values = portfolio_df[weight_factor].fillna(0.0001)
        factor_values[factor_values <= 0] = 0.0001
        total_factor = factor_values.sum()
        
        if total_factor > 0:
            portfolio_df['權重(%)'] = (factor_values / total_factor * 100).round(2)
        else: # 如果所有因子都是負的，就用平均權重
             portfolio_df['權重(%)'] = (100 / len(portfolio_df)).round(2)

    # --- 策略二：純ETF組合 ---
    elif portfolio_type == 'ETF':
        # 這是簡化版的ETF配置，僅作為範例
        # 完整的機構級配置需要更複雜的模型 (例如 MVO)
        selected_etfs = []
        
        # 挑選股票型ETF
        stock_alloc = rules['asset_allocation']['Stocks']
        if stock_alloc > 0:
            stock_pool_names = rules['stock_source_pools']
            # 合併所有候選股票ETF池
            all_stock_etfs = pd.concat([asset_pools.get(p, pd.DataFrame()) for p in stock_pool_names]).drop_duplicates(subset=['代碼'])
            candidate_pools['股票ETF'] = all_stock_etfs.sort_values(by='年報酬率.含息.', ascending=False)
            # 簡單挑選2檔績效最好的
            selected_etfs.extend(candidate_pools['股票ETF'].head(2).to_dict('records'))

        # 挑選債券型ETF
        bond_alloc = rules['asset_allocation']['Bonds']
        if bond_alloc > 0:
            bond_pool_names = rules['bond_source_pools']
            all_bond_etfs = pd.concat([asset_pools.get(p, pd.DataFrame()) for p in bond_pool_names]).drop_duplicates(subset=['代碼'])
            candidate_pools['債券ETF'] = all_bond_etfs.sort_values(by='一年(σ年)')
            # 簡單挑選2檔波動最低的
            selected_etfs.extend(candidate_pools['債券ETF'].head(2).to_dict('records'))
            
        portfolio_df = pd.DataFrame(selected_etfs).drop_duplicates(subset=['代碼'])
        # 簡化權重分配：平均分配
        portfolio_df['權重(%)'] = (100 / len(portfolio_df)).round(2)

    # --- 策略三：混合型組合 ---
    elif portfolio_type == 'Hybrid':
        core_alloc = rules['core_satellite_split']['core']
        satellite_alloc = rules['core_satellite_split']['satellite']
        
        # 核心ETF
        core_etf_pools_names = rules['core_etf_pools']
        all_core_etfs = pd.concat([asset_pools.get(p, pd.DataFrame()) for p in core_etf_pools_names]).drop_duplicates(subset=['代碼'])
        candidate_pools['核心ETF'] = all_core_etfs.sort_values(by='一年(σ年)')
        core_selection = candidate_pools['核心ETF'].head(2) # 挑選波動最低的2檔
        
        # 衛星個股
        satellite_pool_name = rules['satellite_stock_pool']
        satellite_pool = asset_pools.get(satellite_pool_name, pd.DataFrame())
        candidate_pools['衛星個股'] = satellite_pool
        num_satellite = rules['num_satellite_stocks'][1]
        satellite_selection = candidate_pools['衛星個股'].head(num_satellite)

        # 合併並分配權重
        portfolio_df = pd.concat([core_selection, satellite_selection])
        num_core = len(core_selection)
        num_satellite = len(satellite_selection)
        
        if num_core > 0:
            portfolio_df.loc[core_selection.index, '權重(%)'] = (core_alloc * 100 / num_core).round(2)
        if num_satellite > 0:
            portfolio_df.loc[satellite_selection.index, '權重(%)'] = (satellite_alloc * 100 / num_satellite).round(2)
        
    else:
        print(f"錯誤: 不支援的組合類型 '{portfolio_type}'")
        return pd.DataFrame(), {}

    # 確保權重總和為100%
    if not portfolio_df.empty:
        diff = 100 - portfolio_df['權重(%)'].sum()
        portfolio_df.loc[portfolio_df.index[0], '權重(%)'] += diff

    # 計算 HHI
    hhi = _calculate_hhi(portfolio_df['權重(%)'].values / 100)
    print(f"投資組合建構完成，共 {len(portfolio_df)} 筆標的，HHI值為: {hhi:.4f}")

    return portfolio_df, candidate_pools