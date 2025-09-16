import yfinance as yf
import streamlit as st
import pandas as pd

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
    使用 Streamlit 的快取功能避免重複下載。
    """
    all_info = []
    progress_bar = st.progress(0, text="正在下載市場數據...")
    
    for i, ticker_id in enumerate(TICKER_LIST):
        try:
            ticker_obj = yf.Ticker(ticker_id)
            # .info 是一個包含大量詳細資訊的字典
            info = ticker_obj.info
            # 我們只選取需要的欄位，並加上 tickerId
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
            # st.warning(f"無法獲取 {ticker_id} 的數據: {e}")
            pass # 如果有股票下市或暫停交易，直接跳過
        
        progress_bar.progress((i + 1) / len(TICKER_LIST), text=f"正在下載 {ticker_id} 的數據...")

    progress_bar.empty() # 清除進度條
    
    if not all_info:
        return pd.DataFrame()

    df = pd.DataFrame(all_info)
    df = df.set_index('tickerId')
    
    # 數據清洗：將 None 或 無效值轉換為 np.nan，並設定正確的數據類型
    df = df.apply(pd.to_numeric, errors='coerce')
    # shortName 和 industry 是字串，需要另外處理
    df['shortName'] = [info.get('shortName') for info in all_info]
    df['industry'] = [info.get('industry') for info in all_info]
    
    # 移除缺少關鍵數據的行
    df.dropna(subset=['marketCap', 'beta', 'averageVolume', 'shortName'], inplace=True)
    
    return df
