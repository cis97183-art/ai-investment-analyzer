# investment_analyzer.py (修正版)

import pandas as pd
import numpy as np
from portfolio_rules import PORTFOLIO_CONSTRUCTION_RULES
import config

def calculate_hhi(weights):
    """計算 HHI 指數"""
    return sum([w**2 for w in weights])

def rank_based_weighting(df):
    """
    根據 DataFrame 的排名（由上到下）來分配權重。
    排名越高，權重越重。
    """
    num_assets = len(df)
    rank_scores = np.arange(num_assets, 0, -1)
    total_score = np.sum(rank_scores)
    
    if total_score > 0:
        weights = rank_scores / total_score
        return weights.tolist()
    else:
        return [1 / num_assets] * num_assets

def build_portfolio(screened_assets, portfolio_type, optimization_strategy, master_df):
    """
    根據標的池、組合類型與優化策略建構投資組合。
    """
    print(f"\n--- 開始建構【{portfolio_type} / {optimization_strategy}】投資組合 ---")
    
    if screened_assets.empty:
        print("標的池為空。")
        return None
        
    rules = PORTFOLIO_CONSTRUCTION_RULES.get(portfolio_type)
    if not rules:
        print(f"錯誤：找不到 '{portfolio_type}' 的規則。")
        return None

    portfolio_codes = []
    portfolio_weights = []

    if portfolio_type == '純個股':
        stocks = screened_assets[screened_assets['資產類別'] == '上市櫃股票'].copy()
        target_size = min(rules['max_assets'], len(stocks))
        
        final_selection_df = pd.DataFrame()
        industry_count = {}
        for _, row in stocks.iterrows():
            if len(final_selection_df) >= target_size: break
            industry = row['產業別']
            if industry_count.get(industry, 0) < rules['max_industry_assets']:
                final_selection_df = pd.concat([final_selection_df, row.to_frame().T], ignore_index=True)
                industry_count[industry] = industry_count.get(industry, 0) + 1
        
        if final_selection_df.empty:
            print("無法依產業分散規則選出任何個股。")
            return None
        
        if optimization_strategy == '夏普比率優化':
            print("採用【夏普比率優化】策略進行標的再篩選...")
            final_selection_df['年報酬率(含息)'].fillna(0, inplace=True)
            final_selection_df['一年(σ年)'].replace(0, np.nan, inplace=True)
            final_selection_df['sharpe_ratio'] = (final_selection_df['年報酬率(含息)'] - config.RISK_FREE_RATE) / final_selection_df['一年(σ年)']
            final_selection_df.sort_values(by='sharpe_ratio', ascending=False, inplace=True)
            print("已依夏普比率重新排序標的池。")

        portfolio_codes = final_selection_df['代號'].tolist()

        if optimization_strategy in ['排名加權', '夏普比率優化']:
             print(f"採用【排名加權】策略分配權重...")
             portfolio_weights = rank_based_weighting(final_selection_df)
        else:
            print("採用【平均權重】策略...")
            num_assets = len(final_selection_df)
            portfolio_weights = [1 / num_assets] * num_assets

        hhi = calculate_hhi(portfolio_weights)
        print(f"純個股組合 HHI: {hhi:.4f} (限制 < {rules['hhi_limit']})")

    elif portfolio_type in ['純 ETF', '混合型']:
        if portfolio_type == '純 ETF':
            etfs = screened_assets[screened_assets['資產類別'] == 'ETF'].copy()
            target_size = min(rules['max_assets'], len(etfs))
            if len(etfs) < rules['min_assets']: return None
            portfolio_df = etfs.head(target_size)
            num_assets = len(portfolio_df)
            portfolio_codes = portfolio_df['代號'].tolist()
            portfolio_weights = [1 / num_assets] * num_assets
        else:
            core_etfs = screened_assets[screened_assets['資產類別'] == 'ETF'].head(rules['core_etfs'])
            satellite_stocks = screened_assets[screened_assets['資產類別'] == '上市櫃股票'].head(rules['satellite_stocks'])
            if core_etfs.empty or satellite_stocks.empty: return None
            core_weight, satellite_weight = rules['core_weight'], 1 - rules['core_weight']
            core_codes, core_weights = core_etfs['代號'].tolist(), [core_weight / len(core_etfs)] * len(core_etfs)
            satellite_codes, satellite_weights = satellite_stocks['代號'].tolist(), [satellite_weight / len(satellite_stocks)] * len(satellite_stocks)
            portfolio_codes = core_codes + satellite_codes
            portfolio_weights = core_weights + satellite_weights

    final_portfolio = pd.DataFrame({'代號': portfolio_codes, '建議權重': [f"{w:.2%}" for w in portfolio_weights]})
    
    # *** 修正點：在合併時，多選入 '產業別' 欄位 ***
    final_portfolio = final_portfolio.merge(master_df[['代號', '名稱', '產業別', '資產類別']], on='代號', how='left')
    
    return final_portfolio