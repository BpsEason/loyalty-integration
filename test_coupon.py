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

    # 取得第一個會員
    customers = await customer_client.list(per_page=1)
    data = customers.get("data", [])
    if isinstance(data, dict):
        items = data.get("data", [])
    else:
        items = data

    if not items:
        console.print("[red]沒有會員[/red]")
        return

    customer_id = items[0]["id"]
    console.print(f"[bold]使用會員 ID: {customer_id}[/bold]")

    # 1. 查詢目前持有的優惠券
    console.print("\n=== 目前持有的優惠券 ===")
    coupons = await coupon_client.list(customer_id)
    console.print(coupons)

    # 2. 嘗試領取一張優惠券（請改成你系統裡真實存在的 code）
    # 如果還沒有可用的優惠券 code，這步會失敗，屬正常現象
    console.print("\n=== 嘗試領取優惠券 ===")
    test_code = "SUMMER2024"  # ← 請改成你實際有的優惠券 code
    try:
        claim_key = client.generate_idempotency_key(prefix="claim")
        claim_result = await coupon_client.claim(
            customer_id=customer_id,
            code=test_code,
            idempotency_key=claim_key,
        )
        console.print("[green]領取成功[/green]")
        console.print(claim_result)
    except Exception as e:
        console.print(f"[yellow]領取失敗（可能是 code 不存在或已領過）: {e}[/yellow]")

    # 3. 再次查詢持有的優惠券
    console.print("\n=== 領取後的優惠券列表 ===")
    coupons_after = await coupon_client.list(customer_id)
    console.print(coupons_after)


if __name__ == "__main__":
    asyncio.run(main())