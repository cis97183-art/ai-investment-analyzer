# prompts.py

# 這個函式維持原樣，但現在是給 AI 用的
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

    optimization_strategy = '平均權重'
    if portfolio_type == '純個股':
        strategy_map = {'1': '平均權重', '2': '夏普比率優化', '3': '排名加權'}
        while True:
            strategy_choice = input("請選擇個股優化策略 (1:平均權重, 2:夏普比率優化, 3:排名加權): ")
            if strategy_choice in strategy_map:
                optimization_strategy = strategy_map[strategy_choice]
                break
            else:
                print("無效輸入，請重新輸入。")

    return risk_profile, portfolio_type, optimization_strategy

# *** 新增給 AI 使用的提示語函式 ***
def get_ai_response(portfolios_dict, user_question):
    """
    呼叫 Gemini API 來獲取 AI 的回答。
    現在接收一個包含所有 portfolio 的字典。
    """
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 組合包含所有 portfolio 上下文的提示語
        prompt = get_system_prompt(portfolios_dict, user_question)
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        error_message = f"呼叫 AI 時發生錯誤：{e} \n\n請確認：\n1. `.streamlit/secrets.toml` 檔案已建立。\n2. `GOOGLE_API_KEY` 已正確設定。"
        st.error(error_message)
        return None