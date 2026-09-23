from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from rich.console import Console
from app.client.base import LaravelClient, LaravelAPIError
from app.client.customer import CustomerClient
from app.client.point import PointClient
from app.client.coupon import CouponClient
from app.client.reward import RewardClient
from app.workflows.pos_checkout import POSCheckoutWorkflow

console = Console()

# 全域 Client（服務啟動時登入一次，之後共用）
laravel_client = LaravelClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動時自動登入
    try:
        await laravel_client.login()
        console.print("[green]Laravel API 登入成功，服務準備就緒[/green]")
    except Exception as e:
        console.print(f"[red]啟動時登入失敗: {e}[/red]")
        raise
    yield
    # 關閉時可做清理（目前不需要）


app = FastAPI(
    title="Loyalty Integration API",
    description="外部整合層，串接 Laravel Multi-Tenant Loyalty Platform",
    version="1.0.0",
    lifespan=lifespan,
)


# ==================== Schemas ====================

class RedeemRequest(BaseModel):
    customer_id: int
    amount: int = Field(..., gt=0)
    description: Optional[str] = "Redeemed via Integration API"
    reference: Optional[str] = None


class EarnRequest(BaseModel):
    customer_id: int
    amount: int = Field(..., gt=0)
    description: Optional[str] = None
    reference: Optional[str] = None


class POSCheckoutRequest(BaseModel):
    customer_id: int
    earn_amount: int = Field(100, ge=0)
    redeem_amount: int = Field(0, ge=0)
    order_reference: Optional[str] = None


class CouponRedeemRequest(BaseModel):
    customer_id: int
    user_coupon_id: int
    reference: str
    order_reference: Optional[str] = None
    order_amount: Optional[int] = None


class MixedPaymentRequest(BaseModel):
    customer_id: int
    reference: str
    order_amount: int = Field(..., ge=0)
    user_coupon_id: Optional[int] = None
    points_amount: Optional[int] = Field(None, ge=0)
    order_reference: Optional[str] = None


class CouponClaimRequest(BaseModel):
    customer_id: int
    code: str = Field(..., description="優惠券代碼")


class PointTransactionRequest(BaseModel):
    """通用點數交易建立請求 - 對應 Laravel POST /api/v1/customers/{customer}/point-transactions"""
    type: str = Field(..., description="交易類型: earn, redeem, adjust, etc.")
    amount: int = Field(..., gt=0, description="交易金額（必須為正數）")
    description: Optional[str] = Field(None, description="交易描述")
    reference: Optional[str] = Field(None, description="參考編號")


class IdentifyByQrRequest(BaseModel):
    qr_token: str


class LoginRequest(BaseModel):
    email: str
    password: str


class GrantRewardRequest(BaseModel):
    """獎勵發放請求 - 對應 Laravel POST /api/v1/customers/{customer}/rewards/grant"""
    campaign_reward_id: int
    quantity: int = 1
    reference: Optional[str] = None
    description: Optional[str] = None


# ==================== Health ====================

