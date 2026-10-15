"""
WebSocket頻道授權測試：驗證合法訂閱成功、跨租戶訂閱遭拒、冒用其他會員ID遭拒，以及缺少或無效認證遭拒
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import WebSocket, status, WebSocketDisconnect
from src.interfaces.fastapi.routers.websockets import websocket_endpoint, get_current_user_from_token


@pytest.mark.asyncio
async def test_legitimate_websocket_connection():
    """測試合法的WebSocket連線可以成功建立"""
    # 模擬WebSocket物件
    mock_websocket = Mock(spec=WebSocket)
    mock_websocket.headers.get.return_value = "Bearer valid_token"
    mock_websocket.accept = AsyncMock()
    mock_websocket.close = AsyncMock()
    # 模擬receive_text()會拋出WebSocketDisconnect來結束迴圈，避免無限等待
    mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
    
    # 模擬LaravelClient的me()方法回傳正確的使用者資訊
    with patch('src.interfaces.fastapi.routers.websockets.laravel_client') as mock_laravel_client:
        mock_clone = Mock()
        mock_laravel_client.clone.return_value = mock_clone
        mock_clone.set_token = Mock()
        mock_clone.set_tenant_id = Mock()
        # 模擬使用者是正確的租戶和會員
        mock_clone.me = AsyncMock(return_value={
            'id': 123,
            'tenant_id': 1,
            'is_admin': False
        })
        
        # 模擬reverb_client
        with patch('src.interfaces.fastapi.routers.websockets.reverb_client') as mock_reverb:
            mock_reverb.connected = True
            mock_reverb.socket_id = "test_socket_id"
            mock_reverb.ensure_connected = AsyncMock()
            mock_reverb.subscribe_to_channel = AsyncMock()
            mock_reverb.add_frontend_connection = Mock()
            mock_reverb.remove_frontend_connection = Mock()
            
            # 呼叫websocket端點，token參數由Dependency注入，測試時直接傳遞從header提取的token
            token = "valid_token"
            await websocket_endpoint(mock_websocket, tenant_id=1, member_id=123, token=token)
            
            # 驗證連線被接受
            mock_websocket.accept.assert_called_once()
            # 驗證不會被關閉
            mock_websocket.close.assert_not_called()


@pytest.mark.asyncio
async def test_cross_tenant_access_blocked():
    """測試跨租戶的存取嘗試會被拒絕"""
    mock_websocket = Mock(spec=WebSocket)
    mock_websocket.headers.get.return_value = "Bearer valid_token"
    mock_websocket.accept = AsyncMock()
    mock_websocket.close = AsyncMock()
    
    with patch('src.interfaces.fastapi.routers.websockets.laravel_client') as mock_laravel_client:
        mock_clone = Mock()
        mock_laravel_client.clone.return_value = mock_clone
        mock_clone.set_token = Mock()
        mock_clone.set_tenant_id = Mock()
        # 使用者屬於租戶1，但嘗試存取租戶2的頻道
        mock_clone.me = AsyncMock(return_value={
            'id': 123,
            'tenant_id': 1,
            'is_admin': False
        })
        
        with patch('src.interfaces.fastapi.routers.websockets.reverb_client') as mock_reverb:
            mock_reverb.connected = True
            mock_reverb.socket_id = "test_socket_id"
            mock_reverb.ensure_connected = AsyncMock()
            
            # 嘗試存取不同租戶的頻道
            token = "valid_token"
            await websocket_endpoint(mock_websocket, tenant_id=2, member_id=123, token=token)
            
            # 驗證連線被拒絕
            mock_websocket.close.assert_called_once_with(code=status.WS_1008_POLICY_VIOLATION)
            mock_websocket.accept.assert_not_called()


@pytest.mark.asyncio
async def test_impersonate_other_member_blocked():
    """測試冒用其他會員ID的存取嘗試會被拒絕"""
    mock_websocket = Mock(spec=WebSocket)
    mock_websocket.headers.get.return_value = "Bearer valid_token"
    mock_websocket.accept = AsyncMock()
    mock_websocket.close = AsyncMock()
    
    with patch('src.interfaces.fastapi.routers.websockets.laravel_client') as mock_laravel_client:
        mock_clone = Mock()
        mock_laravel_client.clone.return_value = mock_clone
        mock_clone.set_token = Mock()
        mock_clone.set_tenant_id = Mock()
        # 使用者是ID 123，但嘗試存取會員456的頻道
        mock_clone.me = AsyncMock(return_value={
            'id': 123,
            'tenant_id': 1,
            'is_admin': False
        })
        
        with patch('src.interfaces.fastapi.routers.websockets.reverb_client') as mock_reverb:
            mock_reverb.connected = True
            mock_reverb.socket_id = "test_socket_id"
            mock_reverb.ensure_connected = AsyncMock()
            
            # 嘗試存取其他會員的頻道
            token = "valid_token"
            await websocket_endpoint(mock_websocket, tenant_id=1, member_id=456, token=token)
            
            # 驗證連線被拒絕
            mock_websocket.close.assert_called_once_with(code=status.WS_1008_POLICY_VIOLATION)
            mock_websocket.accept.assert_not_called()


@pytest.mark.asyncio
async def test_admin_can_access_any_member():
    """測試管理員可以存取任何會員的頻道"""
    mock_websocket = Mock(spec=WebSocket)
    mock_websocket.headers.get.return_value = "Bearer admin_token"
    mock_websocket.accept = AsyncMock()
    mock_websocket.close = AsyncMock()
    # 模擬receive_text()會拋出WebSocketDisconnect來結束迴圈，避免無限等待
    mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
    
    with patch('src.interfaces.fastapi.routers.websockets.laravel_client') as mock_laravel_client:
        mock_clone = Mock()
        mock_laravel_client.clone.return_value = mock_clone
        mock_clone.set_token = Mock()
        mock_clone.set_tenant_id = Mock()
        # 管理員使用者
        mock_clone.me = AsyncMock(return_value={
            'id': 1,  # 管理員自己的ID
            'tenant_id': 1,
            'is_admin': True
        })
        
        with patch('src.interfaces.fastapi.routers.websockets.reverb_client') as mock_reverb:
            mock_reverb.connected = True
            mock_reverb.socket_id = "test_socket_id"
            mock_reverb.ensure_connected = AsyncMock()
            mock_reverb.subscribe_to_channel = AsyncMock()
            mock_reverb.add_frontend_connection = Mock()
            mock_reverb.remove_frontend_connection = Mock()
            
            # 管理員嘗試存取其他會員的頻道，應該成功
            token = "admin_token"
            await websocket_endpoint(mock_websocket, tenant_id=1, member_id=456, token=token)
            
            # 驗證連線被接受
            mock_websocket.accept.assert_called_once()
            mock_websocket.close.assert_not_called()


@pytest.mark.asyncio
async def test_missing_authorization_header():
    """測試缺少Authorization header的連線會被拒絕"""
    mock_websocket = Mock(spec=WebSocket)
    mock_websocket.headers.get.return_value = None  # 缺少header
    mock_websocket.close = AsyncMock()
    
    token = await get_current_user_from_token(mock_websocket)
    
    assert token is None
    mock_websocket.close.assert_called_once_with(code=status.WS_1008_POLICY_VIOLATION)


@pytest.mark.asyncio
async def test_invalid_token_format():
    """測試無效的token格式會被拒絕"""
    mock_websocket = Mock(spec=WebSocket)
    mock_websocket.headers.get.return_value = "InvalidTokenFormat"  # 格式錯誤
    mock_websocket.close = AsyncMock()
    
    token = await get_current_user_from_token(mock_websocket)
    
    assert token is None
    mock_websocket.close.assert_called_once_with(code=status.WS_1008_POLICY_VIOLATION)