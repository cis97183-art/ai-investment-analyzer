import pandas as pd

def screen_stocks(df: pd.DataFrame, risk_profile: str) -> pd.DataFrame:
    """
    根據用戶的風險偏好，對數據進行多層量化篩選。
    返回一個通過所有篩選條件的 DataFrame。
    """
    
    # --- 1. 流動性篩選 (Liquidity) ---
    # 這是第一道關卡，成交量太低的股票直接剔除
    liquidity_thresholds = {
        '保守型': 5_000_000_000, # 日均成交額 > 50億 (用市值*價格粗估)
        '穩健型': 1_000_000_000, # > 10億
        '積極型': 500_000_000  # > 5億
    }
    # 估算日均成交額 (成交量 * 股價)
    df['estimated_turnover'] = df['averageVolume'] * df['regularMarketPrice']
    min_liquidity = liquidity_thresholds[risk_profile]
    df_liquidity = df[df['estimated_turnover'] > min_liquidity].copy()
    
    # --- 2. 公司規模篩選 (Market Cap) ---
    size_thresholds = {
        '保守型': 200_000_000_000, # > 2000億
        '穩健型': 50_000_000_000,  # > 500億
        '積極型': 10_000_000_000   # > 100億
    }
    min_size = size_thresholds[risk_profile]
    df_size = df_liquidity[df_liquidity['marketCap'] > min_size].copy()
    
    # --- 3. 波動性篩選 (Beta) ---
    beta_thresholds = {
        '保守型': (0, 0.8),    # Beta < 0.8
        '穩健型': (0.8, 1.1), # 0.8 < Beta < 1.1
        '積極型': (1.1, 999)   # Beta > 1.1
    }
    min_beta, max_beta = beta_thresholds[risk_profile]
    df_beta = df_size[(df_size['beta'] > min_beta) & (df_size['beta'] < max_beta)].copy()

    # --- 4. 估值篩選 (Valuation) ---
    # 這裡我們用一個簡化規則：保守型P/E不能太高，積極型可以容忍
    pe_thresholds = {
        '保守型': 20,
        '穩健型': 40,
        '積極型': 100 
    }
    max_pe = pe_thresholds[risk_profile]
    # 處理PE為負或NaN的情況
    df_pe = df_beta[(df_beta['trailingPE'].notna()) & (df_beta['trailingPE'] > 0) & (df_beta['trailingPE'] < max_pe)].copy()

    # --- 5. 股息篩選 (Dividend) ---
    # 僅對保守型與穩健型有要求
    if risk_profile in ['保守型', '穩健型']:
        div_thresholds = {
            '保守型': 0.04, # > 4%
            '穩健型': 0.03  # > 3%
        }
        min_div = div_thresholds[risk_profile]
        df_final = df_pe[df_pe['dividendYield'] > min_div].copy()
    else:
        df_final = df_pe.copy()
        
    # --- 交叉比對後返回最終結果 ---
    # 因為我們是一層一層篩選下來，所以 df_final 就是最終結果
    # 為了讓結果更多樣化，我們按市值排序取前 20 名作為候選
    return df_final.sort_values(by='marketCap', ascending=False).head(20)
