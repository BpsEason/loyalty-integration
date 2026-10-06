"""PointBalance value object - immutable point balance calculation"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)  # 不可變的值物件
class PointBalance:
    """點數餘額值物件，封裝點數計算的業務邏輯"""
    balance: int
    
    def __post_init__(self):
        if self.balance < 0:
            raise ValueError("點數餘額不能為負數")
    
    def add_points(self, amount: int) -> PointBalance:
        """增加點數，返回新的餘額物件"""
        if amount <= 0:
            raise ValueError("增加的點數必須大於0")
        return PointBalance(self.balance + amount)
    
    def subtract_points(self, amount: int) -> PointBalance:
        """扣除點數，返回新的餘額物件，檢查餘額是否足夠"""
        if amount <= 0:
            raise ValueError("扣除的點數必須大於0")
        if self.balance < amount:
            raise ValueError(f"點數餘額不足，目前餘額: {self.balance}，欲扣除: {amount}")
        return PointBalance(self.balance - amount)
    
    def calculate_after_transaction(self, earn_amount: int, redeem_amount: int) -> PointBalance:
        """計算交易後的最終餘額，支援只有收入或只有支出的場景"""
        if earn_amount < 0:
            raise ValueError("增加的點數不能為負數")
        if redeem_amount < 0:
            raise ValueError("扣除的點數不能為負數")
            
        current_balance = self.balance + earn_amount
        if current_balance < redeem_amount:
            raise ValueError(f"點數餘額不足，目前餘額: {self.balance}，收入後: {current_balance}，欲扣除: {redeem_amount}")
            
        return PointBalance(current_balance - redeem_amount)