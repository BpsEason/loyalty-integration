from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from typing import Any, Callable, Dict, Set
from urllib.parse import urlencode

import websockets
from websockets.exceptions import ConnectionClosedError

from app.config import settings
from app.core.dependencies import laravel_client

logger = logging.getLogger(__name__)


class ReverbClient:
    """
    Laravel Reverb WebSocket Client
    連接 Laravel Reverb 伺服器，接收廣播事件並轉發給前端連線
    """

    def __init__(self):
        self.app_id = settings.reverb_app_id
        self.app_key = settings.reverb_app_key
        self.app_secret = settings.reverb_app_secret
        self.host = settings.reverb_host
        self.port = settings.reverb_port
        self.scheme = settings.reverb_scheme
        self.auth_endpoint = settings.reverb_auth_endpoint

        self.ws = None
        self.connected = False
        self.subscribed_channels: Set[str] = set()
        self.connection_retries = 0
        self.max_retries = 10
        self.retry_delay = 1.0

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
        """為私有頻道產生授權簽名"""
        string_to_sign = f"{socket_id}:{channel_name}"
        signature = hmac.new(
            self.app_secret.encode(),
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"{self.app_key}:{signature}"

    async def subscribe_to_channel(self, channel_name: str, socket_id: str):
        """訂閱特定頻道"""
        if channel_name in self.subscribed_channels:
            logger.info(f"Already subscribed to {channel_name}")
            return

        # 發送訂閱訊息
        subscribe_message = {
            'event': 'pusher:subscribe',
            'data': {
                'channel': channel_name,
                'auth': self.generate_auth_signature(channel_name, socket_id),
            }
        }

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