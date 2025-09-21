# screener.py (最終強健版)

import pandas as pd
import numpy as np
from portfolio_rules import UNIVERSAL_EXCLUSION_RULES, STOCK_SCREENING_RULES, ETF_SCREENING_RULES

def _to_numeric(series: pd.Series) -> pd.Series:
    """
    輔助函式：將 Series 轉換為數值型態，並強健地處理 '%' 或 ',' 符號。
    """
    if pd.api.types.is_object_dtype(series):
        return pd.to_numeric(
            series.astype(str).str.replace('%', '', regex=False).str.replace(',', '', regex=False),
            errors='coerce'
        )
    return pd.to_numeric(series, errors='coerce')

def apply_universal_exclusion_rules(df: pd.DataFrame) -> pd.DataFrame:
    """實施規則零：基礎排雷篩選，對所有資產都適用。"""
    print("--- 步驟 1: 執行基礎排雷篩選 (規則零) ---")
    df_filtered = df.copy()
    initial_count = len(df_filtered)

    # 規則 1: 排除槓桿/反向型ETF
    exclude_types = UNIVERSAL_EXCLUSION_RULES['exclude_etf_types']
    df_filtered = df_filtered[~((df_filtered['資產類別'] == 'ETF') & (df_filtered['產業別'].isin(exclude_types)))]
    print(f"排雷 1: 排除槓桿/反向型ETF後，剩下 {len(df_filtered)} 筆")

    # 規則 2: 排除市值過小的標的
    min_cap = UNIVERSAL_EXCLUSION_RULES['min_market_cap_billion']
    df_filtered['市值(億)'] = _to_numeric(df_filtered['市值(億)'])
    df_filtered.dropna(subset=['市值(億)'], inplace=True)
    df_filtered = df_filtered[df_filtered['市值(億)'] >= min_cap]
    print(f"排雷 2: 排除市值小於 {min_cap} 億的標的後，剩下 {len(df_filtered)} 筆")

    # 規則 3: 排除上市/成立年資過短的標的
    min_years = UNIVERSAL_EXCLUSION_RULES['min_listing_years']
    
    # 強健地合併 '成立年數' 和 '成立年齡' 欄位
    df_filtered['合併年資'] = np.nan
    if '成立年數' in df_filtered.columns:
        df_filtered['合併年資'] = _to_numeric(df_filtered['成立年數'])
    if '成立年齡' in df_filtered.columns:
        df_filtered['合併年資'].fillna(_to_numeric(df_filtered['成立年齡']), inplace=True)
    
    # 執行篩選，只保留年資足夠的標的
    df_filtered = df_filtered[df_filtered['合併年資'] >= min_years]
    print(f"排雷 3: 排除上市(櫃)/成立未滿 {min_years} 年的標的後，剩下 {len(df_filtered)} 筆")

    # 規則 4: 排除自由現金流為負的個股
    min_fcf_key = 'min_free_cash_flow_per_share'
    fcf_col = '最新近4Q每股自由金流(元)'
    if min_fcf_key in UNIVERSAL_EXCLUSION_RULES and fcf_col in df_filtered.columns:
        min_fcf = UNIVERSAL_EXCLUSION_RULES[min_fcf_key]
        df_filtered[fcf_col] = _to_numeric(df_filtered[fcf_col])
        # 此規則只對個股生效
        exclude_mask = (df_filtered['資產類別'].isin(['上市', '上櫃'])) & (df_filtered[fcf_col] < min_fcf)
        df_filtered = df_filtered[~exclude_mask]
        print(f"排雷 4: 排除近4季每股自由金流為負的個股後，剩下 {len(df_filtered)} 筆")

    final_count = len(df_filtered)
    print(f"排雷完成。總共排除了 {initial_count - final_count} 筆標的，最終剩下 {final_count} 筆進入標的池篩選。")
    return df_filtered.drop(columns=['合併年資'], errors='ignore')


