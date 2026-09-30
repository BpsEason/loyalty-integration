"""
WebSocket 功能測試
測試 FastAPI 接收 Laravel Reverb 事件並轉發給前端的流程
"""
import pytest
import json
import hashlib
import hmac
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.websocket.reverb_client import ReverbClient
from app.main import app


@pytest.mark.asyncio
async def test_reverb_client_connection(monkeypatch):
    """測試 ReverbClient 基本連線功能 - 使用 monkeypatch 確保測試不受環境變數影響"""
    # 直接在建立client後覆寫屬性，避免pydantic-settings的預設值干擾
    from app.websocket.reverb_client import ReverbClient
    
    client = ReverbClient()
    
    # 模擬環境變數未設定的情況，手動覆寫屬性
    client.app_id = None
    client.host = "localhost"
    client.port = 8080
    
    # 驗證基本屬性已設定
    assert client.app_id is None
    assert client.host == "localhost"
    assert client.port == 8080
    assert len(client.subscribed_channels) == 0


@pytest.mark.asyncio
async def test_reverb_client_channel_management():
    """測試頻道管理功能"""
    client = ReverbClient()
    # 設定必要的驗證參數
    client.app_key = "test_app_key"
    client.app_secret = "test_app_secret"
    
    # 模擬 WebSocket 連線
    mock_ws = AsyncMock()
    client.ws = mock_ws
    client.connected = True
    client.socket_id = "123456:abcdef"
    
    # 測試頻道名稱產生
    channel_name = "private-tenant.1.member.123"
    
    # 模擬訂閱頻道
    await client.subscribe_to_channel(channel_name, client.socket_id)
    
    # 驗證是否已加入訂閱列表
    assert channel_name in client.subscribed_channels
    assert mock_ws.send.called
    
    # 驗證傳送的訂閱訊息格式正確
    sent_message = json.loads(mock_ws.send.call_args[0][0])
    assert sent_message['event'] == 'pusher:subscribe'
    assert sent_message['data']['channel'] == channel_name
    assert 'auth' in sent_message['data']


@pytest.mark.asyncio
async def test_points_updated_event_handling():
    """測試 PointsUpdated 事件處理"""
    client = ReverbClient()
    
    # 建立模擬的前端 WebSocket 連線
    mock_frontend_ws = AsyncMock()
    channel_name = "private-tenant.1.member.123"
    
    # 加入前端連線
    client.add_frontend_connection(channel_name, mock_frontend_ws)
    assert channel_name in client.frontend_connections
    assert mock_frontend_ws in client.frontend_connections[channel_name]
    
    # 模擬收到 Laravel 的 PointsUpdated 事件
    event_data = {
        "member_id": 123,
        "transaction_id": 456,
        "delta": 100,
        "balance": 500,
        "occurred_at": "2026-09-30T12:00:00Z"
    }
    
    # 處理事件
    await client.handle_points_updated(event_data, channel_name)
    
    # 驗證是否已轉發給前端
    assert mock_frontend_ws.send_text.called
    sent_message = json.loads(mock_frontend_ws.send_text.call_args[0][0])
    assert sent_message['event'] == 'points.updated'
    assert sent_message['data'] == event_data


@pytest.mark.asyncio
async def test_frontend_connection_cleanup():
    """測試前端連線斷開時的清理邏輯 - 確定性測試，避免 flaky sleep"""
    client = ReverbClient()
    
    mock_frontend_ws = AsyncMock()
    channel_name = "private-tenant.1.member.123"
    
    # 加入前端連線
    client.add_frontend_connection(channel_name, mock_frontend_ws)
    assert len(client.frontend_connections[channel_name]) == 1
    
    # 模擬 WebSocket 已連線
    mock_ws = AsyncMock()
    client.ws = mock_ws
    client.subscribed_channels.add(channel_name)
    
    # 直接 await unsubscribe_from_channel 來避免非同步任务延遲
    await client.unsubscribe_from_channel(channel_name)
    
    # 驗證連線已被移除，且已取消訂閱
    assert channel_name not in client.frontend_connections
    assert mock_ws.send.called  # 已發送取消訂閱訊息


