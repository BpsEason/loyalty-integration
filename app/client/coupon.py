from __future__ import annotations

from app.client.base import LaravelClient


class CouponClient:
    def __init__(self, client: LaravelClient):
        self.client = client

    async def list(self, customer_id: int, per_page: int = 15) -> dict:
        return await self.client.get(
            f"/customers/{customer_id}/coupons",
            params={"per_page": per_page},
        )

    async def get(self, customer_id: int, user_coupon_id: int) -> dict:
        return await self.client.get(
            f"/customers/{customer_id}/coupons/{user_coupon_id}",
        )

    async def claim(
        self,
        customer_id: int,
        code: str,
        idempotency_key: str | None = None,
    ) -> dict:
        return await self.client.post(
            f"/customers/{customer_id}/coupons/claim",
            json={"code": code},
            idempotency_key=idempotency_key,
            expect_status=[201, 200],
        )

    async def redeem(
        self,
        customer_id: int,
        user_coupon_id: int,
        reference: str,
        order_reference: str | None = None,
        order_amount: int | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        payload = {"reference": reference}
        if order_reference:
            payload["order_reference"] = order_reference
        if order_amount is not None:
            payload["order_amount"] = order_amount

        return await self.client.post(
            f"/customers/{customer_id}/coupons/{user_coupon_id}/redeem",
            json=payload,
            idempotency_key=idempotency_key,
        )

    async def list_redemptions(self, customer_id: int, per_page: int = 15) -> dict:
        return await self.client.get(
            f"/customers/{customer_id}/coupon-redemptions",
            params={"per_page": per_page},
        )

    async def mixed_payment(
        self,
        customer_id: int,
        reference: str,
        order_amount: int,
        user_coupon_id: int | None = None,
        points_amount: int | None = None,
        order_reference: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        payload = {
            "reference": reference,
            "order_amount": order_amount,
        }
        if user_coupon_id is not None:
            payload["user_coupon_id"] = user_coupon_id
        if points_amount is not None:
            payload["points_amount"] = points_amount
        if order_reference:
            payload["order_reference"] = order_reference

        return await self.client.post(
            f"/customers/{customer_id}/mixed-payment",
            json=payload,
            idempotency_key=idempotency_key,
        )