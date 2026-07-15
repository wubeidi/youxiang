"""账号管理接口：导入、列表、单账号详情、手动刷新、删除。"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import EmailAccount, SiteRegistration
from ..schemas import AccountOut, ImportResult, SiteOut, WatchBatchRequest, CheckAliveBatchRequest
from ..security import require_auth
from ..services import poller
from ..services.watch import manager as watch_manager
from ..services.poller_import import import_accounts
from ..services import check_alive

router = APIRouter(prefix="/api/accounts", tags=["accounts"], dependencies=[Depends(require_auth)])


@router.post("/import", response_model=ImportResult)
async def import_config(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """上传配置文件（每行 邮箱----密码----ClientID----RefreshToken）。"""
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("gbk", errors="replace")
    return await import_accounts(db, content)


@router.post("/import-text", response_model=ImportResult)
async def import_config_text(payload: dict, db: AsyncSession = Depends(get_db)):
    """直接粘贴文本导入。"""
    content = payload.get("content", "")
    return await import_accounts(db, content)


@router.get("", response_model=dict)
async def list_accounts(
    q: str | None = Query(None, description="按邮箱模糊搜索"),
    status: str | None = Query(None),
    page: int = 1,
    size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(EmailAccount)
    count_stmt = select(func.count(EmailAccount.id))
    if q:
        stmt = stmt.where(EmailAccount.email.ilike(f"%{q}%"))
        count_stmt = count_stmt.where(EmailAccount.email.ilike(f"%{q}%"))
    if status:
        stmt = stmt.where(EmailAccount.status == status)
        count_stmt = count_stmt.where(EmailAccount.status == status)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(EmailAccount.id.desc()).offset((page - 1) * size).limit(size)
    rows = (await db.execute(stmt)).scalars().all()
    return {"total": total, "items": [AccountOut.model_validate(r) for r in rows]}


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    """概览统计：总账号、状态分布、邮件/未读/今日收件、账号邮件分布。"""
    from datetime import datetime, timezone, timedelta
    from ..models import Message

    total = (await db.execute(select(func.count(EmailAccount.id)))).scalar_one()
    by_status = (await db.execute(
        select(EmailAccount.status, func.count(EmailAccount.id)).group_by(EmailAccount.status)
    )).all()
    total_msgs = (await db.execute(select(func.sum(EmailAccount.message_count)))).scalar_one() or 0

    unread = (await db.execute(
        select(func.count(Message.id)).where(Message.is_read == False)  # noqa: E712
    )).scalar_one()
    with_code = (await db.execute(
        select(func.count(Message.id)).where(Message.verification_code.is_not(None))
    )).scalar_one()

    # 今日（UTC）新入库邮件
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_msgs = (await db.execute(
        select(func.count(Message.id)).where(Message.created_at >= day_start)
    )).scalar_one()

    # 近 7 天每日入库量（用于折线图）
    week_start = day_start - timedelta(days=6)
    daily_rows = (await db.execute(
        select(
            func.date_trunc("day", Message.created_at).label("day"),
            func.count(Message.id),
        )
        .where(Message.created_at >= week_start)
        .group_by("day")
        .order_by("day")
    )).all()
    day_map = {}
    for d, c in daily_rows:
        if d is None:
            continue
        key = d.date().isoformat() if hasattr(d, "date") else str(d)[:10]
        day_map[key] = int(c)
    daily_series = []
    for i in range(7):
        day = (week_start + timedelta(days=i)).date()
        daily_series.append({"date": day.isoformat(), "count": day_map.get(day.isoformat(), 0)})

    # 账号邮件分布（Top 8，用于环形图）
    top_accounts = (await db.execute(
        select(EmailAccount.email, EmailAccount.message_count, EmailAccount.status)
        .order_by(EmailAccount.message_count.desc(), EmailAccount.id.desc())
        .limit(8)
    )).all()
    distribution = [
        {"email": e, "message_count": int(c or 0), "status": s}
        for e, c, s in top_accounts
    ]

    return {
        "total_accounts": total,
        "by_status": {s: c for s, c in by_status},
        "total_messages": int(total_msgs),
        "unread_messages": int(unread),
        "today_messages": int(today_msgs),
        "code_messages": int(with_code),
        "daily_series": daily_series,
        "distribution": distribution,
    }


@router.get("/{account_id}/sites", response_model=list[SiteOut])
async def account_sites(account_id: int, db: AsyncSession = Depends(get_db)):
    """某账号注册过的网站列表。"""
    rows = (await db.execute(
        select(SiteRegistration)
        .where(SiteRegistration.account_id == account_id)
        .order_by(SiteRegistration.last_seen_at.desc())
    )).scalars().all()
    return [SiteOut.model_validate(r) for r in rows]


@router.post("/{account_id}/refresh")
async def refresh_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """立即拉取该账号最新邮件。"""
    account = await db.get(EmailAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    await poller.poll_single(account_id)
    await db.refresh(account)
    return {"status": account.status, "last_error": account.last_error, "message_count": account.message_count}


@router.post("/{account_id}/check")
async def check_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """单账号测活：OAuth 换票 + IMAP 轻量登录，不拉邮件正文。"""
    account = await db.get(EmailAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    return await check_alive.check_one(account_id)


@router.post("/check-batch")
async def check_accounts_batch(body: CheckAliveBatchRequest, db: AsyncSession = Depends(get_db)):
    """批量测活。account_ids 为空时测全部启用账号。"""
    if body.account_ids:
        ids = body.account_ids
    else:
        ids = await check_alive.list_enabled_account_ids(db, only_enabled=True)
    if not ids:
        return {"total": 0, "alive": 0, "dead": 0, "items": []}
    return await check_alive.check_batch(ids)


@router.post("/{account_id}/watch/start")
async def watch_start(account_id: int, db: AsyncSession = Depends(get_db)):
    """开始临时监听：只对该账号短时快速拉取，拿到验证码或超时后自动停止。"""
    account = await db.get(EmailAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    try:
        await watch_manager.start(account_id, account.email)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))
    return watch_manager.status(account_id)


@router.post("/watch/start-batch")
async def watch_start_batch(body: WatchBatchRequest, db: AsyncSession = Depends(get_db)):
    """批量开始监听多个账号（看板用）。返回成功/失败清单与全部监听状态。"""
    started, failed = [], []
    if body.account_ids:
        rows = (await db.execute(
            select(EmailAccount).where(EmailAccount.id.in_(body.account_ids))
        )).scalars().all()
        id_email = {r.id: r.email for r in rows}
        # 保持传入顺序去重
        seen = set()
        for aid in body.account_ids:
            if aid in seen:
                continue
            seen.add(aid)
            if aid not in id_email:
                failed.append({"account_id": aid, "reason": "账号不存在"})
                continue
            try:
                await watch_manager.start(aid, id_email[aid])
                started.append(aid)
            except RuntimeError as e:
                failed.append({"account_id": aid, "reason": str(e)})
    return {"started": started, "failed": failed, "active": watch_manager.status_all()}


@router.get("/watch/active")
async def watch_active():
    """看板轮询此接口：返回所有被跟踪的监听状态（活跃优先）。"""
    return watch_manager.status_all()


@router.post("/watch/stop-all")
async def watch_stop_all():
    """停止全部监听。"""
    n = watch_manager.stop_all()
    return {"stopped": n, "active": watch_manager.status_all()}


@router.post("/watch/clear-finished")
async def watch_clear_finished():
    """清除已结束的监听记录（从看板移除）。"""
    n = watch_manager.clear_finished()
    return {"cleared": n, "active": watch_manager.status_all()}


@router.post("/{account_id}/watch/stop")
async def watch_stop(account_id: int):
    """手动停止监听。"""
    watch_manager.stop(account_id)
    return watch_manager.status(account_id)


@router.get("/{account_id}/watch/status")
async def watch_status(account_id: int):
    """查询监听状态与已捕获的验证码（前端轮询此接口更新倒计时/展示码）。"""
    return watch_manager.status(account_id)


@router.delete("/{account_id}")
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    account = await db.get(EmailAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    await db.delete(account)
    await db.commit()
    return {"ok": True}
