import pandas as pd
from FinMind.data import DataLoader
from config import FINMIND_API_TOKEN

def run_api_test():
    """
    執行一個簡單的 FinMind API 連線與數據抓取測試。
    """
    if not FINMIND_API_TOKEN or FINMIND_API_TOKEN == "在此貼上您從 FinMind 網站獲取的 API Token":
        print("錯誤：請在 config.py 中設定您的 FINMIND_API_TOKEN。")
        return

    print("正在初始化 FinMind DataLoader...")
    api = DataLoader()
    api.login_by_token(api_token=FINMIND_API_TOKEN)
    print("API 登入成功！")

    # 1. 測試獲取台灣股市股票列表
    print("\n正在測試獲取台股列表...")
    try:
        stock_list = api.taiwan_stock_info()
        if not stock_list.empty:
            print(f"成功獲取 {len(stock_list)} 筆股票資訊。")
            print("前五筆資料：")
            print(stock_list.head())
        else:
            print("錯誤：未能獲取股票列表，回傳為空。")
            return
    except Exception as e:
        print(f"獲取股票列表時發生錯誤: {e}")
        return


    # 2. 測試獲取單一股票的交易數據
    stock_id = "2330"
    print(f"\n正在測試獲取 {stock_id} (台積電) 的股價資訊...")
    try:
        df = api.taiwan_stock_daily(
            stock_id=stock_id,
            start_date='2025-09-01',
            end_date='2025-09-17'
        )
        if not df.empty:
            print(f"成功獲取 {stock_id} 的 {len(df)} 天交易資料。")
            print(df.tail())
        else:
            print(f"錯誤：未能獲取 {stock_id} 的交易資料，回傳為空。")
    except Exception as e:
        print(f"獲取 {stock_id} 的交易資料時發生錯誤: {e}")

if __name__ == "__main__":
    run_api_test()
