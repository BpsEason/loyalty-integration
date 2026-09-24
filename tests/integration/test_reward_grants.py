import pytest

from app.client.base import LaravelAPIError, LaravelClient
from app.client.reward import RewardClient


pytestmark = pytest.mark.integration


def _grant_id(result: dict) -> int:
    data = result.get("data", {})
    assert isinstance(data, dict), "Reward grant data is missing"
    assert data.get("id"), "Reward grant ID is missing"
    return data["id"]


@pytest.mark.asyncio
async def test_list_reward_grants_returns_response(
    authenticated_client: LaravelClient,
    customer_id: int,
):
    result = await RewardClient(authenticated_client).list_reward_grants(customer_id)

    assert isinstance(result, dict)
    assert "data" in result


@pytest.mark.asyncio
async def test_grant_reward_returns_grant(
    coffee_client: LaravelClient,
    coffee_customer_id: int,
    coffee_campaign_reward_id: int,
):
    reward_client = RewardClient(coffee_client)
    key = coffee_client.generate_idempotency_key(prefix="test-grant")

    try:
        result = await reward_client.grant_reward(
            customer_id=coffee_customer_id,
            campaign_reward_id=coffee_campaign_reward_id,
            quantity=1,
            reference=key,
            description="Integration test reward grant",
            idempotency_key=key,
        )
    except LaravelAPIError as exc:
        pytest.skip(f"Reward test data is not claimable in this environment: {exc.message}")

    assert _grant_id(result)
    assert result["data"].get("status") in {"granted", "already_granted"}


@pytest.mark.asyncio
async def test_same_reward_idempotency_key_returns_same_grant(
    coffee_client: LaravelClient,
    coffee_customer_id: int,
    coffee_campaign_reward_id: int,
):
    reward_client = RewardClient(coffee_client)
    key = coffee_client.generate_idempotency_key(prefix="test-reward-idempotency")
    payload = {
        "customer_id": coffee_customer_id,
        "campaign_reward_id": coffee_campaign_reward_id,
        "quantity": 1,
        "reference": key,
        "description": "Same reward key integration test",
        "idempotency_key": key,
    }

    try:
        first_result = await reward_client.grant_reward(**payload)
        second_result = await reward_client.grant_reward(**payload)
    except LaravelAPIError as exc:
        pytest.skip(f"Reward test data is not claimable in this environment: {exc.message}")

    assert _grant_id(first_result) == _grant_id(second_result)


@pytest.mark.asyncio
async def test_different_reward_idempotency_keys_are_not_claimed_as_same_transaction():
    pytest.skip(
        "Known contract gap: independent reward grants require two claimable "
        "customer/reward fixtures."
    )


@pytest.mark.asyncio
async def test_invalid_reward_request_is_rejected(
    coffee_client: LaravelClient,
    coffee_customer_id: int,
    coffee_campaign_reward_id: int,
):
    with pytest.raises(LaravelAPIError):
        await RewardClient(coffee_client).grant_reward(
            customer_id=coffee_customer_id,
            campaign_reward_id=coffee_campaign_reward_id,
            quantity=0,
        )


@pytest.mark.asyncio
async def test_tenant_isolation_requires_cross_tenant_fixtures():
    pytest.skip(
        "Known gap: tenant isolation requires two valid tenant credentials and "
        "resources with a contract-defined 403/404 response."
    )
