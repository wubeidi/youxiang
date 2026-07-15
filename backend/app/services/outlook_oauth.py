"""微软 OAuth2：用 refresh token 换取 access token（供 IMAP XOAUTH2 使用）。

消费级 outlook.com 账号走 /consumers 端点。access token 有效期约 1 小时，
这里带内存缓存，避免每次收信都请求 token 端点被限流。
"""
import time
import httpx

from ..config import get_settings

settings = get_settings()

# email -> (access_token, 过期时间戳)
_cache: dict[str, tuple[str, float]] = {}


class OAuthError(Exception):
    pass


async def get_access_token(email: str, client_id: str, refresh_token: str) -> str:
    """返回可用的 access token；命中缓存直接返回。"""
    cached = _cache.get(email)
    now = time.time()
    if cached and cached[1] - 60 > now:      # 提前 60 秒过期，留足余量
        return cached[0]

    data = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": settings.oauth_scope,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(settings.oauth_token_url, data=data)

    if resp.status_code != 200:
        raise OAuthError(f"刷新 token 失败 [{resp.status_code}]: {resp.text[:300]}")

    payload = resp.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise OAuthError(f"响应缺少 access_token: {payload}")

    expires_in = int(payload.get("expires_in", 3600))
    _cache[email] = (access_token, now + expires_in)

    # 注意：某些情况下微软会滚动下发新的 refresh_token，调用方可据此更新入库
    return access_token


def pop_new_refresh_token(payload: dict) -> str | None:
    """若响应里带了新的 refresh_token，返回它（用于滚动更新）。"""
    return payload.get("refresh_token")
