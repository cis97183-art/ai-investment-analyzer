# investment_analyzer.py

import pandas as pd
import numpy as np
from portfolio_rules import PORTFOLIO_CONSTRUCTION_RULES
import config

def calculate_hhi(weights):
    """計算 Herfindahl-Hirschman Index (HHI)"""
    if not weights:
        return 0.0
    return sum([w**2 for w in weights])

def build_portfolio(screened_assets, portfolio_type, risk_profile, master_df):
    """
    根據最新、最詳細的規則建構投資組合。
    回傳: (DataFrame of portfolio, float of HHI value)
    """
    print(f"\n--- 開始建構【{risk_profile} - {portfolio_type}】投資組合 ---")
    
    rules = PORTFOLIO_CONSTRUCTION_RULES.get(portfolio_type)
    if not rules:
        print(f"錯誤：找不到 '{portfolio_type}' 的規則。")
        return None, 0.0

    # ========================== 純個股 (Pure Stock) ==========================
    if portfolio_type == '純個股':
        stocks = screened_assets[screened_assets['資產類別'] == '上市櫃股票'].copy()
        
        if risk_profile in ['保守型', '穩健型']:
            sort_factor = '近3年平均ROE(%)'
            # 優先使用 ROE，若無則用殖利率作為次要排序因子
            stocks.sort_values(by=[sort_factor, '成交價現金殖利率'], ascending=False, inplace=True)
            print(f"採用「{sort_factor}」因子進行排序...")
        else: # 積極型
            sort_factor = '累月營收年增(%)'
            # 優先使用營收成長，若無則用年報酬率
            stocks.sort_values(by=[sort_factor, '年報酬率(含息)'], ascending=False, inplace=True)
            print(f"採用「{sort_factor}」因子進行排序...")

        selection = []
        industry_count = {}
        for _, row in stocks.iterrows():
            if len(selection) >= rules['max_assets']:
                break
            industry = row['產業別']
            if industry_count.get(industry, 0) < rules['max_industry_assets']:
                selection.append(row)
                industry_count[industry] = industry_count.get(industry, 0) + 1
        
        if not selection:
            return None, 0.0
        
        final_portfolio_df = pd.DataFrame(selection).reset_index(drop=True)
        num_assets = len(final_portfolio_df)
        weights = [1 / num_assets] * num_assets
        final_portfolio_df['建議權重'] = [f"{w:.2%}" for w in weights]
        hhi = calculate_hhi(weights)
        
        cols_to_keep = ['代號', '名稱', '產業別', '資產類別', '建議權重']
        return final_portfolio_df[cols_to_keep], hhi

    # ========================== 純 ETF (Pure ETF) ==========================
    elif portfolio_type == '純 ETF':
        etfs = screened_assets[screened_assets['資產類別'] == 'ETF'].copy()
        if len(etfs) < rules['min_assets']:
            return None, 0.0

        etfs_calc = etfs[etfs['一年(σ年)'] > 0].copy()
        etfs_calc['sharpe_ratio'] = (etfs_calc['年報酬率(含息)'].fillna(0) - config.RISK_FREE_RATE) / (etfs_calc['一年(σ年)'] / 100)
        etfs_calc.sort_values(by='sharpe_ratio', ascending=False, inplace=True)

        selection_list = []
        selected_indices = []

        if risk_profile == '保守型':
            bond_etf = etfs_calc[etfs_calc['產業別'] == '債券ETF'].head(1)
            if not bond_etf.empty:
                selection_list.append(bond_etf.iloc[0])
                selected_indices.append(bond_etf.index[0])
        
        large_cap = etfs_calc[~etfs_calc.index.isin(selected_indices) & (etfs_calc['產業別'] == '國內成分股ETF')].head(1)
        if not large_cap.empty:
            selection_list.append(large_cap.iloc[0])
            selected_indices.append(large_cap.index[0])

        needed = rules['max_assets'] - len(selection_list)
        if needed > 0:
            remaining_etfs = etfs_calc[~etfs_calc.index.isin(selected_indices)]
            selection_list.extend(remaining_etfs.head(needed).to_dict('records'))

        if not selection_list: return None, 0.0
        final_portfolio_df = pd.DataFrame(selection_list)
        num_assets = len(final_portfolio_df)
        weights = []

        if risk_profile == '保守型' and any(final_portfolio_df['產業別'] == '債券ETF'):
            bond_count = (final_portfolio_df['產業別'] == '債券ETF').sum()
            other_count = num_assets - bond_count
            weight_bond = 0.6 / bond_count if bond_count > 0 else 0
            weight_other = 0.4 / other_count if other_count > 0 else 0
            weights = [weight_bond if etf_type == '債券ETF' else weight_other for etf_type in final_portfolio_df['產業別']]
        else:
            weights = [1 / num_assets] * num_assets
        
        final_portfolio_df['建議權重'] = [f"{w:.2%}" for w in weights]
        hhi = calculate_hhi(weights)
        
        cols_to_keep = ['代號', '名稱', '產業別', '資產類別', '建議權重', 'sharpe_ratio']
        final_cols = [col for col in cols_to_keep if col in final_portfolio_df.columns]
        return final_portfolio_df[final_cols], hhi

    # ========================== 混合型 (Mixed) ==========================
    elif portfolio_type == '混合型':
        stocks = screened_assets[screened_assets['資產類別'] == '上市櫃股票'].copy()
        etfs = screened_assets[screened_assets['資產類別'] == 'ETF'].copy()

        # Core
        core_etfs_calc = etfs[etfs['一年(σ年)'] > 0].copy()
        core_etfs_calc['sharpe_ratio'] = (core_etfs_calc['年報酬率(含息)'].fillna(0) - config.RISK_FREE_RATE) / (core_etfs_calc['一年(σ年)'] / 100)
        core_etfs_calc.sort_values(by='sharpe_ratio', ascending=False, inplace=True)
        core_df = core_etfs_calc.head(rules['core_etfs'])

        # Satellite
        if risk_profile in ['保守型', '穩健型']:
            stocks.sort_values(by='近3年平均ROE(%)', ascending=False, inplace=True)
        else:
            stocks.sort_values(by='累月營收年增(%)', ascending=False, inplace=True)
        
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
        all_weights = [core_weight/len(core_df)]*len(core_df) + [satellite_weight/len(satellite_df)]*len(satellite_df)
        hhi = calculate_hhi(all_weights)
        
        cols_to_keep = ['代號', '名稱', '產業別', '資產類別', '建議權重']
        final_cols = [col for col in cols_to_keep if col in final_portfolio_df.columns]
        return final_portfolio_df[final_cols], hhi

    return None, 0.0