"""과거 기록(9/1~9/30)과 가상 사내 문서를 읽어 둔다. 서버를 켤 때와 [처음으로] 때 읽는다.

- 보고서·문서 이력·알림·정비 문서·검사·출하·재고·공구 기록은 **백엔드 DB**에서 읽는다 (2026-10-23).
  칸 이름 = 논리 ERD 속성이라 DB 표와 생성기 out/ CSV가 같다. 값은 CSV와 같은 글자 모양으로 바꿔 둔다 (db_text).
  10/1 시연 시작(config realtime.start) 전 기록만 — 시연 중 DB에 쌓인 10/1 기록은 실시간 부분이 따로 내준다 (PAST_WHERE).
  DB를 못 쓰면(주소 없음·접속 실패·생성기 데이터와 다름) 생성기 out/ CSV를 읽는다. 어느 쪽인지는 source·/api/health.
- 기준 정보(masters)는 CSV 그대로 — 실시간 모드(생성기)가 같은 파일을 쓴다.
- 사내 문서는 가상사내문서/*.md 를 절(##·###) 단위로 나눈다 (SCR-24 보기, 비서 검색).
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import time
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote, urlparse


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------- DB에서 읽기 (2026-10-23) ----------
# 표마다 "10/1 시연 시작 전" 조건. %(c)s = 시작 시각, %(d)s = 시작 날짜
PAST_WHERE = {
    "shift": "start_at < %(c)s",
    "shift_report": "shift_id IN (SELECT shift_id FROM shift WHERE start_at < %(c)s)",
    "daily_report": "work_date < %(d)s",
    "document_revision": "created_at < %(c)s",
    "document_revision_change": "revision_id IN (SELECT revision_id FROM document_revision WHERE created_at < %(c)s)",
    "notification": "raised_at < %(c)s",
    "notification_recipient": "notification_id IN (SELECT notification_id FROM notification WHERE raised_at < %(c)s)",
    "alarm_event": "occurred_at < %(c)s",
    "maintenance_work_order": "created_at < %(c)s",
    "work_order_step": "wo_no IN (SELECT wo_no FROM maintenance_work_order WHERE created_at < %(c)s)",
    "work_record": "start_at < %(c)s",
    "work_record_check": "record_no IN (SELECT record_no FROM work_record WHERE start_at < %(c)s)",
    "work_record_part": "record_no IN (SELECT record_no FROM work_record WHERE start_at < %(c)s)",
    "pm_record": "(done_at < %(c)s OR (done_at IS NULL AND due_date < %(d)s))",
    "inventory_txn": "txn_at < %(c)s",
    "shipment": "shipped_at < %(c)s",
    "shipment_line": "shipment_no IN (SELECT shipment_no FROM shipment WHERE shipped_at < %(c)s)",
    "defect_record": "found_at < %(c)s",
    "inspection_result": "measured_at < %(c)s",
    "cmm_import": "received_at < %(c)s",
    "lot_hold": "held_at < %(c)s",
    "inspection_plan": "lot_no IN (SELECT l.lot_no FROM production_lot l JOIN shift s ON s.shift_id = l.input_shift_id WHERE s.start_at < %(c)s)",
    "tool_change": "changed_at < %(c)s",
    "raw_material_lot": "received_date < %(d)s",
}
# 줄 순서 = 생성기 CSV 순서. 기본은 기본 키 순서, 기본 키 순서가 CSV와 다른 표만 따로
PAST_ORDER = {
    "shipment_line": "shipment_no, lot_passed_at, lot_no",                       # 출하 안에서는 합격 시각 순 (FIFO)
    "document_revision_change": "revision_id, array_position(ARRAY['증상', '원인', '조치', '특이 사항', '인계 사항', '오늘의 문제'], field_name::text), field_name",
}
PK_SQL = """SELECT a.attname FROM pg_constraint c JOIN LATERAL unnest(c.conkey) WITH ORDINALITY k(attnum, n) ON true
  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
 WHERE c.contype = 'p' AND c.conrelid = %s::regclass ORDER BY k.n"""


def db_text(v) -> str:
    """DB 값 → 생성기 CSV와 같은 글자 (시각 2026-09-01T08:00:00+09:00, 수 61.6·8, 참거짓 true)."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, datetime):
        from gen.common import KST
        return v.astimezone(KST).isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(int(v)) if v == v.to_integral_value() else format(v.normalize(), "f")
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def past_db_target(root: Path) -> tuple[str | None, str]:
    """(접속 주소, 왜 이 주소인지). 주소가 None이면 CSV.
    ① MOM_PAST_DB_URL (off·csv = 끄기)  ② 백엔드 환경 파일(MOM_ENV_FILE, 기본 .env.supabase — npm run dev:api와 같은 DB)의
    MOM_READONLY_DATABASE_URL  ③ 그 파일에 MOM_AI_DB_PASSWORD만 있으면(Docker .env) 로컬 Docker DB의 읽기 계정."""
    v = os.environ.get("MOM_PAST_DB_URL", "").strip()
    if v.lower() in ("off", "csv", "0"):
        return None, "MOM_PAST_DB_URL=off"
    if v:
        return v, "MOM_PAST_DB_URL"
    name = os.environ.get("MOM_ENV_FILE", "").strip() or ".env.supabase"
    f = root / "backend" / name
    if not f.exists():
        return None, f"backend/{name} 없음"
    env = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, val = line.partition("=")
            env[k.strip()] = val.strip().strip('"').strip("'")
    if env.get("MOM_READONLY_DATABASE_URL"):
        return env["MOM_READONLY_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://"), f"backend/{name}"
    if env.get("MOM_AI_DB_PASSWORD"):
        return f"postgresql://mom_ai_ro:{quote(env['MOM_AI_DB_PASSWORD'], safe='')}@127.0.0.1:5432/mom", f"backend/{name} (로컬 Docker)"
    return None, f"backend/{name}에 DB 주소 없음"


