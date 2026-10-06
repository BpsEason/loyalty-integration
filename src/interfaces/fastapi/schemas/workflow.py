from pydantic import BaseModel, Field


class POSCheckoutRequest(BaseModel):
    customer_id: int
    earn_amount: int = Field(100, ge=0)
    redeem_amount: int = Field(0, ge=0)
    order_reference: str | None = None