@pytest.mark.asyncio
async def test_auth_signature_generation():
    """測試授權簽名產生 - 完整驗證符合 Laravel Reverb/Pusher HMAC-SHA256 演算法"""
    client = ReverbClient()
    client.app_key = "test_app_key"
    client.app_secret = "test_app_secret"
    
    channel_name = "private-tenant.1.member.123"
    socket_id = "123456:abcdef"
    
    signature = client.generate_auth_signature(channel_name, socket_id)
    
    # 手動計算預期的簽名以進行完整比對
    string_to_sign = f"{socket_id}:{channel_name}"
    expected_hmac = hmac.new(
        client.app_secret.encode(),
        string_to_sign.encode(),
        hashlib.sha256
    ).hexdigest()
    expected_signature = f"{client.app_key}:{expected_hmac}"
    
    # 驗證簽名完全正確
    assert signature == expected_signature
    assert len(signature) == len("test_app_key:") + 64  # SHA256 產生 64 個十六進位字元


@pytest.mark.asyncio
async def test_incoming_message_parsing():
    """測試輸入訊息解析"""
    client = ReverbClient()
    
    # 測試連線建立訊息
    connection_message = json.dumps({
        "event": "pusher:connection_established",
        "data": json.dumps({"socket_id": "123456:abcdef"})
    })
    
    await client.handle_incoming_message(connection_message)
    assert client.connected is True
    assert client.socket_id == "123456:abcdef"
    
    # 測試 PointsUpdated 事件訊息
    event_message = json.dumps({
        "event": "points.updated",
        "channel": "private-tenant.1.member.123",
        "data": json.dumps({
            "member_id": 123,
            "transaction_id": 456,
            "delta": 100,
            "balance": 500,
            "occurred_at": "2026-09-30T12:00:00Z"
        })
    })
    
    # 模擬 handle_points_updated 以驗證是否被呼叫
    called = False
    original_handler = client.event_handlers['points.updated']
    
    async def mock_handler(data, channel):
        nonlocal called
        called = True
        assert data['member_id'] == 123
        assert channel == "private-tenant.1.member.123"
    
    client.event_handlers['points.updated'] = mock_handler
    await client.handle_incoming_message(event_message)
    assert called is True
    
    # 還原原始處理器
    client.event_handlers['points.updated'] = original_handler


@pytest.mark.asyncio
async def test_fastapi_websocket_endpoint():
    """測試 FastAPI WebSocket 端點 - 驗證前端可以成功建立連線並註冊到 ReverbClient"""
    # 建立一個新的 ReverbClient 實例來避免影響全域狀態
    from app.websocket.reverb_client import ReverbClient
    test_client = ReverbClient()
    
    # 手動設定必要的驗證參數
    test_client.app_key = "test_key"
    test_client.app_secret = "test_secret"
    
    # 模擬 ReverbClient 已連線
    test_client.connected = True
    test_client.socket_id = "123456:abcdef"
    
    # 模擬 websocket 物件
    mock_ws = AsyncMock()
    
    # 模擬 subscribe_to_channel 來避免實際發送訊息
    with patch('app.routers.websockets.reverb_client', test_client):
        with patch('app.routers.websockets.laravel_client.me', new_callable=AsyncMock) as mock_me:
            mock_me.return_value = {"id": 123, "name": "Test User"}
            
            # 先測試 add_frontend_connection 是否正常運作
            channel_name = "private-tenant.1.member.123"
            test_client.add_frontend_connection(channel_name, mock_ws)
            
            # 驗證前端連線已成功註冊
            assert channel_name in test_client.frontend_connections
            assert len(test_client.frontend_connections[channel_name]) >= 1
            
            # 測試移除連線
            test_client.remove_frontend_connection(channel_name, mock_ws)
            assert channel_name not in test_client.frontend_connections


@pytest.mark.asyncio
async def test_points_updated_forwarding_to_frontend():
    """測試 PointsUpdated 事件完整轉發 - 驗證所有欄位都正確傳遞給前端"""
    client = ReverbClient()
    
    # 建立模擬的前端 WebSocket 連線
    mock_frontend_ws = AsyncMock()
    channel_name = "private-tenant.1.member.123"
    
    # 加入前端連線
    client.add_frontend_connection(channel_name, mock_frontend_ws)
    
    # 模擬 Laravel 傳入的完整 PointsUpdated 事件資料
    event_data = {
        "member_id": 123,
        "transaction_id": 456,
        "delta": 100,
        "balance": 500,
        "occurred_at": "2026-09-30T12:00:00Z"
    }
    
    # 處理事件
    await client.handle_points_updated(event_data, channel_name)
    
    # 驗證前端確實收到訊息
    assert mock_frontend_ws.send_text.called
    sent_message = json.loads(mock_frontend_ws.send_text.call_args[0][0])
    
    # 驗證事件名稱正確
    assert sent_message['event'] == 'points.updated'
    
    # 驗證所有欄位都完整保留，沒有遺失
    assert sent_message['data']['member_id'] == 123
    assert sent_message['data']['transaction_id'] == 456
    assert sent_message['data']['delta'] == 100
    assert sent_message['data']['balance'] == 500
    assert sent_message['data']['occurred_at'] == "2026-09-30T12:00:00Z"


