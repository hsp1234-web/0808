# -*- coding: utf-8 -*-
import os
try:
    from google.colab import userdata
    # 嘗試獲取金鑰，如果未設定，則回傳一個空字串
    key = userdata.get('GOOGLE_API_KEY')
    if key:
        print(key)
except (ImportError, ModuleNotFoundError):
    # 如果不在 Colab 環境中，或找不到模組，則不執行任何操作
    pass
