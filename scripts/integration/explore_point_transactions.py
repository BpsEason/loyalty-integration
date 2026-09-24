import asyncio
from app.client.base import LaravelClient
from app.client.customer import CustomerClient
from app.client.point import PointClient


async def main():
    client = LaravelClient()
    await client.login()

    customer_client = CustomerClient(client)
    point_client = PointClient(client)

    # 1. 取得會員列表
    print("\n=== 會員列表 ===")
    customers = await customer_client.list(per_page=5)
    print(customers)

    # 取出第一個會員 ID（如果有的話）
    data = customers.get("data", [])
    if not data:
        print("目前沒有會員，請先在 Laravel 建立至少一個會員再重試")
        return

    # 處理分頁格式
    if isinstance(data, dict) and "data" in data:
        items = data["data"]
    else:
        items = data

    if not items:
        print("目前沒有會員資料")
        return

    customer_id = items[0]["id"]
    print(f"\n使用會員 ID: {customer_id}")

    # 2. 測試 Transaction List
    print("\n=== 測試 1: Transaction List - GET /customers/{customer}/point-transactions ===")
    try:
        transactions = await point_client.list_transactions(customer_id, per_page=5)
        print("✓ 交易列表取得成功")
        print(transactions)
        
        # 檢查是否有交易可以用來測試 detail
        transaction_data = transactions.get("data", [])  # Laravel 直接回傳 list，不是巢狀分頁
        if isinstance(transaction_data, list) and len(transaction_data) > 0:
            first_transaction_id = transaction_data[0]["id"]
            print(f"\n找到第一筆交易 ID: {first_transaction_id}")
            
            # 3. 測試 Transaction Detail
            print("\n=== 測試 2: Transaction Detail - GET /customers/{customer}/point-transactions/{id} ===")
            try:
                detail = await point_client.get_transaction(customer_id, first_transaction_id)
                print("✓ 交易詳細資料取得成功")
                print(detail)
            except Exception as e:
                print(f"✗ 取得交易詳細資料失敗: {e}")
        else:
            print("\n沒有找到任何交易，無法測試 Transaction Detail")
            
    except Exception as e:
        print(f"✗ 取得交易列表失敗: {e}")

    # 4. 測試 Expiring Transactions
    print("\n=== 測試 3: Expiring Transactions - GET /customers/{customer}/point-transactions/expiring ===")
    try:
        expiring = await point_client.get_expiring(customer_id, days=30)
        print("✓ 即將到期交易取得成功")
        print(expiring)
    except Exception as e:
        print(f"✗ 取得即將到期交易失敗: {e}")

    # 5. 測試錯誤情境 - 不存在的交易
    print("\n=== 測試 4: 錯誤情境 - 不存在的交易 ID ===")
    try:
        await point_client.get_transaction(customer_id, 999999)  # 使用一個不可能存在的 ID
        print("✗ 不應該成功取得不存在的交易")
    except Exception as e:
        print(f"✓ 正確捕獲錯誤 (預期行為): {e}")

    # 6. 測試錯誤情境 - 未授權（清除 token 後測試）
    print("\n=== 測試 5: 錯誤情境 - 未授權 ===")
    try:
        client.set_token(None)  # 清除 token
        await point_client.list_transactions(customer_id)
        print("✗ 不應該在未授權的情況下取得資料")
    except Exception as e:
        print(f"✓ 正確捕獲未授權錯誤 (預期行為): {e}")


if __name__ == "__main__":
    asyncio.run(main())