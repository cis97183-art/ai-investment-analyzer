# screener.py

import pandas as pd
import numpy as np
from portfolio_rules import UNIVERSAL_EXCLUSION_RULES, STOCK_SCREENING_RULES, ETF_SCREENING_RULES

def _to_numeric(series):
    """輔助函式：將 Series 轉換為數值型態，錯誤則轉為 NaN"""
    return pd.to_numeric(series, errors='coerce')

def apply_universal_exclusion_rules(df: pd.DataFrame) -> pd.DataFrame:
    """
    實施規則零：基礎排雷篩選
    """
    print("--- 步驟 1: 執行基礎排雷篩選 (規則零) ---")
    
    # 複製一份資料以避免修改原始 DataFrame
    df_filtered = df.copy()
    initial_count = len(df_filtered)
    
    # 1. 排除槓桿型、反向型ETF
    exclude_types = UNIVERSAL_EXCLUSION_RULES['exclude_etf_types']
    etf_mask = df_filtered['資產類別'] == 'ETF'
    type_mask = df_filtered['產業別'].isin(exclude_types)
    df_filtered = df_filtered[~(etf_mask & type_mask)]
    print(f"排雷 1: 排除槓桿/反向型ETF後，剩下 {len(df_filtered)} 筆")

    # 2. 排除規模過小
    min_cap = UNIVERSAL_EXCLUSION_RULES['min_market_cap_billion']
    # 將市值相關欄位轉為數值
    df_filtered['市值(億)'] = _to_numeric(df_filtered['市值(億)'])
    df_filtered['資產規模.億.'] = _to_numeric(df_filtered['資產規模.億.'])
    # 用 fillna 合併兩個市值欄位
    df_filtered['合併市值'] = df_filtered['市值(億)'].fillna(df_filtered['資產規模.億.'])
    df_filtered = df_filtered[df_filtered['合併市值'] >= min_cap]
    print(f"排雷 2: 排除市值小於 {min_cap} 億的標的後，剩下 {len(df_filtered)} 筆")
    
    # 3. 排除數據不足
    min_years = UNIVERSAL_EXCLUSION_RULES['min_listing_years']
    # 將成立年數相關欄位轉為數值
    df_filtered['成立年數'] = _to_numeric(df_filtered['成立年數'])
    df_filtered['成立年齡'] = _to_numeric(df_filtered['成立年齡'])
     # 用 fillna 合併兩個成立年數欄位
    df_filtered['合併年資'] = df_filtered['成立年數'].fillna(df_filtered['成立年齡'])
    df_filtered = df_filtered[df_filtered['合併年資'] >= min_years]
    print(f"排雷 3: 排除上市(櫃)未滿 {min_years} 年的標的後，剩下 {len(df_filtered)} 筆")

    # 4. 排除財務惡化：最新近4季每股自由金流(元) 為負的個股
    min_fcf_key = 'min_free_cash_flow_per_share'
    fcf_col = '最新近4Q每股自由金流(元)'
    if min_fcf_key in UNIVERSAL_EXCLUSION_RULES and fcf_col in df_filtered.columns:
        min_fcf = UNIVERSAL_EXCLUSION_RULES[min_fcf_key]
        df_filtered[fcf_col] = _to_numeric(df_filtered[fcf_col])
        
        # 只針對個股進行此項篩選
        stock_mask = df_filtered['資產類別'].isin(['上市', '上櫃'])
        fcf_mask = df_filtered[fcf_col] < min_fcf
        
        # 結合兩個條件，找出需要被排除的個股
        exclude_mask = stock_mask & fcf_mask
        
        # 排除這些個股
        df_filtered = df_filtered[~exclude_mask]
        print(f"排雷 4: 排除近4季每股自由金流為負的個股後，剩下 {len(df_filtered)} 筆")
    else:
        print(f"排雷 4: 警告 - 找不到 '{fcf_col}' 欄位或規則，跳過此篩選。")

    final_count = len(df_filtered)
    print(f"排雷完成。總共排除了 {initial_count - final_count} 筆標的，最終剩下 {final_count} 筆進入標的池篩選。")
    
    return df_filtered.drop(columns=['合併市值', '合併年資'], errors='ignore')