def db_where_label(url: str) -> str:
    """로그에 남길 DB 이름 (비밀번호 빼고 호스트만)."""
    return urlparse(url).hostname or "?"


def read_past_db(url: str, cutoff: datetime, gen_out: Path) -> dict[str, list[dict]]:
    """9월 표 24개를 DB에서 한 번에 읽는다 (읽기 전용 거래). 생성기 데이터와 다른 DB면 ValueError."""
    import psycopg
    with psycopg.connect(url, connect_timeout=5) as con:
        con.read_only = True
        man = gen_out / "manifest.json"
        if man.exists():
            want = json.loads(man.read_text(encoding="utf-8")).get("config_sha256")
            got = con.execute("SELECT config_sha256 FROM dataset_info WHERE id = 1").fetchone()
            if want and (not got or (got[0] or "").strip() != want):
                raise ValueError("DB의 생성기 데이터가 이 PC의 생성기 out/ 과 다름 (dataset_info.config_sha256)")
        arg = {"c": cutoff, "d": cutoff.date()}
        out = {}
        for t, where in PAST_WHERE.items():
            order = PAST_ORDER.get(t) or ", ".join(r[0] for r in con.execute(PK_SQL, (t,)).fetchall())
            cur = con.execute(f"SELECT * FROM {t} WHERE {where} ORDER BY {order}", arg)
            cols = [d.name for d in cur.description]
            out[t] = [{c: db_text(v) for c, v in zip(cols, row)} for row in cur.fetchall()]
        # 작업지시서 계기는 DB가 계산해 보여 준다 (논리 ERD "계산" 속성 — 표에는 없음) → CSV처럼 A|B 글자로
        kinds = dict(con.execute("SELECT wo_no, array_to_string(trigger_kind::text[], '|') FROM v_work_order").fetchall())
        for w in out["maintenance_work_order"]:
            w["trigger_kind"] = kinds.get(w["wo_no"]) or ""
    return out


def num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except ValueError:
        return v


