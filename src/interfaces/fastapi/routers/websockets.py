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

    # 建立WebSocket專用的客戶端副本，不修改全局狀態
    request_client = laravel_client.clone()
    request_client.set_token(token)
    request_client.set_tenant_id(tenant_id)

    try:
        # 驗證使用者是否有權限存取這個頻道
        try:
            # 先驗證 token 有效性，取得目前使用者資訊
            user_info = await request_client.me()
            logger.debug("取得使用者資訊", extra={"user_info": user_info, "request_tenant": tenant_id, "request_member": member_id})
            
            # 第一層驗證：驗證使用者屬於正確的租戶
            # 從使用者資訊中提取租戶資訊，這裡假設user_info中有tenant_id欄位
            # 如果Laravel回傳的使用者資訊格式不同，可能需要調整這裡的欄位名稱
            user_tenant_id = user_info.get('tenant_id')
            if user_tenant_id is not None and str(user_tenant_id) != str(tenant_id):
                logger.warning("WebSocket跨租戶存取嘗試被阻止", 
                             extra={"user_tenant": user_tenant_id, "request_tenant": tenant_id, "member_id": member_id})
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
                
            # 第二層驗證：驗證使用者確實有權存取這個會員的頻道
            # 檢查是否是使用者本人，或者使用者有權限存取其他會員的資料
            user_id = user_info.get('id')
            # 這裡可以根據業務需求調整授權邏輯：
            # - 使用者只能存取自己的member_id對應的頻道
            # - 或者管理員可以存取所有會員的頻道
            is_authorized = False
            # 情況1：使用者存取自己的頻道
            if str(user_id) == str(member_id):
                is_authorized = True
            # 情況2：如果是管理員，可以存取所有頻道（可以根據roles或permissions判斷）
            elif user_info.get('is_admin') or user_info.get('role') == 'admin':
                is_authorized = True
            # 可以在此加入其他授權條件...
            
            if not is_authorized:
                logger.warning("WebSocket未授權的會員頻道存取嘗試被阻止", 
                             extra={"user_id": user_id, "request_member": member_id, "tenant_id": tenant_id})
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
                
        except Exception as e:
            logger.warning("WebSocket連線驗證失敗", exc_info=True, extra={"tenant_id": tenant_id, "member_id": member_id})
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

        # 訂閱頻道 - 傳遞tenant_id以進行租戶隔離驗證，使用隔離的請求客戶端
        await reverb_client.subscribe_to_channel(channel_name, reverb_client.socket_id, tenant_id, request_client)

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
    except Exception as e:
        logger.error("WebSocket連線發生未預期的錯誤", exc_info=True, extra={"tenant_id": tenant_id, "member_id": member_id})
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass