from __future__ import annotations

import uuid
from typing import Any

import httpx
from rich.console import Console

from app.config import settings

console = Console()


class LaravelAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        self.message = message
        self.status_code = status_code
        self.payload = payload
        super().__init__(message)


class LaravelClient:
    """
    與 Laravel Loyalty API 溝通的核心 Client。
    負責 JWT、Idempotency-Key、統一錯誤處理。
    """

    def __init__(self):
        self.base_url = settings.laravel_api_base_url.rstrip("/")
        self.timeout = settings.default_timeout
        self._token: str | None = None
        self._token_type: str = "Bearer"

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._token:
            headers["Authorization"] = f"{self._token_type} {self._token}"
        return headers

    async def login(self, email: str | None = None, password: str | None = None) -> dict:
        email = email or settings.laravel_email
        password = password or settings.laravel_password

        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                resp = await client.post(
                    "/auth/login",
                    json={"email": email, "password": password},
                )
        except httpx.RequestError as exc:
            raise LaravelAPIError(
                message=f"Laravel API request failed: {exc}",
                status_code=502,
            ) from exc

        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text}

        if resp.status_code != 200 or not isinstance(data, dict) or not data.get("success"):
            raise LaravelAPIError(
                message=data.get("message", "Login failed") if isinstance(data, dict) else "Login failed",
                status_code=resp.status_code,
                payload=data,
            )

        token_data = data["data"]
        self._token = token_data["access_token"]
        self._token_type = token_data.get("token_type", "Bearer")

        console.print(f"[green]✓ Login successful[/green] as {email}")
        return token_data

    async def me(self) -> dict:
        """取得目前登入的使用者資訊"""
        return await self.get("/auth/me")

    async def refresh(self) -> dict:
        """刷新 JWT Token"""
        resp = await self.post("/auth/refresh")
        # 更新本機儲存的 token - 遵循 Laravel 標準 API 回傳格式
        if "data" in resp and "access_token" in resp["data"]:
            self._token = resp["data"]["access_token"]
            self._token_type = resp["data"].get("token_type", "Bearer")
        return resp

    async def logout(self) -> dict:
        """登出並清除本機 token"""
        try:
            resp = await self.post("/auth/logout")
        finally:
            # 無論 API 呼叫是否成功，都清除本機 token
            self._token = None
        return resp

    def set_token(self, token: str, token_type: str = "Bearer"):
        self._token = token
        self._token_type = token_type

    def generate_idempotency_key(self, prefix: str = "demo") -> str:
        return f"{prefix}-{uuid.uuid4()}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        idempotency_key: str | None = None,
        expect_status: int | list[int] | None = None,
    ) -> dict:
        if self._token is None:
            raise LaravelAPIError(
                "Not authenticated. Call login() first.",
                status_code=401,
            )

        headers = self.headers.copy()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                resp = await client.request(
                    method=method.upper(),
                    url=path,
                    json=json,
                    params=params,
                    headers=headers,
                )
        except httpx.RequestError as exc:
            raise LaravelAPIError(
                message=f"Laravel API request failed: {exc}",
                status_code=502,
            ) from exc

        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}

        allowed = expect_status or [200, 201]
        if isinstance(allowed, int):
            allowed = [allowed]

        if resp.status_code not in allowed:
            message = data.get("message") if isinstance(data, dict) else str(data)
            raise LaravelAPIError(
                message=message or f"HTTP {resp.status_code}",
                status_code=resp.status_code,
                payload=data,
            )

        return data

    async def get(self, path: str, **kwargs) -> dict:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> dict:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs) -> dict:
        return await self.request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs) -> dict:
        return await self.request("DELETE", path, **kwargs)