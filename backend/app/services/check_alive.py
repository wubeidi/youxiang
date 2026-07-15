"""邮箱测活：用 refresh token 换 access token，并轻量验证 IMAP 是否可登录。

与「立即刷新」的区别：
- 测活只验证凭证是否有效，不拉取邮件正文，更轻、更快。
- 结果回写账号 status / last_error / last_polled_at，方便列表筛选「正常/错误」。

两层判定：
1. OAuth 刷新失败 → 凭证失效（改密/风控/token 过期）
2. OAuth 成功但 IMAP 失败 → 可能是 IMAP 被关、权限不足、微软侧策略
"""
import asyncio
import imaplib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crypto
from ..config import get_settings
from ..database import AsyncSessionLocal
from ..models import EmailAccount
from . import outlook_oauth, imap_client

settings = get_settings()


def _probe_imap(email_addr: str, access_token: str) -> None:
    """同步：XOAUTH2 登录 + SELECT INBOX，成功即视为可收信。"""
    conn = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    try:
        auth = imap_client._build_auth_string(email_addr, access_token)
        typ, data = conn.authenticate("XOAUTH2", lambda _: auth.encode())
        if typ != "OK":
            raise RuntimeError(f"IMAP 认证失败: {data}")
        typ, data = conn.select("INBOX", readonly=True)
        if typ != "OK":
            raise RuntimeError(f"无法打开收件箱: {data}")
    finally:
        try:
            conn.logout()
        except Exception:
            pass


async def check_one(account_id: int) -> dict:
    """测活单个账号，返回结构化结果并回写数据库状态。"""
    async with AsyncSessionLocal() as db:  # type: AsyncSession
        account = await db.get(EmailAccount, account_id)
        if not account:
            return {
                "account_id": account_id,
                "email": "",
                "alive": False,
                "stage": "missing",
                "error": "账号不存在",
            }

        email_addr = account.email
        result = {
            "account_id": account_id,
            "email": email_addr,
            "alive": False,
            "stage": "oauth",
            "error": None,
            "status": account.status,
        }

        try:
            refresh_token = crypto.decrypt(account.refresh_token_enc)
            access_token = await outlook_oauth.get_access_token(
                email_addr, account.client_id, refresh_token
            )
            result["stage"] = "imap"
            await asyncio.to_thread(_probe_imap, email_addr, access_token)

            account.status = "ok"
            account.last_error = None
            result["alive"] = True
            result["stage"] = "ok"
            result["status"] = "ok"
        except outlook_oauth.OAuthError as e:
            msg = str(e)[:500]
            account.status = "error"
            account.last_error = f"[OAuth] {msg}"
            result["error"] = account.last_error
            result["status"] = "error"
            result["stage"] = "oauth"
        except Exception as e:
            msg = str(e)[:500]
            account.status = "error"
            # stage 已在进入 IMAP 前切到 imap；OAuth 其他异常仍标 oauth
            prefix = "IMAP" if result["stage"] == "imap" else "OAuth"
            account.last_error = f"[{prefix}] {msg}"
            result["error"] = account.last_error
            result["status"] = "error"
        finally:
            account.last_polled_at = datetime.now(timezone.utc)
            await db.commit()

        return result


async def check_batch(account_ids: list[int], concurrency: int | None = None) -> dict:
    """批量测活：信号量限流，避免同时打爆微软 token/IMAP。"""
    # 去重并保持顺序
    seen, ids = set(), []
    for aid in account_ids:
        if aid not in seen:
            seen.add(aid)
            ids.append(aid)

    limit = concurrency or min(20, max(1, settings.poll_concurrency))
    sem = asyncio.Semaphore(limit)
    results: list[dict] = []

    async def _run(aid: int):
        async with sem:
            return await check_one(aid)

    raw = await asyncio.gather(*(_run(aid) for aid in ids), return_exceptions=True)
    alive = dead = 0
    for aid, item in zip(ids, raw):
        if isinstance(item, Exception):
            results.append({
                "account_id": aid,
                "email": "",
                "alive": False,
                "stage": "error",
                "error": str(item)[:500],
                "status": "error",
            })
            dead += 1
        else:
            results.append(item)
            if item.get("alive"):
                alive += 1
            else:
                dead += 1

    return {
        "total": len(results),
        "alive": alive,
        "dead": dead,
        "items": results,
    }


async def list_enabled_account_ids(db: AsyncSession, only_enabled: bool = True) -> list[int]:
    stmt = select(EmailAccount.id)
    if only_enabled:
        stmt = stmt.where(EmailAccount.enabled == True)  # noqa: E712
    stmt = stmt.order_by(EmailAccount.id.asc())
    return list((await db.execute(stmt)).scalars().all())
