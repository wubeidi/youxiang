"""IMAP 收信：用 XOAUTH2 认证，增量拉取新邮件。

imaplib 是同步库，XOAUTH2 支持最稳定。轮询时由上层用线程池 + 信号量并发调度，
单个账号内部保持同步逻辑，简单可靠。
"""
import email
import imaplib
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime, parseaddr

from bs4 import BeautifulSoup

from ..config import get_settings

settings = get_settings()

_MAX_BODY_CHARS = 20000       # 正文入库截断，避免超大邮件撑爆存储


def _build_auth_string(email_addr: str, access_token: str) -> str:
    return f"user={email_addr}\x01auth=Bearer {access_token}\x01\x01"


def _decode_mime(value: str | None) -> str:
    """解码 MIME 编码的邮件头（如 =?utf-8?B?...?=）。"""
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            try:
                out.append(text.decode(enc or "utf-8", errors="replace"))
            except LookupError:
                out.append(text.decode("utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _extract_body(msg: email.message.Message) -> str:
    """提取纯文本正文；HTML 则用 BeautifulSoup 转纯文本。"""
    text_body = ""
    html_body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                continue
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
            except Exception:
                continue
            if ctype == "text/plain" and not text_body:
                text_body = decoded
            elif ctype == "text/html" and not html_body:
                html_body = decoded
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace") if payload else ""
        except Exception:
            decoded = ""
        if msg.get_content_type() == "text/html":
            html_body = decoded
        else:
            text_body = decoded

    if not text_body and html_body:
        text_body = BeautifulSoup(html_body, "html.parser").get_text(" ", strip=True)
    return text_body[:_MAX_BODY_CHARS]


def fetch_new_messages(email_addr: str, access_token: str, last_uid: int, limit: int) -> list[dict]:
    """连接 IMAP，拉取 UID 大于 last_uid 的新邮件。返回解析后的 dict 列表。

    该函数为同步阻塞，调用方需放到线程池执行。
    """
    conn = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    try:
        auth = _build_auth_string(email_addr, access_token)
        conn.authenticate("XOAUTH2", lambda _: auth.encode())
        conn.select("INBOX")

        # 用 UID 搜索大于 last_uid 的邮件；last_uid=0 时取最近 limit 封
        typ, data = conn.uid("search", None, f"UID {last_uid + 1}:*")
        if typ != "OK":
            return []
        uids = [int(x) for x in data[0].split()] if data and data[0] else []
        # UID x:* 在没有新邮件时会返回最后一封，需过滤掉 <= last_uid 的
        uids = [u for u in uids if u > last_uid]
        uids = sorted(uids)[-limit:]

        results = []
        for uid in uids:
            typ, msg_data = conn.uid("fetch", str(uid), "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            from_name, from_addr = parseaddr(msg.get("From", ""))
            from_domain = from_addr.split("@")[-1].lower() if "@" in from_addr else ""
            subject = _decode_mime(msg.get("Subject"))
            try:
                received = parsedate_to_datetime(msg.get("Date"))
                if received and received.tzinfo is None:
                    received = received.replace(tzinfo=timezone.utc)
            except Exception:
                received = None

            results.append({
                "uid": uid,
                "from_addr": from_addr,
                "from_name": _decode_mime(from_name),
                "from_domain": from_domain,
                "subject": subject,
                "body_text": _extract_body(msg),
                "received_at": received,
            })
        return results
    finally:
        try:
            conn.logout()
        except Exception:
            pass
