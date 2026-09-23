import asyncio
from app.client.base import LaravelClient
from app.client.customer import CustomerClient
from app.workflows.pos_checkout import POSCheckoutWorkflow


async def main():
    client = LaravelClient()
    await client.login()

    # 取得第一個會員
    customer_client = CustomerClient(client)
    customers = await customer_client.list(per_page=1)
    data = customers.get("data", [])
    if isinstance(data, dict):
        items = data.get("data", [])
    else:
        items = data

    if not items:
        print("沒有會員，無法執行 POS 流程")
        return

    customer_id = items[0]["id"]

    # 執行 POS 結帳流程
    workflow = POSCheckoutWorkflow(client)
    result = await workflow.run(
        customer_id=customer_id,
        earn_amount=100,   # 消費發 100 點
        redeem_amount=30,  # 兌換 30 點
    )

    print("\n回傳結果：")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())