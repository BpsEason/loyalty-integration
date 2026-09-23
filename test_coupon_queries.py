import asyncio
from rich.console import Console
from app.client.base import LaravelClient, LaravelAPIError
from app.client.customer import CustomerClient
from app.client.coupon import CouponClient

console = Console()

# 測試結果追蹤
test_results = []

def record_test(name: str, result: str, details: str = ""):
    test_results.append({
        "name": name,
        "result": result,
        "details": details
    })
    status_color = "green" if result == "PASS" else "red" if result == "FAIL" else "yellow"
    console.print(f"[{status_color}]{result:<6}[/{status_color}] {name}{': ' + details if details else ''}")


async def main():
    client = LaravelClient()
    await client.login()

    customer_client = CustomerClient(client)
    coupon_client = CouponClient(client)

    # 取得第一個會員
    customers = await customer_client.list(per_page=1)
    # 處理不同的回傳格式
    if isinstance(customers.get("data"), list):
        items = customers.get("data", [])
    else:
        items = customers.get("data", {}).get("data", [])

    if not items:
        console.print("[red]沒有找到任何會員，無法執行測試[/red]")
        return

    customer_id = items[0]["id"]
    console.print(f"[bold]使用測試會員 ID: {customer_id}[/bold]")

    # 先取得會員的優惠券列表，找到一個真實的 user_coupon_id
    valid_user_coupon_id = None
    try:
        coupons = await coupon_client.list(customer_id, per_page=1)
        data = coupons.get("data", [])
        if isinstance(data, dict):
            coupon_items = data.get("data", [])
        else:
            coupon_items = data
        
        if coupon_items and len(coupon_items) > 0:
            valid_user_coupon_id = coupon_items[0]["id"]
            console.print(f"找到有效的 user_coupon_id: {valid_user_coupon_id}")
    except Exception as e:
        console.print(f"[yellow]無法取得優惠券列表: {e}[/yellow]")

    # ==============================================
    # Test 1 - Coupon Detail (單一優惠券查詢)
    # ==============================================
    console.print("\n=== Test 1 - Coupon Detail ===")
    if valid_user_coupon_id:
        try:
            coupon_detail = await coupon_client.get(customer_id, valid_user_coupon_id)
            if coupon_detail and "data" in coupon_detail:
                record_test("Test 1 - Coupon Detail", "PASS", f"成功取得優惠券 #{valid_user_coupon_id}")
            else:
                record_test("Test 1 - Coupon Detail", "FAIL", "回傳結構異常")
        except Exception as e:
            record_test("Test 1 - Coupon Detail", "FAIL", str(e))
    else:
        record_test("Test 1 - Coupon Detail", "SKIPPED", "沒有可用的優惠券測試資料")

    # ==============================================
    # Test 2 - Redemption History (核銷歷史查詢)
    # ==============================================
    console.print("\n=== Test 2 - Redemption History ===")
    try:
        redemptions = await coupon_client.list_redemptions(customer_id, per_page=15)
        if redemptions:
            data = redemptions.get("data", [])
            if isinstance(data, dict):
                records = data.get("data", [])
            else:
                records = data
            record_test("Test 2 - Redemption History", "PASS", f"成功取得 {len(records)} 筆核銷記錄")
        else:
            record_test("Test 2 - Redemption History", "FAIL", "回傳結構異常")
    except Exception as e:
        record_test("Test 2 - Redemption History", "FAIL", str(e))

    # ==============================================
    # Test 3 - Invalid User Coupon (不存在的優惠券)
    # ==============================================
    console.print("\n=== Test 3 - Invalid User Coupon ===")
    invalid_id = 999999
    try:
        await coupon_client.get(customer_id, invalid_id)
        record_test("Test 3 - Invalid User Coupon", "FAIL", "應該要擲出錯誤但沒有")
    except LaravelAPIError as e:
        if e.status_code in [404, 400]:
            record_test("Test 3 - Invalid User Coupon", "PASS", f"正確擲出 {e.status_code} 錯誤")
        else:
            record_test("Test 3 - Invalid User Coupon", "FAIL", f"收到錯誤但狀態碼不正確: {e.status_code}")
    except Exception as e:
        record_test("Test 3 - Invalid User Coupon", "FAIL", f"擲出非預期錯誤: {str(e)}")

    # ==============================================
    # Test 4 - Unauthorized (未授權測試)
    # ==============================================
    console.print("\n=== Test 4 - Unauthorized ===")
    unauthorized_client = LaravelClient()
    # 不登入，直接呼叫 API
    try:
        await unauthorized_client.get(f"/customers/{customer_id}/coupons/{valid_user_coupon_id or 1}")
        record_test("Test 4 - Unauthorized", "FAIL", "應該要擲出錯誤但沒有")
    except LaravelAPIError as e:
        if "Not authenticated" in str(e.message):
            record_test("Test 4 - Unauthorized", "PASS", "正確偵測未授權狀態")
        elif e.status_code == 401:
            record_test("Test 4 - Unauthorized", "PASS", f"正確收到 Laravel 401 錯誤")
        else:
            record_test("Test 4 - Unauthorized", "FAIL", f"收到錯誤但類型不正確: {e.message} ({e.status_code})")
    except Exception as e:
        record_test("Test 4 - Unauthorized", "FAIL", f"擲出非預期錯誤: {str(e)}")

    # ==============================================
    # Test 5 - Tenant Isolation (租戶隔離測試)
    # ==============================================
    console.print("\n=== Test 5 - Tenant Isolation ===")
    record_test("Test 5 - Tenant Isolation", "SKIPPED", "目前測試資料不足，無法驗證跨租戶隔離")

    # ==============================================
    # 彙整測試結果
    # ==============================================
    console.print("\n" + "="*50)
    console.print("[bold]最終測試結果彙整:[/bold]")
    console.print("="*50)
    for res in test_results:
        status_color = "green" if res["result"] == "PASS" else "red" if res["result"] == "FAIL" else "yellow"
        console.print(f"[{status_color}]{res['result']:<6}[/{status_color}] {res['name']}")
        if res["details"]:
            console.print(f"       {res['details']}")

    # 統計
    pass_count = sum(1 for r in test_results if r["result"] == "PASS")
    fail_count = sum(1 for r in test_results if r["result"] == "FAIL")
    skip_count = sum(1 for r in test_results if r["result"] == "SKIPPED")
    console.print("\n" + "-"*50)
    console.print(f"總計: PASS {pass_count}, FAIL {fail_count}, SKIPPED {skip_count}")


if __name__ == "__main__":
    asyncio.run(main())