# prompts.py (修正版)

def get_user_preferences():
    """獲取使用者的風險偏好與組合類型"""
    print("--- 投資組合建構器 ---")
    
    profile_map = {'1': '保守型', '2': '穩健型', '3': '積極型'}
    while True:
        profile_choice = input("請選擇風險偏好 (1:保守型, 2:穩健型, 3:積極型): ")
        if profile_choice in profile_map:
            risk_profile = profile_map[profile_choice]
            break
        else:
            print("無效輸入，請重新輸入。")
            
    type_map = {'1': '純個股', '2': '純 ETF', '3': '混合型'}
    while True:
        type_choice = input("請選擇組合類型 (1:純個股, 2:純 ETF, 3:混合型): ")
        if type_choice in type_map:
            portfolio_type = type_map[type_choice]
            break
        else:
            print("無效輸入，請重新輸入。")

    # 不再需要回傳 optimization_strategy
    return risk_profile, portfolio_type


def get_system_prompt(portfolios_dict, user_question):
    """
    產生一個包含所有投資組合上下文的完整提示語給 AI 模型。
    """
    context_str = ""
    for strategy_name, df in portfolios_dict.items():
        context_str += f"--- 投資組合策略: {strategy_name} ---\n"
        context_str += df.to_string(index=False)
        context_str += "\n\n"

    prompt = f"""
    你是一位專業、友善且客觀的AI投資組合分析助理。你的任務是根據以下提供的多個投資組合數據，回答使用者的問題。

    **規則與限制:**
    1.  你**不能**提供任何未來的預測或直接的買賣建議。你的回答應專注於解釋這份報告的數據。
    2.  你的回答必須基於以下提供的「當前投資組合數據」。不要提及任何外部市場資訊。
    3.  如果問題涉及比較，請根據數據進行客觀比較。
    4.  回答應簡潔、有條理，並使用繁體中文。

    ---
    **當前已生成的投資組合數據:**
    {context_str}
    ---

    **使用者問題:**
    {user_question}

    **你的回答:**
    """
    return prompt