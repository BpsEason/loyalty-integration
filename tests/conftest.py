import pytest
from app.client.base import LaravelClient
from app.client.customer import CustomerClient


@pytest.fixture(scope="session")
async def customer_id():
    """取得一個可用的 customer_id 供測試使用"""
    client = LaravelClient()
    try:
        await client.login()
    except Exception as e:
        pytest.fail(f"Laravel API login failed during fixture setup: {e}")

    customer_client = CustomerClient(client)
    customers = await customer_client.list(per_page=1)

    data = customers.get("data", [])
    if isinstance(data, dict):
        items = data.get("data", [])
    else:
        items = data

    if not items:
        pytest.skip("No available customers to test with.")

    return items[0]["id"]