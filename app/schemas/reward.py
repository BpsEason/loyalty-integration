from pydantic import BaseModel


class GrantRewardRequest(BaseModel):
    """獎勵發放請求 - 對應 Laravel POST /api/v1/customers/{customer}/rewards/grant"""
    campaign_reward_id: int
    quantity: int = 1
    reference: str | None = None
    description: str | None = None