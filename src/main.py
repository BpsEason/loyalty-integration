from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.core.logging import setup_logging, get_logger
from src.core.dependencies import laravel_client
from src.infrastructure.websocket.reverb_client import reverb_client
from src.infrastructure.clients.base import LaravelAPIError
from src.domain.exceptions.domain_errors import LoyaltyIntegrationError
from src.config.settings import settings
from src.interfaces.fastapi.routers import (
    auth_router,
    customers_router,
    points_router,
    coupons_router,
    rewards_router,
    workflows_router,
    websocket_router,
)

# 初始化日誌系統
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    reverb_task = None
    try:
        await laravel_client.login()
        logger.info("Laravel API 登入成功，服務準備就緒")
        
        # 啟動 Reverb WebSocket 連線
        if settings.reverb_app_id and settings.reverb_app_key and settings.reverb_app_secret:
            reverb_task = asyncio.create_task(reverb_client.connect())
            logger.info("Reverb WebSocket 用戶端已啟動", extra={
                "reverb_host": settings.reverb_host,
                "reverb_port": settings.reverb_port
            })
        else:
            logger.warning("Reverb 設定未完整，WebSocket 功能已停用")
    except Exception as e:
        logger.error("啟動時登入失敗", exc_info=True, extra={"error": str(e)})
        raise
    yield
    # Shutdown 流程：優雅關閉 Reverb 連線
    if reverb_task and not reverb_task.done():
        reverb_task.cancel()
        try:
            await reverb_task
        except asyncio.CancelledError:
            logger.info("Reverb WebSocket task cancelled successfully")
        await reverb_client.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Loyalty Integration API",
        description="外部整合層，串接 Laravel Multi-Tenant Loyalty Platform",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.exception_handler(LaravelAPIError)
    async def laravel_api_error_handler(request: Request, exc: LaravelAPIError):
        # 清理敏感資訊
        payload = exc.context.get("payload")
        safe_payload = None
        if payload:
            safe_payload = payload.copy() if isinstance(payload, dict) else payload
            if isinstance(safe_payload, dict):
                # 移除敏感欄位
                sensitive_fields = {'password', 'token', 'jwt', 'authorization', 'secret', 'access_token', 'refresh_token'}
                for field in sensitive_fields:
                    if field in safe_payload:
                        safe_payload[field] = '<redacted>'
        
        logger.error(
            "Laravel API 呼叫失敗",
            exc_info=True,
            extra={
                "path": request.url.path,
                "message": exc.message,
                "status_code": exc.status_code,
                "endpoint": exc.context.get("endpoint"),
                "payload": safe_payload
            }
        )
        return JSONResponse(
            status_code=exc.status_code or 400,
            content={"detail": exc.message},
        )

    @app.exception_handler(LoyaltyIntegrationError)
    async def loyalty_integration_error_handler(request: Request, exc: LoyaltyIntegrationError):
        """處理所有自訂的應用程式例外"""
        logger.error(
            f"應用程式錯誤: {exc.message}",
            exc_info=True,
            extra={
                "path": request.url.path,
                "error_type": type(exc).__name__,
                "context": exc.context
            }
        )
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """全域例外處理器，捕獲所有未處理的例外"""
        logger.critical(
            "未處理的伺服器錯誤",
            exc_info=True,
            extra={
                "path": request.url.path,
                "error_type": type(exc).__name__,
                "error_message": str(exc)
            }
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "內部伺服器錯誤"},
        )

    # 註冊所有路由
    app.include_router(auth_router)
    app.include_router(customers_router)
    app.include_router(points_router)
    app.include_router(coupons_router)
    app.include_router(rewards_router)
    app.include_router(workflows_router)
    app.include_router(websocket_router)

    @app.get("/")
    async def root():
        return {
            "service": "Loyalty Integration API",
            "status": "ok",
            "laravel_connected": laravel_client.is_authenticated,
        }

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app


app = create_app()