import pandas as pd

def screen_stocks(df: pd.DataFrame, risk_profile: str) -> pd.DataFrame:
    """
    [FinMind 版本] 根據用戶風險偏好，對從本地資料庫讀取的數據進行篩選。
    此版本基於 P/E, P/B, and Yield 進行篩選。
    """
    if df.empty:
        return pd.DataFrame()

    # --- 1. 估值篩選 (Valuation) ---
    # 保守型選擇低估值，積極型可接受較高估值
    pe_thresholds = {
        '保守型': (0, 15),    # 本益比 0-15
        '穩健型': (0, 25),    # 本益比 0-25
        '積極型': (10, 50)     # 本益比 10-50 (允許較高估值，但排除極端值)
    }
    pb_thresholds = {
        '保守型': (0, 2),     # 股價淨值比 0-2
        '穩健型': (0.5, 4),   # 股價淨值比 0.5-4
        '積極型': (1.5, 8)    # 股價淨值比 1.5-8
    }
    
    min_pe, max_pe = pe_thresholds[risk_profile]
    df_pe = df[(df['pe_ratio'] > min_pe) & (df['pe_ratio'] < max_pe)].copy()

    min_pb, max_pb = pb_thresholds[risk_profile]
    df_pb = df_pe[(df_pe['pb_ratio'] > min_pb) & (df_pe['pb_ratio'] < max_pb)].copy()

    # --- 2. 股息篩選 (Dividend Yield) ---
    # 僅對保守型與穩健型有較高要求
    if risk_profile in ['保守型', '穩健型']:
        div_thresholds = {
            '保守型': 4.0, # 殖利率 > 4%
            '穩健型': 2.5  # 殖利率 > 2.5%
        }
        min_div = div_thresholds[risk_profile]
        # FinMind 的 'yield' 欄位是百分比數值，例如 3.5 代表 3.5%
        df_final = df_pb[df_pb['yield'] > min_div].copy()
    else:
        # 積極型對股息沒有硬性要求
        df_final = df_pb.copy()
        
    # --- 返回最終結果 ---
    # 為了讓 AI 有足夠的選擇，我們返回最多 25 筆符合條件的股票
    # 以 P/E Ratio 排序，讓估值較合理的股票排在前面
    return df_final.sort_values(by='pe_ratio', ascending=True).head(25)
