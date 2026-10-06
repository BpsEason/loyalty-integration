"""Unit tests for POSCheckoutWorkflow - core business workflow logic"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.application.use_cases.workflows.pos_checkout import POSCheckoutWorkflow
from src.domain.exceptions.domain_errors import WorkflowExecutionError


class TestPOSCheckoutWorkflowUnit:
    """POS結帳工作流程的單元測試 - 使用mock隔離外部API依賴"""

    @pytest.fixture
    def mock_laravel_client(self):
        """建立模擬的Laravel客戶端，包含async方法的mock"""
        client = MagicMock()
        client.generate_idempotency_key.return_value = "test-idempotency-key-123"
        # 模擬base client的async方法，讓CustomerClient和PointClient可以await
        client.get = AsyncMock()
        client.post = AsyncMock()
        # 建立customer_client和point_client的mock
        client.customer_client = MagicMock()
        client.customer_client.get = AsyncMock()
        client.point_client = MagicMock()
        client.point_client.get_balance = AsyncMock()
        client.point_client.create_transaction = AsyncMock()
        client.point_client.redeem = AsyncMock()
        return client

    @pytest.fixture
    def workflow(self, mock_laravel_client):
        """建立POS結帳工作流程實例，並覆蓋內部的客戶端以使用mock"""
        workflow = POSCheckoutWorkflow(mock_laravel_client)
        # 覆蓋Workflow自動建立的客戶端，使用我們的mock客戶端
        workflow.customer_client = mock_laravel_client.customer_client
        workflow.point_client = mock_laravel_client.point_client
        return workflow

    @pytest.mark.asyncio
    async def test_successful_checkout_flow(self, workflow, mock_laravel_client):
        """測試正常的結帳流程成功執行"""
        # 模擬會員查詢 (使用customer_client.get)
        mock_laravel_client.customer_client.get.return_value = {
            "data": {"name": "測試會員", "email": "test@example.com"}
        }
        # 模擬初始餘額查詢和最終餘額查詢
        mock_laravel_client.point_client.get_balance.side_effect = [
            {"data": {"balance": 100}},                               # 第一次get_balance: 查詢初始餘額
            {"data": {"balance": 170}}                                # 第二次get_balance: 查詢最終餘額 (100 + 100 - 30 = 170)
        ]
        
        # 模擬交易創建請求
        mock_laravel_client.point_client.create_transaction.return_value = {
            "data": {"id": "earn-transaction-001"}                    # 發點交易
        }
        mock_laravel_client.point_client.redeem.return_value = {
            "data": {"id": "redeem-transaction-001"}                  # 兌換交易
        }

        # 執行工作流程
        result = await workflow.run(
            customer_id=123,
            earn_amount=100,
            redeem_amount=30,
            order_reference="test-order-001"
        )

        # 驗證結果
        assert result["success"] is True
        assert result["balance_before"] == 100
        assert result["earn_amount"] == 100
        assert result["redeem_amount"] == 30
        assert result["balance_after"] == 170
        assert result["expected_balance"] == 170
        assert result["customer_id"] == 123
        assert result["order_reference"] == "test-order-001"

    @pytest.mark.asyncio
    async def test_balance_mismatch_warning(self, workflow, mock_laravel_client):
        """測試當實際餘額與預期不符時的警告行為"""
        # 模擬會員查詢
        mock_laravel_client.customer_client.get = AsyncMock(return_value={
            "data": {"name": "測試會員", "email": "test@example.com"}
        })
        
        # 模擬初始餘額與最終餘額（使用side_effect確保第一次拿到100，第二次拿到160）
        mock_laravel_client.point_client.get_balance = AsyncMock(side_effect=[
            {"data": {"balance": 100}},    # 第一次查詢：初始餘額
            {"data": {"balance": 160}}     # 第二次查詢：最終餘額（不符預期）
        ])
        
        # 模擬交易成功
        mock_laravel_client.point_client.create_transaction = AsyncMock(return_value={
            "data": {"id": "earn-transaction-001"}
        })
        mock_laravel_client.point_client.redeem = AsyncMock(return_value={
            "data": {"id": "redeem-transaction-001"}
        })

        # 執行工作流程
        result = await workflow.run(customer_id=123, earn_amount=100, redeem_amount=30)

        # 驗證結果標示為不成功
        assert result["success"] is False
        assert result["balance_after"] == 160
        assert result["expected_balance"] == 170  # 初始100 + 發點100 - 兌換30 = 170

    @pytest.mark.asyncio
    async def test_insufficient_balance_raises_error(self, workflow, mock_laravel_client):
        """測試餘額不足時會拋出工作流程執行錯誤"""
        # 模擬會員查詢
        mock_laravel_client.customer_client.get = AsyncMock(return_value={
            "data": {"name": "測試會員", "email": "test@example.com"}
        })
        
        # 初始餘額只有50，但要兌換100點
        mock_laravel_client.point_client.get_balance = AsyncMock(return_value={
            "data": {"balance": 50}
        })

        # 執行工作流程應該失敗
        with pytest.raises(WorkflowExecutionError) as exc_info:
            await workflow.run(customer_id=123, earn_amount=0, redeem_amount=100)
        
        assert "POS結帳流程失敗" in str(exc_info.value)
        assert "點數餘額不足" in str(exc_info.value.__cause__)

    @pytest.mark.asyncio
    async def test_api_failure_propagates_correctly(self, workflow, mock_laravel_client):
        """測試當API呼叫失敗時，錯誤會正確傳播並包裝"""
        # 模擬會員查詢失敗
        mock_laravel_client.customer_client.get = AsyncMock(side_effect=Exception("API連線失敗"))

        # 執行工作流程應該失敗並包裝錯誤
        with pytest.raises(WorkflowExecutionError) as exc_info:
            await workflow.run(customer_id=999)
        
        assert "POS結帳流程失敗" in str(exc_info.value)
        assert "API連線失敗" in str(exc_info.value.__cause__)

    @pytest.mark.asyncio
    async def test_workflow_generates_order_reference_if_not_provided(self, workflow, mock_laravel_client):
        """測試當未提供訂單參考號時，工作流程會自動生成"""
        # 模擬基本成功流程
        mock_laravel_client.customer_client.get = AsyncMock(return_value={
            "data": {"name": "測試會員", "email": "test@example.com"}
        })
        mock_laravel_client.point_client.get_balance = AsyncMock(return_value={
            "data": {"balance": 100}
        })
        mock_laravel_client.point_client.create_transaction = AsyncMock(return_value={
            "data": {"id": "earn-001"}
        })
        mock_laravel_client.point_client.redeem = AsyncMock(return_value={
            "data": {"id": "redeem-001"}
        })
        mock_laravel_client.point_client.get_balance = AsyncMock(return_value={
            "data": {"balance": 170}
        })
        mock_laravel_client.generate_idempotency_key.side_effect = lambda prefix="": f"{prefix}-123"

        # 不提供order_reference
        result = await workflow.run(customer_id=123)

        # 驗證自動生成了訂單參考號
        assert result["order_reference"] == "pos-order-123"
        mock_laravel_client.generate_idempotency_key.assert_any_call(prefix="pos-order")