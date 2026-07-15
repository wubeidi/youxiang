"""邮件解析：从邮件中提取验证码，并推断「注册的是哪个网站」。

两件事都属于启发式：
- 验证码：结合主题/正文的中英文关键词 + 数字模式，尽量减少误报。
- 注册网站：优先用发件域名（去掉邮件服务前缀），再用品牌名兜底。
"""
import re

# 验证码上下文关键词（命中则更可能是验证码邮件）
_CODE_KEYWORDS = [
    "验证码", "校验码", "动态码", "确认码", "verification", "verify", "code",
    "otp", "one-time", "passcode", "security code", "confirm",
]

# 常见的纯数字/字母数字验证码：4-8 位，边界避免匹配到长串
_CODE_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9])(\d{4,8})(?![A-Za-z0-9])"),
    re.compile(r"(?<![A-Za-z0-9])([A-Z0-9]{6})(?![A-Za-z0-9])"),  # 6 位大写字母数字混合
]

# 发件域名中属于邮件发送服务/通用子域的前缀，剥离后更接近真实站点
_STRIP_SUBDOMAINS = {
    "mail", "email", "e", "em", "mailer", "smtp", "notification", "notifications",
    "notify", "no-reply", "noreply", "reply", "news", "newsletter", "info", "account",
    "accounts", "member", "support", "service", "send", "sender", "mktg", "marketing",
    "t", "click", "link", "mg", "sg", "post", "edm",
}


def extract_verification_code(subject: str, body: str) -> str | None:
    """从主题+正文中提取验证码；无明显验证码上下文则返回 None。"""
    text = f"{subject}\n{body}"
    lower = text.lower()

    # 没有任何验证码语境关键词时，不硬猜，避免把订单号/金额误判为验证码
    if not any(kw in lower for kw in _CODE_KEYWORDS):
        return None

    # 优先在关键词附近的窗口里找数字，命中率更高
    for kw in _CODE_KEYWORDS:
        idx = lower.find(kw)
        if idx == -1:
            continue
        window = text[idx: idx + 60]
        for pat in _CODE_PATTERNS:
            m = pat.search(window)
            if m:
                return m.group(1)

    # 退回到全文找第一个符合模式的
    for pat in _CODE_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1)
    return None


def infer_site(from_domain: str, from_name: str) -> tuple[str, str]:
    """推断注册站点，返回 (站点域名, 站点名)。

    站点域名：对发件域名剥离邮件服务子域后取主域。
    站点名：优先用发件人显示名，其次用主域的主体部分。
    """
    domain = (from_domain or "").lower().strip()
    if not domain:
        return ("", (from_name or "").strip())

    labels = domain.split(".")
    # 剥离已知的发信子域前缀（可能有多层，如 email.click.example.com）
    while len(labels) > 2 and labels[0] in _STRIP_SUBDOMAINS:
        labels = labels[1:]
    site_domain = ".".join(labels)

    # 站点名：显示名去掉常见后缀词，否则用主域名主体
    name = (from_name or "").strip()
    if not name or "@" in name:
        core = labels[0] if len(labels) >= 2 else site_domain
        name = core.capitalize()
    return (site_domain, name)
