import asyncio
from app.client.base import LaravelClient, LaravelAPIError
from app.client.reward import RewardClient


async def test_1_list_reward_grants():
    """Test 1 - List Reward Grants - 取得客戶的獎勵發放記錄"""
    client = LaravelClient()
    await client.login()
    
    reward_client = RewardClient(client)
    # 使用測試用的 customer_id，請依實際環境調整
    customer_id = 1
    
    try:
        result = await reward_client.list_reward_grants(customer_id)
        print("✓ List reward grants successful")
        print(f"  Data: {result}")
        assert isinstance(result, dict)
        return True
    except LaravelAPIError as e:
        print(f"✗ List reward grants failed: {e.message} (status: {e.status_code})")
        raise


async def test_2_grant_reward():
    """Test 2 - Grant Reward - 實際發放獎勵測試"""
    client = LaravelClient()
    # 使用coffee租戶的管理員登入，才能存取該租戶的客戶和獎勵
    await client.login(email="admin-c@example.com", password="password123")
    
    reward_client = RewardClient(client)
    # 使用從資料庫查詢到的有效ID (均屬於coffee租戶)
    customer_id = 10  # Customer C5 (Demo Coffee租戶，可用於Test 2)
    campaign_reward_id = 1  # 早安咖啡優惠的50點獎勵 (active且enabled=true)
    
    try:
        result = await reward_client.grant_reward(
            customer_id,
            campaign_reward_id,
            quantity=1,
            reference="test-grant-2026",
            description="Integration test reward grant",
            idempotency_key="test-idempotency-key-20260923-001"
        )
        print("✓ Grant reward successful")
        print(f"  Data: {result}")
        assert isinstance(result, dict)
        assert result.get('data', {}).get('status') in ['granted', 'already_granted']
        return True
    except LaravelAPIError as e:
        print(f"✗ Grant reward failed: {e.message} (status: {e.status_code})")
        raise


async def test_3_same_idempotency_key():
    """Test 3 - Same Idempotency-Key - 測試冪等性，相同 Key 不應重複建立"""
    client = LaravelClient()
    # 使用coffee租戶的管理員登入，才能存取該租戶的客戶和獎勵
    await client.login(email="admin-c@example.com", password="password123")
    
    reward_client = RewardClient(client)
    customer_id = 8  # Customer C3 (Demo Coffee租戶，尚未獲得過campaign_reward_id=1)
    campaign_reward_id = 1  # 早安咖啡優惠的50點獎勵 (active且enabled=true)
    same_idempotency_key = "test-idempotency-key-20260923-002"  # 使用固定的冪等性key
    
    try:
        # 第一次請求 - 應該成功發放
        print("  第一次發送請求 (使用相同的Idempotency-Key)...")
        first_result = await reward_client.grant_reward(
            customer_id,
            campaign_reward_id,
            quantity=1,
            reference="test-idempotency-first",
            description="First request with idempotency key",
            idempotency_key=same_idempotency_key
        )
        print("  ✓ 第一次請求成功")
        
        # 第二次請求 - 使用完全相同的Idempotency-Key和完全相同的請求內容
        print("  第二次發送請求 (使用相同的Idempotency-Key)...")
        second_result = await reward_client.grant_reward(
            customer_id,
            campaign_reward_id,
            quantity=1,
            reference="test-idempotency-first",  # 必須與第一次完全相同，確保request_hash一致
            description="First request with idempotency key",  # 必須與第一次完全相同
            idempotency_key=same_idempotency_key
        )
        print("  ✓ 第二次請求成功 (冪等性驗證通過)")
        print(f"  第一次回應: {first_result}")
        print(f"  第二次回應: {second_result}")
        
        # 驗證兩次請求返回的是同一個資源（冪等性）
        assert first_result.get('data', {}).get('id') == second_result.get('data', {}).get('id'), "兩次請求應返回相同的RewardGrant ID"
        return True
    except LaravelAPIError as e:
        print(f"✗ Idempotency test failed: {e.message} (status: {e.status_code})")
        raise


async def test_4_different_idempotency_keys():
    """Test 4 - Different Idempotency-Key - 不同 Key 應視為不同交易"""
    print("\n⚠ Test 4 - Different Idempotency-Key: SKIPPED (requires valid test data to allow multiple grants)")
    return "SKIPPED"


async def test_5_invalid_request():
    """Test 5 - Invalid Request - 測試無效的請求"""
    client = LaravelClient()
    await client.login()
    
    reward_client = RewardClient(client)
    customer_id = 999999  # 不存在的客戶
    
    try:
        await reward_client.list_reward_grants(customer_id)
        assert False, "Should have raised LaravelAPIError"
    except LaravelAPIError as e:
        print(f"✓ Invalid customer correctly returned error: {e.message} (status: {e.status_code})")
        assert e.status_code in [404, 401], f"Expected 404 or 401, got {e.status_code}"
        return True


async def test_6_unauthorized():
    """Test 6 - Unauthorized - 未登入時應拒絕存取"""
    client = LaravelClient()
    # 不呼叫 login()，直接嘗試存取
    reward_client = RewardClient(client)
    customer_id = 1
    
    try:
        await reward_client.list_reward_grants(customer_id)
        assert False, "Should have raised LaravelAPIError"
    except LaravelAPIError as e:
        print(f"✓ Unauthorized request correctly blocked: {e.message}")
        assert "Not authenticated" in e.message
        return True


async def test_7_tenant_isolation():
    """Test 7 - Tenant Isolation - 多租戶隔離測試"""
    print("\n⚠ Test 7 - Tenant Isolation: SKIPPED (insufficient test data with multiple tenants)")
    return "SKIPPED"


async def main():
    """執行所有測試"""
    tests = [
        ("Test 1 - List Reward Grants", test_1_list_reward_grants),
        ("Test 2 - Grant Reward", test_2_grant_reward),
        ("Test 3 - Same Idempotency-Key", test_3_same_idempotency_key),
        ("Test 4 - Different Idempotency-Key", test_4_different_idempotency_keys),
        ("Test 5 - Invalid Request", test_5_invalid_request),
        ("Test 6 - Unauthorized", test_6_unauthorized),
        ("Test 7 - Tenant Isolation", test_7_tenant_isolation),
    ]
    
    results = {}
    print("=" * 60)
    print("Running Reward Grant Integration Tests")
    print("=" * 60)
    
    for name, test_func in tests:
        print(f"\n▶ {name}")
        try:
            result = await test_func()
            if result == "SKIPPED":
                results[name] = "SKIPPED"
            else:
                results[name] = "PASS"
        except Exception as e:
            print(f"  Test failed with exception: {e}")
            results[name] = "FAIL"
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    for name, result in results.items():
        status_icon = "✓" if result == "PASS" else "⚠" if result == "SKIPPED" else "✗"
        print(f"{status_icon} {name:<40} {result}")


if __name__ == "__main__":
    asyncio.run(main())