@app.get("/")
async def root():
    return {
        "service": "Loyalty Integration API",
        "status": "ok",
        "laravel_connected": laravel_client._token is not None,
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ==================== Auth ====================

@app.post("/auth/login")
async def auth_login(body: LoginRequest):
    """手動登入取得 JWT Token"""
    try:
        return await laravel_client.login(body.email, body.password)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.get("/auth/me")
async def auth_me():
    """取得目前登入的使用者資訊"""
    try:
        return await laravel_client.me()
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.post("/auth/refresh")
async def auth_refresh():
    """刷新 JWT Token"""
    try:
        return await laravel_client.refresh()
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.post("/auth/logout")
async def auth_logout():
    """登出並清除目前的 Token"""
    try:
        return await laravel_client.logout()
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


# ==================== Customer ====================

@app.get("/customers")
async def list_customers(per_page: int = 15):
    try:
        client = CustomerClient(laravel_client)
        return await client.list(per_page=per_page)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.get("/customers/{customer_id}")
async def get_customer(customer_id: int):
    try:
        client = CustomerClient(laravel_client)
        return await client.get(customer_id)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.get("/customers/{customer_id}/qr-code")
async def get_qr_code(customer_id: int):
    """取得會員 QR Code（回傳 base64 SVG）"""
    try:
        client = CustomerClient(laravel_client)
        return await client.get_qr_code(customer_id)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.get("/customers/{customer_id}/membership")
async def get_membership(customer_id: int):
    """取得會員等級資訊"""
    try:
        client = CustomerClient(laravel_client)
        return await client.get_membership(customer_id)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.post("/customers/identify")
async def identify_by_qr(body: IdentifyByQrRequest):
    """透過 QR Token 識別會員（模擬 POS 掃碼）"""
    try:
        client = CustomerClient(laravel_client)
        return await client.identify_by_qr(body.qr_token)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


# ==================== Points ====================

@app.get("/customers/{customer_id}/points")
async def get_balance(customer_id: int):
    try:
        client = PointClient(laravel_client)
        return await client.get_balance(customer_id)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.get("/customers/{customer_id}/point-transactions")
async def list_point_transactions(customer_id: int, per_page: int = 15, type: str | None = None):
    try:
        client = PointClient(laravel_client)
        return await client.list_transactions(customer_id, per_page=per_page, type=type)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.post("/customers/{customer_id}/point-transactions")
async def create_point_transaction(
    customer_id: int, 
    body: PointTransactionRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """建立通用點數交易 - 對應 Laravel POST /api/v1/customers/{customer}/point-transactions"""
    try:
        client = PointClient(laravel_client)
        # 如果外部系統有提供 Idempotency-Key，就使用它；否則自動產生
        key = idempotency_key or laravel_client.generate_idempotency_key(prefix="transaction")
        return await client.create_transaction(
            customer_id=customer_id,
            type=body.type,
            amount=body.amount,
            description=body.description,
            reference=body.reference,
            idempotency_key=key,
        )
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.get("/customers/{customer_id}/point-transactions/expiring")
async def get_expiring_transactions(customer_id: int, days: int = 30):
    try:
        client = PointClient(laravel_client)
        return await client.get_expiring(customer_id, days=days)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.get("/customers/{customer_id}/point-transactions/{transaction_id}")
async def get_point_transaction(customer_id: int, transaction_id: int):
    try:
        client = PointClient(laravel_client)
        return await client.get_transaction(customer_id, transaction_id)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.post("/points/earn")
async def earn_points(body: EarnRequest):
    try:
        client = PointClient(laravel_client)
        key = laravel_client.generate_idempotency_key(prefix="earn")
        return await client.create_transaction(
            customer_id=body.customer_id,
            type="earn",
            amount=body.amount,
            description=body.description,
            reference=body.reference,
            idempotency_key=key,
        )
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.post("/points/redeem")
async def redeem_points(
    body: RedeemRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    try:
        client = PointClient(laravel_client)
        # 如果外部系統有提供 Idempotency-Key，就使用它；否則自動產生
        key = idempotency_key or laravel_client.generate_idempotency_key(prefix="redeem")
        return await client.redeem(
            customer_id=body.customer_id,
            amount=body.amount,
            description=body.description,
            reference=body.reference,
            idempotency_key=key,
        )
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


# ==================== POS Workflow ====================

@app.post("/workflows/pos-checkout")
async def pos_checkout(body: POSCheckoutRequest):
    try:
        workflow = POSCheckoutWorkflow(laravel_client)
        result = await workflow.run(
            customer_id=body.customer_id,
            earn_amount=body.earn_amount,
            redeem_amount=body.redeem_amount,
            order_reference=body.order_reference,
        )
        return result
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Coupons ====================

@app.get("/customers/{customer_id}/coupons")
async def list_coupons(customer_id: int, per_page: int = 15):
    try:
        client = CouponClient(laravel_client)
        return await client.list(customer_id, per_page=per_page)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.get("/customers/{customer_id}/coupons/{user_coupon_id}")
async def get_coupon(customer_id: int, user_coupon_id: int):
    """取得單一會員優惠券的詳細資訊"""
    try:
        client = CouponClient(laravel_client)
        return await client.get(customer_id, user_coupon_id)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.get("/customers/{customer_id}/coupon-redemptions")
async def list_coupon_redemptions(customer_id: int, per_page: int = 15):
    """取得會員的優惠券核銷歷史記錄"""
    try:
        client = CouponClient(laravel_client)
        return await client.list_redemptions(customer_id, per_page=per_page)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.post("/coupons/redeem")
async def redeem_coupon(
    body: CouponRedeemRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    try:
        client = CouponClient(laravel_client)
        # 如果外部系統有提供 Idempotency-Key，就使用它；否則自動產生
        key = idempotency_key or laravel_client.generate_idempotency_key(prefix="coupon-redeem")
        return await client.redeem(
            customer_id=body.customer_id,
            user_coupon_id=body.user_coupon_id,
            reference=body.reference,
            order_reference=body.order_reference,
            order_amount=body.order_amount,
            idempotency_key=key,
        )
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.post("/payments/mixed")
async def mixed_payment(
    body: MixedPaymentRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    try:
        client = CouponClient(laravel_client)
        # 如果外部系統有提供 Idempotency-Key，就使用它；否則自動產生
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
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.post("/customers/{customer_id}/coupons/claim")
async def claim_coupon(
    customer_id: int,
    body: CouponClaimRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """領取優惠券 - 對應 Laravel POST /api/v1/customers/{customer}/coupons/claim"""
    try:
        client = CouponClient(laravel_client)
        # 如果外部系統有提供 Idempotency-Key，就使用它；否則自動產生
        key = idempotency_key or laravel_client.generate_idempotency_key(prefix="coupon-claim")
        return await client.claim(
            customer_id=customer_id,
            code=body.code,
            idempotency_key=key,
        )
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.post("/coupons/claim")
async def claim_coupon_via_api(
    body: CouponClaimRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """領取優惠券 - 統一 API 格式"""
    try:
        client = CouponClient(laravel_client)
        # 如果外部系統有提供 Idempotency-Key，就使用它；否則自動產生
        key = idempotency_key or laravel_client.generate_idempotency_key(prefix="coupon-claim")
        return await client.claim(
            customer_id=body.customer_id,
            code=body.code,
            idempotency_key=key,
        )
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


# ==================== Rewards ====================

@app.get("/customers/{customer_id}/reward-grants")
async def list_reward_grants(customer_id: int, per_page: int = 15):
    """列出客戶的所有獎勵發放記錄 - 對應 Laravel GET /api/v1/customers/{customer}/reward-grants"""
    try:
        client = RewardClient(laravel_client)
        return await client.list_reward_grants(customer_id, per_page=per_page)
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)


@app.post("/customers/{customer_id}/rewards/grant")
async def grant_reward(
    customer_id: int,
    body: GrantRewardRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """發放獎勵給客戶 - 對應 Laravel POST /api/v1/customers/{customer}/rewards/grant"""
    try:
        client = RewardClient(laravel_client)
        # 如果外部系統有提供 Idempotency-Key，就使用它；否則自動產生
        key = idempotency_key or laravel_client.generate_idempotency_key(prefix="grant-reward")
        return await client.grant_reward(
            customer_id=customer_id,
            campaign_reward_id=body.campaign_reward_id,
            quantity=body.quantity,
            reference=body.reference,
            description=body.description,
            idempotency_key=key,
        )
    except LaravelAPIError as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.message)