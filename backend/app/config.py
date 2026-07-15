"""应用配置：全部从环境变量读取，敏感项不落代码库。"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 数据库连接（异步驱动）
    database_url: str = "postgresql+asyncpg://mailadmin:mailadmin@localhost:5432/maildb"

    # token 加密主密钥：32 字节的 base64（用 `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"` 生成）
    master_key: str = ""

    # 面板登录：管理员账号 + JWT 密钥
    admin_username: str = "admin"
    admin_password: str = "changeme"          # 首次启动后请务必改掉
    jwt_secret: str = "please-change-this-jwt-secret"
    jwt_expire_minutes: int = 720

    # 微软 OAuth2：消费级 outlook.com 账号的 token 端点与 scope
    oauth_token_url: str = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
    oauth_scope: str = "https://outlook.office.com/IMAP.AccessAsUser.All offline_access"

    # IMAP 服务器
    imap_host: str = "outlook.office365.com"
    imap_port: int = 993

    # 轮询设置
    # 低频账号默认【关闭】后台全量轮询：平时零操作，最省资源、最保号（避免异常访问触发微软风控）。
    # 需要即时收码时用「临时监听」（只对单个账号短时快拉），或直接「按需刷新」。
    poll_enabled: bool = False
    poll_interval_seconds: int = 300          # 每轮间隔（仅在 poll_enabled=true 时生效）
    poll_concurrency: int = 30                # 同时并发的 IMAP 连接数（防微软限流）
    fetch_max_per_account: int = 30           # 单账号每次最多拉取的新邮件数

    # 临时监听：等验证码时，只对【单个】账号做短时快速拉取，拿到即停、超时自停
    watch_interval_seconds: int = 10          # 监听期间每隔多少秒拉一次
    watch_duration_seconds: int = 180         # 单次监听最长持续时间（自动停止）
    watch_max_concurrent: int = 20            # 同时最多监听的账号数（安全上限）


@lru_cache
def get_settings() -> Settings:
    return Settings()
