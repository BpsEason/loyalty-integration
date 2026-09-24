from typing import Optional
from fastapi import APIRouter, Header
from app.core.dependencies import laravel_client
from app.client.reward import RewardClient
from app.schemas.reward import GrantRewardRequest

router = APIRouter(tags=["rewards"])


@router.get("/customers/{customer_id}/reward-grants")
async def list_reward_grants(customer_id: int, per_page: int = 15):
    client = RewardClient(laravel_client)
    return await client.list_reward_grants(customer_id, per_page=per_page)


@router.post("/customers/{customer_id}/rewards/grant")
async def grant_reward(
    customer_id: int,
    body: GrantRewardRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    client = RewardClient(laravel_client)
    # 呼叫端未提供 Idempotency-Key 時，由 Integration Layer
    # 為這一次 request 產生新的 key。此 key 不會跨 request 持久化，
    # 因此無法提供跨重試的 Workflow-level Idempotency；需要安全重試時，呼叫端應提供穩定的 key。
    key = idempotency_key or laravel_client.generate_idempotency_key(prefix="grant-reward")
    return await client.grant_reward(
        customer_id=customer_id,
        campaign_reward_id=body.campaign_reward_id,
        quantity=body.quantity,
        reference=body.reference,
        description=body.description,
        idempotency_key=key,
    )