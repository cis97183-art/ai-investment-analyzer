# main.py (修正後的版本)

import config
import data_loader
import screener
import investment_analyzer
import prompts
import pandas as pd # 匯入 pandas

def _calculate_hhi(weights: list) -> float:
    """從權重列表計算 HHI 集中度指數。權重應為 0-1 之間的小數。"""
    return sum([w**2 for w in weights])

def main():
    """程式主執行流程 (已修正)"""
    risk_profile, portfolio_type = prompts.get_user_preferences()

    master_df = data_loader.load_and_prepare_data(
        config.LISTED_STOCK_PATH, config.OTC_STOCK_PATH, config.ETF_PATH
    )
    if master_df is None: 
        print("錯誤：資料載入失敗，程式終止。")
        return

    # --- 【修正點 1】呼叫正確的函式 ---
    # generate_asset_pools 會回傳一個字典，裡面是所有篩選過的標的池
    print("\n--- 步驟 2: 正在建立高品質動態觀察名單... ---")
    asset_pools = screener.generate_asset_pools(master_df)
    
    # --- 【修正點 2】傳入正確的參數並接收正確的回傳值 ---
    # 將整個 asset_pools 字典傳入 build_portfolio
    final_portfolio, candidate_pools = investment_analyzer.build_portfolio(
        asset_pools=asset_pools,
        risk_preference=risk_profile, # 注意：這裡的 risk_profile 是中文，需要轉換
        portfolio_type=portfolio_type # 注意：這裡的 portfolio_type 也是中文
    )
    
    if final_portfolio is not None and not final_portfolio.empty:
        # --- 【修正點 3】在主流程中計算 HHI 指數 ---
        weights = final_portfolio['權重(%)'].values / 100
        hhi_value = _calculate_hhi(weights)

        # 這裡的 risk_profile 和 portfolio_type 是從 prompts.py 來的中文，可以直接使用
        print(f"\n--- 【{risk_profile} - {portfolio_type}】投資組合建議 ---")
        print(f"投資組合 HHI 指數: {hhi_value:.4f} (指數越低代表越分散)")
        
        # 為了更好的顯示效果，可以只選擇幾個關鍵欄位
        display_cols = ['代碼', '名稱', '產業別', '權重(%)', '資產類別']
        print(final_portfolio[display_cols].to_string(index=False))
        
        # 匯出 CSV
        output_filename = f"{risk_profile}_{portfolio_type}_portfolio.csv"
        final_portfolio.to_csv(output_filename, index=False, encoding='utf_8_sig')
        print(f"\n已將結果匯出至 {output_filename}")
    else:
        print(f"\n無法為【{risk_profile} - {portfolio_type}】建立投資組合。可能是市場上暫無符合所有規則的標的。")

if __name__ == "__main__":
    main()