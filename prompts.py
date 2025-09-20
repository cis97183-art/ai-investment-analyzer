# prompts.py

def get_user_preferences():
    """獲取使用者的風險偏好與組合類型"""
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

    return risk_profile, portfolio_type