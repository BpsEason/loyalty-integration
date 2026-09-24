import asyncio
from app.client.base import LaravelClient
from app.client.customer import CustomerClient
from app.client.point import PointClient
from rich.console import Console

console = Console()


async def main():
    client = LaravelClient()
    await client.login()

    customer_client = CustomerClient(client)
    point_client = PointClient(client)

    # 取得第一個會員
    customers = await customer_client.list(per_page=1)
    data = customers.get("data", [])
    if isinstance(data, dict):
        items = data.get("data", [])
    else:
        items = data

    if not items:
        console.print("[red]沒有會員，無法測試[/red]")
        return

    customer_id = items[0]["id"]
    console.print(f"[bold]使用會員 ID: {customer_id}[/bold]")

    # 查詢目前餘額
    balance_before = await point_client.get_balance(customer_id)
    current_balance = balance_before["data"]["balance"]
    console.print(f"目前餘額: [cyan]{current_balance}[/cyan]")

    # 產生固定的 Idempotency-Key（模擬網路超時後重送）
    idem_key = client.generate_idempotency_key(prefix="idem-test")
    console.print(f"\nIdempotency-Key: [yellow]{idem_key}[/yellow]")

    # ===== 第一次請求：兌換 50 點 =====
    console.print("\n[bold green]>>> 第一次請求：兌換 50 點[/bold green]")
    try:
        result1 = await point_client.redeem(
            customer_id=customer_id,
            amount=50,
            description="Idempotency 測試 - 第一次",
            reference="ORDER-IDEM-001",
            idempotency_key=idem_key,
        )
        console.print("[green]第一次請求成功[/green]")
        console.print(result1)
    except Exception as e:
        console.print(f"[red]第一次請求失敗: {e}[/red]")
        return

    # 查詢餘額
    balance_after_first = await point_client.get_balance(customer_id)
    balance1 = balance_after_first["data"]["balance"]
    console.print(f"第一次後餘額: [cyan]{balance1}[/cyan]")

    # ===== 第二次請求：用「同一個」Idempotency-Key 重送 =====
    console.print("\n[bold yellow]>>> 第二次請求：用同一個 Idempotency-Key 重送[/bold yellow]")
    try:
        result2 = await point_client.redeem(
            customer_id=customer_id,
            amount=50,
            description="Idempotency 測試 - 重送",
            reference="ORDER-IDEM-001",
            idempotency_key=idem_key,  # 同一個 key
        )
        console.print("[green]第二次請求成功（應為 Replay，不重複扣點）[/green]")
        console.print(result2)
    except Exception as e:
        console.print(f"[red]第二次請求失敗: {e}[/red]")
        # 即使失敗也繼續查餘額，方便觀察

    # 最終餘額
    balance_after_second = await point_client.get_balance(customer_id)
    balance2 = balance_after_second["data"]["balance"]
    console.print(f"\n最終餘額: [cyan]{balance2}[/cyan]")

    # ===== 結果判斷 =====
    console.print("\n" + "=" * 50)
    if balance1 == balance2 and balance1 == current_balance - 50:
        console.print("[bold green]✓ Idempotency 測試通過！[/bold green]")
        console.print("同一個 Key 重送後，點數沒有被重複扣除。")
    else:
        console.print("[bold red]✗ Idempotency 可能有問題[/bold red]")
        console.print(f"原始餘額: {current_balance}")
        console.print(f"第一次後: {balance1}")
        console.print(f"第二次後: {balance2}")


if __name__ == "__main__":
    asyncio.run(main())