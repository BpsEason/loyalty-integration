import asyncio
import uuid
import pytest

from app.client.base import LaravelAPIError, LaravelClient
from app.client.point import PointClient


pytestmark = pytest.mark.integration


async def semaphore_limited_request(
    semaphore: asyncio.Semaphore,
    point_client: PointClient,
    customer_id: int,
    transaction_type: str,
    amount: int,
) -> dict:
    """使用 Semaphore 限制併發數的單一請求函數"""
    async with semaphore:
        idempotency_key = f"concurrency-{transaction_type}-{uuid.uuid4()}"
        try:
            result = await point_client.create_transaction(
                customer_id=customer_id,
                transaction_type=transaction_type,
                amount=amount,
                description=f"Concurrency test {transaction_type}",
                reference=idempotency_key,
                idempotency_key=idempotency_key,
            )
            return {"success": True, "data": result["data"]}
        except LaravelAPIError as e:
            return {"success": False, "error": str(e), "status_code": e.status_code}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "total_requests, concurrency",
    [
        (10, 10),
        (50, 20),
        (100, 50),
    ]
)
async def test_point_earn_concurrency(
    authenticated_client: LaravelClient,
    customer_id: int,
    total_requests: int,
    concurrency: int,
):
    """測試 earn 操作的高併發一致性"""
    test_customer_id = customer_id
    
    # 建立共享的 HTTP client，使用連接池來控制併發連線數，避免每次請求都建立新 TCP 連線
    import httpx
    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
    )
    
    # 使用 async with 管理共享 client 的生命週期，所有請求共用同一個連接池
    async with LaravelClient(limits=limits) as shared_client:
        # 複製原 authenticated_client 的認證資訊
        shared_client.set_token(authenticated_client._token, authenticated_client._token_type)
        if authenticated_client._tenant_id:
            shared_client.set_tenant_id(authenticated_client._tenant_id)
            
        point_client = PointClient(shared_client)

        # 測試前取得初始狀態 - 依照實際 API contract
        initial_balance_resp = await point_client.get_balance(test_customer_id)
        initial_balance = initial_balance_resp["data"]["balance"]
        initial_transactions_resp = await point_client.list_transactions(test_customer_id, per_page=1000)
        initial_transactions = initial_transactions_resp["data"]
        initial_transaction_count = len(initial_transactions)

        # 建立 Semaphore 限制最大併發數
        semaphore = asyncio.Semaphore(concurrency)
        
        # 產生所有請求任務
        tasks = [
            semaphore_limited_request(
                semaphore,
                point_client,
                test_customer_id,
                "earn",
                10
            )
            for _ in range(total_requests)
        ]

        # 執行所有請求
        results = await asyncio.gather(*tasks)

        # 統計成功數
        success_count = sum(1 for r in results if r["success"])
        successful_transactions = [r["data"] for r in results if r["success"]]
        failed_count = len(results) - success_count
        failed_requests = [r for r in results if not r["success"]]

        # 測試後取得最終狀態 - 依照實際 API contract
        final_balance_resp = await point_client.get_balance(test_customer_id)
        final_balance = final_balance_resp["data"]["balance"]
        final_transactions_resp = await point_client.list_transactions(test_customer_id, per_page=1000)
        final_transactions = final_transactions_resp["data"]
        final_transaction_count = len(final_transactions)

        # 驗證交易ID不重複
        transaction_ids = [t["id"] for t in successful_transactions]
        assert len(transaction_ids) == len(set(transaction_ids)), "交易ID重複"

        # 驗證資料庫中交易ID不重複
        db_transaction_ids = [t["id"] for t in final_transactions]
        assert len(db_transaction_ids) == len(set(db_transaction_ids)), "資料庫中交易ID重複"

        # 驗證餘額正確：initial + 成功數 * 10
        assert final_balance == initial_balance + success_count * 10, f"餘額不正確：期望 {initial_balance + success_count * 10}, 實際 {final_balance}"
        
        # 驗證交易數量正確
        assert final_transaction_count == initial_transaction_count + success_count, f"交易數量不正確：期望 {initial_transaction_count + success_count}, 實際 {final_transaction_count}"
        
        # 驗證餘額不為負數
        assert final_balance >= 0, "餘額不可為負數"

        # 輸出測試結果
        print(f"\n[Earn Test] total_requests={total_requests}, concurrency={concurrency}")
        print(f"成功: {success_count}, 失敗: {failed_count}")
        if failed_requests:
            print(f"失敗請求詳情(前5筆): {[{k: r[k] for k in ['error', 'status_code']} for r in failed_requests[:5]]}")
        print(f"初始餘額: {initial_balance}, 最終餘額: {final_balance}")
        print(f"初始交易數: {initial_transaction_count}, 最終交易數: {final_transaction_count}")


