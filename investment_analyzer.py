# investment_analyzer.py (升級版)

import pandas as pd
import numpy as np
from portfolio_rules import PORTFOLIO_CONSTRUCTION_RULES
import config # 匯入 config 以取得無風險利率

def calculate_hhi(weights):
    """計算 Herfindahl-Hirschman Index (HHI)"""
    return sum([w**2 for w in weights])

def build_portfolio(screened_assets, portfolio_type, optimization_strategy, master_df):
    """
    根據標的池、組合類型與優化策略建構投資組合。
    """
    print(f"\n--- 開始建構【{portfolio_type} / {optimization_strategy}】投資組合 ---")
    
    if screened_assets.empty:
        print("標的池為空，無法建立投資組合。")
        return None
        
    rules = PORTFOLIO_CONSTRUCTION_RULES.get(portfolio_type)
    if not rules:
        print(f"錯誤：找不到組合類型 '{portfolio_type}' 的規則。")
        return None

    portfolio_codes = []
    portfolio_weights = []

    # --- 針對純個股組合，執行不同的優化策略 ---
    if portfolio_type == '純個股':
        stocks = screened_assets[screened_assets['資產類別'] == '上市櫃股票'].copy()
        
        # 1. 根據產業分散規則，初步篩選出股票池
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

        num_assets = len(final_selection_df)
        portfolio_codes = final_selection_df['代號'].tolist()

        # 2. 根據選擇的優化策略分配權重
        if optimization_strategy == '平均權重':
            print("採用【平均權重】策略...")
            weight = 1 / num_assets
            portfolio_weights = [weight] * num_assets

        elif optimization_strategy == '夏普比率優化':
            print("採用【夏普比率優化】策略...")
            # 計算夏普比率 (注意: ETF資料可能沒有年報酬率)
            final_selection_df['年報酬率(含息)'].fillna(0, inplace=True)
            final_selection_df['一年(σ年)'].replace(0, np.nan, inplace=True) # 避免除以零
            
            final_selection_df['sharpe_ratio'] = (final_selection_df['年報酬率(含息)'] - config.RISK_FREE_RATE) / final_selection_df['一年(σ年)']
            
            # 以夏普比率重新排序並選取
            final_selection_df.sort_values(by='sharpe_ratio', ascending=False, inplace=True)
            final_selection_df = final_selection_df.head(target_size)
            
            # 更新 portfolio_codes 並使用平均權重
            portfolio_codes = final_selection_df['代號'].tolist()
            num_assets = len(portfolio_codes)
            portfolio_weights = [1 / num_assets] * num_assets
            print("已挑選出夏普比率最高的標的。")

        elif optimization_strategy == '因子加權':
            print("採用【因子加權】策略...")
            # 根據你的規則，因子與風險偏好掛鉤，但此處簡化為選擇最適合的因子
            # 此處以 '近3年平均ROE(%)' (品質因子) 為範例
            factor_col = '近3年平均ROE(%)'
            print(f"使用因子: {factor_col}")

            factor_values = final_selection_df[factor_col].copy()
            # 處理負值或空值，避免權重計算錯誤 (策略：負值當作0)
            factor_values[factor_values < 0] = 0
            factor_values.fillna(0, inplace=True)
            
            total_factor = factor_values.sum()
            if total_factor > 0:
                portfolio_weights = (factor_values / total_factor).tolist()
            else: # 如果所有因子值都是0，則退回平均權重
                print("因子總和為0，退回平均權重策略。")
                portfolio_weights = [1 / num_assets] * num_assets
        
        # HHI 檢核
        hhi = calculate_hhi(portfolio_weights)
        print(f"純個股組合 HHI: {hhi:.4f} (限制 < {rules['hhi_limit']})")

    # --- 處理純 ETF 和混合型 (維持平均權重) ---
    elif portfolio_type == '純 ETF':
        # (此處邏輯不變，省略以保持簡潔)
        etfs = screened_assets[screened_assets['資產類別'] == 'ETF'].copy()
        target_size = min(rules['max_assets'], len(etfs))
        if len(etfs) < rules['min_assets']:
            print(f"ETF 數量不足 {rules['min_assets']} 支，無法建立純ETF組合。")
            return None
        portfolio_df = etfs.head(target_size)
        num_assets = len(portfolio_df)
        portfolio_codes = portfolio_df['代號'].tolist()
        portfolio_weights = [1 / num_assets] * num_assets
        print(f"純 ETF 組合 HHI: {calculate_hhi(portfolio_weights):.4f}")

    elif portfolio_type == '混合型':
        # (此處邏輯不變，省略以保持簡潔)
        core_etfs = screened_assets[screened_assets['資產類別'] == 'ETF'].head(rules['core_etfs'])
        satellite_stocks = screened_assets[screened_assets['資產類別'] == '上市櫃股票'].head(rules['satellite_stocks'])
        if core_etfs.empty or satellite_stocks.empty:
            print("ETF 或個股數量不足，無法建立混合型組合。")
            return None
        core_weight = rules['core_weight']
        satellite_weight = 1 - core_weight
        core_codes = core_etfs['代號'].tolist()
        core_weights = [core_weight / len(core_etfs)] * len(core_etfs)
        satellite_codes = satellite_stocks['代號'].tolist()
        satellite_weights = [satellite_weight / len(satellite_stocks)] * len(satellite_stocks)
        portfolio_codes = core_codes + satellite_codes
        portfolio_weights = core_weights + satellite_weights
        print(f"混合型組合 HHI: {calculate_hhi(portfolio_weights):.4f} (建議 < {rules['hhi_limit']})")
            
    # 建立最終的 DataFrame
    final_portfolio = pd.DataFrame({
        '代號': portfolio_codes,
        '建議權重': [f"{w:.2%}" for w in portfolio_weights]
    })
    
    final_portfolio = final_portfolio.merge(master_df[['代號', '名稱', '資產類別']], on='代號', how='left')
    
    return final_portfolio