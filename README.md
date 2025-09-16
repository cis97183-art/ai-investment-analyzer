AI 個人化投資組合建構與分析系統這是一個使用 Streamlit、LangChain 和 Google Gemini API 打造的 AI 投資組合分析工具。本系統採用專業的「台股投資組合風險偏好定義規則」框架，由 AI 為您量身打造專屬的純個股、純 ETF 或核心-衛星混合型台股投資組合，並提供視覺化的分析報告與互動式問答調整功能。✨ 功能特色三種投資組合類型：可根據偏好選擇建立純個股、純 ETF 或核心-衛星混合型投資組合。三種風險偏好：支援積極型、穩健型、保守型三種風險等級，AI 會依據對應規則進行分析。專業規則框架：內建詳細的量化與質化規則 (Prompt Framework)，引導 AI 產生專業且符合邏輯的建議。視覺化報告：將 AI 生成的投資組合以互動式圖表（圓餅圖、長條圖）和表格呈現，一目了然。互動式調整：在生成報告後，可以透過聊天視窗向 AI 提問，進行微調或深入了解特定持股的理由。安全金鑰管理：使用 Streamlit Secrets 功能管理 API 金鑰，避免金鑰外洩。🚀 安裝與執行請依照以下步驟在您的本機環境中執行此專案。1. 前置準備已安裝 Python 3.8 或更高版本。擁有一個有效的 Google AI Platform API 金鑰。2. 下載專案git clone [https://github.com/your-username/ai-investment-analyzer.git](https://github.com/your-username/ai-investment-analyzer.git)
cd ai-investment-analyzer
3. 建立虛擬環境並安裝相依套件建議使用虛擬環境以避免套件版本衝突。# 建立虛擬環境
python -m venv venv

# 啟用虛擬環境
# Windows
.\venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 安裝所有必要的套件
pip install -r requirements.txt
4. 設定 API 金鑰在專案的根目錄下，建立一個名為 .streamlit 的資料夾，並在其中新增一個 secrets.toml 檔案。.
├── .streamlit/
│   └── secrets.toml  <-- 在這裡設定金鑰
├── investment_analyzer.py
└── ...
secrets.toml 檔案的內容如下：# .streamlit/secrets.toml
GOOGLE_API_KEY = "將你從 Google Cloud 取得的 API 金鑰貼在這裡"
5. 執行應用程式在終端機中執行以下指令：streamlit run investment_analyzer.py
應用程式將會在本機的瀏覽器視窗中開啟。🖼️ 畫面預覽(請替換為您自己的截圖連結)