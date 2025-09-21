import pandas as pd
import data_loader
import screener
import config

def inspect_stock_data():
    """
    執行資料載入與基礎排雷，並檢查最終個股資料的健康狀況。
    """
    print("--- 開始執行資料健康檢查 ---")
    
    try:
        # 1. 載入並準備資料
        master_df = data_loader.load_and_prepare_data(
            config.LISTED_STOCK_PATH,
            config.OTC_STOCK_PATH,
            config.ETF_PATH
        )
        
        # 2. 執行基礎排雷
        df_screened = screener.apply_universal_exclusion_rules(master_df)
        
        # 3. 提取出用於篩選的個股資料
        df_stocks = df_screened[df_screened['資產類別'].isin(['上市', '上櫃'])].copy()
        
        if df_stocks.empty:
            print("\n錯誤：排雷後沒有剩下任何個股資料可供分析！")
            return

        print(f"\n--- 個股資料健康報告 (共 {len(df_stocks)} 筆) ---")
        
        # 4. 定義所有篩選會用到的關鍵欄位
        key_cols = [
            '名稱', '代碼', '產業別',
            '一年(σ年)', '一年(β)', '現金股利連配次數', 
            '最新近4Q每股自由金流(元)', '近3年平均ROE(%)', 
            '累月營收年增(%)', '最新單季ROE(%)'
        ]
        
        # 篩選出存在的欄位
        existing_key_cols = [col for col in key_cols if col in df_stocks.columns]
        
        # 5. 印出關鍵欄位的 .info() 摘要
        print("\n[1] 關鍵欄位資料型態 (Dtype) 及非空值數量 (Non-Null Count):")
        df_stocks[existing_key_cols].info()
        
        # 6. 印出前 5 筆資料的實際內容，以便肉眼檢查
        print("\n[2] 關鍵欄位資料預覽 (前 5 筆):")
        print(df_stocks[existing_key_cols].head())

    except Exception as e:
        print(f"\n執行檢查時發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    inspect_stock_data()