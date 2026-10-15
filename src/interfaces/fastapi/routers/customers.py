from fastapi import APIRouter, Header, HTTPException, Depends
from src.core.dependencies import laravel_client
from src.infrastructure.clients.customer import CustomerClient
from src.interfaces.fastapi.schemas.customer import IdentifyByQrRequest
from typing import Optional

router = APIRouter(prefix="/customers", tags=["customers"])


def get_tenant_id(x_tenant_id: Optional[str] = Header(None)) -> str:
    """從請求header中提取並驗證租戶ID"""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is required")
    return x_tenant_id


@router.get("")
async def list_customers(
    per_page: int = 15,
    tenant_id: str = Depends(get_tenant_id)
):
    # 克隆全局客戶端以隔離租戶上下文，共享底層HTTPX連線池
    request_client = laravel_client.clone()
    request_client.set_tenant_id(tenant_id)
    client = CustomerClient(request_client)
    return await client.list(per_page=per_page)


@router.get("/{customer_id}")
async def get_customer(
    customer_id: int,
    tenant_id: str = Depends(get_tenant_id)
):
    # 克隆全局客戶端以隔離租戶上下文，共享底層HTTPX連線池
    request_client = laravel_client.clone()
    request_client.set_tenant_id(tenant_id)
    client = CustomerClient(request_client)
    return await client.get(customer_id)


@router.get("/{customer_id}/qr-code")
async def get_qr_code(
    customer_id: int,
    tenant_id: str = Depends(get_tenant_id)
):
    """取得會員 QR Code（回傳 base64 SVG）"""
    # 克隆全局客戶端以隔離租戶上下文，共享底層HTTPX連線池
    request_client = laravel_client.clone()
    request_client.set_tenant_id(tenant_id)
    client = CustomerClient(request_client)
    return await client.get_qr_code(customer_id)


@router.get("/{customer_id}/membership")
async def get_membership(
    customer_id: int,
    tenant_id: str = Depends(get_tenant_id)
):
    """取得會員等級資訊"""
    # 克隆全局客戶端以隔離租戶上下文，共享底層HTTPX連線池
    request_client = laravel_client.clone()
    request_client.set_tenant_id(tenant_id)
    client = CustomerClient(request_client)
    return await client.get_membership(customer_id)


@router.post("/identify")
async def identify_by_qr(
    body: IdentifyByQrRequest,
    tenant_id: str = Depends(get_tenant_id)
):
    """透過 QR Token 識別會員（模擬 POS 掃碼）"""
    # 克隆全局客戶端以隔離租戶上下文，共享底層HTTPX連線池
    request_client = laravel_client.clone()
    request_client.set_tenant_id(tenant_id)
    client = CustomerClient(request_client)
    return await client.identify_by_qr(body.qr_token)