"""后台轮询引擎：定时遍历所有启用的账号，增量拉取新邮件入库。

并发模型：
- 主协程用 asyncio.Semaphore 限制同时在线的 IMAP 连接数（防微软限流）。
- 每个账号：异步刷新 token → 线程池跑同步 IMAP 拉取 → 异步写库。
- 单账号失败只标记该账号 error，不影响其他账号。
"""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import AsyncSessionLocal
from .. import crypto
from ..models import EmailAccount, Message, SiteRegistration
from . import outlook_oauth, imap_client, parser

settings = get_settings()

_running = False    # 防止上一轮没跑完又叠一轮


async def _persist_messages(db: AsyncSession, account: EmailAccount, msgs: list[dict]):
    """把拉取到的邮件写库，并更新验证码 / 站点聚合。"""
    if not msgs:
        return 0

    new_max_uid = account.last_uid
    saved = 0
    for m in msgs:
        code = parser.extract_verification_code(m["subject"], m["body_text"])
        db.add(Message(
            account_id=account.id,
            uid=m["uid"],
            from_addr=m["from_addr"],
            from_domain=m["from_domain"],
            subject=m["subject"],
            body_text=m["body_text"],
            received_at=m["received_at"],
            verification_code=code,
        ))
        saved += 1
        new_max_uid = max(new_max_uid, m["uid"])

        # 更新站点聚合
        site_domain, site_name = parser.infer_site(m["from_domain"], m.get("from_name", ""))
        if site_domain:
            reg = (await db.execute(
                select(SiteRegistration).where(
                    SiteRegistration.account_id == account.id,
                    SiteRegistration.site_domain == site_domain,
                )
            )).scalar_one_or_none()
            ts = m["received_at"] or datetime.now(timezone.utc)
            if reg:
                reg.email_count += 1
                reg.last_seen_at = max(reg.last_seen_at or ts, ts)
            else:
                db.add(SiteRegistration(
                    account_id=account.id, site_domain=site_domain, site_name=site_name,
                    email_count=1, first_seen_at=ts, last_seen_at=ts,
                ))

    account.last_uid = new_max_uid
    account.message_count += saved
    return saved


async def poll_account(sem: asyncio.Semaphore, account_id: int):
    """轮询单个账号。独立会话，避免相互影响。"""
    async with sem:
        async with AsyncSessionLocal() as db:
            account = await db.get(EmailAccount, account_id)
            if not account or not account.enabled:
                return
            try:
                refresh_token = crypto.decrypt(account.refresh_token_enc)
                access_token = await outlook_oauth.get_access_token(
                    account.email, account.client_id, refresh_token
                )
                # IMAP 同步拉取放线程池
                msgs = await asyncio.to_thread(
                    imap_client.fetch_new_messages,
                    account.email, access_token, account.last_uid, settings.fetch_max_per_account,
                )
                await _persist_messages(db, account, msgs)
                account.status = "ok"
                account.last_error = None
            except Exception as e:
                account.status = "error"
                account.last_error = str(e)[:500]
            finally:
                account.last_polled_at = datetime.now(timezone.utc)
                await db.commit()


async def poll_all_once():
    """跑一轮：遍历所有启用账号。"""
    global _running
    if _running:
        return
    _running = True
    try:
        async with AsyncSessionLocal() as db:
            ids = (await db.execute(
                select(EmailAccount.id).where(EmailAccount.enabled == True)  # noqa: E712
            )).scalars().all()

        sem = asyncio.Semaphore(settings.poll_concurrency)
        await asyncio.gather(*(poll_account(sem, aid) for aid in ids), return_exceptions=True)
    finally:
        _running = False


async def poll_single(account_id: int):
    """立即轮询单个账号（供「手动刷新」按钮调用）。"""
    sem = asyncio.Semaphore(1)
    await poll_account(sem, account_id)
