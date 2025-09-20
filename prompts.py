# prompts.py (修正版)

def get_user_preferences():
    """獲取使用者的風險偏好、組合類型與優化策略"""
    print("--- 投資組合建構器 ---")
    
    # 風險偏好
    profile_map = {'1': '保守型', '2': '穩健型', '3': '積極型'}
    while True:
        profile_choice = input("請選擇風險偏好 (1:保守型, 2:穩健型, 3:積極型): ")
        if profile_choice in profile_map:
            risk_profile = profile_map[profile_choice]
            break
        else:
            print("無效輸入，請重新輸入。")
            
    # 組合類型
    type_map = {'1': '純個股', '2': '純 ETF', '3': '混合型'}
    while True:
        type_choice = input("請選擇組合類型 (1:純個股, 2:純 ETF, 3:混合型): ")
        if type_choice in type_map:
            portfolio_type = type_map[type_choice]
            break
        else:
            print("無效輸入，請重新輸入。")

    # *** 新增：優化策略選擇 ***
    strategy_map = {'1': '平均權重', '2': '夏普比率優化', '3': '因子加權'}
    optimization_strategy = '平均權重' # 預設值
    if portfolio_type == '純個股': # 優化策略只針對純個股組合
        while True:
            strategy_choice = input("請選擇個股優化策略 (1:平均權重, 2:夏普比率優化, 3:因子加權): ")
            if strategy_choice in strategy_map:
                optimization_strategy = strategy_map[strategy_choice]
                break
            else:
                print("無效輸入，請重新輸入。")

    return risk_profile, portfolio_type, optimization_strategy