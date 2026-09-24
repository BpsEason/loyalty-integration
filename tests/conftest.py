import pytest
from app.client.base import LaravelClient
from app.client.customer import CustomerClient
from app.client.reward import RewardClient
from app.config import settings


@pytest.fixture
async def authenticated_client():
    """Return a client authenticated with the default tenant credentials."""
    client = LaravelClient()
    await client.login()
    return client


@pytest.fixture
async def coffee_client():
    """Return a client authenticated with the optional Coffee tenant."""
    if not settings.laravel_coffee_email or not settings.laravel_coffee_password:
        pytest.skip(
            "LARAVEL_COFFEE_EMAIL and LARAVEL_COFFEE_PASSWORD are required "
            "for Coffee tenant integration tests."
        )

    client = LaravelClient()
    await client.login(
        email=settings.laravel_coffee_email,
        password=settings.laravel_coffee_password,
    )
    return client


@pytest.fixture
async def customer_id(authenticated_client):
    """取得一個可用的 customer_id 供測試使用。"""
    client = authenticated_client
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


@pytest.fixture
async def coffee_customer_id(coffee_client, coffee_campaign_reward_id):
    """取得尚未領取指定 reward 的 Coffee tenant customer。"""
    customers = await CustomerClient(coffee_client).list(per_page=100)
    data = customers.get("data", [])
    items = data.get("data", []) if isinstance(data, dict) else data

    reward_client = RewardClient(coffee_client)
    for customer in items:
        grants = await reward_client.list_reward_grants(customer["id"], per_page=100)
        grant_data = grants.get("data", [])
        grant_items = grant_data.get("data", []) if isinstance(grant_data, dict) else grant_data
        claimed_reward_ids = {
            grant.get("campaign_reward_id")
            for grant in grant_items
            if isinstance(grant, dict)
        }
        if coffee_campaign_reward_id not in claimed_reward_ids:
            return customer["id"]

    pytest.skip("No Coffee tenant customer is available for this reward.")


@pytest.fixture
def coffee_campaign_reward_id():
    """Return the configured Coffee campaign reward ID."""
    return settings.laravel_coffee_campaign_reward_id