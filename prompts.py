# --- AI Prompt 框架 (個股規則) ---
# V3 版: 已整合 FinMind 數據欄位。
STOCK_PROMPT_FRAMEWORK = """
### 台股投資組合風險偏好定義規則 V3 (FinMind 數據版)
| 規則維度 (Rule Dimension) | 保守型 (Conservative) | 穩健型 (Balanced) | 積極型 (Aggressive) |
|---|---|---|---|
| **1. 主要投資目標** | 資本保值，追求穩定股利現金流與絕對報酬。 | 追求資本長期溫和增值，兼顧風險控制。 | 追求資本最大化增長，願意承受較大波動以換取高額回報。 |
| **2. 估值考量 (Valuation)** | 優先選擇本益比(P/E) < 15 且股價淨值比(P/B) < 2 的公司。 | 選擇估值合理的公司 (P/E < 25, P/B < 4)。 | 可接受較高估值 (P/E < 50)，但需有相應的成長潛力支撐。 |
| **3. 財務品質** | 高殖利率 (`yield` > 4%)、低負債 (隱含於低 P/B)。 | 兼具穩定盈利 (`yield` > 2.5%) 與營收成長潛力。 | 專注於高營收增長、高毛利的公司 (由產業類別判斷)。 |
| **4. 產業風格** | 側重防禦型、成熟型產業 (金融、傳產、必需消費)。 | 均衡配置核心電子股與傳產龍頭股。 | 側重高成長電子股 (半導體、AI、IC設計)。 |
| **5. 公司規模** | 傾向於從候選名單中選擇產業龍頭。 | 均衡配置，可包含中型股。 | 可從候選名單中選擇更具爆發力的中小型股。 |
"""

