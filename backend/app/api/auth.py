"""登录接口。"""
from fastapi import APIRouter, HTTPException

from ..schemas import LoginRequest, TokenResponse
from .. import security

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    if not security.verify_admin(body.username, body.password):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    return TokenResponse(access_token=security.create_token(body.username))