def generate_asset_pools(master_df: pd.DataFrame) -> dict:
    """對通過排雷的標的進行平行/分類篩選，產出各類資產的候選池。"""
    print("\n--- 步驟 2: 建立高品質動態觀察名單 ---")
    df_screened = apply_universal_exclusion_rules(master_df)
    df_stocks = df_screened[df_screened['資產類別'].isin(['上市', '上櫃'])].copy()
    df_etfs = df_screened[df_screened['資產類別'] == 'ETF'].copy()

    # --- A: 個股標的池篩選 (平行篩選) ---
    stock_pools = {}
    
    # 強健化處理波動率欄位
    if '一年(σ年)' not in df_stocks.columns:
        print("警告: 股票資料中缺少 '一年(σ年)' 欄位，將無法進行波動率相關篩選。")
        df_stocks['一年(σ年)'] = np.nan
    else:
        df_stocks['一年(σ年)'] = _to_numeric(df_stocks['一年(σ年)'])
    
    # 計算波動率的百分位排名，供後續篩選使用
    df_stocks['std_dev_rank'] = df_stocks['一年(σ年)'].rank(pct=True)

    for pool_name, rules in STOCK_SCREENING_RULES.items():
        temp_df = df_stocks.copy()
        conditions = rules['conditions']
        
        # 動態應用規則中定義的所有條件
        if 'std_dev_rank_max' in conditions: temp_df = temp_df[temp_df['std_dev_rank'] <= conditions['std_dev_rank_max']]
        if 'std_dev_rank_min' in conditions: temp_df = temp_df[temp_df['std_dev_rank'] >= conditions['std_dev_rank_min']]
        if 'beta_max' in conditions: temp_df = temp_df[_to_numeric(temp_df['一年(β)']) <= conditions['beta_max']]
        if 'beta_min' in conditions: temp_df = temp_df[_to_numeric(temp_df['一年(β)']) >= conditions['beta_min']]
        if 'dividend_streak_min' in conditions: temp_df = temp_df[_to_numeric(temp_df['現金股利連配次數']) > conditions['dividend_streak_min']]
        if 'free_cash_flow_min' in conditions: temp_df = temp_df[_to_numeric(temp_df['最新近4Q每股自由金流(元)']) > conditions['free_cash_flow_min']]
        if 'avg_roe_min' in conditions: temp_df = temp_df[_to_numeric(temp_df['近3年平均ROE(%)']) > conditions['avg_roe_min']]
        if 'revenue_growth_min' in conditions: temp_df = temp_df[_to_numeric(temp_df['累月營收年增(%)']) > conditions['revenue_growth_min']]

        temp_df = temp_df.sort_values(by=rules['sort_by'], ascending=rules['ascending'])
        stock_pools[pool_name] = temp_df.reset_index(drop=True)
        print(f" -> 「{pool_name}」個股池建立完成，共 {len(temp_df)} 筆標的。")

    # --- B: ETF 標的池篩選 (關鍵字分類) ---
    etf_pools = {}
    for pool_name, rules in ETF_SCREENING_RULES.items():
        keywords_pattern = '|'.join(rules['keywords'])
        
        # 特殊規則：主題型ETF要排除掉高股息ETF
        if pool_name == '主題/產業型':
            high_div_keywords = '|'.join(ETF_SCREENING_RULES['高股息型']['keywords'])
            temp_df = df_etfs[df_etfs['名稱'].str.contains(keywords_pattern, na=False) & ~df_etfs['名稱'].str.contains(high_div_keywords, na=False)].copy()
        else:
             temp_df = df_etfs[df_etfs['名稱'].str.contains(keywords_pattern, na=False)].copy()
        
        # 根據波動率排序 (如果欄位存在)
        if '一年(σ年)' in temp_df.columns:
             temp_df['一年(σ年)'] = _to_numeric(temp_df['一年(σ年)'])
             etf_pools[pool_name] = temp_df.sort_values(by='一年(σ年)').reset_index(drop=True)
        else:
             etf_pools[pool_name] = temp_df.reset_index(drop=True) 
             
        print(f" -> 「{pool_name}」ETF池建立完成，共 {len(temp_df)} 筆標的。")
        
    # 合併個股與ETF標的池並回傳
    return {**stock_pools, **etf_pools}
