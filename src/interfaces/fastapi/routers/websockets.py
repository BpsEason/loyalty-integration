from __future__ import annotations

import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
from typing import Annotated

from src.infrastructure.websocket.reverb_client import reverb_client
from src.core.dependencies import laravel_client

logger = logging.getLogger(__name__)

websocket_router = APIRouter(prefix="/ws", tags=["websockets"])


async def get_current_user_from_token(websocket: WebSocket):
    """從 WebSocket 連線的 Authorization header 取得目前使用者"""
    auth_header = websocket.headers.get('authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    token = auth_header.split(' ')[1]
    # 暫時儲存 token 以便後續請求使用
    return token


@websocket_router.websocket("/points/{tenant_id}/{member_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    tenant_id: int,
    member_id: int,
    token: Annotated[str | None, Depends(get_current_user_from_token)]
):
    """
    前端 WebSocket 連線端點
    格式: /ws/points/{tenant_id}/{member_id}
    
    範例: /ws/points/1/123
    """
    if not token:
        return

    # 設定 Laravel client 的 token 以進行驗證
    original_token = laravel_client._token
    laravel_client.set_token(token)

    try:
        # 驗證使用者是否有權限存取這個頻道（對應 Laravel routes/channels.php 的邏輯）
        try:
            # 先驗證 token 有效性
            await laravel_client.me()
        except Exception as e:
            logger.warning("WebSocket連線使用了無效的token", exc_info=True, extra={"tenant_id": tenant_id, "member_id": member_id})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # 接受連線
        await websocket.accept()
        logger.info("建立新的前端WebSocket連線", extra={"tenant_id": tenant_id, "member_id": member_id})

        # 對應 Laravel 的頻道名稱格式: private-tenant.{tenantId}.member.{memberId}
        channel_name = f"private-tenant.{tenant_id}.member.{member_id}"

        # 確保 Reverb 用戶端已連線
        await reverb_client.ensure_connected()

        # 等待 Reverb 連線建立並取得 socket_id
        wait_attempts = 0
        while not reverb_client.connected and wait_attempts < 30:
            await asyncio.sleep(0.5)
            wait_attempts += 1

        if not reverb_client.connected or not hasattr(reverb_client, 'socket_id'):
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

        # 訂閱頻道
        await reverb_client.subscribe_to_channel(channel_name, reverb_client.socket_id)

        # 將前端連線加入頻道的連線列表
        reverb_client.add_frontend_connection(channel_name, websocket)

        # 持續接收前端的訊息（主要是保持連線活著，處理 ping/pong）
        try:
            while True:
                data = await websocket.receive_text()
                # 可以處理前端發送的控制訊息
                try:
                    message = json.loads(data)
                    if message.get('type') == 'ping':
                        await websocket.send_text(json.dumps({'type': 'pong'}))
                except json.JSONDecodeError:
                    pass

        except WebSocketDisconnect:
            logger.info("前端WebSocket連線中斷", extra={"tenant_id": tenant_id, "member_id": member_id})
            reverb_client.remove_frontend_connection(channel_name, websocket)

    finally:
        # 恢復原本的 token
        laravel_client.set_token(original_token)