# screener.py (階層順序 + 單一規則版)

import pandas as pd
from portfolio_rules import SCREENING_RULES

def screen_assets(data_df, risk_profile):
    """
    執行新的階層式篩選優先序，並採用單一規則：
    1. 優先篩選「積極型」
    2. 從剩餘標的中篩選「保守型」
    3. 最後從剩餘標的中篩選「穩健型」
    最終只回傳使用者指定的風險類別標的池。
    """
    print(f"\n--- 開始執行新版階層式篩選 (單一規則) ---")
    
    # 複製一份原始資料以進行操作，避免修改到原始 master_df
    df = data_df.copy()

    # 1. 優先篩選「積極型」
    print("Step 1: 正在從所有標的中篩選【積極型】...")
    aggressive_cond = SCREENING_RULES['積極型']['rule'](df)
    aggressive_pool = df[aggressive_cond].copy()
    aggressive_pool['篩選層級'] = '積極型'
    print(f"找到 {len(aggressive_pool)} 支積極型標的。")

    # 2. 從剩餘標的中篩選「保守型」
    print("Step 2: 正在從剩餘標的中篩選【保守型】...")
    remaining_after_aggressive = df.drop(index=aggressive_pool.index)
    conservative_cond = SCREENING_RULES['保守型']['rule'](remaining_after_aggressive)
    conservative_pool = remaining_after_aggressive[conservative_cond].copy()
    conservative_pool['篩選層級'] = '保守型'
    print(f"找到 {len(conservative_pool)} 支保守型標的。")

    # 3. 最後從剩餘標的中篩選「穩健型」
    print("Step 3: 正在從最後剩餘標的中篩選【穩健型】...")
    remaining_after_conservative = remaining_after_aggressive.drop(index=conservative_pool.index)
    moderate_cond = SCREENING_RULES['穩健型']['rule'](remaining_after_conservative)
    moderate_pool = remaining_after_conservative[moderate_cond].copy()
    moderate_pool['篩選層級'] = '穩健型'
    print(f"找到 {len(moderate_pool)} 支穩健型標的。")

    # 根據使用者選擇，回傳對應的標的池
    final_pool = pd.DataFrame()
    pool_map = {
        '積極型': aggressive_pool,
        '保守型': conservative_pool,
        '穩健型': moderate_pool
    }
    final_pool = pool_map.get(risk_profile, pd.DataFrame())
        
    # 對最終回傳的標的池進行排序
    if not final_pool.empty:
        ruleset = SCREENING_RULES[risk_profile]
        final_pool.sort_values(
            by=ruleset['sort_by'], 
            ascending=ruleset['ascending'],
            inplace=True
        )
            
    return final_pool