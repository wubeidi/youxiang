"""凭证加密：refresh token 等长期凭证入库前用 AES-256-GCM 加密。

设计要点：
- 主密钥来自环境变量 MASTER_KEY（32 字节 base64），绝不落库、绝不进代码。
- 每条密文自带随机 12 字节 nonce，输出格式：base64(nonce + ciphertext + tag)。
- GCM 自带完整性校验，密文被篡改会解密失败。
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import get_settings

_settings = get_settings()


def _load_key() -> bytes:
    raw = _settings.master_key.strip()
    if not raw:
        raise RuntimeError("未配置 MASTER_KEY，无法加密凭证。请在 .env 中设置 32 字节 base64 密钥。")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError("MASTER_KEY 解码后必须是 32 字节（AES-256）。")
    return key


_KEY = _load_key()
_aesgcm = AESGCM(_KEY)


def encrypt(plaintext: str) -> str:
    """加密明文，返回 base64 字符串。"""
    nonce = os.urandom(12)
    ct = _aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt(token: str) -> str:
    """解密 base64 密文，返回明文。"""
    data = base64.b64decode(token)
    nonce, ct = data[:12], data[12:]
    return _aesgcm.decrypt(nonce, ct, None).decode("utf-8")
