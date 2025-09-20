# prompts.py (最終簡化版)

def get_user_preferences():
    """獲取使用者的風險偏好與組合類型"""
    # (此函式內容不變，但確認它只回傳 risk_profile, portfolio_type)
    profile_map = {'1': '保守型', '2': '穩健型', '3': '積極型'}
    while True:
        profile_choice = input("請選擇風險偏好 (1:保守型, 2:穩健型, 3:積極型): ")
        if profile_choice in profile_map:
            risk_profile = profile_map[profile_choice]
            break
    type_map = {'1': '純個股', '2': '純 ETF', '3': '混合型'}
    while True:
        type_choice = input("請選擇組合類型 (1:純個股, 2:純 ETF, 3:混合型): ")
        if type_choice in type_map:
            portfolio_type = type_map[type_choice]
            break
    return risk_profile, portfolio_type

def get_system_prompt(portfolios_dict, user_question):
    """產生一個包含所有投資組合上下文的完整提示語給 AI 模型。"""
    # (此函式內容不變)