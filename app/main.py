from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from rich.console import Console

from app.core.dependencies import laravel_client
from app.websocket.reverb_client import reverb_client
from app.client.base import LaravelAPIError
from app.config import settings
from app.routers import (
    auth_router,
    customers_router,
    points_router,
    coupons_router,
    rewards_router,
    workflows_router,
    websocket_router,
)

console = Console()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await laravel_client.login()
        console.print("[green]Laravel API 登入成功，服務準備就緒[/green]")
        
        # 啟動 Reverb WebSocket 連線
        if settings.reverb_app_id and settings.reverb_app_key and settings.reverb_app_secret:
            asyncio.create_task(reverb_client.connect())
            console.print("[green]Reverb WebSocket 用戶端已啟動[/green]")
        else:
            console.print("[yellow]Reverb 設定未完整，WebSocket 功能已停用[/yellow]")
    except Exception as e:
        console.print(f"[red]啟動時登入失敗: {e}[/red]")
        raise
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Loyalty Integration API",
        description="外部整合層，串接 Laravel Multi-Tenant Loyalty Platform",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.exception_handler(LaravelAPIError)
    async def laravel_api_error_handler(request, exc: LaravelAPIError):
        return JSONResponse(
            status_code=exc.status_code or 400,
            content={"detail": exc.message},
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
            "laravel_connected": laravel_client._token is not None,
        }

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app


app = create_app()