def generate_asset_pools(master_df: pd.DataFrame) -> dict:
    """
    對通過排雷的標的進行平行/分類篩選，產出各類標的池
    """
    print("\n--- 步驟 2: 建立高品質動態觀察名單 ---")
    
    # 執行基礎排雷
    df_screened = apply_universal_exclusion_rules(master_df)
    
    # 分離個股與 ETF
    df_stocks = df_screened[df_screened['資產類別'].isin(['上市', '上櫃'])].copy()
    df_etfs = df_screened[df_screened['資產類別'] == 'ETF'].copy()

    # --- A: 個股標的池篩選 (平行) ---
    stock_pools = {}
    
    # 預先計算排名以供使用
    df_stocks['一年(σ年)'] = _to_numeric(df_stocks['一年(σ年)'])
    df_stocks['std_dev_rank'] = df_stocks['一年(σ年)'].rank(pct=True)

    for pool_name, rules in STOCK_SCREENING_RULES.items():
        print(f"建立個股標的池: {pool_name}...")
        temp_df = df_stocks.copy()
        conditions = rules['conditions']
        
        # 篩選條件
        if 'std_dev_rank_max' in conditions:
            temp_df = temp_df[temp_df['std_dev_rank'] <= conditions['std_dev_rank_max']]
        if 'std_dev_rank_min' in conditions:
            temp_df = temp_df[temp_df['std_dev_rank'] >= conditions['std_dev_rank_min']]
        if 'beta_max' in conditions:
            temp_df['一年(β)'] = _to_numeric(temp_df['一年(β)'])
            temp_df = temp_df[temp_df['一年(β)'] <= conditions['beta_max']]
        if 'beta_min' in conditions:
            temp_df['一年(β)'] = _to_numeric(temp_df['一年(β)'])
            temp_df = temp_df[temp_df['一年(β)'] >= conditions['beta_min']]
        if 'dividend_streak_min' in conditions:
            temp_df['現金股利連配次數'] = _to_numeric(temp_df['現金股利連配次數'])
            temp_df = temp_df[temp_df['現金股利連配次數'] > conditions['dividend_streak_min']]
        if 'free_cash_flow_min' in conditions:
            temp_df['最新近4Q每股自由金流(元)'] = _to_numeric(temp_df['最新近4Q每股自由金流(元)'])
            temp_df = temp_df[temp_df['最新近4Q每股自由金流(元)'] > conditions['free_cash_flow_min']]
        if 'avg_roe_min' in conditions:
            temp_df['近3年平均ROE(%)'] = _to_numeric(temp_df['近3年平均ROE(%)'])
            temp_df = temp_df[temp_df['近3年平均ROE(%)'] > conditions['avg_roe_min']]
        if 'revenue_growth_min' in conditions:
            temp_df['累月營收年增(%)'] = _to_numeric(temp_df['累月營收年增(%)'])
            temp_df = temp_df[temp_df['累月營收年增(%)'] > conditions['revenue_growth_min']]
        
        # 排序
        temp_df = temp_df.sort_values(by=rules['sort_by'], ascending=rules['ascending'])
        stock_pools[pool_name] = temp_df.reset_index(drop=True)
        print(f" -> {pool_name} 標的池建立完成，共 {len(temp_df)} 筆標的。")

    # --- B: ETF 標的池篩選 (分類) ---
    etf_pools = {}
    for pool_name, rules in ETF_SCREENING_RULES.items():
        print(f"建立ETF標的池: {pool_name}...")
        keywords_pattern = '|'.join(rules['keywords'])
        
        # 排除主題型中的高股息關鍵字，避免重複分類
        if pool_name == 'Thematic/Sector':
            high_div_keywords = '|'.join(ETF_SCREENING_RULES['HighDividend']['keywords'])
            temp_df = df_etfs[
                df_etfs['名稱'].str.contains(keywords_pattern, na=False) & 
                ~df_etfs['名稱'].str.contains(high_div_keywords, na=False)
            ].copy()
        else:
             temp_df = df_etfs[df_etfs['名稱'].str.contains(keywords_pattern, na=False)].copy()
        
        # 排序 (例如，依年化標準差由低到高)
        temp_df['一年(σ年)'] = _to_numeric(temp_df['一年(σ年)'])
        etf_pools[pool_name] = temp_df.sort_values(by='一年(σ年)').reset_index(drop=True)
        print(f" -> {pool_name} 標的池建立完成，共 {len(temp_df)} 筆標的。")
        
    return {**stock_pools, **etf_pools}
