"""로그인 토큰 (JWT HS256, PyJWT). 로그인 방식 자체는 [선택 필요: 기술 회의] — 지금은 아이디·비밀번호 + 토큰."""
from __future__ import annotations

import datetime as dt

import jwt


def create_token(user_id: str, role_code: str, secret: str, minutes: int, now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(dt.timezone.utc)
    payload = {"sub": user_id, "role": role_code, "iat": int(now.timestamp()),
               "exp": int((now + dt.timedelta(minutes=minutes)).timestamp())}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict:
    """만료·서명 오류면 jwt.PyJWTError를 던진다."""
    return jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["sub", "exp"]})
