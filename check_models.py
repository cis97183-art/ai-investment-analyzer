import google.generativeai as genai
import os

# --- 請在這裡貼上你的 API 金鑰 ---
# 將 "..." 替換成你從 Google Cloud 專案中取得的金鑰
YOUR_API_KEY = "AIzaSyDV2-1uRb2yHJ5vAy_dc65NbuIZNbTHQmA"

try:
    genai.configure(api_key=YOUR_API_KEY)
    print("🚀 正在查詢您的 API 金鑰可使用的模型...\n")
    
    # Debugging: Print all models
    print("🔍 所有模型:")
    for m in genai.list_models():
        print(m)
    
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)
    
    if available_models:
        print("🎉 查詢成功！您的金鑰可以使用以下模型：")
        for model_name in available_models:
            print(f"- {model_name}")
    else:
        print("❌ 找不到任何支援 'generateContent' 的可用模型。")
except Exception as e:
    print(f"🚫 發生錯誤: {e}")

