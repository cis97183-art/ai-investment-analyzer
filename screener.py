# screener.py (已修正)

import pandas as pd
import numpy as np
from portfolio_rules import UNIVERSAL_EXCLUSION_RULES, STOCK_SCREENING_RULES, ETF_SCREENING_RULES

def _to_numeric(series: pd.Series) -> pd.Series:
    """
    輔助函式：將 Series 轉換為數值型態。
    特別處理可能包含 '%' 或 ',' 的 object (文字) 型態欄位。
    """
    if pd.api.types.is_object_dtype(series):
        return pd.to_numeric(
            series.astype(str).str.replace('%', '', regex=False).str.replace(',', '', regex=False),
            errors='coerce'
        )
    return pd.to_numeric(series, errors='coerce')

def apply_universal_exclusion_rules(df: pd.DataFrame) -> pd.DataFrame:
    """實施規則零：基礎排雷篩選"""
    print("--- 步驟 1: 執行基礎排雷篩選 (規則零) ---")
    df_filtered = df.copy()
    initial_count = len(df_filtered)

    # 1. 排除槓桿/反向型ETF
    exclude_types = UNIVERSAL_EXCLUSION_RULES['exclude_etf_types']
    df_filtered = df_filtered[~((df_filtered['資產類別'] == 'ETF') & (df_filtered['產業別'].isin(exclude_types)))]
    print(f"排雷 1: 排除槓桿/反向型ETF後，剩下 {len(df_filtered)} 筆")

    # 2. 排除規模過小
    min_cap = UNIVERSAL_EXCLUSION_RULES['min_market_cap_billion']
    df_filtered['市值(億)'] = _to_numeric(df_filtered['市值(億)'])
    df_filtered.dropna(subset=['市值(億)'], inplace=True)
    df_filtered = df_filtered[df_filtered['市值(億)'] >= min_cap]
    print(f"排雷 2: 排除市值小於 {min_cap} 億的標的後，剩下 {len(df_filtered)} 筆")

    # 3. 排除數據不足 (核心修正點)
    min_years = UNIVERSAL_EXCLUSION_RULES['min_listing_years']
    
    # --- 【核心修正】讓合併年資的計算更強健 ---
    # 步驟 a: 預設合併年資為空值 (NaN)
    df_filtered['合併年資'] = np.nan
    # 步驟 b: 如果 '成立年數' 欄位存在，就用它的值
    if '成立年數' in df_filtered.columns:
        df_filtered['合併年資'] = _to_numeric(df_filtered['成立年數'])
    # 步驟 c: 如果 '成立年齡' 欄位存在，用它的值去填補上面可能留下的空值
    if '成立年齡' in df_filtered.columns:
        df_filtered['合併年資'].fillna(_to_numeric(df_filtered['成立年齡']), inplace=True)
    # --- 修正結束 ---
        
    df_filtered = df_filtered[df_filtered['合併年資'] >= min_years]
    print(f"排雷 3: 排除上市(櫃)未滿 {min_years} 年的標的後，剩下 {len(df_filtered)} 筆")

    # 4. 排除財務惡化
    min_fcf_key = 'min_free_cash_flow_per_share'
    fcf_col = '最新近4Q每股自由金流(元)'
    if min_fcf_key in UNIVERSAL_EXCLUSION_RULES and fcf_col in df_filtered.columns:
        min_fcf = UNIVERSAL_EXCLUSION_RULES[min_fcf_key]
        df_filtered[fcf_col] = _to_numeric(df_filtered[fcf_col])
        exclude_mask = (df_filtered['資產類別'].isin(['上市', '上櫃'])) & (df_filtered[fcf_col] < min_fcf)
        df_filtered = df_filtered[~exclude_mask]
        print(f"排雷 4: 排除近4季每股自由金流為負的個股後，剩下 {len(df_filtered)} 筆")

    final_count = len(df_filtered)
    print(f"排雷完成。總共排除了 {initial_count - final_count} 筆標的，最終剩下 {final_count} 筆進入標的池篩選。")
    return df_filtered.drop(columns=['合併年資'], errors='ignore')


