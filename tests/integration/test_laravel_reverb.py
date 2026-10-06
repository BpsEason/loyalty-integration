import asyncio
import json
import pytest
import httpx2 as httpx
from src.infrastructure.websocket.reverb_client import ReverbClient
from src.config.settings import settings
import websockets
from src.infrastructure.clients.point import PointClient
from src.infrastructure.clients.customer import CustomerClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_laravel_reverb_full_flow():
    """
    完整測試 Laravel PointService → PointsUpdated → Laravel Reverb → FastAPI ReverbClient 流程
    必須真實連接到 127.0.0.1:8888 的 Reverb 伺服器
    絕不使用 skip，連接失敗或未收到事件則測試直接失敗
    """
    # 1. 初始化客戶端，確認 Laravel API 可連接
    from src.infrastructure.clients.base import LaravelClient
    laravel_client = LaravelClient()
    await laravel_client.login()
    # 取得登入使用者的真實資訊，確保使用正確的tenant和member ID
    user_info = await laravel_client.me()
    print(f"登入使用者資訊: {json.dumps(user_info, indent=2)}")
    
    # 從API回應中取得真實的tenant_id
    tenant_id = user_info.get('data', {}).get('tenant', {}).get('id') or 1
    laravel_client.set_tenant_id(tenant_id)
    print(f"使用的tenant_id: {tenant_id}")
    
    # 初始化CustomerClient，先嘗試取得現有Customer，如果沒有則建立新的
    customer_client = CustomerClient(laravel_client)
    customers = await customer_client.list(per_page=1)
    # 依照專案既有模式處理API回應結構（支援data是list或dict的兩種情況）
    data = customers.get("data", [])
    items = data.get("data", []) if isinstance(data, dict) else data
    
    if items and len(items) > 0:
        # 使用第一個存在的Customer
        customer = items[0]
        customer_id = customer['id']
        print(f"使用現有Customer: ID={customer_id}, 名稱={customer['name']}")
    else:
        # 沒有現有Customer，建立一個新的
        new_customer = await customer_client.create(
            name="Reverb Test Customer",
            email="reverb-test@example.com",
            phone="0912345678"
        )
        customer_id = new_customer['data']['id']
        print(f"建立新Customer: ID={customer_id}")
    
    # 使用Customer.id作為Reverb channel的member_id（符合Laravel channel contract要求）
    member_id = customer_id
    print(f"使用的member_id (Customer.id): {member_id}")
    
    point_client = PointClient(laravel_client)
    
    # 2. 建立 Reverb 客戶端並嘗試連接
    channel_name = f'tenant.{tenant_id}.member.{member_id}'
    full_channel_name = f'private-{channel_name}'
    
    reverb_client = ReverbClient(laravel_client)
    ws_url = reverb_client.get_ws_url()
    print(f"Connecting to Reverb: {ws_url}")
    
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
        
        # 4. 訂閱私有頻道，並等待訂閱成功事件
        # 傳遞tenant_id給subscribe_to_channel，讓broadcasting auth可以正確處理多租戶
        await reverb_client.subscribe_to_channel(full_channel_name, socket_id, tenant_id)
        print(f"Sent subscription request for channel: {full_channel_name}")
        
        # 嚴格等待 pusher_internal:subscription_succeeded 事件
        subscription_succeeded = False
        sub_start_time = asyncio.get_event_loop().time()
        all_messages = []
        
        while asyncio.get_event_loop().time() - sub_start_time < 5:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                message_data = json.loads(message)
                all_messages.append(message_data)
                
                print(f"\n=== Received WebSocket message during subscription ===")
                print(f"Event: {message_data.get('event')}")
                print(f"Channel: {message_data.get('channel')}")
                print(f"Data: {json.dumps(message_data.get('data'), indent=2)}")
                
                # 檢查是否是錯誤消息，如果有立即失敗
                if message_data.get('event') == 'pusher:error':
                    error_msg = f"❌ Pusher error during subscription: {json.dumps(message_data.get('data'), indent=2)}"
                    print(error_msg)
                    assert False, error_msg
                
                # 檢查是否訂閱成功，並驗證channel是否正確
                if message_data.get('event') == 'pusher_internal:subscription_succeeded':
                    received_channel = message_data.get('channel')
                    assert received_channel == full_channel_name, f"Subscription succeeded but channel mismatch: expected {full_channel_name}, got {received_channel}"
                    print(f"✅ Successfully subscribed to channel: {received_channel}")
                    subscription_succeeded = True
                    break
                    
            except asyncio.TimeoutError:
                continue
        
        # 如果訂閱超時，輸出所有收到的消息並失敗
        if not subscription_succeeded:
            print(f"\n=== Subscription timeout, all messages received ({len(all_messages)}): ===")
            for i, msg in enumerate(all_messages):
                print(f"{i+1}. Event: {msg.get('event')}, Channel: {msg.get('channel')}, Data: {json.dumps(msg.get('data'), indent=2)}")
            assert False, f"FAIL: Did not receive pusher_internal:subscription_succeeded within timeout. Channel: {full_channel_name}"
        
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
                all_messages.append(message_data)
                
                print(f"\n=== Received WebSocket message ===")
                print(f"Event: {message_data.get('event')}")
                print(f"Channel: {message_data.get('channel')}")
                print(f"Data: {json.dumps(message_data.get('data'), indent=2)}")
                
                # 繼續檢查錯誤消息，如果有立即失敗
                if message_data.get('event') == 'pusher:error':
                    error_msg = f"❌ Pusher error during event waiting: {json.dumps(message_data.get('data'), indent=2)}"
                    print(error_msg)
                    assert False, error_msg
                
                # 檢查是否是我們等待的事件
                if message_data.get('event') == 'points.updated':
                    event_data = json.loads(message_data['data']) if isinstance(message_data['data'], str) else message_data['data']
                    received_channel = message_data.get('channel')
                    
                    print(f"\n=== Received points.updated event ===")
                    print(f"Event: {message_data['event']}")
                    print(f"Channel: {received_channel}")
                    print(f"Payload: {json.dumps(event_data, indent=2)}")
                    
                    # 只處理符合本次交易條件的事件：正確的頻道、member_id 和 transaction_id
                    # 忽略其他舊的或不相關的 points.updated 事件，繼續等待正確的事件
                    if (
                        received_channel == full_channel_name
                        and event_data.get('member_id') == member_id
                        and event_data.get('transaction_id') == transaction_id
                    ):
                        print(f"\n=== Received correct event for current transaction ===")
                        # 驗證所有必要欄位都存在且正確
                        assert event_data['member_id'] == member_id
                        assert event_data['transaction_id'] == transaction_id
                        assert event_data['delta'] == 10
                        assert 'balance' in event_data
                        assert 'occurred_at' in event_data
                        
                        event_received = True
                        break
                    else:
                        # 記錄但忽略不符合條件的事件，繼續等待正確的事件
                        print(f"⚠️ Ignoring old/irrelevant points.updated event (waiting for our transaction)")
                        continue
                    
            except asyncio.TimeoutError:
                continue
        
        # 輸出所有收到的消息以用於調試
        print(f"\n=== All received WebSocket messages ({len(all_messages)}): ===")
        for i, msg in enumerate(all_messages):
            print(f"{i+1}. Event: {msg.get('event')}, Channel: {msg.get('channel')}")
        
        # 確保真的收到事件
        assert event_received, "FAIL: Did not receive points.updated event from Laravel Reverb within timeout"
        print("\n✅ INTEGRATION TEST PASSED: Full Laravel Reverb flow verified successfully")