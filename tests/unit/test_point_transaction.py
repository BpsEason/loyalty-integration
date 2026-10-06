"""Unit tests for PointTransaction domain entity - business rules validation"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from src.domain.entities.point_transaction import PointTransaction


class TestPointTransactionInvariants:
    """測試點數交易的核心業務規則"""

    def test_can_create_valid_earn_transaction(self):
        """測試：可以建立合法的發點交易"""
        transaction = PointTransaction(
            customer_id=123,
            transaction_type="earn",
            amount=100,
            description="消費發點",
            reference="ORDER-12345"
        )
        
        assert transaction.customer_id == 123
        assert transaction.transaction_type == "earn"
        assert transaction.amount == 100
        assert transaction.description == "消費發點"
        assert transaction.reference == "ORDER-12345"
        assert transaction.is_earn() is True
        assert transaction.is_redeem() is False
        assert isinstance(transaction.id, str)
        assert isinstance(transaction.created_at, datetime)

    def test_can_create_valid_redeem_transaction(self):
        """測試：可以建立合法的兌換交易"""
        transaction = PointTransaction(
            customer_id=123,
            transaction_type="redeem",
            amount=50,
            description="優惠兌換",
            reference="ORDER-12345"
        )
        
        assert transaction.transaction_type == "redeem"
        assert transaction.amount == 50
        assert transaction.is_earn() is False
        assert transaction.is_redeem() is True

    def test_cannot_create_transaction_with_zero_amount(self):
        """測試：無法建立金額為零的交易"""
        with pytest.raises(ValueError, match="交易金額必須大於0"):
            PointTransaction(
                customer_id=123,
                transaction_type="earn",
                amount=0,
                description="零點數交易"
            )

    def test_cannot_create_transaction_with_negative_amount(self):
        """測試：無法建立金額為負數的交易"""
        with pytest.raises(ValueError, match="交易金額必須大於0"):
            PointTransaction(
                customer_id=123,
                transaction_type="earn",
                amount=-100,
                description="負點數交易"
            )

    def test_cannot_create_transaction_with_invalid_type(self):
        """測試：無法建立具有無效交易類型的交易"""
        invalid_types = ["add", "remove", "transfer", "", None, "EARN", "Redeem"]
        
        for invalid_type in invalid_types:
            with pytest.raises(ValueError, match=f"交易類型必須是 \\['earn', 'redeem'\\] 其中之一"):
                PointTransaction(
                    customer_id=123,
                    transaction_type=invalid_type,
                    amount=100,
                    description="無效類型交易"
                )

    def test_transaction_id_is_uuid_format(self):
        """測試：交易ID是UUID格式（自動生成）"""
        transaction = PointTransaction(
            customer_id=123,
            transaction_type="earn",
            amount=100,
            description="測試交易ID格式"
        )
        
        # UUID字符串長度為36（含連字符）
        assert len(transaction.id) == 36
        # 驗證UUID格式（簡單檢查）
        assert transaction.id.count('-') == 4

    def test_created_at_is_set_automatically(self):
        """測試：建立時間自動設定"""
        before = datetime.now(timezone.utc)
        transaction = PointTransaction(
            customer_id=123,
            transaction_type="earn",
            amount=100,
            description="測試建立時間"
        )
        after = datetime.now(timezone.utc)
        
        assert before <= transaction.created_at <= after

    def test_can_provide_custom_id_and_idempotency_key(self):
        """測試：可以自訂ID和冪等性金鑰"""
        custom_id = "custom-transaction-001"
        idempotency_key = "idem-key-abc123"
        
        transaction = PointTransaction(
            customer_id=123,
            transaction_type="redeem",
            amount=50,
            description="自訂ID交易",
            id=custom_id,
            idempotency_key=idempotency_key
        )
        
        assert transaction.id == custom_id
        assert transaction.idempotency_key == idempotency_key