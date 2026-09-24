from fastapi import APIRouter
from app.core.dependencies import laravel_client
from app.client.customer import CustomerClient
from app.schemas.customer import IdentifyByQrRequest

router = APIRouter(prefix="/customers", tags=["customers"])



@router.get("")
async def list_customers(per_page: int = 15):
    client = CustomerClient(laravel_client)
    return await client.list(per_page=per_page)


@router.get("/{customer_id}")
async def get_customer(customer_id: int):
    client = CustomerClient(laravel_client)
    return await client.get(customer_id)


@router.get("/{customer_id}/qr-code")
async def get_qr_code(customer_id: int):
    """取得會員 QR Code（回傳 base64 SVG）"""
    client = CustomerClient(laravel_client)
    return await client.get_qr_code(customer_id)


@router.get("/{customer_id}/membership")
async def get_membership(customer_id: int):
    """取得會員等級資訊"""
    client = CustomerClient(laravel_client)
    return await client.get_membership(customer_id)


@router.post("/identify")
async def identify_by_qr(body: IdentifyByQrRequest):
    """透過 QR Token 識別會員（模擬 POS 掃碼）"""
    client = CustomerClient(laravel_client)
    return await client.identify_by_qr(body.qr_token)