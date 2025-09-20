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
    """
    產生一個精簡、高效的提示語給 AI 模型。
    """
    context_str = "目前尚未生成任何投資組合。"
    if portfolios_dict:
        context_str = ""
        for strategy_name, df in portfolios_dict.items():
            context_str += f"--- 投資組合策略: {strategy_name} ---\n"
            # *** 修正點：只選擇最重要的欄位給 AI ***
            display_cols = ['代號', '名稱', '產業別', '建議權重', '配置金額(元)']
            # 檢查夏普比率是否存在，若存在則加入
            if '夏普比率' in df.columns:
                display_cols.insert(3, '夏普比率')
            
            # 只選取存在的欄位
            existing_display_cols = [col for col in display_cols if col in df.columns]
            context_str += df[existing_display_cols].to_string(index=False)
            context_str += "\n\n"

    prompt = f"""
    你是一位專業、友善且客觀的AI投資組合分析助理。

    你的能力有兩種模式：
    1.  **報告分析模式**：當使用者問題與下方提供的「當前投資組合數據」相關時，你的任務是根據這些數據回答問題。
    2.  **投資知識庫模式**：當使用者問題是關於一般性的投資觀念時（例如「什麼是本益比？」、「解釋一下什麼是 HHI」），請從你的知識庫中提供準確、客觀的定義與解釋。
    3.  **指令識別模式**：當使用者下達類似「加入 [股票代號]」的指令時，你的唯一任務就是回答「好的，我正在為您加入新標的並重新計算投資組合...」。

    **規則與限制:**
    -   **絕不**提供任何未來的預測或直接的買賣建議。所有回答都應保持中立客觀。
    -   在「報告分析模式」下，回答必須嚴格基於下方提供的數據。

    ---
    **當前投資組合數據:**
    {context_str}
    ---

    **使用者問題:**
    {user_question}

    **你的回答:**
    """
    return prompt