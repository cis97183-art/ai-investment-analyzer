# investment_analyzer.py

import pandas as pd
from portfolio_rules import PORTFOLIO_CONSTRUCTION_RULES

def calculate_hhi(weights):
    """計算 Herfindahl-Hirschman Index (HHI)"""
    return sum([w**2 for w in weights])

def build_portfolio(screened_assets, portfolio_type, master_df):
    """
    根據標的池與組合類型建構投資組合。
    """
    print(f"\n--- 開始建構【{portfolio_type}】投資組合 ---")
    
    if screened_assets.empty:
        print("標的池為空，無法建立投資組合。")
        return None
        
    rules = PORTFOLIO_CONSTRUCTION_RULES.get(portfolio_type)
    if not rules:
        print(f"錯誤：找不到組合類型 '{portfolio_type}' 的規則。")
        return None

    portfolio_codes = []
    portfolio_weights = []

    if portfolio_type == '純個股':
        stocks = screened_assets[screened_assets['資產類別'] == '上市櫃股票'].copy()
        target_size = min(rules['max_assets'], len(stocks))
        
        final_selection_df = pd.DataFrame()
        industry_count = {}

        for _, row in stocks.iterrows():
            if len(final_selection_df) >= target_size:
                break
            industry = row['產業別']
            if industry_count.get(industry, 0) < rules['max_industry_assets']:
                final_selection_df = pd.concat([final_selection_df, row.to_frame().T], ignore_index=True)
                industry_count[industry] = industry_count.get(industry, 0) + 1
        
        if len(final_selection_df) < rules['min_assets']:
            print(f"注意：依產業分散規則，僅選出 {len(final_selection_df)} 支個股，未達 {rules['min_assets']} 支的低標。")
        if final_selection_df.empty:
            print("無法依產業分散規則選出任何個股。")
            return None
        
        num_assets = len(final_selection_df)
        weight = 1 / num_assets
        portfolio_codes = final_selection_df['代號'].tolist()
        portfolio_weights = [weight] * num_assets
        
        hhi = calculate_hhi(portfolio_weights)
        print(f"純個股組合 HHI: {hhi:.4f} (限制 < {rules['hhi_limit']})")
        if hhi >= rules['hhi_limit']:
            print("警告：HHI 超出限制！")

    elif portfolio_type == '純 ETF':
        etfs = screened_assets[screened_assets['資產類別'] == 'ETF'].copy()
        target_size = min(rules['max_assets'], len(etfs))

        if len(etfs) < rules['min_assets']:
            print(f"ETF 數量不足 {rules['min_assets']} 支，無法建立純ETF組合。")
            return None
            
        portfolio_df = etfs.head(target_size)
        num_assets = len(portfolio_df)
        weight = 1 / num_assets
        portfolio_codes = portfolio_df['代號'].tolist()
        portfolio_weights = [weight] * num_assets
        
        print(f"純 ETF 組合 HHI: {calculate_hhi(portfolio_weights):.4f}")

    elif portfolio_type == '混合型':
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
        
        hhi = calculate_hhi(portfolio_weights)
        print(f"混合型組合 HHI: {hhi:.4f} (建議 < {rules['hhi_limit']})")

    # 建立最終的 DataFrame
    final_portfolio = pd.DataFrame({
        '代號': portfolio_codes,
        '建議權重': [f"{w:.2%}" for w in portfolio_weights]
    })
    
    # 合併標的資訊
    final_portfolio = final_portfolio.merge(master_df[['代號', '名稱', '資產類別']], on='代號', how='left')
    
    return final_portfolio