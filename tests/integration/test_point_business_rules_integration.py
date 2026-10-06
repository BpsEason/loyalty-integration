"""Integration tests for point-related business rules against live Laravel API"""
from __future__ import annotations

import pytest
from src.infrastructure.clients.base import LaravelClient
from src.infrastructure.clients.point import PointClient
from src.domain.value_objects.point_balance import PointBalance
from src.domain.entities.point_transaction import PointTransaction


@pytest.mark.integration
class TestPointBusinessRulesIntegration:
    """針對點數業務規則的整合測試 - 需要連線到運行中的Laravel API"""

    @pytest.fixture
    async def laravel_client(self):
        """建立實際的Laravel客戶端連線"""
        client = LaravelClient()
        return client

    @pytest.fixture(autouse=True)
    async def setup_authentication(self, laravel_client):
        """自動登入以取得認證 (優先使用配置檔中的認證)"""
        # 不傳參數，讓 login() 自動使用 settings.laravel_email 與 settings.laravel_password
        await laravel_client.login()

    @pytest.fixture
    def point_client(self, laravel_client):
        """建立點數客戶端"""
        return PointClient(laravel_client)

    @pytest.mark.asyncio
    async def test_balance_never_goes_negative(self, point_client):
        """測試：系統永遠不允許餘額變為負數（整合測試驗證API層也 enforcing 此規則）"""
        # 使用一個已知有足夠餘額的測試會員
        test_customer_id = 1  # 請依實際測試環境調整
        
        # 先查詢目前餘額
        balance_response = await point_client.get_balance(test_customer_id)
        current_balance = balance_response["data"]["balance"]
        
        if current_balance <= 0:
            pytest.skip("測試會員餘額不足，無法進行此測試")

        # 嘗試兌換超過餘額的點數，應該失敗
        try:
            await point_client.redeem(
                customer_id=test_customer_id,
                amount=current_balance + 100,
                description="測試：嘗試過度兌換",
                reference="INTEGRATION-TEST-001"
            )
            pytest.fail("應該要擲出錯誤但沒有，系統可能允許負餘額")
        except Exception as e:
            # 驗證API正確拒絕了這個請求
            assert "餘額不足" in str(e) or "Insufficient balance" in str(e)
            
            # 再次查詢餘額，確保餘額沒有被改變
            new_balance_response = await point_client.get_balance(test_customer_id)
            new_balance = new_balance_response["data"]["balance"]
            assert new_balance == current_balance, "餘額不應該被修改"

    @pytest.mark.asyncio
    async def test_concurrent_transactions_maintain_balance_integrity(self, point_client):
        """測試：並發交易維持餘額完整性（測試樂觀鎖或資料庫鎖的有效性）"""
        import asyncio
        
        test_customer_id = 1  # 請依實際測試環境調整
        initial_balance_response = await point_client.get_balance(test_customer_id)
        initial_balance = initial_balance_response["data"]["balance"]
        
        if initial_balance < 500:
            pytest.skip("測試會員餘額不足，無法進行並發測試")

        # 並發執行多次兌換
        redeem_tasks = []
        redeem_amount = 10
        num_concurrent = 20
        
        for i in range(num_concurrent):
            task = point_client.redeem(
                customer_id=test_customer_id,
                amount=redeem_amount,
                description=f"並發測試兌換 #{i}",
                reference=f"CONCURRENT-TEST-{i}-{__import__('time').time()}"
            )
            redeem_tasks.append(task)

        # 執行所有並發請求
        results = await asyncio.gather(*redeem_tasks, return_exceptions=True)
        
        # 計算成功的次數
        successful_redeems = sum(1 for r in results if not isinstance(r, Exception))
        
        # 查詢最終餘額
        final_balance_response = await point_client.get_balance(test_customer_id)
        final_balance = final_balance_response["data"]["balance"]
        
        # 驗證餘額正確性：只有成功的交易才會扣除點數
        expected_balance = initial_balance - (successful_redeems * redeem_amount)
        assert final_balance == expected_balance, f"餘額不一致：預期 {expected_balance}，實際 {final_balance}"

    @pytest.mark.asyncio
    async def test_idempotency_prevents_duplicate_transactions(self, point_client, laravel_client):
        """測試：冪等性金鑰防止重複交易"""
        import uuid
        test_customer_id = 1  # 請依實際測試環境調整
        
        # 使用動態 UUID 生成唯一的冪等性金鑰，避免多次執行測試時與舊資料衝突
        idempotency_key = f"idem-test-{uuid.uuid4().hex}"
        earn_amount = 50
        transaction_reference = f"IDEMPOTENCY-TEST-{uuid.uuid4().hex[:8]}"
        transaction_description = "冪等性測試發點"
        
        # 第一次發點應該成功
        first_response = await point_client.create_transaction(
            customer_id=test_customer_id,
            transaction_type="earn",
            amount=earn_amount,
            description=transaction_description,
            reference=transaction_reference,
            idempotency_key=idempotency_key
        )
        
        assert first_response is not None
        
        # 記錄第一次交易後的餘額
        balance_after_first = await point_client.get_balance(test_customer_id)
        balance1 = balance_after_first["data"]["balance"]
        
        # 使用同一個冪等性金鑰再次發送完全相同的請求
        # 標準冪等性應該會直接重放 (Replay) 第一次的成功結果，不會重複新增點數
        second_response = await point_client.create_transaction(
            customer_id=test_customer_id,
            transaction_type="earn",
            amount=earn_amount,
            description=transaction_description,  # 保持完全相同的描述
            reference=transaction_reference,     # 保持完全相同的參考編號
            idempotency_key=idempotency_key      # 使用相同的冪等性金鑰
        )
        
        assert second_response is not None
        
        # 再次查詢餘額，確保第二次請求沒有重複新增點數
        balance_after_second = await point_client.get_balance(test_customer_id)
        balance2 = balance_after_second["data"]["balance"]
        
        # 關鍵驗證：第二次請求後，點數餘額「絕不能再增加」
        assert balance2 == balance1, "冪等性失效：重複請求導致點數被重複發放！"