# investment_analyzer.py (最終策略重構版)

import pandas as pd
import numpy as np
from portfolio_rules import PORTFOLIO_CONSTRUCTION_RULES
import config

def calculate_hhi(weights):
    if not weights: return 0.0
    return sum([w**2 for w in weights])

def _factor_weighting(df, factor_col):
    """根據因子數值分配權重"""
    factor_values = df[factor_col].copy()
    factor_values[factor_values < 0] = 0
    factor_values.fillna(0, inplace=True)
    total_factor = factor_values.sum()
    if total_factor > 0:
        return (factor_values / total_factor).tolist()
    else:
        return [1 / len(df)] * len(df)

def build_portfolio(screened_assets, portfolio_type, risk_profile, master_df):
    """根據最新、最詳細的客製化規則建構投資組合。"""
    print(f"\n--- 開始建構【{risk_profile} - {portfolio_type}】投資組合 ---")
    
    try:
        rules = PORTFOLIO_CONSTRUCTION_RULES[risk_profile][portfolio_type]
    except KeyError:
        print(f"錯誤：找不到對應的組合規則 [{risk_profile}][{portfolio_type}]")
        return None, 0.0

    final_portfolio_df = pd.DataFrame()
    weights = []

    # ========================== 純個股 (Pure Stock) ==========================
    if portfolio_type == '純個股':
        stocks = screened_assets[screened_assets['資產類別'] == '上市櫃股票'].copy()
        
        # 1. 因子排序
        factor_col = rules['weighting_factor']
        stocks.sort_values(by=factor_col, ascending=False, inplace=True)
        print(f"採用「{factor_col}」因子進行排序...")
        
        # 2. 產業分散選股
        selection = []
        industry_count = {}
        for _, row in stocks.iterrows():
            if len(selection) >= rules['num_assets_max']: break
            industry = row['產業別']
            if industry_count.get(industry, 0) < rules['max_industry_assets']:
                selection.append(row)
                industry_count[industry] = industry_count.get(industry, 0) + 1
        
        if len(selection) < rules['num_assets_min']: return None, 0.0
        final_portfolio_df = pd.DataFrame(selection)
        
        # 3. 權重分配
        if rules['weighting_method'] == '因子加權':
            weights = _factor_weighting(final_portfolio_df, factor_col)
        else: # 平均權重
            weights = [1 / len(final_portfolio_df)] * len(final_portfolio_df)

    # ========================== 純 ETF (Pure ETF) ==========================
    elif portfolio_type == '純 ETF':
        etfs = screened_assets[screened_assets['資產類別'] == 'ETF'].copy()
        if len(etfs) < rules['num_assets_min']: return None, 0.0

        etfs_calc = etfs[etfs['一年(σ年)'] > 0].copy()
        etfs_calc['sharpe_ratio'] = (etfs_calc['年報酬率(含息)'].fillna(0) - config.RISK_FREE_RATE) / (etfs_calc['一年(σ年)'] / 100)
        etfs_calc.sort_values(by='sharpe_ratio', ascending=False, inplace=True)

        # 類型分散選股
        selection_list = []
        if rules.get('required_etf_type'):
            required_etf = etfs_calc[etfs_calc['產業別'] == rules['required_etf_type']].head(1)
            if not required_etf.empty:
                selection_list.append(required_etf.iloc[0])
        
        remaining_etfs = etfs_calc.drop(index=[s.name for s in selection_list])
        needed = rules['num_assets_max'] - len(selection_list)
        selection_list.extend([row for _, row in remaining_etfs.head(needed).iterrows()])
        
        if len(selection_list) < rules['num_assets_min']: return None, 0.0
        final_portfolio_df = pd.DataFrame(selection_list)
        
        # 權重分配
        if rules['weighting_method'] == '波動率倒數加權':
            inv_vols = 1 / final_portfolio_df['一年(σ年)']
            weights = (inv_vols / inv_vols.sum()).tolist()
        elif rules['weighting_method'] == '集中加權':
            weights = [0] * len(final_portfolio_df)
            weights[0] = 1.0 # 100% 集中在第一支
        else: # 平均權重
            weights = [1 / len(final_portfolio_df)] * len(final_portfolio_df)

    # ========================== 混合型 (Mixed) ==========================
    elif portfolio_type == '混合型':
        stocks = screened_assets[screened_assets['資產類別'] == '上市櫃股票'].copy()
        etfs = screened_assets[screened_assets['資產類別'] == 'ETF'].copy()

        # Core
        core_etfs_calc = etfs[etfs['產業別'].isin(rules['core_etf_type']) & (etfs['一年(σ年)'] > 0)]
        core_etfs_calc['sharpe_ratio'] = (core_etfs_calc['年報酬率(含息)'].fillna(0) - config.RISK_FREE_RATE) / (core_etfs_calc['一年(σ年)'] / 100)
        core_etfs_calc.sort_values(by='sharpe_ratio', ascending=False, inplace=True)
        core_df = core_etfs_calc.head(rules['core_etfs'])

        # Satellite
        satellite_sort_factor = PORTFOLIO_CONSTRUCTION_RULES[risk_profile]['純個股']['weighting_factor']
        stocks.sort_values(by=satellite_sort_factor, ascending=False, inplace=True)
        
        satellite_selection = []
        industry_count = {}
        for _, row in stocks.iterrows():
            if len(satellite_selection) >= rules['satellite_stocks']: break
            industry = row['產業別']
            if industry_count.get(industry, 0) < rules['max_industry_assets']:
                satellite_selection.append(row)
                industry_count[industry] = industry_count.get(industry, 0) + 1
        satellite_df = pd.DataFrame(satellite_selection)

        if core_df.empty or satellite_df.empty: return None, 0.0

        # Combine & Weight
        core_weight, satellite_weight = rules['core_weight'], 1 - rules['core_weight']
        core_df['建議權重'] = f"{(core_weight / len(core_df)):.2%}"
        satellite_df['建議權重'] = f"{(satellite_weight / len(satellite_df)):.2%}"
        
        final_portfolio_df = pd.concat([core_df, satellite_df], ignore_index=True)
        weights = [core_weight/len(core_df)]*len(core_df) + [satellite_weight/len(satellite_df)]*len(satellite_df)
    
    # 最終處理
    hhi = calculate_hhi(weights)
    if '建議權重' not in final_portfolio_df.columns:
        final_portfolio_df['建議權重'] = [f"{w:.2%}" for w in weights]
    
    cols_to_keep = ['代號', '名稱', '產業別', '資產類別', '建議權重', 'sharpe_ratio']
    final_cols = [col for col in cols_to_keep if col in final_portfolio_df.columns]
    
    return final_portfolio_df[final_cols], hhi