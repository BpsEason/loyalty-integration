from fastapi import APIRouter, HTTPException, Header, Depends
from src.core.dependencies import laravel_client
from src.infrastructure.clients.base import LaravelAPIError
from src.application.use_cases.workflows.pos_checkout import POSCheckoutWorkflow
from src.interfaces.fastapi.schemas.workflow import POSCheckoutRequest
from typing import Optional

router = APIRouter(prefix="/workflows", tags=["workflows"])


def get_tenant_id(x_tenant_id: Optional[str] = Header(None)) -> str:
    """從請求header中提取並驗證租戶ID"""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is required")
    return x_tenant_id


@router.post("/pos-checkout")
async def pos_checkout(
    body: POSCheckoutRequest,
    tenant_id: str = Depends(get_tenant_id),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    # 克隆全局客戶端以隔離租戶上下文，共享底層HTTPX連線池
    request_client = laravel_client.clone()
    request_client.set_tenant_id(tenant_id)
    
    workflow = POSCheckoutWorkflow(request_client)
    # 如果呼叫端提供了全域的Idempotency-Key，將其作為工作流程的冪等前綴
    # 確保整個工作流程的所有步驟都使用基於此key的穩定冪等鍵
    result = await workflow.run(
        customer_id=body.customer_id,
        earn_amount=body.earn_amount,
        redeem_amount=body.redeem_amount,
        order_reference=body.order_reference,
        workflow_idempotency_prefix=idempotency_key,
    )
    return result