from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from typing import Any

import httpx2 as httpx

from src.config.settings import settings
from src.core.logging import get_logger
from src.domain.exceptions.domain_errors import ExternalAPIError

logger = get_logger(__name__)


class LaravelAPIError(ExternalAPIError):
    """Laravel API呼叫失敗時拋出的例外，繼承自統一的ExternalAPIError"""
    def __init__(self, message: str, status_code: int | None = None, endpoint: str | None = None, payload: Any = None):
        super().__init__(message, status_code=status_code, endpoint=endpoint, payload=payload)


class LaravelClient:
    """
    與 Laravel Loyalty API 溝通的核心 Client。
    負責 JWT、Idempotency-Key、統一錯誤處理。
    """
    
    # 定義修改操作的HTTP方法，這些方法需要等冪性鍵才能重試
    MUTATION_METHODS = {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }
    
    # 定義可重試的例外類型 - 只有暫時性的網路問題才適合重試
    RETRYABLE_EXCEPTIONS = (
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.PoolTimeout,
        httpx.WriteTimeout,
    )

    def __init__(self, limits: httpx.Limits | None = None):
        self.base_url = settings.laravel_api_base_url.rstrip("/")
        self.timeout = settings.default_timeout
        self._token: str | None = None
        self._token_type: str = "Bearer"
        self._token_expires_at: float = 0.0  # JWT 過期時間 (Unix timestamp)
        self._refresh_buffer: int = 30  # 過期前30秒自動刷新
        self._refresh_lock: asyncio.Lock = asyncio.Lock()  # 防止並發刷新
        self._tenant_id: str | None = None
        # 建立共享的 AsyncClient 與連接池
        self._client: httpx.AsyncClient | None = None
        self._limits = limits

    async def __aenter__(self) -> LaravelClient:
        """支援 async with 語法，確保資源正確管理"""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            limits=self._limits or httpx.Limits()
        )
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object | None) -> None:
        """結束時正確關閉 HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        """確保 client 已初始化，如果未使用 async with 則自動建立"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=self._limits or httpx.Limits()
            )
        return self._client

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            # 移除 Connection: close 以支援 HTTP 連線复用，讓連接池正常運作
        }
        if self._token:
            headers["Authorization"] = f"{self._token_type} {self._token}"
        if self._tenant_id:
            headers["X-Tenant-ID"] = self._tenant_id
        return headers

    def set_tenant_id(self, tenant_id: int | str) -> None:
        """設定租戶ID，會自動加入到所有請求的X-Tenant-ID header中"""
        self._tenant_id = str(tenant_id)

    async def login(self, email: str | None = None, password: str | None = None) -> dict[str, Any]:
        email = email or settings.laravel_email
        password = password or settings.laravel_password
        if not email or not password:
            raise LaravelAPIError(
                "Laravel credentials are not configured. Set LARAVEL_EMAIL and LARAVEL_PASSWORD.",
                status_code=503,
                endpoint="/auth/login",
            )

        try:
            client = self._ensure_client()
            resp = await client.post(
                "/auth/login",
                json={"email": email, "password": password},
            )
        except httpx.TimeoutException as exc:
            raise LaravelAPIError(
                message=f"Laravel API timeout: {exc}",
                status_code=504,
                endpoint="/auth/login",
            ) from exc
        except httpx.RequestError as exc:
            raise LaravelAPIError(
                message=f"Laravel API connection failed: {exc}",
                status_code=502,
                endpoint="/auth/login",
            ) from exc

        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text}

        if resp.status_code != 200 or not isinstance(data, dict):
            raise LaravelAPIError(
                message=data.get("message", "Login failed") if isinstance(data, dict) else "Login failed",
                status_code=resp.status_code,
                payload=data,
            )

        # 處理 Laravel 標準 API 回應格式
        if "data" in data and "access_token" in data["data"]:
            token_data = data["data"]
            self.set_token(token_data["access_token"], token_data.get("token_type", "Bearer"))
        # 備用：處理舊版格式
        elif "access_token" in data:
            self.set_token(data["access_token"], data.get("token_type", "Bearer"))
        else:
            raise LaravelAPIError(
                message="Invalid login response: missing access_token",
                status_code=resp.status_code,
                payload=data,
            )

        logger.info("Laravel API 登入成功", extra={"email": email, "base_url": self.base_url})
        return token_data

    async def me(self) -> dict[str, Any]:
        """取得目前登入的使用者資訊"""
        return await self.get("/auth/me")

    async def refresh(self) -> dict[str, Any]:
        """刷新 JWT Token - 使用Single Flight Pattern防止並發刷新
        直接使用底層httpx client呼叫，避免進入request()流程導致無限遞迴
        """
        # 快速路徑檢查：如果token還不需要刷新，直接返回，避免等待鎖
        if not self._is_token_about_to_expire() and self._token is not None:
            return {"data": {"access_token": self._token, "token_type": self._token_type}}
            
        # 只有獲取到鎖的協程才能執行刷新操作
        async with self._refresh_lock:
            # 雙重檢查鎖內：等待鎖的過程中可能已經有其他協程刷新過token了
            if not self._is_token_about_to_expire() and self._token is not None:
                logger.debug("Token already refreshed by another request, skipping refresh")
                return {"data": {"access_token": self._token, "token_type": self._token_type}}
                
            logger.info("Starting token refresh")
            
            # 直接使用底層httpx client呼叫，不經過request()，避免無限遞迴
            client = self._ensure_client()
            try:
                headers = self.headers.copy()
                resp = await client.post(
                    "/auth/refresh",
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                raise LaravelAPIError(
                    message=f"Laravel API timeout during refresh: {exc}",
                    status_code=504,
                    endpoint="/auth/refresh",
                ) from exc
            except httpx.RequestError as exc:
                raise LaravelAPIError(
                    message=f"Laravel API connection failed during refresh: {exc}",
                    status_code=502,
                    endpoint="/auth/refresh",
                ) from exc

            try:
                data = resp.json()
            except ValueError:
                data = {"raw": resp.text}

            if resp.status_code != 200 or not isinstance(data, dict):
                raise LaravelAPIError(
                    message=data.get("message", "Refresh failed") if isinstance(data, dict) else "Refresh failed",
                    status_code=resp.status_code,
                    payload=data,
                    endpoint="/auth/refresh",
                )

            # 更新本機儲存的 token - 遵循 Laravel 標準 API 回傳格式
            if "data" in data and "access_token" in data["data"]:
                self.set_token(data["data"]["access_token"], data["data"].get("token_type", "Bearer"))
                logger.info("Token refresh successful")
            elif "access_token" in data:
                self.set_token(data["access_token"], data.get("token_type", "Bearer"))
                logger.info("Token refresh successful")
            else:
                raise LaravelAPIError(
                    message="Invalid refresh response: missing access_token",
                    status_code=resp.status_code,
                    payload=data,
                    endpoint="/auth/refresh",
                )
            return data

    async def logout(self) -> dict[str, Any]:
        """登出並清除本機 token"""
        try:
            resp = await self.post("/auth/logout")
        finally:
            # 無論遠端 logout 是否成功，都清除本機 token state。
            self._token = None
            self._token_expires_at = 0.0  # 同步清除過期時間，避免殘留
        return resp

    def _parse_jwt_expiry(self, token: str) -> float:
        """解析JWT token的exp欄位，返回Unix timestamp"""
        try:
            # JWT格式: header.payload.signature
            parts = token.split(".")
            if len(parts) != 3:
                logger.warning("Invalid JWT format, could not parse expiry")
                return 0.0
                
            # 解碼payload (base64url)
            payload_b64 = parts[1]
            # 添加padding如果需要 - 使用更穩定的計算方式
            # -len(payload_b64) % 4 永遠會得到正確需要的padding數量(0,1,2,3)
            # 當長度已經是4的倍數時，-len %4 =0，不會添加多餘的=
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_bytes)
            
            exp = payload.get("exp", 0)
            return float(exp)
        except Exception as e:
            logger.warning(f"Failed to parse JWT expiry: {e}")
            return 0.0
            
    def _is_token_about_to_expire(self) -> bool:
        """檢查token是否即將過期（需要在過期前refresh_buffer秒內刷新）"""
        if self._token_expires_at == 0.0:
            return True  # 如果無法解析過期時間，保守處理，認為需要刷新
        current_time = time.time()
        return current_time + self._refresh_buffer >= self._token_expires_at
        
    def set_token(self, token: str, token_type: str = "Bearer") -> None:
        self._token = token
        self._token_type = token_type
        self._token_expires_at = self._parse_jwt_expiry(token)

    def generate_idempotency_key(self, prefix: str = "demo") -> str:
        return f"{prefix}-{uuid.uuid4()}"
            
    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        expect_status: int | list[int] | None = None,
    ) -> dict[str, Any]:
        # 刻意在送出 request 前拒絕未認證請求，
        # 避免明知缺少 Authentication Context 仍呼叫 Laravel API。
        if self._token is None:
            raise LaravelAPIError(
                "Not authenticated. Call login() first.",
                status_code=401,
                endpoint=path,
            )
            
        # 預先檢查token是否即將過期，如果是則先刷新
        if self._is_token_about_to_expire():
            logger.debug("Token is about to expire, refreshing preemptively", extra={"endpoint": path})
            await self.refresh()

        headers = self.headers.copy()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        # 實現手動重試邏輯，處理指數退避
        max_retries = 3
        retry_delay = 2  # 初始延遲2秒
        attempt = 0
        method_upper = method.upper()
        has_retried_401 = False
        last_exception: Exception | None = None
        last_response: httpx.Response | None = None
        
        while attempt < max_retries:
            last_exception = None
            last_response = None
            
            try:
                client = self._ensure_client()
                resp = await client.request(
                    method=method_upper,
                    url=path,
                    json=json,
                    params=params,
                    headers=headers,
                )
                last_response = resp
                
                # 處理401未授權 - 只嘗試刷新token後重試一次
                if resp.status_code == 401 and not has_retried_401:
                    logger.warning("Received 401, attempting to refresh token and retry once", extra={"endpoint": path})
                    has_retried_401 = True
                    await self.refresh()
                    # 刷新後更新headers，然後繼續重試一次
                    headers = self.headers.copy()
                    if idempotency_key:
                        headers["Idempotency-Key"] = idempotency_key
                    continue  # 進入下一次循環，只會再執行一次
                
                # 如果請求成功，跳出循環
                allowed = expect_status or [200, 201]
                if isinstance(allowed, int):
                    allowed = [allowed]
                if resp.status_code in allowed:
                    break
                    
                # 檢查是否需要重試
                retryable_statuses = {429, 500, 502, 503, 504}
                if resp.status_code not in retryable_statuses:
                    break
                    
                # 修改操作(Mutation)必須有Idempotency-Key才能重試
                if method_upper in self.MUTATION_METHODS and idempotency_key is None:
                    break
                    
            except self.RETRYABLE_EXCEPTIONS as exc:
                last_exception = exc
                # 只有可重試的暫時性網路例外才進行重試
                # 修改操作(Mutation)必須有Idempotency-Key才能重試
                if method_upper in self.MUTATION_METHODS and idempotency_key is None:
                    raise LaravelAPIError(
                        message=f"Laravel API error: {exc}",
                        status_code=504,
                        endpoint=path,
                    ) from exc
                    
            except httpx.RequestError as exc:
                # 其他不可重試的網路錯誤(如DNS錯誤、SSL錯誤、連線被拒等)直接拋出
                raise LaravelAPIError(
                    message=f"Laravel API connection failed: {exc}",
                    status_code=502,
                    endpoint=path,
                ) from exc
                    
            # 如果到達這裡，說明需要重試
            attempt += 1
            if attempt < max_retries:
                logger.warning(
                    f"Retrying request, attempt {attempt + 1}/{max_retries}",
                    extra={"endpoint": path, "method": method}
                )
                # 指數退避
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 10)  # 最大延遲10秒
            else:
                # 已達到最大重試次數，重新拋出最後的異常
                if last_exception:
                    raise LaravelAPIError(
                        message=f"Max retries exceeded. Last error: {last_exception}",
                        status_code=502 if isinstance(last_exception, httpx.RequestError) else 504,
                        endpoint=path,
                    ) from last_exception
                else:
                    # 如果是狀態碼導致的重試失敗
                    raise LaravelAPIError(
                        message=f"Max retries exceeded. Last status code: {last_response.status_code}",
                        status_code=last_response.status_code,
                        endpoint=path,
                        payload=last_response.text if last_response else None,
                    )

        # 確保resp變數存在
        if last_response is None:
            raise LaravelAPIError(
                "No response received from Laravel API",
                status_code=502,
                endpoint=path,
            )
        resp = last_response

        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}

        allowed = expect_status or [200, 201]
        if isinstance(allowed, int):
            allowed = [allowed]

        if resp.status_code not in allowed:
            message = data.get("message") if isinstance(data, dict) else str(data)
            # 記錄錯誤但不洩露敏感的stack trace資訊到生產日誌
            logger.error(
                "Laravel API 回傳錯誤",
                extra={
                    "endpoint": path,
                    "status_code": resp.status_code,
                    "error_message": message,
                }
            )
            raise LaravelAPIError(
                message=message or f"HTTP {resp.status_code}",
                status_code=resp.status_code,
                endpoint=path,
                payload=data,
            )

        return data

    async def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.request("DELETE", path, **kwargs)