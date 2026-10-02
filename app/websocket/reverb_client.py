from __future__ import annotations

import asyncio
import json
import logging
import hashlib
import hmac
from typing import Any, Callable, Dict, Set
from urllib.parse import urlencode
import httpx

import websockets
from websockets.exceptions import ConnectionClosedError

from app.config import settings
from app.client.base import LaravelClient

logger = logging.getLogger(__name__)


class ReverbClient:
    """
    Laravel Reverb WebSocket Client
    連接 Laravel Reverb 伺服器，接收廣播事件並轉發給前端連線
    """

    def __init__(self, laravel_client: LaravelClient | None = None):
        self.app_id = settings.reverb_app_id
        self.app_key = settings.reverb_app_key
        self.app_secret = settings.reverb_app_secret
        self.host = settings.reverb_host
        self.port = settings.reverb_port
        self.scheme = settings.reverb_scheme
        self.auth_endpoint = settings.reverb_auth_endpoint

        self.laravel_client = laravel_client
        self.ws = None
        self.connected = False
        self.subscribed_channels: Set[str] = set()
        self.connection_retries = 0
        self.max_retries = 10
        self.retry_delay = 1.0
        self.socket_id: str | None = None

        # 前端連線管理：{channel_name: {websocket_connection1, websocket_connection2, ...}}
        self.frontend_connections: Dict[str, Set[Any]] = {}

        # 事件處理器
        self.event_handlers: Dict[str, Callable] = {
            'points.updated': self.handle_points_updated,
        }

    def get_ws_url(self) -> str:
        """產生 Reverb WebSocket 連線 URL"""
        params = {
            'protocol': 'pusher',
            'client': 'loyalty-integration',
            'version': '7.0.0',
        }
        query_string = urlencode(params)
        return f"{self.scheme}://{self.host}:{self.port}/app/{self.app_key}?{query_string}"

    def generate_auth_signature(self, channel_name: str, socket_id: str) -> str:
        """
        產生 Pusher/Reverb 相容的授權簽名 - 維持向後相容性
        當沒有提供 LaravelClient 時，可以使用這個方法生成客戶端簽名
        """
        string_to_sign = f"{socket_id}:{channel_name}"
        hmac_signature = hmac.new(
            self.app_secret.encode(),
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"{self.app_key}:{hmac_signature}"

    async def get_broadcasting_auth(self, channel_name: str, socket_id: str, tenant_id: int | None = None) -> str:
        """
        向 Laravel /broadcasting/auth 端點請求授權，獲取合法的auth簽名
        遵循Laravel官方的broadcasting認證流程
        """
        if not self.laravel_client or not self.laravel_client._token:
            raise Exception("LaravelClient must be authenticated before subscribing to private channels via Laravel auth")

        # 準備要傳送給Laravel broadcasting auth的參數
        payload = {
            'socket_id': socket_id,
            'channel_name': channel_name
        }

        # 複製LaravelClient的headers並加入X-Tenant-ID（如果有提供）
        headers = self.laravel_client.headers.copy()
        # broadcasting auth需要使用form-data格式，所以覆蓋Content-Type
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        # 只要tenant_id不是None就加入X-Tenant-ID header（包括0這個合法值）
        if tenant_id is not None:
            headers['X-Tenant-ID'] = str(tenant_id)

        try:
            # 輸出除錯資訊：送出的請求詳情
            logger.info(f"=== Broadcasting auth request details ===")
            logger.info(f"URL: {self.auth_endpoint}")
            logger.info(f"Payload: {payload}")
            # 只輸出非敏感的headers資訊
            safe_headers = {k: v for k, v in headers.items() if k not in ['Authorization']}
            if 'Authorization' in headers:
                safe_headers['Authorization'] = 'Bearer <token>'  # 隱藏實際token
            logger.info(f"Headers: {safe_headers}")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self.auth_endpoint,
                    data=payload,  # Laravel的broadcasting auth接收form-data格式
                    headers=headers
                )
                # 輸出回應詳情
                logger.info(f"=== Broadcasting auth response details ===")
                logger.info(f"HTTP Status: {resp.status_code}")
                logger.info(f"Response body: {resp.text}")
                resp.raise_for_status()
                auth_data = resp.json()
                logger.info(f"Successfully obtained broadcasting auth for channel {channel_name}")
                return auth_data['auth']
        except httpx.HTTPError as e:
            logger.error(f"Failed to get broadcasting auth: {e}, Response: {resp.text if 'resp' in locals() else 'N/A'}")
            raise Exception(f"Broadcasting auth failed for channel {channel_name}: {str(e)}")

    async def subscribe_to_channel(self, channel_name: str, socket_id: str, tenant_id: int | None = None):
        """訂閱特定頻道 - 支援兩種認證方式：
        1. 如果有提供laravel_client，使用Laravel /broadcasting/auth 進行授權（生產環境使用）
        2. 如果沒有提供laravel_client，使用客戶端生成簽名的方式（向後相容性，單元測試使用）
        """
        if channel_name in self.subscribed_channels:
            logger.info(f"Already subscribed to {channel_name}")
            return

        # 處理私有頻道
        auth = None
        if channel_name.startswith('private-'):
            # 檢查是否有laravel_client可用，如果有，使用Laravel的broadcasting auth
            if self.laravel_client and self.laravel_client._token:
                # 傳送完整的channel_name給Laravel broadcasting auth（包含private-前綴）
                # Laravel的broadcasting auth需要完整的頻道名稱來進行認證
                auth = await self.get_broadcasting_auth(channel_name, socket_id, tenant_id)
            else:
                # 沒有laravel_client，使用傳統的客戶端生成簽名方式以維持向後相容性
                auth = self.generate_auth_signature(channel_name, socket_id)
                logger.info(f"Using client-side auth signature for channel {channel_name}")
        else:
            # 公共頻道不需要授權
            auth = None

        # 發送訂閱訊息 - 符合Pusher/Reverb協議
        subscribe_message = {
            'event': 'pusher:subscribe',
            'data': {
                'channel': channel_name,
            }
        }

        # 如果有auth，加入到訂閱請求中
        if auth:
            subscribe_message['data']['auth'] = auth

        if self.ws:
            await self.ws.send(json.dumps(subscribe_message))
            self.subscribed_channels.add(channel_name)
            logger.info(f"Subscribed to channel: {channel_name}")

    async def unsubscribe_from_channel(self, channel_name: str):
        """取消訂閱特定頻道"""
        if channel_name not in self.subscribed_channels:
            return

        if self.ws:
            unsubscribe_message = {
                'event': 'pusher:unsubscribe',
                'data': {
                    'channel': channel_name,
                }
            }
            await self.ws.send(json.dumps(unsubscribe_message))
            self.subscribed_channels.remove(channel_name)
            logger.info(f"Unsubscribed from channel: {channel_name}")

        # 清理前端連線
        if channel_name in self.frontend_connections:
            del self.frontend_connections[channel_name]

    def add_frontend_connection(self, channel_name: str, websocket):
        """加入前端連線到指定頻道"""
        if channel_name not in self.frontend_connections:
            self.frontend_connections[channel_name] = set()
        self.frontend_connections[channel_name].add(websocket)
        logger.info(f"Added frontend connection to {channel_name}, total: {len(self.frontend_connections[channel_name])}")

    def remove_frontend_connection(self, channel_name: str, websocket):
        """從頻道中移除前端連線"""
        if channel_name in self.frontend_connections:
            self.frontend_connections[channel_name].discard(websocket)
            if not self.frontend_connections[channel_name]:
                # 如果沒有前端連線了，取消訂閱這個頻道
                asyncio.create_task(self.unsubscribe_from_channel(channel_name))
                del self.frontend_connections[channel_name]
            logger.info(f"Removed frontend connection from {channel_name}")

    async def handle_points_updated(self, data: dict, channel_name: str):
        """處理 PointsUpdated 事件，轉發給所有前端連線"""
        if channel_name not in self.frontend_connections:
            return

        # 廣播給所有連線到這個頻道的前端
        message = json.dumps({
            'event': 'points.updated',
            'data': data
        })

        # 建立要移除的失效連線列表
        to_remove = []
        for websocket in self.frontend_connections[channel_name]:
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send message to frontend: {e}")
                to_remove.append(websocket)

        # 移除失效的連線
        for websocket in to_remove:
            self.remove_frontend_connection(channel_name, websocket)

    async def handle_incoming_message(self, message: str):
        """處理從 Reverb 收到的訊息"""
        try:
            data = json.loads(message)
            event_name = data.get('event')
            channel_name = data.get('channel')

            if event_name == 'pusher:connection_established':
                self.connected = True
                self.connection_retries = 0
                logger.info("Connected to Reverb server successfully")

                # 解析 socket_id
                connection_data = json.loads(data['data'])
                self.socket_id = connection_data.get('socket_id')
                logger.info(f"Socket ID: {self.socket_id}")

            elif event_name == 'pusher:error':
                logger.error(f"Pusher error: {data['data']}")

            elif event_name in self.event_handlers:
                # 處理應用層事件
                event_data = json.loads(data['data'])
                await self.event_handlers[event_name](event_data, channel_name)
                logger.debug(f"Handled event {event_name} on channel {channel_name}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}, message: {message}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def connect(self):
        """連線到 Reverb 伺服器，包含重連邏輯"""
        while self.connection_retries < self.max_retries:
            try:
                logger.info(f"Connecting to Reverb server: {self.get_ws_url()}")

                async with websockets.connect(self.get_ws_url()) as websocket:
                    self.ws = websocket
                    logger.info("WebSocket connection established")

                    # 持續接收訊息
                    async for message in websocket:
                        await self.handle_incoming_message(message)

            except ConnectionClosedError as e:
                logger.warning(f"WebSocket connection closed: {e}")
                self.connected = False
                self.connection_retries += 1

            except Exception as e:
                logger.error(f"Connection error: {e}")
                self.connected = False
                self.connection_retries += 1

            # 重連前等待
            if self.connection_retries < self.max_retries:
                wait_time = self.retry_delay * (2 ** (self.connection_retries - 1))  # 指數退避
                logger.info(f"Retrying connection in {wait_time}s... (attempt {self.connection_retries}/{self.max_retries})")
                await asyncio.sleep(wait_time)
            else:
                logger.error("Max retries reached, giving up connection to Reverb")
                break

    async def ensure_connected(self):
        """確保已連線，如果未連線則嘗試連線"""
        if not self.connected and self.ws is None:
            asyncio.create_task(self.connect())


# 全域 Reverb 客戶端實例
reverb_client = ReverbClient()