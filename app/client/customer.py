from __future__ import annotations

from app.client.base import LaravelClient


class CustomerClient:
    def __init__(self, client: LaravelClient):
        self.client = client

    async def list(self, per_page: int = 15) -> dict:
        return await self.client.get("/customers", params={"per_page": per_page})

    async def get(self, customer_id: int) -> dict:
        return await self.client.get(f"/customers/{customer_id}")

    async def create(self, name: str, email: str, phone: str | None = None) -> dict:
        payload = {"name": name, "email": email}
        if phone:
            payload["phone"] = phone
        return await self.client.post("/customers", json=payload)

    async def identify_by_qr(self, qr_token: str) -> dict:
        return await self.client.post(
            "/customers/identify",
            json={"qr_token": qr_token},
        )

    async def get_qr_code(self, customer_id: int) -> dict:
        return await self.client.get(f"/customers/{customer_id}/qr-code")

    async def get_membership(self, customer_id: int) -> dict:
        return await self.client.get(f"/customers/{customer_id}/membership")