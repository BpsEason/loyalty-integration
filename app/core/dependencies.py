# app/core/dependencies.py
from app.client.base import LaravelClient

# 全域 Client（服務啟動時登入一次，之後共用）
# 這個實例將在整個應用程式中共享
laravel_client = LaravelClient()