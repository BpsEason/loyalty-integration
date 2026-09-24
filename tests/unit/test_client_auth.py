import pytest

from app.client.base import LaravelAPIError, LaravelClient
from app.client.point import PointClient
from app.client.reward import RewardClient


@pytest.mark.asyncio
async def test_point_client_rejects_unauthenticated_request():
    client = LaravelClient()
    point_client = PointClient(client)

    with pytest.raises(LaravelAPIError, match="Not authenticated"):
        await point_client.create_transaction(
            customer_id=1,
            transaction_type="earn",
            amount=100,
        )


@pytest.mark.asyncio
async def test_reward_client_rejects_unauthenticated_request():
    client = LaravelClient()
    reward_client = RewardClient(client)

    with pytest.raises(LaravelAPIError, match="Not authenticated"):
        await reward_client.list_reward_grants(customer_id=1)