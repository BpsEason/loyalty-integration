import pytest

from src.infrastructure.clients.base import LaravelAPIError, LaravelClient
from src.infrastructure.clients.point import PointClient
from src.infrastructure.clients.reward import RewardClient


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