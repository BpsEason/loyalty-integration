"""PointTransaction domain entity"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


@dataclass
class PointTransaction:
    """點數交易領域實體，代表一筆點數的變更記錄"""
    customer_id: int
    transaction_type: str  # 'earn' 或 'redeem'
    amount: int
    description: str
    reference: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    idempotency_key: Optional[str] = None
    
    def __post_init__(self):
        """驗證交易資料的有效性"""
        if self.amount <= 0:
            raise ValueError("交易金額必須大於0")
        
        valid_types = ['earn', 'redeem']
        if self.transaction_type not in valid_types:
            raise ValueError(f"交易類型必須是 {valid_types} 其中之一，目前為: {self.transaction_type}")
    
    def is_earn(self) -> bool:
        """是否為發點交易"""
        return self.transaction_type == 'earn'
    
    def is_redeem(self) -> bool:
        """是否為兌換交易"""
        return self.transaction_type == 'redeem'