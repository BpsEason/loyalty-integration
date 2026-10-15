from __future__ import annotations

import asyncio
import uuid
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import copy

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

# 模組層級編譯一次UUID正規表示式，避免每個請求重複編譯
UUID_PATTERN = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', re.IGNORECASE)
MAX_REQUEST_ID_LENGTH = 64
# 敏感欄位列表（大小寫不敏感，先移除底線和底線以外的符號，統一處理各種命名格式）
SENSITIVE_FIELDS = {
    'password', 'token', 'jwt', 'authorization', 'secret', 
    'accesstoken', 'refreshtoken', 'apikey', 'api_key', 
    'access_token', 'refresh_token', 'secret_key'
}

# 初始化日誌系統
setup_logging()
logger = get_logger(__name__)


def redact_sensitive_data(data):
    """深層清理敏感資訊，支援字典、列表和其他類型，大小寫不敏感"""
    if isinstance(data, dict):
        redacted = {}
        for key, value in data.items():
            # 檢查當前鍵是否是敏感欄位（不區分大小寫）
            if key.lower() in SENSITIVE_FIELDS:
                redacted[key] = '<redacted>'
            else:
                # 遞迴處理巢狀結構
                redacted[key] = redact_sensitive_data(value)
        return redacted
    elif isinstance(data, list):
        # 處理列表中的每個元素
        return [redact_sensitive_data(item) for item in data]
    else:
        # 非字典/列表類型直接返回
        return data


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

    # 添加請求ID中間件，為每個請求生成唯一的request_id並注入到請求狀態
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        # 從請求header獲取X-Request-ID，如果不存在則生成新的
        incoming_request_id = request.headers.get("X-Request-ID")
        # 驗證傳入的request_id格式和長度，避免信任任意外部字串
        if incoming_request_id and (len(incoming_request_id) > MAX_REQUEST_ID_LENGTH or not UUID_PATTERN.match(incoming_request_id)):
            # 如果格式不正確，生成新的UUID
            request_id = str(uuid.uuid4())
        else:
            request_id = incoming_request_id or str(uuid.uuid4())
            
        # 將request_id存儲到request.state中，僅在本檔案中使用
        request.state.request_id = request_id
        # 在回應header中加入X-Request-ID
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(LaravelAPIError)
    async def laravel_api_error_handler(request: Request, exc: LaravelAPIError):
        # 清理敏感資訊
        payload = exc.context.get("payload")
        safe_payload = redact_sensitive_data(payload) if payload is not None else None
        
        # 從request狀態獲取request_id（僅本檔案使用）
        request_id = getattr(request.state, 'request_id', None)
        status_code = exc.context.get("status_code")
        endpoint = exc.context.get("endpoint")
        
        logger.error(
            "Laravel API 呼叫失敗",
            exc_info=True,
            extra={
                "path": request.url.path,
                "error_message": exc.message,
                "status_code": status_code,
                "endpoint": endpoint,
                "payload": safe_payload,
                "request_id": request_id
            }
        )
        response = JSONResponse(
            status_code=status_code or 400,
            content={"detail": exc.message},
        )
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(LoyaltyIntegrationError)
    async def loyalty_integration_error_handler(request: Request, exc: LoyaltyIntegrationError):
        """處理所有自訂的應用程式例外"""
        # 從request狀態獲取request_id（僅本檔案使用）
        request_id = getattr(request.state, 'request_id', None)
        # 清理context中的敏感資訊
        safe_context = redact_sensitive_data(exc.context) if exc.context is not None else None
        
        logger.error(
            f"應用程式錯誤: {exc.message}",
            exc_info=True,
            extra={
                "path": request.url.path,
                "error_type": type(exc).__name__,
                "context": safe_context,
                "request_id": request_id
            }
        )
        response = JSONResponse(
            status_code=400,
            content={"detail": exc.message},
        )
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """全域例外處理器，捕獲所有未處理的例外"""
        # 從request狀態獲取request_id（僅本檔案使用）
        request_id = getattr(request.state, 'request_id', None)
        
        logger.critical(
            "未處理的伺服器錯誤",
            exc_info=True,
            extra={
                "path": request.url.path,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "request_id": request_id
            }
        )
        response = JSONResponse(
            status_code=500,
            content={"detail": "內部伺服器錯誤"},
        )
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response

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