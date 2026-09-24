import asyncio
from rich.console import Console
from app.client.base import LaravelClient
from app.client.customer import CustomerClient
from app.client.point import PointClient
from app.client.coupon import CouponClient

console = Console()


async def main():
    client = LaravelClient()
    await client.login()

    customer_client = CustomerClient(client)
    point_client = PointClient(client)
    coupon_client = CouponClient(client)

    customer_id = 1

    # 1. 查目前餘額
    console.print("[bold]=== 目前點數餘額 ===[/bold]")
    balance = await point_client.get_balance(customer_id)
    current_balance = balance["data"]["balance"]
    console.print(f"餘額: {current_balance}")

    # 2. 查目前可用優惠券
    console.print("\n[bold]=== 目前可用優惠券 ===[/bold]")
    coupons = await coupon_client.list(customer_id)
    available_coupons = []
    data = coupons.get("data", [])
    if isinstance(data, list):
        available_coupons = [c for c in data if c.get("status") == "available"]
    console.print(f"可用優惠券數量: {len(available_coupons)}")
    for c in available_coupons:
        console.print(f"  - ID: {c['id']}, Code: {c.get('template', {}).get('code')}")

    # 3. 執行混合支付
    console.print("\n[bold]=== 執行混合支付 ===[/bold]")
    mixed_key = client.generate_idempotency_key(prefix="mixed")

    # 如果有可用優惠券就帶上，沒有就只扣點數
    user_coupon_id = available_coupons[0]["id"] if available_coupons else None
    points_to_use = 100  # 先扣 100 點測試

    try:
        result = await coupon_client.mixed_payment(
            customer_id=customer_id,
            reference="MIXED-PAY-001",
            order_amount=1000,          # 訂單金額 1000
            user_coupon_id=user_coupon_id,
            points_amount=points_to_use,
            order_reference="ORDER-MIXED-001",
            idempotency_key=mixed_key,
        )
        console.print("[green]混合支付成功[/green]")
        console.print(result)
    except Exception as e:
        console.print(f"[red]混合支付失敗: {e}[/red]")
        return

    # 4. 再查餘額
    console.print("\n[bold]=== 混合支付後餘額 ===[/bold]")
    balance_after = await point_client.get_balance(customer_id)
    console.print(f"餘額: {balance_after['data']['balance']}")


if __name__ == "__main__":
    asyncio.run(main())