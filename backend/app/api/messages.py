"""邮件接口：列表（可按账号/验证码筛选）、详情、标记已读。"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Message
from ..schemas import MessageOut, PaginatedMessages
from ..security import require_auth

router = APIRouter(prefix="/api/messages", tags=["messages"], dependencies=[Depends(require_auth)])


@router.get("", response_model=PaginatedMessages)
async def list_messages(
    account_id: int | None = Query(None),
    only_code: bool = Query(False, description="只看含验证码的邮件"),
    q: str | None = Query(None, description="按主题/发件人搜索"),
    page: int = 1,
    size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Message)
    count_stmt = select(func.count(Message.id))
    conds = []
    if account_id:
        conds.append(Message.account_id == account_id)
    if only_code:
        conds.append(Message.verification_code.is_not(None))
    if q:
        conds.append(Message.subject.ilike(f"%{q}%") | Message.from_addr.ilike(f"%{q}%"))
    for c in conds:
        stmt = stmt.where(c)
        count_stmt = count_stmt.where(c)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Message.received_at.desc().nullslast(), Message.id.desc())
    stmt = stmt.offset((page - 1) * size).limit(size)
    rows = (await db.execute(stmt)).scalars().all()
    return PaginatedMessages(total=total, items=[MessageOut.model_validate(r) for r in rows])


@router.get("/{message_id}", response_model=MessageOut)
async def get_message(message_id: int, db: AsyncSession = Depends(get_db)):
    msg = await db.get(Message, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="邮件不存在")
    if not msg.is_read:
        msg.is_read = True
        await db.commit()
        await db.refresh(msg)
    return MessageOut.model_validate(msg)
