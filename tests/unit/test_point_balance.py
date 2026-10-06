"""Unit tests for PointBalance value object - core business invariants"""
from __future__ import annotations

import pytest
from src.domain.value_objects.point_balance import PointBalance


class TestPointBalanceInvariants:
    """測試點數餘額的核心業務不變量"""

    def test_cannot_create_negative_balance(self):
        """測試：無法建立負數的點數餘額"""
        with pytest.raises(ValueError, match="點數餘額不能為負數"):
            PointBalance(-100)

    def test_cannot_add_zero_or_negative_points(self):
        """測試：無法新增零或負數的點數"""
        balance = PointBalance(100)
        
        # 測試新增0點
        with pytest.raises(ValueError, match="增加的點數必須大於0"):
            balance.add_points(0)
        
        # 測試新增負數點數
        with pytest.raises(ValueError, match="增加的點數必須大於0"):
            balance.add_points(-50)

    def test_cannot_subtract_zero_or_negative_points(self):
        """測試：無法扣除零或負數的點數"""
        balance = PointBalance(100)
        
        # 測試扣除0點
        with pytest.raises(ValueError, match="扣除的點數必須大於0"):
            balance.subtract_points(0)
        
        # 測試扣除負數點數
        with pytest.raises(ValueError, match="扣除的點數必須大於0"):
            balance.subtract_points(-30)

    def test_cannot_subtract_more_than_balance(self):
        """測試：無法扣除超過目前餘額的點數"""
        balance = PointBalance(100)
        
        with pytest.raises(ValueError, match="點數餘額不足，目前餘額: 100，欲扣除: 150"):
            balance.subtract_points(150)

    def test_add_points_returns_new_instance_immutability(self):
        """測試：add_points 回傳新實體，保持原值物件的不可變性"""
        original_balance = PointBalance(100)
        new_balance = original_balance.add_points(50)
        
        # 確保原物件不變
        assert original_balance.balance == 100
        # 確保新物件有正確的值
        assert new_balance.balance == 150
        # 確保是不同的實體
        assert original_balance is not new_balance

    def test_subtract_points_returns_new_instance_immutability(self):
        """測試：subtract_points 回傳新實體，保持原值物件的不可變性"""
        original_balance = PointBalance(100)
        new_balance = original_balance.subtract_points(30)
        
        # 確保原物件不變
        assert original_balance.balance == 100
        # 確保新物件有正確的值
        assert new_balance.balance == 70
        # 確保是不同的實體
        assert original_balance is not new_balance

    def test_calculate_after_transaction_correctly(self):
        """測試：交易後餘額計算正確（先加後扣）"""
        initial_balance = PointBalance(100)
        final_balance = initial_balance.calculate_after_transaction(earn_amount=100, redeem_amount=30)
        
        assert final_balance.balance == 170  # 100 + 100 - 30 = 170

    def test_calculate_after_transaction_maintains_immutability(self):
        """測試：calculate_after_transaction 保持原物件不可變"""
        original_balance = PointBalance(100)
        final_balance = original_balance.calculate_after_transaction(50, 20)
        
        assert original_balance.balance == 100
        assert final_balance.balance == 130
        assert original_balance is not final_balance

    def test_calculate_after_transaction_with_zero_earn(self):
        """測試：只兌換不發點的情況"""
        initial_balance = PointBalance(100)
        final_balance = initial_balance.calculate_after_transaction(earn_amount=0, redeem_amount=30)
        # 當earn_amount=0時，add_points會擲出例外，這是預期的行為
        # 因為業務規則要求所有點數變更都必須是正數