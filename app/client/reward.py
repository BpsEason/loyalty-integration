from __future__ import annotations

from app.client.base import LaravelClient


class RewardClient:
    def __init__(self, client: LaravelClient):
        self.client = client

    async def list_reward_grants(self, customer_id: int, per_page: int = 15) -> dict:
        """列出客戶的所有獎勵發放記錄 - 對應 Laravel GET /api/v1/customers/{customer}/reward-grants"""
        return await self.client.get(
            f"/customers/{customer_id}/reward-grants",
            params={"per_page": per_page},
        )

    async def grant_reward(
        self,
        customer_id: int,
        campaign_reward_id: int,
        quantity: int = 1,
        reference: str | None = None,
        description: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """發放獎勵給客戶 - 對應 Laravel POST /api/v1/customers/{customer}/rewards/grant"""
        payload = {
            "campaign_reward_id": campaign_reward_id,
            "quantity": quantity,
        }
        if reference:
            payload["reference"] = reference
        if description:
            payload["description"] = description

        return await self.client.post(
            f"/customers/{customer_id}/rewards/grant",
            json=payload,
            idempotency_key=idempotency_key,
            expect_status=[201, 200, 400],
        )