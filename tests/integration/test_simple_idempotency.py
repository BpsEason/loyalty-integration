import asyncio
from app.client.base import LaravelClient
from app.client.customer import CustomerClient
from app.client.point import PointClient
from rich.console import Console

console = Console()


async def main():
    """簡化的冪等性測試，避免重複執行的問題"""
    console.print("[bold magenta]=== 簡化的 Point Transaction 冪等性測試 ===[/bold magenta]")
    
    # 初始化客戶端
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
        console.print("[red]沒有可用的會員，測試無法執行[/red]")
        return
    
    customer_id = items[0]["id"]
    console.print(f"使用會員 ID: {customer_id}")
    
    # 生成唯一的測試用 Idempotency-Key
    unique_idem_key = client.generate_idempotency_key(prefix="simple-test")
    console.print(f"測試用 Idempotency-Key: {unique_idem_key}")
    
    # ==============================================
    # 第一次請求：應該成功建立交易
    # ==============================================
    console.print("\n[green]>>> 第一次請求[/green]")
    try:
        result1 = await point_client.create_transaction(
            customer_id=customer_id,
            transaction_type="earn",
            amount=100,
            description="Simple idempotency test",
            reference="SIMPLE-TEST-001",
            idempotency_key=unique_idem_key,
        )
        console.print("[green]✓ 第一次請求成功，交易已建立[/green]")
        first_id = result1["data"]["id"]
        console.print(f"交易ID: {first_id}")
    except Exception as e:
        console.print(f"[red]第一次請求失敗: {e}[/red]")
        return
    
    # ==============================================
    # 第二次請求：使用相同的 Idempotency-Key
    # ==============================================
    console.print("\n[yellow]>>> 第二次請求（同一個 Idempotency-Key）[/yellow]")
    try:
        result2 = await point_client.create_transaction(
            customer_id=customer_id,
            transaction_type="earn",
            amount=100,
            description="Simple idempotency test",
            reference="SIMPLE-TEST-001",
            idempotency_key=unique_idem_key,
        )
        console.print("[green]第二次請求成功回應[/green]")
        second_id = result2["data"]["id"]
        console.print(f"回傳的交易ID: {second_id}")
        
        if first_id == second_id:
            console.print("[bold green]✓ 冪等性運作完美！兩次請求回傳同一筆交易[/bold green]")
        else:
            console.print("[yellow]⚠ 回傳不同的交易ID，但請求成功[/yellow]")
            
    except Exception as e:
        if "冪等性鍵已被使用" in str(e):
            console.print("[bold green]✓ Laravel 正確偵測到重複的 Idempotency-Key！[/bold green]")
            console.print(f"  錯誤訊息: {e}")
        else:
            console.print(f"[red]其他錯誤: {e}[/red]")
    
    # ==============================================
    # 測試不同的 Idempotency-Key 可以建立新交易
    # ==============================================
    console.print("\n[blue]>>> 測試不同的 Idempotency-Key[/blue]")
    another_key = client.generate_idempotency_key(prefix="another-test")
    try:
        result3 = await point_client.create_transaction(
            customer_id=customer_id,
            transaction_type="earn",
            amount=200,
            description="Another test with different key",
            reference="ANOTHER-TEST-001",
            idempotency_key=another_key,
        )
        console.print("[green]✓ 使用不同的Key成功建立新交易[/green]")
        third_id = result3["data"]["id"]
        console.print(f"新交易ID: {third_id}")
    except Exception as e:
        console.print(f"[red]建立新交易失敗: {e}[/red]")
    
    console.print("\n[bold magenta]=== 測試完成 ===[/bold magenta]")


if __name__ == "__main__":
    asyncio.run(main())