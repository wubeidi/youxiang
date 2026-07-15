"""临时监听：等验证码时，只对【单个】账号做短时快速拉取。

设计目标：低频账号平时零操作，只在你主动「开始监听」某个账号时，才对它每隔
几秒拉一次，拿到新验证码或超时后自动停止。全程不碰其他账号。

并发模型：FastAPI 单进程 asyncio 事件循环，每个监听是一个 asyncio.Task，
用字典跟踪，无需锁。停止 = 取消该 Task。
"""
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import AsyncSessionLocal
from ..models import Message, EmailAccount
from . import poller

settings = get_settings()


@dataclass
class WatchState:
    account_id: int
    started_mono: float                       # 单调时钟起点（算剩余时间用）
    expires_mono: float
    started_wall: datetime                    # 墙钟起点（筛选「监听期间新到的」邮件）
    interval: int
    email: str = ""                           # 冗余存邮箱，方便看板直接展示
    task: asyncio.Task | None = None
    poll_count: int = 0
    error_streak: int = 0
    last_error: str | None = None
    stopped: bool = False
    # 监听期间发现的最新验证码
    latest_code: str | None = None
    latest_message_id: int | None = None
    latest_subject: str | None = None
    latest_from: str | None = None


class WatchManager:
    def __init__(self):
        self._watches: dict[int, WatchState] = {}

    def get(self, account_id: int) -> WatchState | None:
        return self._watches.get(account_id)

    def active_count(self) -> int:
        return sum(1 for s in self._watches.values() if not s.stopped)

    async def start(self, account_id: int, email: str = "") -> WatchState:
        """开始监听某账号；若已在监听则续期。"""
        existing = self._watches.get(account_id)
        now = time.monotonic()
        if existing and not existing.stopped and existing.task and not existing.task.done():
            existing.expires_mono = now + settings.watch_duration_seconds   # 续期
            return existing

        if self.active_count() >= settings.watch_max_concurrent:
            raise RuntimeError(f"同时监听的账号已达上限（{settings.watch_max_concurrent}），请先停止部分监听")

        state = WatchState(
            account_id=account_id,
            email=email,
            started_mono=now,
            expires_mono=now + settings.watch_duration_seconds,
            started_wall=datetime.now(timezone.utc),
            interval=settings.watch_interval_seconds,
        )
        state.task = asyncio.create_task(self._run(state))
        self._watches[account_id] = state
        return state

    async def _run(self, state: WatchState):
        """监听主循环：先立即拉一次，之后每 interval 秒拉一次，直到超时/停止/拿到码。"""
        try:
            while time.monotonic() < state.expires_mono and not state.stopped:
                await poller.poll_single(state.account_id)
                state.poll_count += 1
                await self._refresh_status(state)

                # 连续多次失败（多为 token 失效）提前止损，不空转到超时
                if state.error_streak >= 3:
                    break
                # 拿到监听期间的新验证码即可停止
                if state.latest_code:
                    break

                # 剩余时间不足一个间隔则退出，避免超时后还睡
                if time.monotonic() + state.interval >= state.expires_mono:
                    break
                await asyncio.sleep(state.interval)
        except asyncio.CancelledError:
            pass
        finally:
            state.stopped = True

    async def _refresh_status(self, state: WatchState):
        """查账号状态 + 监听期间新到的最新验证码。"""
        async with AsyncSessionLocal() as db:  # type: AsyncSession
            account = await db.get(EmailAccount, state.account_id)
            if account and account.status == "error":
                state.error_streak += 1
                state.last_error = account.last_error
            else:
                state.error_streak = 0
                state.last_error = None

            row = (await db.execute(
                select(Message)
                .where(
                    Message.account_id == state.account_id,
                    Message.verification_code.is_not(None),
                    Message.created_at >= state.started_wall,
                )
                .order_by(Message.id.desc())
                .limit(1)
            )).scalar_one_or_none()
            if row:
                state.latest_code = row.verification_code
                state.latest_message_id = row.id
                state.latest_subject = row.subject
                state.latest_from = row.from_addr

    def stop(self, account_id: int) -> bool:
        state = self._watches.get(account_id)
        if state and state.task and not state.task.done():
            state.stopped = True
            state.task.cancel()
            return True
        return False

    def status(self, account_id: int) -> dict:
        state = self._watches.get(account_id)
        if not state:
            return {"account_id": account_id, "email": "", "active": False, "poll_count": 0, "latest_code": None}
        active = not state.stopped and bool(state.task) and not state.task.done()
        remaining = max(0, int(state.expires_mono - time.monotonic())) if active else 0
        return {
            "account_id": account_id,
            "email": state.email,
            "active": active,
            "remaining_seconds": remaining,
            "duration": settings.watch_duration_seconds,
            "poll_count": state.poll_count,
            "last_error": state.last_error,
            "latest_code": state.latest_code,
            "latest_message_id": state.latest_message_id,
            "latest_subject": state.latest_subject,
            "latest_from": state.latest_from,
        }

    def status_all(self) -> list[dict]:
        """所有被跟踪的监听状态（含已结束但保留了结果的），按剩余时间/活跃优先排序。"""
        items = [self.status(aid) for aid in list(self._watches.keys())]
        # 活跃的排前面，其次是已捕获验证码的
        items.sort(key=lambda s: (not s.get("active"), s.get("latest_code") is None))
        return items

    def stop_all(self) -> int:
        """停止全部监听，返回停止的数量。"""
        cnt = 0
        for aid in list(self._watches.keys()):
            if self.stop(aid):
                cnt += 1
        return cnt

    def clear_finished(self) -> int:
        """清除已结束的监听记录（从看板移除），返回清除数量。"""
        to_del = [aid for aid, s in self._watches.items() if s.stopped or (s.task and s.task.done())]
        for aid in to_del:
            del self._watches[aid]
        return len(to_del)

    async def shutdown(self):
        """应用关闭时取消所有监听。"""
        for state in list(self._watches.values()):
            if state.task and not state.task.done():
                state.stopped = True
                state.task.cancel()


# 全局单例
manager = WatchManager()
