import yfinance as yf
import streamlit as st
import pandas as pd
import numpy as np

# --- 台股成分股列表 ---
# 為了演示，我們選取台灣50指數 + 部分中小型潛力股作為基礎股票池
# 在真實應用中，這個列表可以擴展到台股全市場
TICKER_LIST = [
    "2330.TW", "2317.TW", "2454.TW", "2412.TW", "2881.TW", "2882.TW", "2886.TW", "1301.TW", "1303.TW", "1326.TW",
    "2002.TW", "2207.TW", "2303.TW", "2308.TW", "2382.TW", "2891.TW", "2912.TW", "3008.TW", "3045.TW", "3711.TW",
    "4904.TW", "5871.TW", "5880.TW", "6505.TW", "9910.TW", "2379.TW", "2395.TW", "2884.TW", "1216.TW", "1101.TW",
    "2357.TW", "2603.TW", "2609.TW", "2615.TW", "2880.TW", "2883.TW", "2885.TW", "2892.TW", "4938.TW", "6415.TW",
    "1590.TW", "3661.TW", "8069.TW", "6669.TW", "3529.TW", "3034.TW", "3443.TW", "2458.TW", "5269.TW", "2377.TW"
]

@st.cache_data(ttl=3600) # 快取數據一小時
def get_stock_data():
    """
    使用 yfinance 下載所有目標股票的即時數據。
    [優化版] 增加更詳細的錯誤回報機制。
    """
    all_info = []
    failed_tickers = []
    progress_bar = st.progress(0, text="正在初始化數據下載...")
    
    for i, ticker_id in enumerate(TICKER_LIST):
        try:
            ticker_obj = yf.Ticker(ticker_id)
            info = ticker_obj.info
            
            # [優化] 增加一道驗證：確保關鍵數據存在，否則視為失敗
            if not info or info.get('marketCap') is None or info.get('regularMarketPrice') is None:
                raise ValueError(f"缺少 {ticker_id} 的關鍵市場數據 (例如市值)，可能已下市或為無效代碼。")

            filtered_info = {
                'tickerId': ticker_id,
                'shortName': info.get('shortName'),
                'industry': info.get('industry'),
                'marketCap': info.get('marketCap'),
                'beta': info.get('beta'),
                'averageVolume': info.get('averageVolume10day'),
                'trailingPE': info.get('trailingPE'),
                'forwardPE': info.get('forwardPE'),
                'dividendYield': info.get('dividendYield'),
                'priceToBook': info.get('priceToBook'),
                'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh'),
                'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow'),
                'regularMarketPrice': info.get('regularMarketPrice')
            }
            all_info.append(filtered_info)
        except Exception as e:
            # 如果有股票下市或暫停交易，紀錄起來並在最後回報
            failed_tickers.append(ticker_id)
        
        progress_bar.progress((i + 1) / len(TICKER_LIST), text=f"正在下載 {i+1}/{len(TICKER_LIST)}: {ticker_id} ...")

    progress_bar.empty()
    
    # [優化] 如果有部分股票下載失敗，在 UI 上顯示警告，讓使用者知道
    if failed_tickers:
        st.warning(f"注意：以下 {len(failed_tickers)} 支股票的數據獲取失敗，已被忽略。原因可能是已下市、暫停交易或網路問題： **{', '.join(failed_tickers)}**")

    if not all_info:
        # 只有在 *所有* 股票都失敗時，才返回空的 DataFrame
        return pd.DataFrame()

    df = pd.DataFrame(all_info)
    df = df.set_index('tickerId')
    
    # 數據清洗：暫存原始的字串欄位
    string_cols = df[['shortName', 'industry']].copy()

    # 將所有欄位嘗試轉為數值，失敗的會變成 NaN
    df = df.apply(pd.to_numeric, errors='coerce')

    # 還原字串欄位
    df['shortName'] = string_cols['shortName']
    df['industry'] = string_cols['industry']
    
    # 移除缺少關鍵數據的行 (例如 beta, marketCap)
    df.dropna(subset=['marketCap', 'beta', 'averageVolume', 'shortName'], inplace=True)
    
    return df
