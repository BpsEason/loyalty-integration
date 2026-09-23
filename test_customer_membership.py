import asyncio
from app.client.base import LaravelClient
from app.client.customer import CustomerClient


async def main():
    client = LaravelClient()
    await client.login()

    customer_client = CustomerClient(client)

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

    # 2. 查詢會員等級資訊
    print("\n=== 會員等級資訊 ===")
    membership = await customer_client.get_membership(customer_id)
    print(membership)


if __name__ == "__main__":
    asyncio.run(main())