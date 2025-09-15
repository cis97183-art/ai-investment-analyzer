# 台股 ETF 篩選規則 (AI Prompt Framework for Taiwan ETFs)
# 為了保持主程式碼的整潔，我們將這份詳細的規則框架獨立出來。
# 主程式 (app.py) 將會匯入此檔案中的 ETF_PROMPT_FRAMEWORK 變數。

ETF_PROMPT_FRAMEWORK = """
### 台股 ETF 篩選規則 (AI Prompt Framework for Taiwan ETFs)
| 規則維度 (Rule Dimension) | 保守型 (Conservative) | 穩健型 (Balanced) | 積極型 (Aggressive) |
|---|---|---|---|
| **1. 主要 ETF 類型** | 市值型(0050), 高股息低波動型(00878), 投資等級債券型。| 市值型, 特定產業龍頭型(00891), ESG主題型。 | 積極成長主題型(00757), 中小型股指數型。|
| **2. 總費用率** | < 0.4% | < 0.7% | < 1.0% |
| **3. 資產管理規模 (AUM)** | > 500億 新台幣 | > 100億 新台幣 | > 20億 新台幣 |
| **4. 流動性 (日均成交量)**| > 10,000 張 | > 5,000 張 | > 1,000 張 |
| **5. 成分股集中度** | < 50% | < 65% | 可接受 > 65% |
"""

