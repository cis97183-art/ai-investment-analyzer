# screener.py

import pandas as pd
from portfolio_rules import SCREENING_RULES

def screen_assets(data_df, risk_profile, target_count=10):
    """
    根據 portfolio_rules.py 中定義的規則篩選資產。
    """
    print(f"\n--- 開始進行【{risk_profile}】篩選 ---")
    
    ruleset = SCREENING_RULES.get(risk_profile)
    if not ruleset:
        print(f"錯誤：找不到風險偏好 '{risk_profile}' 的規則。")
        return pd.DataFrame()

    selected_assets = pd.DataFrame()
    
    for tier in sorted(ruleset['tiers'].keys()):
        print(f"正在嘗試第 {tier} 層規則...")
        condition_func = ruleset['tiers'][tier]
        
        # 穩健型第三層的特殊處理：需排除可能被歸類為保守或積極的標的
        if risk_profile == '穩健型' and tier == 3:
            conservative_cond = SCREENING_RULES['保守型']['tiers'][3](data_df)
            aggressive_cond = SCREENING_RULES['積極型']['tiers'][3](data_df)
            
            # 取得不屬於保守型也不屬於積極型的標的
            eligible_df = data_df[~conservative_cond & ~aggressive_cond]
            selected_assets = eligible_df[condition_func(eligible_df)]
        else:
            selected_assets = data_df[condition_func(data_df)].copy()
        
        print(f"第 {tier} 層規則篩選出 {len(selected_assets)} 筆標的。")
        if len(selected_assets) >= target_count:
            print(f"已達到目標數量 {target_count}，篩選停止。")
            break
            
    if not selected_assets.empty:
        print("根據輔助指標進行排序...")
        selected_assets.sort_values(
            by=ruleset['sort_by'], 
            ascending=ruleset['ascending'],
            inplace=True
        )
            
    return selected_assets