import asyncio
from app.client.base import LaravelClient


async def main():
    """查詢 Laravel API 以取得有效的 customer_id 和 campaign_reward_id"""
    client = LaravelClient()
    await client.login()
    
    print("=== 查詢可用的客戶 ===")
    try:
        # 先嘗試取得客戶列表
        customers = await client.get("/customers", params={"per_page": 10})
        print(f"✓ 成功取得客戶列表: {len(customers['data']['data'])} 個客戶")
        for customer in customers['data']['data']:
            print(f"  - Customer ID: {customer['id']}, Name: {customer['name']}, Email: {customer['email']}")
    except Exception as e:
        print(f"✗ 取得客戶列表失敗: {e}")
    
    print("\n=== 嘗試查詢可用的活動獎勵 ===")
    try:
        # 嘗試查詢 campaigns
        campaigns = await client.get("/campaigns", params={"per_page": 10})
        print(f"✓ 成功取得活動列表: {len(campaigns['data']['data'])} 個活動")
        for campaign in campaigns['data']['data']:
            print(f"  - Campaign ID: {campaign['id']}, Name: {campaign['name']}")
            if 'rewards' in campaign:
                for reward in campaign['rewards']:
                    print(f"    → CampaignReward ID: {reward['id']}, Type: {reward.get('type', 'N/A')}")
    except Exception as e:
        print(f"✗ 取得活動列表失敗: {e}")
    
    print("\n=== 嘗試查詢所有可能的 campaign-rewards API ===")
    try:
        # 嘗試不同的 API 路徑來尋找 campaign rewards
        for path in ["/campaign-rewards", "/campaigns/rewards", "/rewards"]:
            try:
                result = await client.get(path, params={"per_page": 10})
                if result.get('success') and 'data' in result:
                    items = result['data']['data'] if 'data' in result['data'] else [result['data']]
                    print(f"✓ 在 {path} 找到 {len(items)} 個項目")
                    for item in items:
                        print(f"  - ID: {item.get('id')}, Name: {item.get('name', 'N/A')}")
            except:
                pass
    except Exception as e:
        print(f"✗ 查詢其他 API 路徑失敗: {e}")


if __name__ == "__main__":
    asyncio.run(main())