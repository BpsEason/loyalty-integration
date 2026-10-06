"""Domain-specific exceptions"""


class LoyaltyIntegrationError(Exception):
    """所有應用程式錯誤的基礎類別，提供額外的上下文資訊"""
    def __init__(self, message: str, context: dict | None = None):
        self.message = message
        self.context = context or {}
        super().__init__(message)


class DomainError(LoyaltyIntegrationError):
    """所有領域錯誤的基礎類別"""
    pass


class InsufficientPointsError(DomainError):
    """點數不足時拋出"""
    def __init__(self, balance: int, required: int, customer_id: int | None = None):
        context = {
            "balance": balance,
            "required": required,
            "customer_id": customer_id
        }
        super().__init__(f"點數不足，目前餘額: {balance}，需要: {required}", context)


class InvalidTransactionError(DomainError):
    """交易資料無效時拋出"""
    def __init__(self, message: str, transaction_details: dict | None = None):
        context = {"transaction_details": transaction_details} if transaction_details else {}
        super().__init__(message, context)


class CustomerNotFoundError(DomainError):
    """找不到會員時拋出"""
    def __init__(self, customer_id: int):
        context = {"customer_id": customer_id}
        super().__init__(f"找不到會員 ID: {customer_id}", context)


# 基礎架構層例外
class InfrastructureError(LoyaltyIntegrationError):
    """基礎架構層錯誤的基礎類別"""
    pass


class ExternalAPIError(InfrastructureError):
    """外部API呼叫失敗時拋出"""
    def __init__(self, message: str, status_code: int | None = None, endpoint: str | None = None, payload: dict | None = None):
        context = {
            "status_code": status_code,
            "endpoint": endpoint,
            "payload": payload
        }
        super().__init__(message, context)


class WebSocketConnectionError(InfrastructureError):
    """WebSocket連線失敗時拋出"""
    def __init__(self, message: str, connection_details: dict | None = None):
        context = {"connection_details": connection_details} if connection_details else {}
        super().__init__(message, context)


# 應用層例外
class ApplicationError(LoyaltyIntegrationError):
    """應用層錯誤的基礎類別"""
    pass


class WorkflowExecutionError(ApplicationError):
    """工作流程執行失敗時拋出"""
    def __init__(self, message: str, workflow_name: str, workflow_context: dict | None = None):
        context = {
            "workflow_name": workflow_name,
            **(workflow_context or {})
        }
        super().__init__(message, context)


class AuthenticationError(LoyaltyIntegrationError):
    """認證失敗時拋出"""
    def __init__(self, message: str, auth_context: dict | None = None):
        context = auth_context or {}
        super().__init__(message, context)


class AuthorizationError(LoyaltyIntegrationError):
    """授權失敗時拋出"""
    def __init__(self, message: str, user_id: int | None = None, resource: str | None = None):
        context = {
            "user_id": user_id,
            "resource": resource
        }
        super().__init__(message, context)