"""과거 기록(생성기 out/ = 9/1~9/30)과 가상 사내 문서를 읽어 둔다. 서버를 켤 때 한 번 읽는다.

- 보고서·문서 이력·알림·정비 문서·검사·출하는 out/ CSV 그대로 (칸 이름 = 논리 ERD 속성).
- 사내 문서는 가상사내문서/*.md 를 절(##·###) 단위로 나눈다 (SCR-24 보기, 비서 검색).
"""
from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from pathlib import Path


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except ValueError:
        return v


class Past:
    def __init__(self, root: Path):
        """root = 11_automotive 폴더."""
        from gen.common import load_config      # 프로필(MOM_PROFILE)이 정한 기록 폴더 (out_video / out_final)
        out, ms = root / "생성기" / load_config()["run"]["out_dir"], root / "생성기" / "masters"
        self.root = root
        r = lambda n: read(out / f"{n}.csv")
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
        """그 시각까지 처리 안 된 과거 알림 (실시간 시작 시각 브리핑·알림 탭의 처음 상태)."""
        out = []
        for n in self.notifications:
            if n["raised_at"] <= at_iso and (n["is_processed"] != "true" or (n["processed_at"] or "") > at_iso):
                out.append({**n, "to": [x["user_id"] for x in self.recipients.get(n["notification_id"], [])]})
        return out


def snippet(text: str, n: int = 3) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip() and not set(l.strip()) <= set("|-: ")]
    return "\n".join(lines[:n])