@pytest.mark.asyncio
async def test_point_redeem_concurrency(
    authenticated_client: LaravelClient,
    customer_id: int,
):
    """測試 redeem 操作的高併發一致性，防止超額扣點"""
    test_customer_id = customer_id
    
    # 設定 redeem 測試參數，確保不超過當前餘額
    redeem_amount = 10
    total_requests = 200
    concurrency = 50
    
    # 建立共享的 HTTP client，使用連接池來控制併發連線數，避免每次請求都建立新 TCP 連線
    import httpx
    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
    )
    
    # 使用 async with 管理共享 client 的生命週期，所有請求共用同一個連接池
    async with LaravelClient(limits=limits) as shared_client:
        # 複製原 authenticated_client 的認證資訊
        shared_client.set_token(authenticated_client._token, authenticated_client._token_type)
        if authenticated_client._tenant_id:
            shared_client.set_tenant_id(authenticated_client._tenant_id)
            
        point_client = PointClient(shared_client)

        # 測試前取得初始狀態，使用客戶現有餘額，避免永久新增點數造成污染
        initial_balance_resp = await point_client.get_balance(test_customer_id)
        initial_balance = initial_balance_resp["data"]["balance"]
        
        # 確保有足夠的餘額進行測試，如果不夠則跳過
        max_possible_success = initial_balance // redeem_amount
        if max_possible_success < 10:
            pytest.skip(f"測試客戶餘額不足，需要至少 {10 * redeem_amount} 點，目前只有 {initial_balance} 點")

        initial_transactions_resp = await point_client.list_transactions(test_customer_id, per_page=1000)
        initial_transactions = initial_transactions_resp["data"]
        initial_transaction_count = len(initial_transactions)

        # 開始 redeem 測試
        semaphore = asyncio.Semaphore(concurrency)
        
        tasks = [
            semaphore_limited_request(
                semaphore,
                point_client,
                test_customer_id,
                "redeem",
                redeem_amount
            )
            for _ in range(total_requests)
        ]

        results = await asyncio.gather(*tasks)

        # 統計成功數
        success_count = sum(1 for r in results if r["success"])
        successful_transactions = [r["data"] for r in results if r["success"]]
        failed_count = len(results) - success_count
        failed_requests = [r for r in results if not r["success"]]

        # 測試後取得最終狀態 - 依照實際 API contract
        final_balance_resp = await point_client.get_balance(test_customer_id)
        final_balance = final_balance_resp["data"]["balance"]
        final_transactions_resp = await point_client.list_transactions(test_customer_id, per_page=1000)
        final_transactions = final_transactions_resp["data"]
        final_transaction_count = len(final_transactions)

        # 核心驗證：確保不會超額扣點
        assert success_count * redeem_amount <= initial_balance, f"超額扣點：成功扣減 {success_count * redeem_amount} 點，超過初始餘額 {initial_balance} 點"
        assert final_balance == initial_balance - success_count * redeem_amount, f"餘額不正確：期望 {initial_balance - success_count * 10}, 實際 {final_balance}"
        assert final_balance >= 0, "餘額不可為負數，發生超額扣點"
        
        # 驗證交易數量正確
        assert final_transaction_count == initial_transaction_count + success_count, f"交易數量不正確：期望 {initial_transaction_count + success_count}, 實際 {final_transaction_count}"
        
        # 驗證交易ID不重複
        transaction_ids = [t["id"] for t in successful_transactions]
        assert len(transaction_ids) == len(set(transaction_ids)), "交易ID重複"

        # 輸出測試結果
        print(f"\n[Redeem Test] total_requests={total_requests}, concurrency={concurrency}")
        print(f"成功: {success_count}, 失敗: {failed_count}")
        if failed_requests:
            print(f"失敗請求詳情(前5筆): {[{k: r[k] for k in ['error', 'status_code']} for r in failed_requests[:5]]}")
        print(f"初始餘額: {initial_balance}, 最終餘額: {final_balance}")
        print(f"初始交易數: {initial_transaction_count}, 最終交易數: {final_transaction_count}")
        print(f"最大可能成功數: {max_possible_success}, 實際成功數: {success_count}")