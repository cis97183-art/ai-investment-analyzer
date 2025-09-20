# main.py (修正版)

import config
import data_loader
import screener
import investment_analyzer
import prompts

def main():
    """程式主執行流程"""
    # 1. 獲取使用者設定 (現在會回傳三個值)
    risk_profile, portfolio_type = prompts.get_user_preferences()

    # 2. 載入並準備所有資料
    master_df = data_loader.load_and_prepare_data(
        listed_path=config.LISTED_STOCK_PATH,
        otc_path=config.OTC_STOCK_PATH,
        etf_path=config.ETF_PATH
    )

    if master_df is None:
        return

    # 3. 根據風險偏好篩選標的
    screened_pool = screener.screen_assets(
        data_df=master_df, 
        risk_profile=risk_profile, 
        target_count=config.TARGET_ASSET_COUNT
    )

    # 4. 根據標的池與組合類型建立投資組合
    if screened_pool is not None and not screened_pool.empty:
        print(f"\n--- 【{risk_profile}】最終標的池 (排序後前15名) ---")
        print(screened_pool[['代號', '名稱', '產業別', '市值(億)']].head(15).reset_index(drop=True))
        
        # *** 修正點：傳入新的 optimization_strategy 參數 ***
        final_portfolio = investment_analyzer.build_portfolio(
        screened_assets=screened_pool, 
        portfolio_type=portfolio_type,
        risk_profile=risk_profile, # <--- 傳入 risk_profile
        master_df=master_df
        )
        
        if final_portfolio is not None:
            print(f"\n--- 【{risk_profile} - {portfolio_type} ({optimization_strategy})】投資組合建議 ---")
            print(final_portfolio.to_string(index=False))
            
            output_filename = f"{risk_profile}_{portfolio_type}_{optimization_strategy}_portfolio.csv"
            try:
                final_portfolio.to_csv(output_filename, index=False, encoding='utf_8_sig')
                print(f"\n已將結果匯出至 {output_filename}")
            except Exception as e:
                print(f"\n匯出檔案失敗: {e}")

    else:
        print(f"\n無法為【{risk_profile}】找到任何符合條件的標的。")

if __name__ == "__main__":
    main()