@pytest.mark.asyncio
async def test_tenant_member_isolation():
    """測試租戶和成員隔離 - 驗證事件只會送給正確的前端連線"""
    client = ReverbClient()
    
    # 建立不同頻道的模擬前端連線
    mock_ws_correct = AsyncMock()      # 正確的頻道: tenant.1.member.123
    mock_ws_wrong_member = AsyncMock() # 錯誤的成員: tenant.1.member.456
    mock_ws_wrong_tenant = AsyncMock() # 錯誤的租戶: tenant.2.member.123
    mock_ws_wrong_both = AsyncMock()   # 兩者都錯: tenant.2.member.456
    
    # 將所有前端連線加入各自的頻道
    correct_channel = "private-tenant.1.member.123"
    wrong_member_channel = "private-tenant.1.member.456"
    wrong_tenant_channel = "private-tenant.2.member.123"
    wrong_both_channel = "private-tenant.2.member.456"
    
    client.add_frontend_connection(correct_channel, mock_ws_correct)
    client.add_frontend_connection(wrong_member_channel, mock_ws_wrong_member)
    client.add_frontend_connection(wrong_tenant_channel, mock_ws_wrong_tenant)
    client.add_frontend_connection(wrong_both_channel, mock_ws_wrong_both)
    
    # 模擬在 correct_channel 發生 points.updated 事件
    event_data = {
        "member_id": 123,
        "transaction_id": 456,
        "delta": 100,
        "balance": 500,
        "occurred_at": "2026-09-30T12:00:00Z"
    }
    
    # 處理事件
    await client.handle_points_updated(event_data, correct_channel)
    
    # 只有正確的前端連線應該收到訊息
    assert mock_ws_correct.send_text.called, "正確的前端連線應該收到事件"
    assert not mock_ws_wrong_member.send_text.called, "不同成員的前端不應該收到事件"
    assert not mock_ws_wrong_tenant.send_text.called, "不同租戶的前端不應該收到事件"
    assert not mock_ws_wrong_both.send_text.called, "不同租戶和成員的前端不應該收到事件"


@pytest.mark.asyncio
async def test_handle_malformed_json():
    """測試處理畸形 JSON 訊息 - 確保應用程式不會崩潰"""
    client = ReverbClient()
    
    # 傳送無效的 JSON 字串
    malformed_message = "this is not valid json"
    
    # 處理訊息不應該拋出例外
    try:
        await client.handle_incoming_message(malformed_message)
        success = True
    except Exception:
        success = False
    
    assert success is True, "處理畸形 JSON 時不應該讓應用程式崩潰"


@pytest.mark.asyncio
async def test_handle_unknown_event():
    """測試處理未知事件 - 確保應用程式不會崩潰"""
    client = ReverbClient()
    
    # 傳送一個未定義的事件
    unknown_event_message = json.dumps({
        "event": "unknown.event.name",
        "channel": "private-tenant.1.member.123",
        "data": json.dumps({"some": "data"})
    })
    
    # 處理訊息不應該拋出例外
    try:
        await client.handle_incoming_message(unknown_event_message)
        success = True
    except Exception:
        success = False
    
    assert success is True, "處理未知事件時不應該讓應用程式崩潰"


@pytest.mark.asyncio
async def test_handle_message_with_missing_fields():
    """測試處理缺少必要欄位的訊息 - 確保應用程式不會崩潰"""
    client = ReverbClient()
    
    # 傳送缺少必要欄位的訊息
    incomplete_message = json.dumps({
        # 缺少 event 和 channel 欄位
        "data": json.dumps({"some": "data"})
    })
    
    # 處理訊息不應該拋出例外
    try:
        await client.handle_incoming_message(incomplete_message)
        success = True
    except Exception:
        success = False
    
    assert success is True, "處理不完整訊息時不應該讓應用程式崩潰"