"""OP-50 측정 결과 파일(CSV) 읽기 — DOC-06 Rev.2 §3.6, 논리 ERD R-78·R-80.

지원 양식: "MOM-CMM-CSV v0.1" (사용자 폴더 Claude outputs/ 의 예시 파일 3개와 같은 모양)
    #format,MOM-CMM-CSV v0.1 ...      ← '#키,값' 머리 줄
    #lot_no,LOT-2609-038-1
    ...
    char_no,char_name,position,nominal,upper_tol,lower_tol,actual,deviation,cmm_judgement,unit
    1,부싱 압입 구멍 지름 Ø45 H7,STD,45.000,0.025,0.000,45.011,0.011,PASS,mm

두 번째 양식 (2026-10-14 생성기 10/1 실시간 `out_realtime/cmm_drop/*.csv` — 가상데이터설계서 5.15, CMM 조사 5.2 양식):
    lot_no,part_seq,insp_kind,program_name_rev,item_seq,position,nominal,upper_tol,lower_tol,measured_value,judgement,
    instrument_id,measure_start_at,measure_end_at,part_temp_c,machine_temp_c,temp_comp_on
    (머리 값이 줄마다 되풀이되는 평평한 표, 1파일 = 측정 부품 1개). 읽을 때 첫 번째 양식으로 바꿔 같은 확인을 거친다.

양식이 깨졌으면(필수 열 빠짐, 숫자 아님, 모르는 값) CmmFormatError → 서버는 기록하지 않고 "오류" 칸으로 옮긴다 (R-80).
지시와 다른 로트·순번·불완전 같은 "내용" 문제는 여기서 판단하지 않는다 → DB fn_import_cmm (확인 필요).

[선택 필요] 부품 순번: 예시 파일은 순번 칸 없이 sample_no(S01·S06·F12)만 있다.
  지금은 ① 머리에 part_seq가 있으면 그것, ② 없으면 sample_no 끝의 숫자를 부품 순번으로 본다.
  S06이 "6번 부품"인지 "6번째 측정"인지 정해지지 않았으므로, 측정 지시와 맞지 않으면 DB가 확인 필요로 돌린다.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import re
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = ("char_no", "actual", "cmm_judgement")
REQUIRED_HEADER = ("lot_no", "insp_kind")
# 측정 위치: 빈칸 = 표준(None → DB NULL), TOP/MID/BOTTOM (논리 ERD 5.F.4, 2026-10-14). 옛 표기 STD·BOT도 받는다
POSITION_MAP = {"": None, "STD": None, "표준": None, "TOP": "TOP", "위": "TOP", "MID": "MID", "중간": "MID",
                "BOTTOM": "BOTTOM", "BOT": "BOTTOM", "아래": "BOTTOM"}
KIND_MAP = {"FIRST": "FIRST", "초품": "FIRST", "SAMPLE": "SAMPLE", "발췌": "SAMPLE", "ENHANCED": "ENHANCED", "강화": "ENHANCED"}
JUDGE_MAP = {"PASS": "PASS", "OK": "PASS", "합격": "PASS", "FAIL": "FAIL", "NG": "FAIL", "불합격": "FAIL"}
BOOL_MAP = {"ON": True, "켬": True, "TRUE": True, "1": True, "OFF": False, "끔": False, "FALSE": False, "0": False}
LOT_RE = re.compile(r"^LOT-\d{4}-\d{3}-\d+$")
# 결과 파일 이름 규칙 [제안]: 재측정 때 이름이 겹치지 않게 측정 끝 시각을 붙인다
SUGGESTED_NAME = "{cmm_id}_{lot_no}_{sample_no}_{insp_kind}_{yyyymmddHHMMSS}.csv"


class CmmFormatError(ValueError):
    def __init__(self, text: str, header: dict | None = None):
        super().__init__(text)
        self.error_kind = "FORMAT"
        self.text = text
        self.header = header or {}


def _num(value: str, what: str, header: dict) -> str:
    try:
        Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        raise CmmFormatError(f"숫자 아님: {what} = {value!r}", header) from None
    return value.strip()


def _ts(value: str, what: str, header: dict) -> str:
    try:
        t = dt.datetime.fromisoformat(value.strip())
    except ValueError:
        raise CmmFormatError(f"시각 형식 아님: {what} = {value!r}", header) from None
    if t.tzinfo is None:
        raise CmmFormatError(f"시각에 시간대가 없음: {what} = {value!r}", header)
    return t.isoformat()


def part_seq_from_sample(sample_no: str | None) -> int | None:
    if not sample_no:
        return None
    m = re.search(r"(\d+)$", sample_no.strip())
    return int(m.group(1)) if m else None


FLAT_REQUIRED = ("lot_no", "part_seq", "insp_kind", "item_seq", "measured_value", "judgement")
FLAT_HEADER = {"program_name_rev": "program", "instrument_id": "cmm_id", "measure_start_at": "measure_start_at",
               "measure_end_at": "measure_end_at", "part_temp_c": "part_temp_c", "machine_temp_c": "machine_temp_c",
               "temp_comp_on": "temp_comp"}


def _flat_to_mom(text: str) -> str:
    """생성기 평평한 양식 → MOM-CMM-CSV 모양 글 (머리 값은 모든 줄이 같아야 한다)"""
    reader = csv.DictReader(io.StringIO(text))
    cols = [c.strip() for c in (reader.fieldnames or [])]
    missing = [c for c in FLAT_REQUIRED if c not in cols]
    if missing:
        raise CmmFormatError("열 빠짐: " + ", ".join(missing))
    rows = [{k.strip(): (v or "").strip() for k, v in raw.items() if k} for raw in reader]
    if not rows:
        raise CmmFormatError("측정 줄이 없음")
    head_keys = ["lot_no", "part_seq", "insp_kind", *[k for k in FLAT_HEADER if k in cols]]
    first = rows[0]
    for i, r_ in enumerate(rows[1:], start=2):
        diff = [k for k in head_keys if r_.get(k, "") != first.get(k, "")]
        if diff:
            raise CmmFormatError(f"{i}번째 줄: 한 파일 안에서 머리 값이 다름 ({', '.join(diff)}) — 1파일 = 측정 부품 1개")
    out = io.StringIO()
    out.write("#format,GEN-CMM-CSV (생성기 5.15)\n")
    for k in ("lot_no", "part_seq", "insp_kind"):
        out.write(f"#{k},{first[k]}\n")
    for k, mk in FLAT_HEADER.items():
        if first.get(k):
            out.write(f"#{mk},{first[k]}\n")
    if first.get("measure_end_at"):
        out.write(f"#measured_at,{first['measure_end_at']}\n")
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["char_no", "position", "nominal", "upper_tol", "lower_tol", "actual", "cmm_judgement"])
    for r_ in rows:
        w.writerow([r_["item_seq"], r_.get("position", ""), r_.get("nominal", ""), r_.get("upper_tol", ""),
                    r_.get("lower_tol", ""), r_["measured_value"], r_["judgement"]])
    return out.getvalue()


def parse(text: str) -> tuple[dict, list[dict]]:
    """파일 내용 → (머리 dict, 줄 list). 줄: {item_seq, position, actual, cmm_judgement, nominal, ...}"""
    if text.startswith("\ufeff"):
        text = text[1:]
    first_line = next((ln for ln in text.splitlines() if ln.strip()), "")
    if first_line.replace(" ", "").startswith("lot_no,"):       # 생성기 평평한 양식
        text = _flat_to_mom(text)
    header: dict = {}
    table_lines: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("#"):
            key, _, value = line[1:].partition(",")
            header[key.strip()] = value.strip()
        else:
            table_lines.append(line)
    if not table_lines:
        raise CmmFormatError("측정 표가 없음", header)

    for key in REQUIRED_HEADER:
        if not header.get(key):
            raise CmmFormatError(f"머리 칸 빠짐: {key}", header)
    if not LOT_RE.match(header["lot_no"]):
        raise CmmFormatError(f"로트 번호 형식 아님: {header['lot_no']}", header)
    kind = KIND_MAP.get(header["insp_kind"].strip().upper(), KIND_MAP.get(header["insp_kind"].strip()))
    if not kind:
        raise CmmFormatError(f"검사 방식 값 모름: {header['insp_kind']}", header)
    header["insp_kind"] = kind
    if header.get("part_seq"):
        if not header["part_seq"].isdigit():
            raise CmmFormatError(f"부품 순번 숫자 아님: {header['part_seq']}", header)
        header["part_seq"] = int(header["part_seq"])
    else:
        seq = part_seq_from_sample(header.get("sample_no"))
        if seq is None:
            raise CmmFormatError("부품 순번(part_seq)도 sample_no 숫자도 없음", header)
        header["part_seq"] = seq
    for key in ("measured_at", "measure_start_at", "measure_end_at"):
        if header.get(key):
            header[key] = _ts(header[key], key, header)
    for key in ("room_temp_c", "part_temp_c", "machine_temp_c"):
        if header.get(key):
            header[key] = _num(header[key], key, header)
    if header.get("temp_comp"):
        b = BOOL_MAP.get(header["temp_comp"].strip().upper(), BOOL_MAP.get(header["temp_comp"].strip()))
        if b is None:
            raise CmmFormatError(f"온도 보정 값 모름: {header['temp_comp']}", header)
        header["temp_comp"] = b

    reader = csv.DictReader(io.StringIO("\n".join(table_lines)))
    cols = [c.strip() for c in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing:
        raise CmmFormatError("열 빠짐: " + ", ".join(missing), header)
    rows: list[dict] = []
    for i, raw in enumerate(reader, start=1):
        r = {k.strip(): (v or "").strip() for k, v in raw.items() if k}
        if not r.get("char_no", "").isdigit():
            raise CmmFormatError(f"{i}번째 줄: 항목 번호(char_no) 숫자 아님 {r.get('char_no')!r}", header)
        raw_pos = r.get("position", "")
        key = raw_pos.upper() if raw_pos.upper() in POSITION_MAP else raw_pos
        if key not in POSITION_MAP:
            raise CmmFormatError(f"{i}번째 줄: 측정 위치 값 모름 {r.get('position')!r}", header)
        judge = JUDGE_MAP.get(r["cmm_judgement"].upper(), JUDGE_MAP.get(r["cmm_judgement"]))
        if judge is None:
            raise CmmFormatError(f"{i}번째 줄: 측정기 판정 값 모름 {r['cmm_judgement']!r}", header)
        row = {"item_seq": int(r["char_no"]), "position": POSITION_MAP[key], "actual": _num(r["actual"], f"{i}번째 줄 actual", header),
               "cmm_judgement": judge}
        for opt in ("nominal", "upper_tol", "lower_tol", "deviation"):
            if r.get(opt):
                row[opt] = _num(r[opt], f"{i}번째 줄 {opt}", header)
        if r.get("char_name"):
            row["char_name"] = r["char_name"]
        rows.append(row)
    if not rows:
        raise CmmFormatError("측정 줄이 없음", header)
    keys = [(r["item_seq"], r["position"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise CmmFormatError("한 파일 안에 같은 항목·측정 위치 줄이 두 번 있음", header)
    return header, rows
