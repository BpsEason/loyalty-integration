import asyncio
from app.client.base import LaravelClient

async def main():
    """完整測試 Auth 生命週期：login → me → refresh → logout"""
    client = LaravelClient()
    
    # 1. 登入
    await client.login()
    print("✅ Login successful!")
    print("Original Token:", client._token[:40] + "...")
    
    # 2. 取得目前使用者資訊
    me_result = await client.me()
    print("\n✅ Me() successful! User:", me_result.get("data", {}).get("email", "unknown"))
    
    # 3. 刷新 Token
    refresh_result = await client.refresh()
    print("\n✅ Refresh successful!")
    print("New Token:", client._token[:40] + "...")
    
    # 4. 使用新 Token 再次取得使用者資訊
    me_result2 = await client.me()
    print("\n✅ Me() with new token successful! User:", me_result2.get("data", {}).get("email", "unknown"))
    
    # 5. 登出
    logout_result = await client.logout()
    print("\n✅ Logout successful! Token cleared.")
    print("Current token is None?", client._token is None)

if __name__ == "__main__":
    asyncio.run(main())