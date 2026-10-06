from fastapi import APIRouter, HTTPException
from src.core.dependencies import laravel_client
from src.infrastructure.clients.base import LaravelAPIError
from src.application.use_cases.workflows.pos_checkout import POSCheckoutWorkflow
from src.interfaces.fastapi.schemas.workflow import POSCheckoutRequest

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("/pos-checkout")
async def pos_checkout(body: POSCheckoutRequest):
    workflow = POSCheckoutWorkflow(laravel_client)
    result = await workflow.run(
        customer_id=body.customer_id,
        earn_amount=body.earn_amount,
        redeem_amount=body.redeem_amount,
        order_reference=body.order_reference,
    )
    return result