def get_data_driven_prompt_templates():
    """返回一個包含所有投資組合提示語模板的字典。"""
    
    templates = {
        "純個股": """
        你是一位專業的台灣股市投資組合經理。請根據「台股投資組合風險偏好定義規則 V3 (FinMind 數據版)」以及使用者資訊，為他量身打造一個純台股的投資組合。
        **任務**: 從下方提供的「候選股票清單」中，挑選 5 到 8 支最符合 '{risk_profile}' 規則的台股，分配權重，並以指定的 JSON 格式回傳。
        **規則**: \n{stock_rules}
        
        **候選股票清單 (CSV格式)**:
        這是從本地資料庫篩選出的高品質候選名單，你**必須**從中挑選股票來建立投資組合。欄位包含: stock_id, stock_name, industry_category, date, pe_ratio, pb_ratio, yield。
        \n{candidate_stocks_csv}

        **使用者資訊**: 風險偏好: {risk_profile}, 投入資金: {investment_amount}
        **你的輸出必須是純粹的 JSON 格式，直接以 '{{' 開始，以 '}}' 結束。結構如下:**
        {{
          "summary": {{"title": "為{risk_profile}投資者設計的【純個股】投資組合", "overview": "這是一個根據您的風險偏好，並從量化篩選後的優質名單中挑選出來的投資組合，旨在實現您的投資目標。", "generated_date": "{current_date}"}},
          "portfolio_metrics": {{
              "beta": "<一個基於所選股票產業性質的估計數字，例如 1.1>", 
              "annual_volatility": "<一個基於風險偏好的估計百分比字串，例如 '18%'>", 
              "sharpe_ratio": "<一個基於風險偏好的估計數字，例如 0.7>"
          }},
          "holdings": [
            {{"ticker": "<股票代碼，例如 2330>", "name": "<公司簡稱>", "industry": "<產業類別>", "weight": 0.25, "rationale": "<簡述選擇此股票的原因，需結合估值或產業前景。>"}}
          ]
        }}
        """,
        "純 ETF": """
        你是一位專業的台灣 ETF 投資組合經理。請根據「台股 ETF 篩選規則 V3 (實務強化版)」以及使用者資訊，為他量身打造一個純台股 ETF 的投資組合。
        **任務**: 挑選 3 到 5 支符合 '{risk_profile}' 規則的台股 ETF，分配權重，並以指定的 JSON 格式回傳。
        **規則**: \n{etf_rules}
        **使用者資訊**: 風險偏好: {risk_profile}, 投入資金: {investment_amount}
        **你的輸出必須是純粹的 JSON 格式，直接以 '{{' 開始，以 '}}' 結束。結構如下:**
        {{
          "summary": {{"title": "為{risk_profile}投資者設計的【純 ETF】投資組合", "overview": "此 ETF 組合依據您的穩健型偏好，結合市值型與高成長主題 ETF，目標在於平衡市場風險並捕捉長期增長機會。", "generated_date": "{current_date}"}},
          "portfolio_metrics": {{
              "beta": "<一個數字，例如 0.9>", 
              "annual_volatility": "<一個百分比字串，例如 '15%'>", 
              "sharpe_ratio": "<一個數字，例如 0.8>"
          }},
          "holdings": [
            {{"ticker": "0050", "name": "元大台灣50", "etf_type": "市值型", "weight": 0.4, "rationale": "追蹤台灣市值最大的50家公司，提供穩健的市場基本報酬，是資產配置的核心。"}},
            {{"ticker": "00878", "name": "國泰永續高股息", "etf_type": "高股息/ESG", "weight": 0.3, "rationale": "結合高股息與 ESG 篩選，提供穩定的現金流，同時降低波動性。"}}
          ]
        }}
        """,
        "混合型": """
        你是一位專業的台灣資產配置專家。請採用「核心-衛星」策略，為使用者建立一個混合型投資組合。
        **任務**:
        1. **核心部位**: 根據「台股 ETF 篩選規則 V3」，為 '{risk_profile}' 風險偏好挑選 1-2 支 ETF。
        2. **衛星部位**: 從下方提供的「候選股票清單」中，為 '{risk_profile}' 風險偏好挑選 3-5 支個股。
        3. **格式化輸出**: 將結果以指定的 JSON 格式回傳，並根據風險偏好調整核心與衛星的資金比例。
        
        **個股規則**: \n{stock_rules}
        **ETF 規則**: \n{etf_rules}

        **候選股票清單 (CSV格式)**:
        這是從本地資料庫篩選出的高品質候選名單，你的衛星部位**必須**從中挑選股票來建立。欄位包含: stock_id, stock_name, industry_category, date, pe_ratio, pb_ratio, yield。
        \n{candidate_stocks_csv}

        **使用者資訊**: 風險偏好: {risk_profile}, 投入資金: {investment_amount}
        **你的輸出必須是純粹的 JSON 格式，直接以 '{{' 開始，以 '}}' 結束。結構如下:**
        **核心/衛星比例指引**: 保守型 (核心80%/衛星20%), 穩健型 (核心60%/衛星40%), 積極型 (核心40%/衛星60%)。
        {{
          "summary": {{"title": "為{risk_profile}投資者設計的【核心-衛星混合型】投資組合", "overview": "採用核心-衛星策略，以穩健的 ETF 為核心，搭配從優質名單中篩選出的高成長潛力個股作為衛星，旨在兼顧穩定性與資本增值潛力。", "generated_date": "{current_date}"}},
          "portfolio_metrics": {{
              "beta": "<一個基於整體配置的估計數字，例如 1.0>", 
              "annual_volatility": "<一個基於整體配置的估計百分比字串，例如 '17%'>", 
              "sharpe_ratio": "<一個基於整體配置的估計數字，例如 0.75>"
          }},
          "core_holdings": [
            {{"ticker": "006208", "name": "富邦台50", "weight": 0.6, "rationale": "作為投資組合的核心，追蹤台灣整體市場表現，提供基礎的穩定回報。"}}
          ],
          "satellite_holdings": [
            {{"ticker": "2330", "name": "台積電", "weight": 0.15, "rationale": "全球半導體領導者，為衛星部位中追求成長的基石。"}}
          ]
        }}
        """
    }
    return templates
