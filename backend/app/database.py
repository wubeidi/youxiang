"""数据库：异步 SQLAlchemy 2.0 引擎与会话工厂。"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()

# 连接池针对几千账号的轮询做了放大；生产可按机器再调
engine = create_async_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖：每个请求一个会话。"""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """启动时建表（生产建议改用 Alembic 迁移）。"""
    from . import models  # noqa: F401 确保模型已注册
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
