from langchain.prompts import PromptTemplate
from portfolio_rules import PORTFOLIO_CONSTRUCTION_RULES

def get_data_driven_prompt_templates():
    """
    根據使用者選擇的投資組合類型，返回對應的LangChain PromptTemplate。
    """

    # --- 1. 純個股投資組合 Prompt ---
    prompt_pure_stock = PromptTemplate(
        input_variables=["risk_profile", "investment_amount", "candidate_stocks_csv"],
        template="""
        # 指令: 擔任資深投資總監

        你是一位專為高淨值客戶服務的資深投資總監。你的任務是根據下方提供的「投資組合建構規則」和「候選股票清單」，為客戶建構一個專業的「純個股投資組合」。

        ## 核心任務
        1.  **理解規則**: 深度分析「投資組合建構規則」中，針對 '{risk_profile}' 風險偏好的「純個股投資組合」策略。
        2.  **篩選標的**: 從下方提供的「候選股票清單」中，根據規則挑選出最符合策略的股票。
        3.  **配置權重**: 根據規則建議的持股數量與分散原則，為選出的股票分配具體的投資權重。
        4.  **撰寫報告**: 產生一份專業的投資建議報告，包含投資組合概述、標的選擇理由、以及配置細節。
        5.  **格式化輸出**: 將最終結果以指定的 JSON 格式回傳。

        ---
        ## 參考資料

        ### 1. 投資組合建構規則
        {rules}

        ### 2. 候選股票清單 (已通過第一輪量化篩選)
        {candidate_stocks_csv}

        ---
        ## 輸出指令

        **客戶資訊**:
        -   **風險偏好**: {risk_profile}
        -   **投入資金**: {investment_amount} 新台幣

        **你的輸出必須是純粹的 JSON 格式，直接以 '{{' 開始，以 '}}' 結束。結構如下:**
        ```json
        {{
          "summary": {{
            "title": "為「{risk_profile}」投資者設計的【純個股】投資組合",
            "overview": "這是一個根據您的風險偏好量身打造的個股投資組合。我們專注於[此處填寫核心邏輯，例如：經營穩健、具長期股利發放紀錄的大型龍頭企業]，旨在實現[此處填寫投資目標，例如：資本保值與穩定現金流]。"
          }},
          "portfolio_composition": {{
            "type": "純個股",
            "holdings": [
              {{
                "stock_id": "股票代號",
                "stock_name": "公司名稱",
                "industry": "產業別",
                "weight": 0.25,
                "reason": "選擇此標的的核心理由（必須根據規則和數據說明，例如：Beta值小於0.8，連續配息超過15年，殖利率高於4%，符合保守型策略的穩定收益要求）。"
              }}
            ]
          }}
        }}
        ```
        """
    ).partial(rules=PORTFOLIO_CONSTRUCTION_RULES)


    # --- 2. 純ETF投資組合 Prompt ---
    prompt_pure_etf = PromptTemplate(
        input_variables=["risk_profile", "investment_amount", "candidate_etfs_csv"],
        template="""
        # 指令: 擔任資深投資總監

        你是一位專為高淨值客戶服務的資深投資總監。你的任務是根據下方提供的「投資組合建構規則」和「候選ETF清單」，為客戶建構一個專業的「純ETF投資組合」。

        ## 核心任務
        1.  **理解規則**: 深度分析「投資組合建構規則」中，針對 '{risk_profile}' 風險偏好的「純ETF投資組合」策略。
        2.  **篩選標的**: 從下方提供的「候選ETF清單」中，根據規則挑選出最符合策略的ETF。
        3.  **配置權重**: 根據規則建議的資產配置原則（例如：債券80%/高股息20%），為選出的ETF分配具體的投資權重。
        4.  **撰寫報告**: 產生一份專業的投資建議報告，包含投資組合概述、標的選擇理由、以及配置細節。
        5.  **格式化輸出**: 將最終結果以指定的 JSON 格式回傳。

        ---
        ## 參考資料

        ### 1. 投資組合建構規則
        {rules}

        ### 2. 候選ETF清單 (已通過第一輪量化篩選)
        {candidate_etfs_csv}

        ---
        ## 輸出指令

        **客戶資訊**:
        -   **風險偏好**: {risk_profile}
        -   **投入資金**: {investment_amount} 新台幣

        **你的輸出必須是純粹的 JSON 格式，直接以 '{{' 開始，以 '}}' 結束。結構如下:**
        ```json
        {{
          "summary": {{
            "title": "為「{risk_profile}」投資者設計的【純ETF】投資組合",
            "overview": "這是一個根據您的風險偏好量身打造的ETF投資組合。我們專注於[此處填寫核心邏輯，例如：透過投資級債券ETF建立穩固的收益基礎]，旨在實現[此處填寫投資目標，例如：資本保護與追求穩定現金流]。"
          }},
          "portfolio_composition": {{
            "type": "純ETF",
            "holdings": [
              {{
                "stock_id": "ETF代號",
                "stock_name": "ETF名稱",
                "industry": "ETF類型",
                "weight": 0.80,
                "reason": "選擇此標的的核心理由（必須根據規則和數據說明，例如：此為長天期美國公債ETF，Beta值低於0.5，費用率小於0.5%，完美符合保守型策略的核心配置需求）。"
              }}
            ]
          }}
        }}
        ```
        """
    ).partial(rules=PORTFOLIO_CONSTRUCTION_RULES)


    # --- 3. 混合型投資組合 Prompt ---
    prompt_hybrid = PromptTemplate(
        input_variables=["risk_profile", "investment_amount", "candidate_stocks_csv", "candidate_etfs_csv"],
        template="""
        # 指令: 擔任資深投資總監

        你是一位專為高淨值客戶服務的資深投資總監。你的任務是根據下方提供的「投資組合建構規則」和「候選清單」，為客戶建構一個專業的「混合型投資組合」。

        ## 核心任務
        1.  **理解規則**: 深度分析「投資組合建構規則」中，針對 '{risk_profile}' 風險偏好的「混合型投資組合」策略，特別注意個股與ETF的配置比例。
        2.  **篩選標的**: 從「候選個股清單」和「候選ETF清單」中，分別根據規則挑選出最符合策略的標的。
        3.  **配置權重**: 嚴格遵循規則建議的資產配置比例（例如：保守型為70%債券ETF+30%個股），為選出的所有標的分配總和為100%的投資權重。
        4.  **撰寫報告**: 產生一份專業的投資建議報告，包含投資組合概述、標的選擇理由、以及配置細節。
        5.  **格式化輸出**: 將最終結果以指定的 JSON 格式回傳。

        ---
        ## 參考資料

        ### 1. 投資組合建構規則
        {rules}

        ### 2. 候選個股清單 (已通過第一輪量化篩選)
        {candidate_stocks_csv}

        ### 3. 候選ETF清單 (已通過第一輪量化篩選)
        {candidate_etfs_csv}

        ---
        ## 輸出指令

        **客戶資訊**:
        -   **風險偏好**: {risk_profile}
        -   **投入資金**: {investment_amount} 新台幣

        **你的輸出必須是純粹的 JSON 格式，直接以 '{{' 開始，以 '}}' 結束。結構如下:**
        ```json
        {{
          "summary": {{
            "title": "為「{risk_profile}」投資者設計的【混合型】投資組合",
            "overview": "這是一個根據您的風險偏好量身打造的混合型投資組合。我們採用[此處填寫核心邏輯，例如：以債券ETF作為穩定基石，搭配少量優質龍頭股增強長期收益]，旨在實現[此處填寫投資目標，例如：在嚴格控制風險的同時，參與股市的長期增長潛力]。"
          }},
          "portfolio_composition": {{
            "type": "混合型",
            "holdings": [
              {{
                "stock_id": "標的代號",
                "stock_name": "標的名稱",
                "industry": "產業別或ETF類型",
                "weight": 0.70,
                "reason": "選擇此標的的核心理由（必須根據規則和數據說明，說明為何選擇此ETF或個股）。"
              }}
            ]
          }}
        }}
        ```
        """
    ).partial(rules=PORTFOLIO_CONSTRUCTION_RULES)


    return {
        "純個股投資組合": prompt_pure_stock,
        "純ETF投資組合": prompt_pure_etf,
        "混合型投資組合": prompt_hybrid
    }
