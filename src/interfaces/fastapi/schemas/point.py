from pydantic import BaseModel, Field


class RedeemRequest(BaseModel):
    customer_id: int
    amount: int = Field(..., gt=0)
    description: str | None = "Redeemed via Integration API"
    reference: str | None = None


class EarnRequest(BaseModel):
    customer_id: int
    amount: int = Field(..., gt=0)
    description: str | None = None
    reference: str | None = None


class PointTransactionRequest(BaseModel):
    """通用點數交易建立請求 - 對應 Laravel POST /api/v1/customers/{customer}/point-transactions"""
    type: str = Field(..., description="交易類型: earn, redeem, adjust, etc.")
    amount: int = Field(..., gt=0, description="交易金額（必須為正數）")
    description: str | None = Field(None, description="交易描述")
    reference: str | None = Field(None, description="參考編號")