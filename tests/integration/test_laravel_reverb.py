import asyncio
import json
import pytest
import httpx
from app.websocket.reverb_client import ReverbClient
from app.config import settings
import websockets
from app.client.point import PointClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_laravel_reverb_full_flow():
    """
    完整測試 Laravel PointService → PointsUpdated → Laravel Reverb → FastAPI ReverbClient 流程
    必須真實連接到 127.0.0.1:8888 的 Reverb 伺服器
    絕不使用 skip，連接失敗或未收到事件則測試直接失敗
    """
    # 1. 初始化客戶端，確認 Laravel API 可連接
    from app.client.base import LaravelClient
    laravel_client = LaravelClient()
    await laravel_client.login()
    point_client = PointClient(laravel_client)
    
    # 2. 建立 Reverb 客戶端並嘗試連接
    reverb_client = ReverbClient()
    ws_url = reverb_client.get_ws_url()
    print(f"Connecting to Reverb: {ws_url}")
    
    # 測試用的 channel 資訊：tenant 1, member 1
    tenant_id = 1
    member_id = 1
    channel_name = f'tenant.{tenant_id}.member.{member_id}'
    full_channel_name = f'private-{channel_name}'
    
    # 3. 連接 Reverb WebSocket，無法連接則測試失敗
    async with websockets.connect(ws_url) as websocket:
        reverb_client.ws = websocket
        
        # 等待連接建立
        connection_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        print(f"\n=== Raw WebSocket connection message: {connection_message} ===")
        connection_data = json.loads(connection_message)
        print(f"=== Parsed connection data: {json.dumps(connection_data, indent=2)} ===")
        assert connection_data['event'] == 'pusher:connection_established', f"Expected pusher:connection_established but got {connection_data['event']}. Full error: {json.dumps(connection_data, indent=2)}"
        socket_data = json.loads(connection_data['data'])
        socket_id = socket_data['socket_id']
        assert socket_id is not None
        print(f"Connected to Reverb successfully, socket ID: {socket_id}")
        
        # 4. 訂閱私有頻道（使用正確的認證簽名）
        await reverb_client.subscribe_to_channel(full_channel_name, socket_id)
        print(f"Subscribed to channel: {full_channel_name}")
        
        # 5. 實際呼叫 Laravel API 來觸發 PointsUpdated 事件（使用現有的 create_transaction 功能）
        print("Calling Laravel Point API to create transaction, which will trigger PointsUpdated event...")
        earn_response = await point_client.create_transaction(
            customer_id=member_id,
            transaction_type="earn",
            amount=10,
            description="Integration test point earn"
        )
        transaction_id = earn_response['data']['id']
        print(f"Point transaction created, ID: {transaction_id}")
        
        # 6. 等待接收真實的 points.updated 事件（最多等 15 秒）
        event_received = False
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < 15:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                message_data = json.loads(message)
                
                if message_data.get('event') == 'points.updated':
                    event_data = json.loads(message_data['data'])
                    received_channel = message_data.get('channel')
                    
                    print(f"\n=== Received real event from Laravel Reverb ===")
                    print(f"Event: {message_data['event']}")
                    print(f"Channel: {received_channel}")
                    print(f"Payload: {json.dumps(event_data, indent=2)}")
                    
                    # 驗證所有必要欄位都存在且正確
                    assert received_channel == full_channel_name
                    assert event_data['member_id'] == member_id
                    assert event_data['transaction_id'] == transaction_id
                    assert event_data['delta'] == 10
                    assert 'balance' in event_data
                    assert 'occurred_at' in event_data
                    
                    event_received = True
                    break
                    
            except asyncio.TimeoutError:
                continue
        
        # 確保真的收到事件
        assert event_received, "FAIL: Did not receive points.updated event from Laravel Reverb within timeout"
        print("\n✅ INTEGRATION TEST PASSED: Full Laravel Reverb flow verified successfully")