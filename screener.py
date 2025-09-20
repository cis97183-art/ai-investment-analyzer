# screener.py (升級版)

import pandas as pd
from portfolio_rules import SCREENING_RULES

def screen_assets(data_df, risk_profile, target_count=10):
    """
    執行累計式、階層式篩選與排序。
    1. 累計篩選：從第一層開始，若數量不足則納入第二層、第三層的標的，直到滿足目標數量。
    2. 階層排序：最終結果排序時，第一層標的永遠在最前面，其次是第二層，最後是第三層。
    """
    print(f"\n--- 開始進行【{risk_profile}】累計式篩選 ---")
    
    ruleset = SCREENING_RULES.get(risk_profile)
    if not ruleset:
        print(f"錯誤：找不到風險偏好 '{risk_profile}' 的規則。")
        return pd.DataFrame()

    all_found_assets = pd.DataFrame()
    found_indices = set()

    for tier in sorted(ruleset['tiers'].keys()):
        print(f"處理第 {tier} 層規則...")
        
        condition_func = ruleset['tiers'][tier]
        
        # 排除已找到的標的，避免重複
        eligible_df = data_df.drop(index=list(found_indices))

        # 穩健型第三層的特殊處理
        if risk_profile == '穩健型' and tier == 3:
            conservative_cond = SCREENING_RULES['保守型']['tiers'][3](eligible_df)
            aggressive_cond = SCREENING_RULES['積極型']['tiers'][3](eligible_df)
            eligible_df = eligible_df[~conservative_cond & ~aggressive_cond]
        
        tier_assets = eligible_df[condition_func(eligible_df)].copy()
        
        if not tier_assets.empty:
            tier_assets['篩選層級'] = tier
            all_found_assets = pd.concat([all_found_assets, tier_assets])
            found_indices.update(tier_assets.index)
            print(f"第 {tier} 層找到 {len(tier_assets)} 支新標的。目前累計 {len(all_found_assets)} 支。")

        if len(all_found_assets) >= target_count:
            print(f"已達到目標數量 {target_count}，停止搜尋。")
            break
            
    if not all_found_assets.empty:
        print("\n進行階層式排序...")
        # 排序邏輯：1. 按篩選層級排 2. 按輔助指標排
        final_sorted_assets = all_found_assets.sort_values(
            by=['篩選層級'] + ruleset['sort_by'], 
            ascending=[True] + ruleset['ascending']
        )
        return final_sorted_assets
            
    return pd.DataFrame() # 如果什麼都沒找到，返回空的 DataFrame