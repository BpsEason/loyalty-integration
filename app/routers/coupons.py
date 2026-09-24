from typing import Optional
from fastapi import APIRouter, Header
from app.core.dependencies import laravel_client
from app.client.coupon import CouponClient
from app.schemas.coupon import (
    CouponRedeemRequest,
    MixedPaymentRequest,
    CouponClaimRequest,
    CustomerCouponClaimRequest,
)

router = APIRouter(tags=["coupons"])


@router.get("/customers/{customer_id}/coupons")
async def list_coupons(customer_id: int, per_page: int = 15):
    client = CouponClient(laravel_client)
    return await client.list(customer_id, per_page=per_page)


@router.get("/customers/{customer_id}/coupons/{user_coupon_id}")
async def get_coupon(customer_id: int, user_coupon_id: int):
    client = CouponClient(laravel_client)
    return await client.get(customer_id, user_coupon_id)


@router.get("/customers/{customer_id}/coupon-redemptions")
async def list_coupon_redemptions(customer_id: int, per_page: int = 15):
    client = CouponClient(laravel_client)
    return await client.list_redemptions(customer_id, per_page=per_page)


@router.post("/coupons/redeem")
async def redeem_coupon(
    body: CouponRedeemRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    client = CouponClient(laravel_client)
    key = idempotency_key or laravel_client.generate_idempotency_key(prefix="coupon-redeem")
    return await client.redeem(
        customer_id=body.customer_id,
        user_coupon_id=body.user_coupon_id,
        reference=body.reference,
        order_reference=body.order_reference,
        order_amount=body.order_amount,
        idempotency_key=key,
    )


@router.post("/payments/mixed")
async def mixed_payment(
    body: MixedPaymentRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    client = CouponClient(laravel_client)
    key = idempotency_key or laravel_client.generate_idempotency_key(prefix="mixed")
    return await client.mixed_payment(
        customer_id=body.customer_id,
        reference=body.reference,
        order_amount=body.order_amount,
        user_coupon_id=body.user_coupon_id,
        points_amount=body.points_amount,
        order_reference=body.order_reference,
        idempotency_key=key,
    )


@router.post("/customers/{customer_id}/coupons/claim")
async def claim_coupon(
    customer_id: int,
    body: CustomerCouponClaimRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """領取優惠券 - 對應 Laravel POST /api/v1/customers/{customer}/coupons/claim"""
    client = CouponClient(laravel_client)
    key = idempotency_key or laravel_client.generate_idempotency_key(prefix="coupon-claim")
    return await client.claim(
        customer_id=customer_id,
        code=body.code,
        idempotency_key=key,
    )


@router.post("/coupons/claim")
async def claim_coupon_via_api(
    body: CouponClaimRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    client = CouponClient(laravel_client)
    key = idempotency_key or laravel_client.generate_idempotency_key(prefix="coupon-claim")
    return await client.claim(
        customer_id=body.customer_id,
        code=body.code,
        idempotency_key=key,
    )