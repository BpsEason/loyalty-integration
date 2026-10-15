"""Unit tests for main.py observability and security features: request ID handling, sensitive data redaction, exception handling"""

import pytest
from fastapi.testclient import TestClient
import uuid
from src.main import app, UUID_PATTERN, MAX_REQUEST_ID_LENGTH, redact_sensitive_data
from src.infrastructure.clients.base import LaravelAPIError
from src.domain.exceptions.domain_errors import LoyaltyIntegrationError

client = TestClient(app, raise_server_exceptions=False)


def test_uuid_pattern_is_valid():
    """Test that the UUID pattern correctly validates UUIDs"""
    valid_uuid = str(uuid.uuid4())
    assert UUID_PATTERN.match(valid_uuid) is not None
    
    invalid_uuids = [
        "not-a-uuid",
        "12345678-1234-1234-1234-1234567890xyz",  # invalid characters
        "123456781234123412341234567890ab",  # no dashes
        "",  # empty string
        "   ",  # whitespace
    ]
    for invalid in invalid_uuids:
        assert UUID_PATTERN.match(invalid) is None


def test_max_request_id_length():
    """Test that MAX_REQUEST_ID_LENGTH is set correctly"""
    assert MAX_REQUEST_ID_LENGTH == 64


def test_redact_sensitive_data_flat_dict():
    """Test sensitive data redaction in flat dictionary"""
    data = {
        "username": "testuser",
        "password": "secret123",
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "email": "test@example.com"
    }
    redacted = redact_sensitive_data(data)
    assert redacted["password"] == "<redacted>"
    assert redacted["token"] == "<redacted>"
    assert redacted["username"] == "testuser"
    assert redacted["email"] == "test@example.com"


def test_redact_sensitive_data_case_insensitive():
    """Test that redaction is case-insensitive for field names"""
    data = {
        "Password": "secret123",
        "TOKEN": "abc123",
        "access_token": "def456",
        "ApiKey": "ghi789"
    }
    redacted = redact_sensitive_data(data)
    assert redacted["Password"] == "<redacted>"
    assert redacted["TOKEN"] == "<redacted>"
    assert redacted["access_token"] == "<redacted>"
    assert redacted["ApiKey"] == "<redacted>"


def test_redact_sensitive_data_nested_dict():
    """Test sensitive data redaction in nested dictionary"""
    data = {
        "user": {
            "name": "test",
            "credentials": {
                "password": "secret",
                "token": "jwt_token"
            }
        },
        "metadata": {
            "Authorization": "Bearer xxx"
        }
    }
    redacted = redact_sensitive_data(data)
    assert redacted["user"]["credentials"]["password"] == "<redacted>"
    assert redacted["user"]["credentials"]["token"] == "<redacted>"
    assert redacted["metadata"]["Authorization"] == "<redacted>"
    assert redacted["user"]["name"] == "test"


def test_redact_sensitive_data_list():
    """Test sensitive data redaction in lists"""
    data = {
        "users": [
            {"name": "user1", "password": "pass1"},
            {"name": "user2", "password": "pass2"},
            "plain_string",
            12345
        ]
    }
    redacted = redact_sensitive_data(data)
    assert redacted["users"][0]["password"] == "<redacted>"
    assert redacted["users"][1]["password"] == "<redacted>"
    assert redacted["users"][2] == "plain_string"
    assert redacted["users"][3] == 12345


def test_redact_sensitive_data_non_dict():
    """Test redaction handles non-dictionary payloads correctly"""
    # String payload
    assert redact_sensitive_data("plain string") == "plain string"
    # Integer payload
    assert redact_sensitive_data(12345) == 12345
    # None payload
    assert redact_sensitive_data(None) is None
    # List of strings
    assert redact_sensitive_data(["a", "b", "c"]) == ["a", "b", "c"]


def test_valid_request_id_is_preserved():
    """Test that a valid incoming X-Request-ID is preserved in response"""
    test_uuid = str(uuid.uuid4())
    response = client.get("/health", headers={"X-Request-ID": test_uuid})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == test_uuid


def test_invalid_request_id_is_replaced():
    """Test that an invalid incoming X-Request-ID is replaced with a new UUID"""
    invalid_ids = [
        "invalid-uuid",
        "not-a-valid-id",
        "12345",  # too short but invalid format
        "a" * 100,  # too long
    ]
    for invalid_id in invalid_ids:
        response = client.get("/health", headers={"X-Request-ID": invalid_id})
        assert response.status_code == 200
        response_id = response.headers["X-Request-ID"]
        # Verify the response ID is a valid UUID
        assert UUID_PATTERN.match(response_id) is not None
        # Verify it's not the invalid one we sent
        assert response_id != invalid_id


