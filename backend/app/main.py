"""FastAPI 应用入口：注册路由、初始化数据库、启动后台轮询调度。"""
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .api import auth, accounts, messages
from .services import poller
from .services.watch import manager as watch_manager

settings = get_settings()
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：建表 + （可选）挂载后台全量轮询任务
    await init_db()
    # 默认 poll_enabled=false：低频账号不做后台全量轮询，改用「临时监听 / 按需刷新」。
    # 仅当确实需要所有账号准实时收信时才置为 true。
    if settings.poll_enabled:
        scheduler.add_job(
            poller.poll_all_once,
            "interval",
            seconds=settings.poll_interval_seconds,
            id="poll_all",
            max_instances=1,
            coalesce=True,           # 错过的任务合并，不堆积
        )
        scheduler.start()
    yield
    # 关闭：停调度器 + 取消所有临时监听
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await watch_manager.shutdown()


app = FastAPI(title="邮箱管理服务", version="1.0", lifespan=lifespan)

# 开发期放开跨域；生产建议由反向代理同域部署并收紧
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(messages.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
