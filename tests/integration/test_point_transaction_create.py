import pytest

from app.client.base import LaravelAPIError, LaravelClient
from app.client.point import PointClient


pytestmark = pytest.mark.integration


def _transaction_id(result: dict) -> int:
    data = result.get("data", {})
    assert isinstance(data, dict), "Transaction data is missing"
    assert data.get("id"), "Transaction ID is missing"
    return data["id"]


@pytest.mark.asyncio
async def test_create_point_transaction_returns_transaction(
    authenticated_client: LaravelClient,
    customer_id: int,
):
    point_client = PointClient(authenticated_client)
    key = authenticated_client.generate_idempotency_key(prefix="test-transaction")

    result = await point_client.create_transaction(
        customer_id=customer_id,
        transaction_type="earn",
        amount=100,
        description="Integration test point transaction",
        reference=key,
        idempotency_key=key,
    )

    transaction_id = _transaction_id(result)
    data = result["data"]
    assert data["customer_id"] == customer_id
    assert data["type"] == "earn"
    assert data["amount"] == 100
    assert transaction_id


@pytest.mark.asyncio
async def test_same_idempotency_key_does_not_double_apply(
    authenticated_client: LaravelClient,
    customer_id: int,
):
    point_client = PointClient(authenticated_client)
    key = authenticated_client.generate_idempotency_key(prefix="test-idempotency")
    payload = {
        "customer_id": customer_id,
        "transaction_type": "earn",
        "amount": 50,
        "description": "Same key integration test",
        "reference": key,
        "idempotency_key": key,
    }

    balance_before = (await point_client.get_balance(customer_id))["data"]["balance"]
    first_result = await point_client.create_transaction(**payload)
    second_result = await point_client.create_transaction(**payload)
    balance_after = (await point_client.get_balance(customer_id))["data"]["balance"]

    assert _transaction_id(first_result) == _transaction_id(second_result)
    assert balance_after == balance_before + 50


@pytest.mark.asyncio
async def test_different_idempotency_keys_create_independent_transactions(
    authenticated_client: LaravelClient,
    customer_id: int,
):
    point_client = PointClient(authenticated_client)
    key_a = authenticated_client.generate_idempotency_key(prefix="test-key-a")
    key_b = authenticated_client.generate_idempotency_key(prefix="test-key-b")
    balance_before = (await point_client.get_balance(customer_id))["data"]["balance"]

    result_a = await point_client.create_transaction(
        customer_id=customer_id,
        transaction_type="earn",
        amount=20,
        description="Different key A integration test",
        reference=key_a,
        idempotency_key=key_a,
    )
    result_b = await point_client.create_transaction(
        customer_id=customer_id,
        transaction_type="earn",
        amount=30,
        description="Different key B integration test",
        reference=key_b,
        idempotency_key=key_b,
    )
    balance_after = (await point_client.get_balance(customer_id))["data"]["balance"]

    assert _transaction_id(result_a) != _transaction_id(result_b)
    assert balance_after == balance_before + 50


@pytest.mark.asyncio
async def test_invalid_point_transaction_is_rejected(
    authenticated_client: LaravelClient,
    customer_id: int,
):
    point_client = PointClient(authenticated_client)

    with pytest.raises(LaravelAPIError):
        await point_client.create_transaction(
            customer_id=customer_id,
            transaction_type="",
            amount=100,
        )

    with pytest.raises(LaravelAPIError):
        await point_client.create_transaction(
            customer_id=customer_id,
            transaction_type="earn",
            amount=-50,
        )
