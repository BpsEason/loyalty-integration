from typing import Optional
from fastapi import APIRouter, Header
from app.core.dependencies import laravel_client
from app.client.point import PointClient
from app.schemas.point import RedeemRequest, EarnRequest, PointTransactionRequest

router = APIRouter(tags=["points"])


@router.get("/customers/{customer_id}/points")
async def get_balance(customer_id: int):
    client = PointClient(laravel_client)
    return await client.get_balance(customer_id)


@router.get("/customers/{customer_id}/point-transactions")
async def list_point_transactions(
    customer_id: int,
    per_page: int = 15,
    type: str | None = None,
):
    client = PointClient(laravel_client)
    return await client.list_transactions(
        customer_id, per_page=per_page, type=type
    )


@router.post("/customers/{customer_id}/point-transactions")
async def create_point_transaction(
    customer_id: int,
    body: PointTransactionRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    client = PointClient(laravel_client)
    key = idempotency_key or laravel_client.generate_idempotency_key(prefix="transaction")
    return await client.create_transaction(
        customer_id=customer_id,
        type=body.type,
        amount=body.amount,
        description=body.description,
        reference=body.reference,
        idempotency_key=key,
    )


@router.get("/customers/{customer_id}/point-transactions/expiring")
async def get_expiring_transactions(customer_id: int, days: int = 30):
    client = PointClient(laravel_client)
    return await client.get_expiring(customer_id, days=days)


@router.get("/customers/{customer_id}/point-transactions/{transaction_id}")
async def get_point_transaction(customer_id: int, transaction_id: int):
    client = PointClient(laravel_client)
    return await client.get_transaction(customer_id, transaction_id)


@router.post("/points/earn")
async def earn_points(
    body: EarnRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),  # 已支援外部 Header
):
    client = PointClient(laravel_client)
    key = idempotency_key or laravel_client.generate_idempotency_key(prefix="earn")
    return await client.create_transaction(
        customer_id=body.customer_id,
        type="earn",
        amount=body.amount,
        description=body.description,
        reference=body.reference,
        idempotency_key=key,
    )


@router.post("/points/redeem")
async def redeem_points(
    body: RedeemRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    client = PointClient(laravel_client)
    key = idempotency_key or laravel_client.generate_idempotency_key(prefix="redeem")
    return await client.redeem(
        customer_id=body.customer_id,
        amount=body.amount,
        description=body.description,
        reference=body.reference,
        idempotency_key=key,
    )