"""Pydantic 出入参模型。"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    status: str
    last_error: str | None
    last_polled_at: datetime | None
    message_count: int
    enabled: bool
    created_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    from_addr: str
    from_domain: str
    subject: str
    body_text: str
    received_at: datetime | None
    verification_code: str | None
    is_read: bool


class SiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    site_domain: str
    site_name: str
    email_count: int
    first_seen_at: datetime | None
    last_seen_at: datetime | None


class ImportResult(BaseModel):
    total: int
    created: int
    updated: int
    skipped: int
    errors: list[str]


class PaginatedMessages(BaseModel):
    total: int
    items: list[MessageOut]


class WatchBatchRequest(BaseModel):
    account_ids: list[int]


class CheckAliveBatchRequest(BaseModel):
    """批量测活请求。account_ids 为空或不传时，测全部启用账号。"""
    account_ids: list[int] | None = None
