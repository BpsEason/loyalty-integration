from __future__ import annotations

from rich.console import Console
from rich.table import Table

from app.client.base import LaravelClient
from app.client.customer import CustomerClient
from app.client.point import PointClient

console = Console()


class POSCheckoutWorkflow:
    """
    模擬 POS 結帳流程：識別會員 → 查餘額 → 消費發點 → 兌換點數 → 再查餘額。

    Workflow 層級目前不提供 End-to-End Idempotency。每個 mutation operation
    都使用自己的 Idempotency-Key，由 Laravel 負責該 mutation 的冪等處理。
    因此 Workflow 重試時，各步驟可能取得新的 key；若 Earn 已成功而 Redeem
    失敗，重新執行可能再次執行 Earn。本 Workflow 不自行 rollback 或 compensation，
    Workflow failure 也不代表先前的 mutation 沒有在 Laravel 生效。

    若未來需要 End-to-End Idempotency，應由呼叫端提供穩定的 Workflow key，
    或由 Laravel 提供 Atomic Composite Checkout API。
    """

    def __init__(self, client: LaravelClient):
        self.client = client
        self.customer_client = CustomerClient(client)
        self.point_client = PointClient(client)

    async def run(
        self,
        customer_id: int,
        earn_amount: int = 100,
        redeem_amount: int = 30,
        order_reference: str | None = None,
    ) -> dict:
        order_reference = order_reference or self.client.generate_idempotency_key(prefix="pos-order")

        console.print("\n[bold blue]========== POS 結帳流程開始 ==========[/bold blue]")
        console.print(f"會員 ID      : {customer_id}")
        console.print(f"訂單參考號  : {order_reference}")
        console.print(f"本次發點    : {earn_amount}")
        console.print(f"本次兌換    : {redeem_amount}")

        # 1. 查詢會員
        console.print("\n[bold]1. 查詢會員資訊[/bold]")
        customer = await self.customer_client.get(customer_id)
        customer_data = customer["data"]
        console.print(f"   姓名: {customer_data.get('name')}")
        console.print(f"   Email: {customer_data.get('email')}")

        # 2. 查詢目前餘額
        console.print("\n[bold]2. 查詢目前點數餘額[/bold]")
        balance_before = await self.point_client.get_balance(customer_id)
        before = balance_before["data"]["balance"]
        console.print(f"   目前餘額: [cyan]{before}[/cyan]")

        # 3. 消費發點（earn）
        console.print("\n[bold]3. 消費發點 (earn)[/bold]")
        earn_key = self.client.generate_idempotency_key(prefix="earn")
        earn_result = await self.point_client.create_transaction(
            customer_id=customer_id,
            transaction_type="earn",
            amount=earn_amount,
            description=f"POS 消費發點 - {order_reference}",
            reference=order_reference,
            idempotency_key=earn_key,
        )
        console.print(f"   [green]發點成功[/green] +{earn_amount}")
        console.print(f"   交易 ID: {earn_result['data']['id']}")

        # 4. 兌換點數（redeem）
        console.print("\n[bold]4. 兌換點數 (redeem)[/bold]")
        redeem_key = self.client.generate_idempotency_key(prefix="redeem")
        redeem_result = await self.point_client.redeem(
            customer_id=customer_id,
            amount=redeem_amount,
            description=f"POS 兌換 - {order_reference}",
            reference=order_reference,
            idempotency_key=redeem_key,
        )
        console.print(f"   [green]兌換成功[/green] -{redeem_amount}")
        console.print(f"   交易 ID: {redeem_result['data']['id']}")

        # 5. 再次查詢餘額
        console.print("\n[bold]5. 查詢最終餘額[/bold]")
        balance_after = await self.point_client.get_balance(customer_id)
        after = balance_after["data"]["balance"]
        console.print(f"   最終餘額: [cyan]{after}[/cyan]")

        # 結果摘要
        expected = before + earn_amount - redeem_amount
        console.print("\n[bold blue]========== 結帳結果摘要 ==========[/bold blue]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("項目")
        table.add_column("數值", justify="right")
        table.add_row("結帳前餘額", str(before))
        table.add_row(f"發點 (+{earn_amount})", f"+{earn_amount}")
        table.add_row(f"兌換 (-{redeem_amount})", f"-{redeem_amount}")
        table.add_row("預期最終餘額", str(expected))
        table.add_row("實際最終餘額", str(after))
        console.print(table)

        if after == expected:
            console.print("\n[bold green]✓ POS 結帳流程成功，餘額計算正確[/bold green]")
        else:
            console.print("\n[bold red]✗ 餘額與預期不符，請檢查[/bold red]")

        return {
            "customer_id": customer_id,
            "order_reference": order_reference,
            "balance_before": before,
            "earn_amount": earn_amount,
            "redeem_amount": redeem_amount,
            "balance_after": after,
            "expected_balance": expected,
            "success": after == expected,
        }