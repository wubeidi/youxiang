"""数据模型。

三张核心表：
- EmailAccount：邮箱账号 + 加密后的凭证 + 轮询状态
- Message：拉取到的邮件（含解析出的验证码）
- SiteRegistration：从邮件反推出的「该邮箱在哪些网站注册过」聚合结果
"""
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Text, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now():
    return datetime.now(timezone.utc)


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)

    # 以下三项均为 AES-GCM 加密后的密文
    password_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_id: Mapped[str] = mapped_column(String(128))          # client_id 非敏感，明文存便于排查
    refresh_token_enc: Mapped[str] = mapped_column(Text)

    # 轮询状态
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/ok/error
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_uid: Mapped[int] = mapped_column(Integer, default=0)     # 已拉取到的最大 IMAP UID（增量拉取用）
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    messages: Mapped[list["Message"]] = relationship(back_populates="account", cascade="all, delete-orphan")
    sites: Mapped[list["SiteRegistration"]] = relationship(back_populates="account", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("account_id", "uid", name="uq_account_uid"),
        Index("ix_messages_account_received", "account_id", "received_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("email_accounts.id", ondelete="CASCADE"), index=True)
    uid: Mapped[int] = mapped_column(Integer)                     # IMAP UID

    from_addr: Mapped[str] = mapped_column(String(320), default="")
    from_domain: Mapped[str] = mapped_column(String(255), default="", index=True)
    subject: Mapped[str] = mapped_column(Text, default="")
    body_text: Mapped[str] = mapped_column(Text, default="")      # 纯文本正文（截断存储）
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    verification_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    account: Mapped["EmailAccount"] = relationship(back_populates="messages")


class SiteRegistration(Base):
    """按（账号, 网站域名）聚合：这个邮箱在某站点收到过多少邮件、最近一次是什么时候。"""
    __tablename__ = "site_registrations"
    __table_args__ = (
        UniqueConstraint("account_id", "site_domain", name="uq_account_site"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("email_accounts.id", ondelete="CASCADE"), index=True)
    site_domain: Mapped[str] = mapped_column(String(255), index=True)
    site_name: Mapped[str] = mapped_column(String(255), default="")   # 推断出的站点名（品牌）
    email_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped["EmailAccount"] = relationship(back_populates="sites")