def generate_asset_pools(master_df: pd.DataFrame) -> dict:
    """對通過排雷的標的進行平行/分類篩選，產出各類標的池"""
    print("\n--- 步驟 2: 建立高品質動態觀察名單 ---")
    df_screened = apply_universal_exclusion_rules(master_df)
    df_stocks = df_screened[df_screened['資產類別'].isin(['上市', '上櫃'])].copy()
    df_etfs = df_screened[df_screened['資產類別'] == 'ETF'].copy()

    # --- A: 個股標的池篩選 (平行) ---
    stock_pools = {}
    
    # 預處理：預先計算排名以供使用
    df_stocks['一年(σ年)'] = _to_numeric(df_stocks['一年(σ年)'])
    df_stocks['std_dev_rank'] = df_stocks['一年(σ年)'].rank(pct=True)

    for pool_name, rules in STOCK_SCREENING_RULES.items():
        temp_df = df_stocks.copy()
        conditions = rules['conditions']
        
        # 逐條應用篩選規則，pandas 會自動處理 NaN (比較結果為 False)
        if 'std_dev_rank_max' in conditions:
            temp_df = temp_df[temp_df['std_dev_rank'] <= conditions['std_dev_rank_max']]
        if 'std_dev_rank_min' in conditions:
            temp_df = temp_df[temp_df['std_dev_rank'] >= conditions['std_dev_rank_min']]
        if 'beta_max' in conditions:
            temp_df = temp_df[_to_numeric(temp_df['一年(β)']) <= conditions['beta_max']]
        if 'beta_min' in conditions:
            temp_df = temp_df[_to_numeric(temp_df['一年(β)']) >= conditions['beta_min']]
        if 'dividend_streak_min' in conditions:
            temp_df = temp_df[_to_numeric(temp_df['現金股利連配次數']) > conditions['dividend_streak_min']]
        if 'free_cash_flow_min' in conditions:
            temp_df = temp_df[_to_numeric(temp_df['最新近4Q每股自由金流(元)']) > conditions['free_cash_flow_min']]
        if 'avg_roe_min' in conditions:
            temp_df = temp_df[_to_numeric(temp_df['近3年平均ROE(%)']) > conditions['avg_roe_min']]
        if 'revenue_growth_min' in conditions:
            temp_df = temp_df[_to_numeric(temp_df['累月營收年增(%)']) > conditions['revenue_growth_min']]

        # 排序
        temp_df = temp_df.sort_values(by=rules['sort_by'], ascending=rules['ascending'])
        stock_pools[pool_name] = temp_df.reset_index(drop=True)
        print(f" -> {pool_name} 標的池建立完成，共 {len(temp_df)} 筆標的。")

    # --- B: ETF 標的池篩選 (分類) ---
    etf_pools = {}
    for pool_name, rules in ETF_SCREENING_RULES.items():
        keywords_pattern = '|'.join(rules['keywords'])
        
        if pool_name == 'Thematic/Sector':
            high_div_keywords = '|'.join(ETF_SCREENING_RULES['HighDividend']['keywords'])
            temp_df = df_etfs[df_etfs['名稱'].str.contains(keywords_pattern, na=False) & ~df_etfs['名稱'].str.contains(high_div_keywords, na=False)].copy()
        else:
             temp_df = df_etfs[df_etfs['名稱'].str.contains(keywords_pattern, na=False)].copy()
        
        temp_df['一年(σ年)'] = _to_numeric(temp_df['一年(σ年)'])
        etf_pools[pool_name] = temp_df.sort_values(by='一年(σ年)').reset_index(drop=True)
        print(f" -> {pool_name} 標的池建立完成，共 {len(temp_df)} 筆標的。")
        
    return {**stock_pools, **etf_pools}