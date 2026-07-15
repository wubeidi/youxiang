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
from ..services.check_job import manager as check_job_manager

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
    """概览统计：KPI + 多维度图表数据（趋势/状态/验证码/域名）。"""
    from datetime import datetime, timezone, timedelta
    from ..models import Message, SiteRegistration

    total = (await db.execute(select(func.count(EmailAccount.id)))).scalar_one()
    by_status = (await db.execute(
        select(EmailAccount.status, func.count(EmailAccount.id)).group_by(EmailAccount.status)
    )).all()
    status_map = {s: int(c) for s, c in by_status}
    total_msgs = (await db.execute(select(func.sum(EmailAccount.message_count)))).scalar_one() or 0

    unread = (await db.execute(
        select(func.count(Message.id)).where(Message.is_read == False)  # noqa: E712
    )).scalar_one()
    with_code = (await db.execute(
        select(func.count(Message.id)).where(Message.verification_code.is_not(None))
    )).scalar_one()

    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_msgs = (await db.execute(
        select(func.count(Message.id)).where(Message.created_at >= day_start)
    )).scalar_one()
    today_codes = (await db.execute(
        select(func.count(Message.id)).where(
            Message.created_at >= day_start,
            Message.verification_code.is_not(None),
        )
    )).scalar_one()

    # 近 90 天按日聚合：总邮件 + 验证码邮件（前端可切 7/30/90）
    range_start = day_start - timedelta(days=89)
    daily_rows = (await db.execute(
        select(
            func.date_trunc("day", Message.created_at).label("day"),
            func.count(Message.id),
            func.count(Message.verification_code),
        )
        .where(Message.created_at >= range_start)
        .group_by("day")
        .order_by("day")
    )).all()
    day_map: dict[str, dict] = {}
    for d, c, code_c in daily_rows:
        if d is None:
            continue
        key = d.date().isoformat() if hasattr(d, "date") else str(d)[:10]
        day_map[key] = {"count": int(c), "code_count": int(code_c or 0)}

    def build_series(days: int) -> list[dict]:
        start = day_start - timedelta(days=days - 1)
        out = []
        for i in range(days):
            day = (start + timedelta(days=i)).date()
            key = day.isoformat()
            item = day_map.get(key, {"count": 0, "code_count": 0})
            out.append({"date": key, "count": item["count"], "code_count": item["code_count"]})
        return out

    daily_series = build_series(7)          # 兼容旧字段
    series_7 = daily_series
    series_30 = build_series(30)
    series_90 = build_series(90)

    # 近 24 小时按小时分布（动态感更强）
    hour_start = now - timedelta(hours=23)
    hour_rows = (await db.execute(
        select(
            func.date_trunc("hour", Message.created_at).label("hour"),
            func.count(Message.id),
        )
        .where(Message.created_at >= hour_start)
        .group_by("hour")
        .order_by("hour")
    )).all()
    hour_map = {}
    for h, c in hour_rows:
        if h is None:
            continue
        key = h.strftime("%Y-%m-%d %H:00") if hasattr(h, "strftime") else str(h)[:13] + ":00"
        hour_map[key] = int(c)
    hourly_series = []
    for i in range(24):
        h = (hour_start + timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        key = h.strftime("%Y-%m-%d %H:00")
        hourly_series.append({
            "hour": h.strftime("%H:00"),
            "count": hour_map.get(key, 0),
        })

    # 账号邮件分布 Top 8
    top_accounts = (await db.execute(
        select(EmailAccount.email, EmailAccount.message_count, EmailAccount.status)
        .order_by(EmailAccount.message_count.desc(), EmailAccount.id.desc())
        .limit(8)
    )).all()
    distribution = [
        {"email": e, "message_count": int(c or 0), "status": s}
        for e, c, s in top_accounts
    ]

    # 热门发件域名 / 注册站点 Top 8
    top_domains = (await db.execute(
        select(Message.from_domain, func.count(Message.id))
        .where(Message.from_domain != "")
        .group_by(Message.from_domain)
        .order_by(func.count(Message.id).desc())
        .limit(8)
    )).all()
    domain_ranking = [
        {"domain": d or "unknown", "count": int(c)}
        for d, c in top_domains
    ]

    top_sites = (await db.execute(
        select(SiteRegistration.site_domain, SiteRegistration.site_name, func.sum(SiteRegistration.email_count))
        .group_by(SiteRegistration.site_domain, SiteRegistration.site_name)
        .order_by(func.sum(SiteRegistration.email_count).desc())
        .limit(8)
    )).all()
    site_ranking = [
        {"domain": d or "unknown", "name": n or d or "unknown", "count": int(c or 0)}
        for d, n, c in top_sites
    ]

    # 账号健康度
    health = {
        "ok": status_map.get("ok", 0),
        "error": status_map.get("error", 0),
        "pending": status_map.get("pending", 0),
        "disabled": (await db.execute(
            select(func.count(EmailAccount.id)).where(EmailAccount.enabled == False)  # noqa: E712
        )).scalar_one(),
    }

    return {
        "total_accounts": total,
        "by_status": status_map,
        "total_messages": int(total_msgs),
        "unread_messages": int(unread),
        "today_messages": int(today_msgs),
        "today_codes": int(today_codes),
        "code_messages": int(with_code),
        "daily_series": daily_series,
        "series_7": series_7,
        "series_30": series_30,
        "series_90": series_90,
        "hourly_series": hourly_series,
        "distribution": distribution,
        "domain_ranking": domain_ranking,
        "site_ranking": site_ranking,
        "health": health,
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
    """批量测活（异步任务）。

    立即返回 job_id，前端轮询 /check-jobs/{job_id} 获取进度。
    避免「测全部账号」时 HTTP 长时间阻塞导致浏览器/axios 超时误报。
    account_ids 为空时测全部启用账号。
    """
    if body.account_ids:
        ids = body.account_ids
    else:
        ids = await check_alive.list_enabled_account_ids(db, only_enabled=True)
    job = await check_job_manager.start(ids)
    # 启动接口不返回全量 items，减小首包
    data = job.to_dict(include_items=False)
    return data


@router.get("/check-jobs/{job_id}")
async def get_check_job(job_id: str, include_items: bool = True):
    """查询批量测活任务进度。"""
    job = check_job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="测活任务不存在或已过期")
    # 运行中可不回全量 items，减少带宽；结束后默认带回
    if job.status == "running" and include_items:
        # 运行中也返回已完成的部分结果，方便实时展示
        return job.to_dict(include_items=True)
    return job.to_dict(include_items=include_items)


@router.post("/check-jobs/{job_id}/cancel")
async def cancel_check_job(job_id: str):
    """取消批量测活任务。"""
    job = check_job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="测活任务不存在或已过期")
    check_job_manager.cancel(job_id)
    return job.to_dict(include_items=False)


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
