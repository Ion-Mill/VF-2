"""QR 내용 규칙 (2026-10-13 가정 "재고·로트는 QR로 관리" [제안]) — DB 없이 도는 순수 로직.

QR 안에는 **번호만** 넣는다. 수량·상태는 넣지 않는다 (라벨을 붙인 뒤에 바뀌므로 찍을 때 서버에서 읽는다).

    MOM:LOT:LOT-2609-041-1     생산 로트 (부품 꼬리표 — OP-50 측정 시작 때 찍는 "로트 바코드"와 같은 것)
    MOM:MAT:MAT-2609-12        원자재 로트 (입고 때 라벨)
    MOM:ITEM:TL-EM10           재고 품목 (공구·소모품 보관함 라벨)

머리(MOM:종류:)가 없는 번호만 찍혀도 번호 모양으로 알아본다 — 이미 붙은 바코드·손으로 친 번호도 받기 위해.
"""
from __future__ import annotations

import re

PREFIX = "MOM"
MAX_LEN = 120
PATTERNS = {
    "LOT": re.compile(r"^LOT-\d{4}-\d{3}-\d+$"),
    "MAT": re.compile(r"^MAT-\d{4}-\d{2,3}$"),
    "ITEM": re.compile(r"^(TL|CS|RM|FG)-[A-Z0-9-]+$"),
}
KIND_KO = {"LOT": "생산 로트", "MAT": "원자재 로트", "ITEM": "재고 품목"}


class QrError(ValueError):
    """읽을 수 없는 QR — 서버는 422 VALIDATION"""


def parse(code: str) -> tuple[str, str]:
    """찍은 글자 → (종류, 번호). 앞뒤 공백·소문자는 고쳐 읽는다."""
    if code is None:
        raise QrError("QR 내용이 비어 있음")
    text = code.strip()
    if not text:
        raise QrError("QR 내용이 비어 있음")
    if len(text) > MAX_LEN:
        raise QrError(f"QR 내용이 너무 김 (>{MAX_LEN}자)")
    text = text.upper()
    parts = text.split(":")
    if len(parts) == 3 and parts[0] == PREFIX:
        kind, no = parts[1], parts[2].strip()
        if kind not in PATTERNS:
            raise QrError(f"모르는 QR 종류 {kind!r} (LOT·MAT·ITEM)")
        if not PATTERNS[kind].match(no):
            raise QrError(f"{KIND_KO[kind]} 번호 모양이 아님: {no!r}")
        return kind, no
    if ":" in text:
        raise QrError(f"MOM QR이 아님: {text!r} (MOM:종류:번호)")
    for kind, pat in PATTERNS.items():
        if pat.match(text):
            return kind, text
    raise QrError(f"번호 모양을 알 수 없음: {text!r} (LOT-…, MAT-…, TL-/CS-/RM-/FG-…)")


def payload(kind: str, no: str) -> str:
    """라벨에 찍을 QR 내용. 번호 모양이 맞는지 확인한다."""
    kind = kind.upper()
    if kind not in PATTERNS:
        raise QrError(f"모르는 QR 종류 {kind!r} (LOT·MAT·ITEM)")
    if not PATTERNS[kind].match(no):
        raise QrError(f"{KIND_KO[kind]} 번호 모양이 아님: {no!r}")
    return f"{PREFIX}:{kind}:{no}"
