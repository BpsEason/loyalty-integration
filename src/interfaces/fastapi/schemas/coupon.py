from pydantic import BaseModel, Field


class CouponRedeemRequest(BaseModel):
    customer_id: int
    user_coupon_id: int
    reference: str
    order_reference: str | None = None
    order_amount: int | None = None


class MixedPaymentRequest(BaseModel):
    customer_id: int
    reference: str
    order_amount: int = Field(..., ge=0)
    user_coupon_id: int | None = None
    points_amount: int | None = Field(None, ge=0)
    order_reference: str | None = None


class CouponClaimRequest(BaseModel):
    customer_id: int
    code: str = Field(..., description="優惠券代碼")


class CustomerCouponClaimRequest(BaseModel):
    code: str = Field(..., description="優惠券代碼")