# main.py

import config
import data_loader
import screener
import investment_analyzer
import prompts

def main():
    """程式主執行流程"""
    risk_profile, portfolio_type = prompts.get_user_preferences()

    master_df = data_loader.load_and_prepare_data(
        config.LISTED_STOCK_PATH, config.OTC_STOCK_PATH, config.ETF_PATH
    )
    if master_df is None: return

    # *** 修正點：移除 target_count 參數 ***
    screened_pool = screener.screen_assets(master_df, risk_profile)
    
    if screened_pool is not None and not screened_pool.empty:
        print(f"\n--- 【{risk_profile}】最終標的池 (排序後前15名) ---")
        print(screened_pool[['代號', '名稱', '產業別', '篩選層級']].head(15).reset_index(drop=True))
        
        final_portfolio, hhi_value = investment_analyzer.build_portfolio(
            screened_assets=screened_pool,
            portfolio_type=portfolio_type,
            risk_profile=risk_profile,
            master_df=master_df
        )
        
        if final_portfolio is not None:
            print(f"\n--- 【{risk_profile} - {portfolio_type}】投資組合建議 ---")
            print(f"投資組合 HHI 指數: {hhi_value:.4f}")
            print(final_portfolio.to_string(index=False))
            
            output_filename = f"{risk_profile}_{portfolio_type}_portfolio.csv"
            final_portfolio.to_csv(output_filename, index=False, encoding='utf_8_sig')
            print(f"\n已將結果匯出至 {output_filename}")
    else:
        print(f"\n無法為【{risk_profile}】找到任何符合條件的標的。")

if __name__ == "__main__":
    main()