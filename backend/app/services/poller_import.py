"""配置导入：解析「邮箱----密码----ClientID----RefreshToken」格式，写入数据库。

支持：
- 多行文本，每行一个账号
- 行首可选的序号（如 "1\t邮箱----..."），自动剥离
- 已存在的邮箱做更新（刷新凭证），不存在则新建
"""
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crypto
from ..models import EmailAccount
from ..schemas import ImportResult

_LEADING_INDEX = re.compile(r"^\s*\d+[\.\)\t\s]+")


def parse_line(line: str) -> dict | None:
    """解析单行；格式非法返回 None。"""
    line = line.strip()
    if not line:
        return None
    line = _LEADING_INDEX.sub("", line)          # 去掉行首序号
    parts = line.split("----")
    if len(parts) < 4:
        return None
    email_addr, password, client_id, refresh_token = (p.strip() for p in parts[:4])
    if "@" not in email_addr or not client_id or not refresh_token:
        return None
    return {
        "email": email_addr.lower(),
        "password": password,
        "client_id": client_id,
        "refresh_token": refresh_token,
    }


async def import_accounts(db: AsyncSession, content: str) -> ImportResult:
    total = created = updated = skipped = 0
    errors: list[str] = []

    for lineno, raw in enumerate(content.splitlines(), 1):
        if not raw.strip():
            continue
        total += 1
        parsed = parse_line(raw)
        if parsed is None:
            skipped += 1
            errors.append(f"第 {lineno} 行：格式不符（需 4 段 ---- 分隔）")
            continue

        existing = (
            await db.execute(select(EmailAccount).where(EmailAccount.email == parsed["email"]))
        ).scalar_one_or_none()

        if existing:
            existing.password_enc = crypto.encrypt(parsed["password"]) if parsed["password"] else None
            existing.client_id = parsed["client_id"]
            existing.refresh_token_enc = crypto.encrypt(parsed["refresh_token"])
            existing.status = "pending"
            existing.last_error = None
            existing.enabled = True
            updated += 1
        else:
            db.add(EmailAccount(
                email=parsed["email"],
                password_enc=crypto.encrypt(parsed["password"]) if parsed["password"] else None,
                client_id=parsed["client_id"],
                refresh_token_enc=crypto.encrypt(parsed["refresh_token"]),
                status="pending",
            ))
            created += 1

    await db.commit()
    return ImportResult(total=total, created=created, updated=updated, skipped=skipped, errors=errors[:50])
