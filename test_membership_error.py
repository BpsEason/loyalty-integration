import asyncio
from app.client.base import LaravelClient, LaravelAPIError
from app.client.customer import CustomerClient


async def main():
    client = LaravelClient()
    await client.login()

    customer_client = CustomerClient(client)

    # 測試查詢不存在的會員ID
    print("\n=== 測試錯誤處理 - 查詢不存在的會員ID ===")
    try:
        await customer_client.get_membership(99999)
    except LaravelAPIError as e:
        print(f"正確捕捉到 LaravelAPIError: {e.message}")
        print(f"HTTP狀態碼: {e.status_code}")
        print(f"Payload: {e.payload}")


if __name__ == "__main__":
    asyncio.run(main())