class Past:
    def __init__(self, root: Path, cutoff: datetime | None = None, log=print):
        """root = 11_automotive 폴더, cutoff = 10/1 시연 시작 시각 (없으면 DB를 쓰지 않고 CSV)."""
        out, ms = root / "생성기" / "out", root / "생성기" / "masters"
        self.root = root
        self.source = "csv"
        db, why = None, "시작 시각 없음"
        if cutoff is not None:
            url, why = past_db_target(root)
            if url:
                t0 = time.monotonic()
                try:
                    db = read_past_db(url, cutoff, out)
                    self.source = f"db:{db_where_label(url)}"
                    log(f"과거 기록 = DB ({db_where_label(url)}, {why}) — 표 {len(db)}개 {sum(map(len, db.values()))}행, {time.monotonic() - t0:.1f}초")
                except Exception as e:     # 접속 실패·psycopg 없음·데이터 다름 → 시연은 CSV로 계속
                    db, why = None, f"DB 읽기 실패 ({type(e).__name__}: {str(e).splitlines()[0][:160] if str(e) else ''})"
        if db is None:
            log(f"과거 기록 = 생성기 out/ CSV — {why}")
        r = (lambda n: db[n]) if db is not None else (lambda n: read(out / f"{n}.csv"))
        self.shift_reports = r("shift_report")
        self.daily_reports = r("daily_report")
        self.shifts = {x["shift_id"]: x for x in r("shift")}
        self.revisions = r("document_revision")
        self.rev_changes = defaultdict(list)
        for c in r("document_revision_change"):
            self.rev_changes[c["revision_id"]].append(c)
        self.notifications = r("notification")
        self.recipients = defaultdict(list)
        for x in r("notification_recipient"):
            self.recipients[x["notification_id"]].append(x)
        self.alarms = r("alarm_event")
        self.work_orders = r("maintenance_work_order")
        self.wo_steps = defaultdict(list)
        for x in r("work_order_step"):
            self.wo_steps[x["wo_no"]].append(x)
        self.work_records = r("work_record")
        self.wr_checks = defaultdict(list)
        for x in r("work_record_check"):
            self.wr_checks[x["record_no"]].append(x)
        self.wr_parts = defaultdict(list)
        for x in r("work_record_part"):
            self.wr_parts[x["record_no"]].append(x)
        self.pm_rows = r("pm_record")
        self.pm_last = {}
        for x in sorted(self.pm_rows, key=lambda x: x["done_at"] or ""):
            if x["done_at"]:
                self.pm_last[x["pm_task_id"]] = {"done_at": x["done_at"], "due_date": x["due_date"], "status": x["status"], "by": x["done_by"]}
        self.stock = defaultdict(float)
        self.inv_txns = r("inventory_txn")
        for t in self.inv_txns:
            self.stock[t["item_no"]] += float(t["qty_change"] or 0)
        self.shipments = r("shipment")
        self.ship_lines = defaultdict(list)
        for x in r("shipment_line"):
            self.ship_lines[x["shipment_no"]].append(x)
        self.defects = r("defect_record")
        self.insp = defaultdict(list)
        for x in r("inspection_result"):
            self.insp[x["lot_no"]].append(x)
        self.cmm = r("cmm_import")
        self.holds = r("lot_hold")
        self.plans = {x["lot_no"]: x for x in r("inspection_plan")}
        self.tool_changes = r("tool_change")
        self.materials = {m["material_lot_no"]: m for m in r("raw_material_lot")}
        self.items = read(ms / "inspection_item.csv")
        self.defect_codes = read(ms / "defect_code.csv")
        self.rules = read(ms / "notification_rule.csv")
        self.docs_meta = read(ms / "internal_doc.csv")
        self.users = {u["user_id"]: u for u in read(ms / "app_user.csv")}
        self.docs = {d["doc_no"]: self._parse_doc(root / d["file_ref"], d) for d in self.docs_meta}

    # ---------- 사내 문서 ----------
    @staticmethod
    def _parse_doc(path: Path, meta: dict) -> dict:
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        secs, cur = [], None
        for line in text.splitlines():
            m = re.match(r"^(#{1,4})\s+(.*)", line)
            if m:
                title = m.group(2).strip()
                sm = re.match(r"^§?(\d+(?:\.\d+)*)\.?\s+(.*)", title)
                cur = {"section": sm.group(1) if sm else title, "title": sm.group(2) if sm else title,
                       "level": len(m.group(1)), "lines": []}
                secs.append(cur)
            elif cur is not None:
                cur["lines"].append(line)
        out = []
        for s in secs:
            body = "\n".join(s["lines"]).strip()
            out.append({"section": s["section"], "title": s["title"], "level": s["level"], "text": body})
        return {"doc_no": meta["doc_no"], "doc_name": meta["doc_name"], "rev": meta["current_rev"], "rev_date": meta["rev_date"],
                "sections": out}

    def doc_section(self, doc_no: str, section: str):
        d = self.docs.get(doc_no)
        if not d:
            return None
        sec = section.lstrip("§")
        for s in d["sections"]:
            if s["section"] == sec:
                return d, s
        for s in d["sections"]:                       # "2.4"가 없으면 "2.4.1"처럼 그 아래 첫 절
            if s["section"].startswith(sec + "."):
                return d, s
        return None

    def search(self, q: str, limit: int = 4) -> list[dict]:
        """사내 문서 검색 (낱말이 많이 겹치는 절 순서). 로컬 LLM 연결 전 비서 답의 근거 찾기."""
        words = [w for w in re.split(r"[\s,.?!·()/]+", q) if len(w) >= 2]
        stems = [re.sub(r"(은|는|이|가|을|를|에|의|와|과|로|으로|도|만|요|나|해|줘|알려|뭐|어떻게|무엇)$", "", w) for w in words]
        stems = [s for s in stems if len(s) >= 2]
        scored = []
        for d in self.docs.values():
            for s in d["sections"]:
                hay = s["title"] + "\n" + s["text"]
                sc = sum(hay.count(w) * (3 if w in s["title"] else 1) for w in stems)
                if sc:
                    scored.append((sc, d, s))
        scored.sort(key=lambda x: -x[0])
        return [{"doc_no": d["doc_no"], "doc_name": d["doc_name"], "rev": d["rev"], "section": s["section"], "title": s["title"],
                 "snippet": snippet(s["text"])} for _, d, s in scored[:limit]]

    # ---------- 알림 ----------
    def open_notifications(self, at_iso: str) -> list[dict]:
        """그 시각까지 처리 안 된 과거 알림 (10/1 08:00 브리핑·알림 탭의 처음 상태)."""
        out = []
        for n in self.notifications:
            if n["raised_at"] <= at_iso and (n["is_processed"] != "true" or (n["processed_at"] or "") > at_iso):
                out.append({**n, "to": [x["user_id"] for x in self.recipients.get(n["notification_id"], [])]})
        return out


def snippet(text: str, n: int = 3) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip() and not set(l.strip()) <= set("|-: ")]
    return "\n".join(lines[:n])
