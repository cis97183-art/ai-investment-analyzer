# investment_analyzer.py (策略重構版)

import pandas as pd
import numpy as np
from portfolio_rules import PORTFOLIO_CONSTRUCTION_RULES
import config

def calculate_hhi(weights):
    """計算 HHI 指數"""
    return sum([w**2 for w in weights])

def build_portfolio(screened_assets, portfolio_type, risk_profile, master_df):
    """
    根據更新的、更詳細的規則建構投資組合。
    """
    print(f"\n--- 開始建構【{risk_profile} - {portfolio_type}】投資組合 ---")
    
    rules = PORTFOLIO_CONSTRUCTION_RULES.get(portfolio_type)
    if not rules:
        print(f"錯誤：找不到 '{portfolio_type}' 的規則。")
        return None

    final_portfolio_df = pd.DataFrame()

    # ======================================================================
    # 規則 1: 純個股 (Pure Stock)
    # ======================================================================
    if portfolio_type == '純個股':
        stocks = screened_assets[screened_assets['資產類別'] == '上市櫃股票'].copy()
        
        # 1. 根據風險偏好決定因子排序的欄位
        if risk_profile in ['保守型', '穩健型']:
            # 優先使用 ROE，若無則用殖利率
            stocks['factor_score'] = stocks['近3年平均ROE(%)'].fillna(stocks['成交價現金殖利率']).fillna(0)
            print("採用「品質/股利因子」進行排序...")
        else: # 積極型
            # 優先使用營收成長，若無則用年報酬率
            stocks['factor_score'] = stocks['累月營收年增(%)'].fillna(stocks['年報酬率(含息)']*100).fillna(0)
            print("採用「動能因子」進行排序...")
        
        stocks.sort_values(by='factor_score', ascending=False, inplace=True)
        
        # 2. 依產業分散規則挑選標的
        target_size = min(rules['max_assets'], len(stocks))
        selection = []
        industry_count = {}
        for _, row in stocks.iterrows():
            if len(selection) >= target_size: break
            industry = row['產業別']
            if industry_count.get(industry, 0) < rules['max_industry_assets']:
                selection.append(row)
                industry_count[industry] = industry_count.get(industry, 0) + 1
        
        if not selection: return None
        final_portfolio_df = pd.DataFrame(selection)
        
        # 3. 平均分配權重
        num_assets = len(final_portfolio_df)
        weights = [1 / num_assets] * num_assets
        final_portfolio_df['建議權重'] = [f"{w:.2%}" for w in weights]
        
        print(f"純個股組合 HHI: {calculate_hhi(weights):.4f}")

    # ======================================================================
    # 規則 2: 純 ETF (Pure ETF)
    # ======================================================================
    elif portfolio_type == '純 ETF':
        etfs = screened_assets[screened_assets['資產類別'] == 'ETF'].copy()
        if len(etfs) < rules['min_assets']: return None

        # 1. 計算夏普比率
        etfs = etfs[etfs['一年(σ年)'] > 0]
        etfs['年報酬率(含息)'].fillna(0, inplace=True)
        etfs['sharpe_ratio'] = (etfs['年報酬率(含息)'] - config.RISK_FREE_RATE) / (etfs['一年(σ年)'] / 100)
        etfs.sort_values(by='sharpe_ratio', ascending=False, inplace=True)

        # 2. 依類型分散挑選
        selection = []
        # 優先選一支大盤型 ETF
        large_cap = etfs[etfs['產業別'] == '國內成分股ETF'].head(1)
        if not large_cap.empty: selection.append(large_cap.iloc[0])
        # 再選一支非大盤、非債券的產業/主題型 ETF
        others = etfs[~etfs['產業別'].isin(['國內成分股ETF', '債券ETF'])].head(1)
        if not others.empty: selection.append(others.iloc[0])
        # 如果是保守型，務必納入一支債券ETF
        if risk_profile == '保守型':
            bond = etfs[etfs['產業別'] == '債券ETF'].head(1)
            if not bond.empty: selection.append(bond.iloc[0])
        
        # 如果數量不足，從剩下的補齊
        remaining_etfs = etfs.drop(index=[s.name for s in selection if s is not None])
        needed = rules['min_assets'] - len(selection)
        if needed > 0: selection.extend([row for _, row in remaining_etfs.head(needed).iterrows()])
        
        if not selection: return None
        final_portfolio_df = pd.DataFrame(selection)
        
        # 3. 依風險偏好分配權重
        num_assets = len(final_portfolio_df)
        if risk_profile == '保守型' and any(final_portfolio_df['產業別'] == '債券ETF'):
            weights = [0.6 if etf_type == '債券ETF' else 0.4 / (num_assets - 1) for etf_type in final_portfolio_df['產業別']]
        else: # 穩健型與積極型暫採平均分配
            weights = [1 / num_assets] * num_assets
        final_portfolio_df['建議權重'] = [f"{w:.2%}" for w in weights]

    # ======================================================================
    # 規則 3: 混合型 (Mixed)
    # ======================================================================
    elif portfolio_type == '混合型':
        stocks = screened_assets[screened_assets['資產類別'] == '上市櫃股票'].copy()
        etfs = screened_assets[screened_assets['資產類別'] == 'ETF'].copy()

        # 1. 建構核心部位 (ETF)
        core_selection = etfs[etfs['一年(σ年)'] > 0]
        core_selection['sharpe_ratio'] = (core_selection['年報酬率(含息)'].fillna(0) - config.RISK_FREE_RATE) / (core_selection['一年(σ年)'] / 100)
        core_selection.sort_values(by='sharpe_ratio', ascending=False, inplace=True)
        core_df = core_selection.head(rules['core_etfs'])

        # 2. 建構衛星部位 (個股)
        if risk_profile in ['保守型', '穩健型']:
            stocks['factor_score'] = stocks['近3年平均ROE(%)'].fillna(0)
        else:
            stocks['factor_score'] = stocks['累月營收年增(%)'].fillna(0)
        stocks.sort_values(by='factor_score', ascending=False, inplace=True)
        
        satellite_selection = []
        industry_count = {}
        for _, row in stocks.iterrows():
            if len(satellite_selection) >= rules['satellite_stocks']: break
            industry = row['產業別']
            if industry_count.get(industry, 0) < rules['max_industry_assets']:
                satellite_selection.append(row)
                industry_count[industry] = industry_count.get(industry, 0) + 1
        satellite_df = pd.DataFrame(satellite_selection)
        
        if core_df.empty or satellite_df.empty: return None

        # 3. 整合與分配權重
        core_weight, satellite_weight = rules['core_weight'], 1 - rules['core_weight']
        core_df['建議權重'] = [f"{(core_weight / len(core_df)):.2%}"] * len(core_df)
        satellite_df['建議權重'] = [f"{(satellite_weight / len(satellite_df)):.2%}"] * len(satellite_df)
        
        final_portfolio_df = pd.concat([core_df, satellite_df], ignore_index=True)
        all_weights = [core_weight/len(core_df)]*len(core_df) + [satellite_weight/len(satellite_df)]*len(satellite_df)
        print(f"混合型組合 HHI: {calculate_hhi(all_weights):.4f}")

    # 回傳結果前，只保留需要的欄位
    cols_to_keep = ['代號', '名稱', '產業別', '資產類別', '建議權重']
    final_cols = [col for col in cols_to_keep if col in final_portfolio_df.columns]
    
    return final_portfolio_df[final_cols]