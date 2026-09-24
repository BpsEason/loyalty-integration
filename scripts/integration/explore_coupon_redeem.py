import asyncio
from rich.console import Console
from app.client.base import LaravelClient
from app.client.customer import CustomerClient
from app.client.coupon import CouponClient

console = Console()


async def main():
    client = LaravelClient()
    await client.login()

    customer_client = CustomerClient(client)
    coupon_client = CouponClient(client)

    customer_id = 1
    user_coupon_id = 2  # 剛才查到狀態為 available 的那張

    console.print(f"[bold]使用會員 ID: {customer_id}[/bold]")
    console.print(f"[bold]核銷優惠券 ID: {user_coupon_id}[/bold]")

    # 1. 核銷前再確認一次狀態
    console.print("\n=== 核銷前優惠券狀態 ===")
    before = await coupon_client.get(customer_id, user_coupon_id)
    console.print(before)

    # 2. 執行核銷
    console.print("\n=== 執行核銷 ===")
    redeem_key = client.generate_idempotency_key(prefix="coupon-redeem")
    try:
        result = await coupon_client.redeem(
            customer_id=customer_id,
            user_coupon_id=user_coupon_id,
            reference="POS-REDEEM-001",
            order_reference="ORDER-20260923-001",
            order_amount=1000,
            idempotency_key=redeem_key,
        )
        console.print("[green]核銷成功[/green]")
        console.print(result)
    except Exception as e:
        console.print(f"[red]核銷失敗: {e}[/red]")
        return

    # 3. 核銷後再查一次
    console.print("\n=== 核銷後優惠券狀態 ===")
    after = await coupon_client.get(customer_id, user_coupon_id)
    console.print(after)

    # 4. 查詢核銷紀錄
    console.print("\n=== 核銷紀錄 ===")
    redemptions = await coupon_client.list_redemptions(customer_id)
    console.print(redemptions)


if __name__ == "__main__":
    asyncio.run(main())