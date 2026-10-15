"""비밀번호 해시 (NFR-SEC-06·07). 표준 라이브러리 hashlib.scrypt만 쓴다.

저장 형식: scrypt$N$r$p$<salt base64>$<hash base64>
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

N, R, P, DKLEN = 2 ** 14, 8, 1, 32


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    if not password:
        raise ValueError("빈 비밀번호")
    salt = salt or os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=DKLEN)
    return f"scrypt${N}${R}${P}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not password:
        return False
    try:
        algo, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk, expected)


# 없는 아이디로 로그인해도 같은 시간이 걸리게 (아이디가 있는지 시간으로 알아내지 못하게)
DUMMY_HASH = hash_password("timing-equalizer", salt=b"\x00" * 16)