def test_missing_request_id_is_generated():
    """Test that a new UUID is generated when no X-Request-ID is provided"""
    response = client.get("/health")
    assert response.status_code == 200
    response_id = response.headers["X-Request-ID"]
    assert UUID_PATTERN.match(response_id) is not None


def test_laravel_api_error_includes_request_id(caplog):
    """Test that LaravelAPIError responses include X-Request-ID"""
    # We'll create a test route that raises LaravelAPIError to test the exception handler
    from fastapi import APIRouter
    test_router = APIRouter()
    
    @test_router.get("/test-laravel-error")
    async def test_laravel_error():
        raise LaravelAPIError(
            message="Test Laravel error",
            status_code=400,
            endpoint="/test",
            payload={"password": "secret", "data": "test"}
        )
    
    # Add unique prefix to avoid route duplication
    app.include_router(test_router, prefix="/unique-1")
    
    test_uuid = str(uuid.uuid4())
    response = client.get("/unique-1/test-laravel-error", headers={"X-Request-ID": test_uuid})
    assert response.status_code == 400
    assert response.headers["X-Request-ID"] == test_uuid
    assert response.json()["detail"] == "Test Laravel error"


def test_loyalty_integration_error_includes_request_id():
    """Test that LoyaltyIntegrationError responses include X-Request-ID"""
    # Create a test route that raises LoyaltyIntegrationError
    from fastapi import APIRouter
    test_router = APIRouter()
    
    @test_router.get("/test-app-error")
    async def test_app_error():
        raise LoyaltyIntegrationError(
            message="Test application error",
            context={"user": {"password": "secret"}, "action": "test"}
        )
    
    # Add unique prefix to avoid route duplication
    app.include_router(test_router, prefix="/unique-2")
    
    test_uuid = str(uuid.uuid4())
    response = client.get("/unique-2/test-app-error", headers={"X-Request-ID": test_uuid})
    assert response.status_code == 400
    assert response.headers["X-Request-ID"] == test_uuid
    assert response.json()["detail"] == "Test application error"


def test_unhandled_exception_includes_request_id():
    """Test that unhandled exceptions still include X-Request-ID in response"""
    # Create a test route that raises a generic exception
    from fastapi import APIRouter
    test_router = APIRouter()
    
    @test_router.get("/test-unhandled-error")
    async def test_unhandled_error():
        raise ValueError("This is an unhandled error")
    
    # Add unique prefix to avoid route duplication
    app.include_router(test_router, prefix="/unique-3")
    
    test_uuid = str(uuid.uuid4())
    response = client.get("/unique-3/test-unhandled-error", headers={"X-Request-ID": test_uuid})
    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == test_uuid
    assert response.json()["detail"] == "內部伺服器錯誤"


def test_sensitive_data_not_logged(caplog):
    """Test that sensitive data is redacted in logs"""
    caplog.set_level("ERROR")
    
    # Create a test route that raises LaravelAPIError with sensitive data
    from fastapi import APIRouter
    test_router = APIRouter()
    
    @test_router.get("/test-sensitive-logging")
    async def test_sensitive_logging():
        raise LaravelAPIError(
            message="Test error with sensitive data",
            status_code=400,
            endpoint="/test",
            payload={
                "password": "mysecretpassword",
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
                "username": "testuser",
                "nested": {
                    "secret_key": "secret123",
                    "public_data": "public"
                }
            }
        )
    
    # Add unique prefix to avoid route duplication
    app.include_router(test_router, prefix="/unique-4")
    
    client.get("/unique-4/test-sensitive-logging")
    
    # Check that sensitive values are redacted in logs by inspecting structured log records
    for record in caplog.records:
        # Check if payload/context attributes exist in the log record
        payload = getattr(record, 'payload', getattr(record, 'context', {}))
        if payload:
            # Verify sensitive values are redacted
            assert payload.get('password') == '<redacted>'
            assert payload.get('token') == '<redacted>'
            assert payload.get('nested', {}).get('secret_key') == '<redacted>'
            # Non-sensitive data remains intact
            assert payload.get('username') == 'testuser'
            assert payload.get('nested', {}).get('public_data') == 'public'