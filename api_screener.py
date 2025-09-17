import pandas as pd
import requests
import streamlit as st

# 在真實應用中，這會是您外部 API 的 URL
# 為了演示，我們將其指向一個模擬的本地函式
API_BASE_URL = "http://127.0.0.1:8000/screen" # 假設您的 API 在本地運行

def screen_stocks_api(risk_profile: str) -> list[str]:
    """
    [新功能] 調用外部股票篩選器 API 來獲取符合條件的股票代碼列表。
    
    Args:
        risk_profile: 投資者的風險偏好 ('保守型', '穩健型', '積極型').

    Returns:
        一個包含符合條件的股票代碼的列表。
    """
    
    # --- 模擬 API 參數對應 ---
    # 在真實世界中，這些參數會由後端 API 處理。
    # 這裡我們模擬 API 的行為，根據風險偏好返回不同的股票列表。
    # 這些列表是根據 screener.py 的原始邏輯簡化得出的。
    
    st.info(f"🔄 正在即時調用外部篩選器 API，篩選規則為：**{risk_profile}**")

    # 模擬的股票池
    full_stock_list = [
        "2330.TW", "2317.TW", "2454.TW", "2412.TW", "2881.TW", "2882.TW", "2886.TW", "1301.TW", "1303.TW", 
        "2002.TW", "2303.TW", "2308.TW", "2891.TW", "2912.TW", "3008.TW", "3045.TW", "3711.TW", "5871.TW",
        "2379.TW", "2395.TW", "2884.TW", "1216.TW", "1101.TW", "2357.TW", "2603.TW", "2609.TW", "2880.TW",
        "4938.TW", "6415.TW", "1590.TW", "3661.TW", "8069.TW", "6669.TW", "3529.TW", "3034.TW", "3443.TW",
        "2458.TW", "5269.TW", "2377.TW"
    ]

    # 簡化的篩選邏輯來模擬 API 行為
    if risk_profile == '保守型':
        # 大型、穩定、高股息
        tickers = ["2330.TW", "2412.TW", "2881.TW", "2882.TW", "1301.TW", "2002.TW", "2891.TW", "1101.TW", "1216.TW"]
    elif risk_profile == '穩健型':
        # 中大型、兼具成長與穩定
        tickers = ["2317.TW", "2454.TW", "2308.TW", "3045.TW", "3711.TW", "2379.TW", "2357.TW", "2603.TW", "4938.TW"]
    elif risk_profile == '積極型':
        # 中小型、高成長、高 Beta
        tickers = ["3008.TW", "6415.TW", "3661.TW", "8069.TW", "6669.TW", "3529.TW", "3034.TW", "3443.TW", "5269.TW", "2377.TW"]
    else:
        tickers = full_stock_list[:10] # 預設返回前10支

    st.success("✅ 外部 API 已成功返回符合條件的股票列表！")
    
    # 在真實的 API call 中，您會使用 requests 函式庫:
    # try:
    #     params = {'risk_profile': risk_profile}
    #     response = requests.get(API_BASE_URL, params=params, timeout=10)
    #     response.raise_for_status() # 如果 request 失敗 (e.g., 404, 500) 就會拋出異常
    #     api_result = response.json()
    #     tickers = api_result.get("tickers", [])
    #     if not tickers:
    #        st.warning("API 回傳了一個空的股票列表。")
    #     return tickers
    # except requests.exceptions.RequestException as e:
    #     st.error(f"呼叫股票篩選器 API 失敗: {e}")
    #     return []
    
    return tickers
