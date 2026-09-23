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

    # 處理分頁格式（可能是 list 或 dict）
    if isinstance(data, dict) and "data" in data:
        items = data["data"]
    else:
        items = data

    if not items:
        print("目前沒有會員資料")
        return

    customer_id = items[0]["id"]
    print(f"\n使用會員 ID: {customer_id}")

    # 2. 查詢點數餘額
    print("\n=== 點數餘額 ===")
    balance = await point_client.get_balance(customer_id)
    print(balance)

    # 3. 查詢最近交易
    print("\n=== 最近交易 ===")
    transactions = await point_client.list_transactions(customer_id, per_page=5)
    print(transactions)


if __name__ == "__main__":
    asyncio.run(main())