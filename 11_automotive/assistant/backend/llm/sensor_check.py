"""센서 값 답 전용 다듬기 검사 (2026-10-19, 기획 `센서조회_화면안내_기획_20261019.md` 3-1 #5).

`adapter.check_text`(숫자 양방향·한글 수사·허락 문구·꼬리표)에 더해, 센서 값 답에서만 다음을 본다. 하나라도 어기면 거절하고 부른 쪽이 프로그램 문장을 낸다 (fail closed):
  · 정상 범위마다 붙는 `[참고]`, psi 옆 `bar`, 기준 시각 문구 "공용 DB 시계"가 초안만큼 남아 있다.
  · 센서 이름이 모두 남고, 센서마다 최소·평균·최대·마지막 값의 짝(예: "평균 0.86")이 **그 센서 대목 안에** 그대로 있다 (숫자 대조는 값을 맞바꿔도 통과하므로).
  · 판정 말("이상입니다·정상입니다·안정적·괜찮습니다·안전합니다·위험합니다 …")과 시점 말("지금·현재 …")이 초안에 없던 것이 새로 생기지 않았다.
`adapter.MARKERS`(문서 답의 쉽게/짧게 거절 검사까지 같이 쓰는 공유 상수)는 고치지 않는다.
"""
from __future__ import annotations

import re

JUDGE = re.compile(
    r"이상\s*(?:입니다|이에요|이야|예요|이네요|있(?:습니다|어요|음|네요)|없(?:습니다|어요|음|네요)|징후|신호)|비정상|"
    r"정상\s*(?:입니다|이에요|이야|이네요|이므로|이라|임|적|으로)|정상\s*범위\s*(?:안|내|이내)\s*(?:에|으로|로)?\s*(?:있|들어|속)|"
    r"안정(?:적|됐|되어|돼|화)|불안정|괜찮|안전(?:합|해|한|하)|위험(?:합|해|한|하|도|수준|신호)|"
    r"문제\s*(?:가\s*)?(?:없|있|될)|양호|우려|걱정|염려|심각|고장|과열|원인|때문에|예측|예상|전망|"
    r"(?:조치|점검|교체|확인)\s*(?:가|이)?\s*필요|주의\s*(?:가\s*)?(?:필요|하세요|해야)|권장|추천|하는\s*게\s*좋|좋습니다|좋아요|나쁘|좋은\s*상태|나쁜\s*상태")
NOW_WORDS = re.compile(r"지금|현재|방금|실시간|오늘|어제|내일")
PAIR = re.compile(r"(최소|평균|최대|마지막)\s*(-?\d+(?:\.\d+)?)")
HEAD = re.compile(r"^(VF2-0\d) 센서", re.M)
ITEM = re.compile(r"^- ([^:\n]+): (.*)$", re.M)
COMPARE_LINE = re.compile(r"^(.+?) 비교 — (.*)$", re.M)      # 두 설비 나란히 보기 줄 ("주축 모터 온도 비교 — 최소 VF2-01 27.7℃ · VF2-02 27.8℃ / 평균 …")
EQ_NUM = re.compile(r"(VF2-0\d)\s*(-?\d+(?:\.\d+)?)")
LABEL = re.compile(r"\s*(최소|평균|최대|마지막)")


def _count(rx: re.Pattern, s: str) -> int:
    return len(rx.findall(s))


def _pairs(s: str) -> set[tuple[str, float]]:
    return {(lab, float(num)) for lab, num in PAIR.findall(s)}


def _triples(body: str) -> set[tuple[str, str, float]]:
    """비교 줄 본문 → {(최소·평균·최대·마지막, 설비, 값)}"""
    out = set()
    for seg in re.split(r"\s/\s", body):
        m = LABEL.match(seg)
        if m:
            out |= {(m.group(1), eq, float(num)) for eq, num in EQ_NUM.findall(seg)}
    return out


def _blocks(draft: str) -> list[tuple[str, list[tuple[str, set[tuple[str, float]]]]]]:
    """초안을 설비 머리 단위로 쪼갠 (설비, [(센서 이름, 짝 집합)]). 머리가 없으면 통째로 한 덩어리."""
    heads = list(HEAD.finditer(draft))
    spans = [(h.group(1), h.start(), heads[i + 1].start() if i + 1 < len(heads) else len(draft)) for i, h in enumerate(heads)] or [("", 0, len(draft))]
    return [(eq, [(m.group(1).strip(), _pairs(m.group(2))) for m in ITEM.finditer(draft[a:b])]) for eq, a, b in spans]


def _segment(text: str, eq: str, eqs: list[str]) -> str:
    """다듬은 글에서 이 설비 대목. 설비가 하나뿐이면 글 전체, 여럿이면 이 설비 ID가 처음 나온 곳부터 다음 설비 ID가 나오기 전까지."""
    if len(eqs) <= 1 or not eq:
        return text
    start = text.find(eq)
    if start < 0:
        return ""
    ends = [text.find(o, start + len(eq)) for o in eqs if o != eq]
    ends = [e for e in ends if e >= 0]
    return text[start:min(ends)] if ends else text[start:]


def check(text: str, draft: str) -> str | None:
    """통과하면 None, 아니면 거부 사유."""
    for label, tag in (("[참고]", "[참고]"), ("bar", "bar"), ("공용 DB 시계", "기준 시각 문구(공용 DB 시계)")):
        if text.count(label) < draft.count(label):
            return f"빠진 꼬리표: {tag}"
    new_judge = [m.group(0) for m in JUDGE.finditer(text)]
    if len(new_judge) > _count(JUDGE, draft):
        return "판정 말: " + new_judge[0]
    new_now = [m.group(0) for m in NOW_WORDS.finditer(text)]
    if len(new_now) > _count(NOW_WORDS, draft):
        return "시점 말: " + new_now[0]
    blocks = _blocks(draft)
    eqs = [eq for eq, _ in blocks if eq]
    for eq, items in blocks:
        seg = _segment(text, eq, eqs)
        names = [n for n, _ in items]
        pos = {n: seg.find(n) for n in names}
        for n in names:
            if pos[n] < 0:
                return f"빠진 센서: {n}"
        ordered = sorted(pos.values())
        for n, pairs in items:
            a = pos[n]
            nxt = [p for p in ordered if p > a]
            part = seg[a:nxt[0]] if nxt else seg[a:]
            lost = sorted(pairs - _pairs(part))
            if lost:
                return f"센서 값 짝이 어긋남: {n} {lost[0][0]} {lost[0][1]:g}"
    for m in COMPARE_LINE.finditer(draft):      # 나란히 보기 줄: 설비별 값이 라벨·설비 짝 그대로 남아야 한다 (설비 둘의 값을 맞바꿔도 숫자 대조는 통과하므로)
        name = m.group(1).strip()
        mt = re.search(r"^" + re.escape(name) + r" 비교 — (.*)$", text, re.M)
        if not mt:
            return f"빠진 비교 줄: {name}"
        if _triples(m.group(2)) - _triples(mt.group(1)):
            return f"비교 줄 값 짝이 어긋남: {name}"
    return None
