from __future__ import annotations

from app.client.base import LaravelClient


class PointClient:
    def __init__(self, client: LaravelClient):
        self.client = client

    async def get_balance(self, customer_id: int) -> dict:
        return await self.client.get(f"/customers/{customer_id}/points")

    async def list_transactions(
        self,
        customer_id: int,
        per_page: int = 15,
        type: str | None = None,
    ) -> dict:
        params: dict = {"per_page": per_page}
        if type:
            params["type"] = type
        return await self.client.get(
            f"/customers/{customer_id}/point-transactions",
            params=params,
        )

    async def create_transaction(
        self,
        customer_id: int,
        type: str,
        amount: int,
        description: str | None = None,
        reference: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        payload = {
            "type": type,
            "amount": amount,
        }
        if description:
            payload["description"] = description
        if reference:
            payload["reference"] = reference

        return await self.client.post(
            f"/customers/{customer_id}/point-transactions",
            json=payload,
            idempotency_key=idempotency_key,
            expect_status=[201, 200],
        )

    async def redeem(
        self,
        customer_id: int,
        amount: int,
        description: str | None = "Redeemed at POS",
        reference: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        payload = {"amount": amount}
        if description:
            payload["description"] = description
        if reference:
            payload["reference"] = reference

        return await self.client.post(
            f"/customers/{customer_id}/points/redeem",
            json=payload,
            idempotency_key=idempotency_key,
            expect_status=[201, 200],
        )

    async def get_expiring(self, customer_id: int, days: int = 30) -> dict:
        return await self.client.get(
            f"/customers/{customer_id}/point-transactions/expiring",
            params={"days": days},
        )

    async def get_transaction(self, customer_id: int, transaction_id: int) -> dict:
        return await self.client.get(
            f"/customers/{customer_id}/point-transactions/{transaction_id}"
        )