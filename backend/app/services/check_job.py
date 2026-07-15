"""批量测活任务：后台异步执行，前端轮询进度。

为什么不用「一个 HTTP 请求跑完全部账号」：
- 账号一多，整批可能跑几分钟甚至更久
- 浏览器/axios 默认超时后前端报错，但后端其实还在继续
- 改成任务模式：接口秒回 job_id，前端轮询进度，体验稳定
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field

from . import check_alive


@dataclass
class CheckJob:
    job_id: str
    account_ids: list[int]
    total: int
    done: int = 0
    alive: int = 0
    dead: int = 0
    status: str = "pending"  # pending / running / done / error / cancelled
    error: str | None = None
    items: list[dict] = field(default_factory=list)
    created_mono: float = field(default_factory=time.monotonic)
    finished_mono: float | None = None
    task: asyncio.Task | None = None

    def to_dict(self, include_items: bool = True) -> dict:
        data = {
            "job_id": self.job_id,
            "status": self.status,
            "total": self.total,
            "done": self.done,
            "alive": self.alive,
            "dead": self.dead,
            "percent": int(self.done * 100 / self.total) if self.total else 100,
            "error": self.error,
            "elapsed_seconds": int(
                (self.finished_mono or time.monotonic()) - self.created_mono
            ),
        }
        if include_items:
            data["items"] = self.items
        return data


class CheckJobManager:
    def __init__(self):
        self._jobs: dict[str, CheckJob] = {}
        self._lock = asyncio.Lock()

    def get(self, job_id: str) -> CheckJob | None:
        return self._jobs.get(job_id)

    async def start(self, account_ids: list[int], concurrency: int | None = None) -> CheckJob:
        # 去重保序
        seen, ids = set(), []
        for aid in account_ids:
            if aid not in seen:
                seen.add(aid)
                ids.append(aid)

        job = CheckJob(
            job_id=uuid.uuid4().hex,
            account_ids=ids,
            total=len(ids),
            status="running" if ids else "done",
        )
        if not ids:
            job.finished_mono = time.monotonic()
            self._jobs[job.job_id] = job
            return job

        self._jobs[job.job_id] = job
        job.task = asyncio.create_task(self._run(job, concurrency))
        self._cleanup_old_jobs()
        return job

    async def _run(self, job: CheckJob, concurrency: int | None):
        try:
            limit = concurrency or 10
            sem = asyncio.Semaphore(limit)

            async def _one(aid: int):
                async with sem:
                    try:
                        return await check_alive.check_one(aid)
                    except Exception as e:
                        return {
                            "account_id": aid,
                            "email": "",
                            "alive": False,
                            "stage": "error",
                            "error": str(e)[:500],
                            "status": "error",
                        }

            # 分批 gather，边跑边推进度，前端能看到 done 增长
            batch_size = max(limit * 2, 20)
            for i in range(0, len(job.account_ids), batch_size):
                if job.status == "cancelled":
                    break
                chunk = job.account_ids[i: i + batch_size]
                results = await asyncio.gather(*(_one(aid) for aid in chunk))
                for item in results:
                    job.items.append(item)
                    job.done += 1
                    if item.get("alive"):
                        job.alive += 1
                    else:
                        job.dead += 1

            if job.status != "cancelled":
                job.status = "done"
        except Exception as e:
            job.status = "error"
            job.error = str(e)[:500]
        finally:
            job.finished_mono = time.monotonic()

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job or job.status not in ("pending", "running"):
            return False
        job.status = "cancelled"
        if job.task and not job.task.done():
            job.task.cancel()
        job.finished_mono = time.monotonic()
        return True

    def _cleanup_old_jobs(self, keep: int = 20, max_age_sec: int = 3600):
        """只保留最近的任务，避免内存无限涨。"""
        now = time.monotonic()
        # 先按时间清过期
        for jid, job in list(self._jobs.items()):
            if job.status in ("done", "error", "cancelled"):
                finished = job.finished_mono or job.created_mono
                if now - finished > max_age_sec:
                    del self._jobs[jid]
        # 再按数量裁剪
        if len(self._jobs) <= keep:
            return
        ordered = sorted(self._jobs.values(), key=lambda j: j.created_mono, reverse=True)
        for job in ordered[keep:]:
            if job.status in ("done", "error", "cancelled"):
                self._jobs.pop(job.job_id, None)


manager = CheckJobManager()
