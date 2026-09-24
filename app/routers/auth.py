from fastapi import APIRouter
from app.core.dependencies import laravel_client
from app.schemas.auth import LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])



@router.post("/login")
async def auth_login(body: LoginRequest):
    """手動登入取得 JWT Token"""
    return await laravel_client.login(body.email, body.password)


@router.get("/me")
async def auth_me():
    """取得目前登入的使用者資訊"""
    return await laravel_client.me()


@router.post("/refresh")
async def auth_refresh():
    """刷新 JWT Token"""
    return await laravel_client.refresh()


@router.post("/logout")
async def auth_logout():
    """登出並清除目前的 Token"""
    return await laravel_client.logout()