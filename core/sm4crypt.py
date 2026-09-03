"""SM4 国密加密传输 - 口令字段加密(等保合规,一次性密钥)。

流程: GET /api/v1/wx/auth/salt -> {kid,key,iv}; 前端 SM4-CBC 加密口令;
POST /api/v1/wx/auth/login form 表单追加 kid 字段, 后端解密后即焚。
不传 kid 的明文请求仍兼容（仅供旧脚本；网页登录会发送 SM4 密文）。
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from cachetools import TTLCache
from gmssl.sm4 import CryptSM4, SM4_DECRYPT

_KID_TTL = 300  # 秒
_keys: TTLCache = TTLCache(maxsize=4096, ttl=_KID_TTL)


def issue_key() -> dict:
    kid = secrets.token_hex(8)
    _keys[kid] = {
        "key": secrets.token_hex(16),
        "iv": secrets.token_hex(16),
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=_KID_TTL),
    }
    return {"kid": kid, "key": _keys[kid]["key"], "iv": _keys[kid]["iv"]}


def decrypt(cipher_hex: str, kid: str) -> str:
    """解密口令密文并即焚。失败抛 400。"""
    entry = _keys.pop(kid, None)  # 取出即焚: 解密成功与否都失效
    if entry is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="加密会话已失效，请刷新重试")
    try:
        cipher = bytes.fromhex(cipher_hex.strip())
        if not cipher or len(cipher) % 16 != 0 or len(cipher) > 1024:
            raise ValueError
        sm4 = CryptSM4()
        sm4.set_key(bytes.fromhex(entry["key"]), SM4_DECRYPT)
        return sm4.crypt_cbc(bytes.fromhex(entry["iv"]), cipher).decode("utf-8")
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="密码解密失败")
