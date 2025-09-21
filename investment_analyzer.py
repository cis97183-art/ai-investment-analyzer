# investment_analyzer.py (已修正 KeyError)

import pandas as pd
import numpy as np
from portfolio_rules import PORTFOLIO_CONSTRUCTION_RULES

def _calculate_hhi(weights: list) -> float:
    """計算 HHI 集中度指數。權重應為 0-1 之間的小數。"""
    if not weights:
        return 0.0
    return sum([w**2 for w in weights])

def _to_numeric(series: pd.Series) -> pd.Series:
    """輔助函式：將 Series 轉換為數值型態，錯誤則轉為 NaN"""
    return pd.to_numeric(series, errors='coerce')

def build_portfolio(asset_pools: dict, risk_preference: str, portfolio_type: str) -> (pd.DataFrame, dict):
    """
    根據使用者偏好與規則建構最終的投資組合。
    返回:
        - portfolio_df: 包含權重的最終投資組合 DataFrame。
        - candidate_pools: 用於建構此組合的候選標的池字典。
    """
    print(f"\n--- 步驟 3: 建構 {risk_preference} 型 {portfolio_type} 投資組合 ---")
    
    rules = PORTFOLIO_CONSTRUCTION_RULES.get(portfolio_type, {}).get(risk_preference)
    if not rules:
        print(f"錯誤：在 portfolio_rules.py 中找不到對應 '{portfolio_type}' -> '{risk_preference}' 的建構規則。")
        return pd.DataFrame(), {}

    portfolio_df = pd.DataFrame()
    candidate_pools = {}
    
    # --- 策略一：純個股組合 ---
    if portfolio_type == '純個股':
        source_pool_name = rules['source_pool']
        source_pool = asset_pools.get(source_pool_name, pd.DataFrame())
        candidate_pools[source_pool_name] = source_pool
        
        if source_pool.empty:
            print(f"警告: '{source_pool_name}' 候選池為空，無法建立純個股投資組合。")
            return pd.DataFrame(), candidate_pools
            
        num_assets = rules['num_assets'][1]
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
        
        if portfolio_df.empty:
             return pd.DataFrame(), candidate_pools

        weight_factor = rules.get('weighting_factor')
        if weight_factor and weight_factor in portfolio_df.columns:
            portfolio_df[weight_factor] = _to_numeric(portfolio_df[weight_factor])
            factor_values = portfolio_df[weight_factor].fillna(0.0001)
            factor_values[factor_values <= 0] = 0.0001
            total_factor = factor_values.sum()
            
            if total_factor > 0:
                portfolio_df['權重(%)'] = (factor_values / total_factor * 100).round(2)
            else:
                 portfolio_df['權重(%)'] = (100 / len(portfolio_df)).round(2)
        else:
            portfolio_df['權重(%)'] = (100 / len(portfolio_df)).round(2)

    # --- 策略二：純ETF組合 ---
    elif portfolio_type == '純ETF':
        selected_etfs_list = []
        
        stock_alloc = rules['asset_allocation']['Stocks']
        if stock_alloc > 0:
            stock_pool_names = rules['stock_source_pools']
            all_stock_etfs = pd.concat([asset_pools.get(p, pd.DataFrame()) for p in stock_pool_names], ignore_index=True)
            
            if not all_stock_etfs.empty and '代碼' in all_stock_etfs.columns:
                all_stock_etfs.drop_duplicates(subset=['代碼'], inplace=True)
                sort_key = '年報酬率.含息.' if risk_preference == '積極型' else '一年(σ年)'
                ascending = False if risk_preference == '積極型' else True
                
                # 【核心修正】排序前先檢查欄位是否存在
                if sort_key in all_stock_etfs.columns:
                    candidate_pools['股票ETF'] = all_stock_etfs.sort_values(by=sort_key, ascending=ascending)
                else:
                    print(f"警告: ETF資料中缺少 '{sort_key}' 欄位，無法進行排序。")
                    candidate_pools['股票ETF'] = all_stock_etfs
                
                selected_etfs_list.extend(candidate_pools['股票ETF'].head(2).to_dict('records'))

        bond_alloc = rules['asset_allocation']['Bonds']
        if bond_alloc > 0:
            bond_pool_names = rules['bond_source_pools']
            all_bond_etfs = pd.concat([asset_pools.get(p, pd.DataFrame()) for p in bond_pool_names], ignore_index=True)

            if not all_bond_etfs.empty and '代碼' in all_bond_etfs.columns:
                all_bond_etfs.drop_duplicates(subset=['代碼'], inplace=True)
                
                # 【核心修正】排序前先檢查欄位是否存在
                if '一年(σ年)' in all_bond_etfs.columns:
                    candidate_pools['債券ETF'] = all_bond_etfs.sort_values(by='一年(σ年)')
                else:
                    print(f"警告: 債券ETF資料中缺少 '一年(σ年)' 欄位，無法進行排序。")
                    candidate_pools['債券ETF'] = all_bond_etfs

                selected_etfs_list.extend(candidate_pools['債券ETF'].head(2).to_dict('records'))

        if not selected_etfs_list:
             return pd.DataFrame(), candidate_pools

        portfolio_df = pd.DataFrame(selected_etfs_list).drop_duplicates(subset=['代碼'])
        portfolio_df['權重(%)'] = (100 / len(portfolio_df)).round(2)

    # --- 策略三：混合型組合 ---
    elif portfolio_type == '混合型':
        core_alloc = rules['core_satellite_split']['core']
        satellite_alloc = rules['core_satellite_split']['satellite']
        
        core_etf_pools_names = rules['core_etf_pools']
        all_core_etfs = pd.concat([asset_pools.get(p, pd.DataFrame()) for p in core_etf_pools_names], ignore_index=True)
        
        core_selection = pd.DataFrame()
        if not all_core_etfs.empty and '代碼' in all_core_etfs.columns:
            all_core_etfs.drop_duplicates(subset=['代碼'], inplace=True)
            
            # 【核心修正】排序前先檢查欄位是否存在
            if '一年(σ年)' in all_core_etfs.columns:
                candidate_pools['核心ETF'] = all_core_etfs.sort_values(by='一年(σ年)')
            else:
                print(f"警告: 核心ETF資料中缺少 '一年(σ年)' 欄位，無法進行排序。")
                candidate_pools['核心ETF'] = all_core_etfs
            
            core_selection = candidate_pools['核心ETF'].head(2)

        satellite_pool_name = rules['satellite_stock_pool']
        satellite_pool = asset_pools.get(satellite_pool_name, pd.DataFrame())
        candidate_pools['衛星個股'] = satellite_pool
        num_satellite = rules['num_satellite_stocks'][1]
        satellite_selection = candidate_pools['衛星個股'].head(num_satellite)

        portfolio_df = pd.concat([core_selection, satellite_selection], ignore_index=True)
        
        if portfolio_df.empty:
             return pd.DataFrame(), candidate_pools

        num_core = len(core_selection)
        num_satellite_actual = len(satellite_selection)
        
        if num_core > 0:
            portfolio_df.loc[core_selection.index, '權重(%)'] = round(core_alloc * 100 / num_core, 2)
        if num_satellite_actual > 0:
            portfolio_df.loc[satellite_selection.index, '權重(%)'] = round(satellite_alloc * 100 / num_satellite_actual, 2)
        
    else:
        print(f"錯誤: 不支援的組合類型 '{portfolio_type}'")
        return pd.DataFrame(), {}

    if not portfolio_df.empty:
        portfolio_df['權重(%)'].fillna(0, inplace=True)
        diff = 100 - portfolio_df['權重(%)'].sum()
        if diff != 0:
            portfolio_df.loc[portfolio_df.index[0], '權重(%)'] += diff
        
        weights = portfolio_df['權重(%)'].values / 100
        hhi = _calculate_hhi(list(weights))
        print(f"投資組合建構完成，共 {len(portfolio_df)} 筆標的，HHI值為: {hhi:.4f}")

    return portfolio_df, candidate_pools

