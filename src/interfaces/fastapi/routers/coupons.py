from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Depends
from src.core.dependencies import laravel_client
from src.infrastructure.clients.coupon import CouponClient
from src.interfaces.fastapi.schemas.coupon import (
    CouponRedeemRequest,
    MixedPaymentRequest,
    CouponClaimRequest,
    CustomerCouponClaimRequest,
)

router = APIRouter(tags=["coupons"])


def get_tenant_id(x_tenant_id: Optional[str] = Header(None)) -> str:
    """從請求header中提取並驗證租戶ID"""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is required")
    return x_tenant_id


@router.get("/customers/{customer_id}/coupons")
async def list_coupons(
    customer_id: int, 
    per_page: int = 15,
    tenant_id: str = Depends(get_tenant_id)
):
    # 克隆全局客戶端以隔離租戶上下文，共享底層HTTPX連線池
    request_client = laravel_client.clone()
    request_client.set_tenant_id(tenant_id)
    client = CouponClient(request_client)
    return await client.list(customer_id, per_page=per_page)


@router.get("/customers/{customer_id}/coupons/{user_coupon_id}")
async def get_coupon(
    customer_id: int, 
    user_coupon_id: int,
    tenant_id: str = Depends(get_tenant_id)
):
    # 克隆全局客戶端以隔離租戶上下文，共享底層HTTPX連線池
    request_client = laravel_client.clone()
    request_client.set_tenant_id(tenant_id)
    client = CouponClient(request_client)
    return await client.get(customer_id, user_coupon_id)


@router.get("/customers/{customer_id}/coupon-redemptions")
async def list_coupon_redemptions(
    customer_id: int, 
    per_page: int = 15,
    tenant_id: str = Depends(get_tenant_id)
):
    # 克隆全局客戶端以隔離租戶上下文，共享底層HTTPX連線池
    request_client = laravel_client.clone()
    request_client.set_tenant_id(tenant_id)
    client = CouponClient(request_client)
    return await client.list_redemptions(customer_id, per_page=per_page)


@router.post("/coupons/redeem")
async def redeem_coupon(
    body: CouponRedeemRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    tenant_id: str = Depends(get_tenant_id)
):
    # 克隆全局客戶端以隔離租戶上下文，共享底層HTTPX連線池
    request_client = laravel_client.clone()
    request_client.set_tenant_id(tenant_id)
    client = CouponClient(request_client)
    # 呼叫端未提供 Idempotency-Key 時，由 Integration Layer
    # 為這一次 request 產生新的 key。此 key 不會跨 request 持久化，
    # 因此無法提供跨重試的 Workflow-level Idempotency；需要安全重試時，呼叫端應提供穩定的 key。
    key = idempotency_key or request_client.generate_idempotency_key(prefix="coupon-redeem")
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
    tenant_id: str = Depends(get_tenant_id)
):
    # 克隆全局客戶端以隔離租戶上下文，共享底層HTTPX連線池
    request_client = laravel_client.clone()
    request_client.set_tenant_id(tenant_id)
    client = CouponClient(request_client)
    # 呼叫端未提供 Idempotency-Key 時，由 Integration Layer
    # 為這一次 request 產生新的 key。此 key 不會跨 request 持久化，
    # 因此無法提供跨重試的 Workflow-level Idempotency；需要安全重試時，呼叫端應提供穩定的 key。
    key = idempotency_key or request_client.generate_idempotency_key(prefix="mixed")
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
    tenant_id: str = Depends(get_tenant_id)
):
    """領取優惠券 - 對應 Laravel POST /api/v1/customers/{customer}/coupons/claim"""
    # 克隆全局客戶端以隔離租戶上下文，共享底層HTTPX連線池
    request_client = laravel_client.clone()
    request_client.set_tenant_id(tenant_id)
    client = CouponClient(request_client)
    key = idempotency_key or request_client.generate_idempotency_key(prefix="coupon-claim")
    return await client.claim(
        customer_id=customer_id,
        coupon_code=body.coupon_code,
        idempotency_key=key
    )


@router.post("/coupons/claim")
async def claim_coupon_via_api(
    body: CouponClaimRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    tenant_id: str = Depends(get_tenant_id)
):
    # 克隆全局客戶端以隔離租戶上下文，共享底層HTTPX連線池
    request_client = laravel_client.clone()
    request_client.set_tenant_id(tenant_id)
    client = CouponClient(request_client)
    # 呼叫端未提供 Idempotency-Key 時，由 Integration Layer
    # 為這一次 request 產生新的 key。此 key 不會跨 request 持久化，