"""시연 서버 → DB 표 맞추기 (POST /api/ingest/sync, 2026-10-23). 시연 모드(로컬 Docker DB)에서만 부른다.

시연 서버(frontend/tools/db_relay.py)가 몇 초마다 생성기 10/1 기록(Realtime.tables() — out_realtime CSV와 같은 칸·번호·글자)
중 바뀐 줄만 보낸다. 여기서는 tools/load_generated.py --realtime 과 같은 규칙으로 넣는다:
  · 한 트랜잭션, app.loading = on (알림·자동 규칙 끔), 부모 표 먼저, 기본 키가 같으면 덮어쓰기 (칸이 같으면 그대로)
  · 빈칸인데 DB는 NOT NULL + 기본값인 칸은 기본값 (예: production_lot.scrap_qty)
  · 추가만 하는 표(inventory_txn)는 있으면 건너뜀
  · 넣은 뒤 일련번호·업무 번호 카운터·공구 누적을 맞춘다
실시간 규칙은 살린다 (9월 적재와 다른 점):
  · 재공·측정값·병목은 새 줄을 app.loading = off로 넣는다 → 재공 경고·관리도 이상·병목 이동 알림 (views/30_live_rules.sql)
  · 새 알람은 fn_ingest_alarm의 뒷부분(등급별 알림·OP-30 정지 초안·반복 알람)을 부른다
번호는 시뮬레이터 번호 그대로다 (9월 번호 다음부터 — 생성기 manifest id_after_past). 그래서 시연 서버 [처음으로]는
DB도 시연 기준점(9월 끝, fn_demo_reset)으로 되돌린 뒤 다시 보낸다 (POST /api/ingest/reset). 되돌릴 때 기준점의 시각·마지막 번호가
시뮬레이터 시작점과 같은지 확인한다(check_baseline). 켜는 곳: MOM_SIM_SYNC=true(공용 DB 포함 — "DB 1개 = 공장 1개") 또는 시연 모드.
표·칸 이름은 SQL 글자에 들어가므로 아래 TABLES와 DB 카탈로그에 있는 것만 쓴다.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from ..errors import invalid_state, validation

if TYPE_CHECKING:
    from ..db import Db

# 넣는 순서 (외래 키 부모 먼저 — 대부분의 외래 키는 바로 확인한다)
TABLES = ["production_order", "production_lot", "inspection_plan", "alarm_event", "pm_record", "equipment_state_log",
          "operation_report", "tool_change", "tool_usage", "bottleneck_log", "wip_log", "lot_hold", "cmm_import",
          "inspection_result", "defect_record", "inventory_txn", "sensor_sample"]
APPEND_ONLY = {"inventory_txn"}                              # 고치기·지우기 금지 표 (trg_append_only)
LIVE = {"wip_log", "inspection_result", "bottleneck_log"}    # 새 줄에 실시간 알림 트리거를 돌림
DELETABLE = {"sensor_sample"}                                # 1분 값이 5초 값으로 바뀌면 옛 줄을 지움 (알람 앞뒤 30분)

_meta: dict[str, Any] | None = None


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def meta(db: Db) -> dict[str, Any]:
    """표마다 칸(생성 칼럼 뺌)·NOT NULL 기본값·기본 키·일련번호 칼럼 (한 번 읽어 둔다)"""
    global _meta
    if _meta is None:
        cols: dict[str, dict[str, str | None]] = {t: {} for t in TABLES}
        for r in db.all("ingest.sync_columns", tables=TABLES):
            if not r["generated"]:
                cols[r["table_name"]][r["column_name"]] = r["not_null_default"]
        pk: dict[str, list[str]] = {t: [] for t in TABLES}
        for r in db.all("ingest.sync_pkeys", tables=TABLES):
            pk[r["table_name"]].append(r["column_name"])
        ident = {r["table_name"]: r["column_name"] for r in db.all("ingest.sync_identity", tables=TABLES)}
        auto_wo = bool(db.scalar("ingest.sync_has_function", fn="fn_auto_work_order_draft"))
        _meta = {"cols": cols, "pk": pk, "ident": ident, "auto_wo": auto_wo}
    return _meta


def check_baseline(db: Db, start_at, id_after: dict[str, int]) -> None:
    """방금 되돌린 DB(= 시연 기준점)가 시뮬레이터 시작점과 같은지. 다르면 INVALID_STATE(BASELINE_MISMATCH) — 부른 쪽 트랜잭션이 취소된다.
    시각: 되돌리면 DB 시계가 기준점 시각에 멈춘다(fn_demo_reset) → app_now() = start_at 이어야 한다.
    번호: 표마다 max(번호) = 시뮬레이터가 이어 붙일 앞 번호여야 한다 (아니면 시뮬레이터 줄이 DB 줄을 덮어씀).
    10/1 뒤 기록을 DB에 채우거나 실제 시간으로 바꿀 때 기준점과 시뮬레이터 시작점을 함께 옮기라는 안전장치 (2026-10-23)"""
    m = meta(db)
    diff: dict[str, Any] = {}
    if start_at is not None:
        now = db.scalar("common.now")
        if now != start_at:
            diff["start_at"] = {"db": str(now), "sim": str(start_at)}
    for t, n in sorted(id_after.items()):
        c = m["ident"].get(t)
        if t not in TABLES or not c:
            raise validation(f"번호를 비교할 수 없는 표: {t}", table=t)
        got = db.conn.execute(text(f"SELECT coalesce(max({_q(c)}), 0) FROM {_q(t)}")).scalar()
        if int(got) != int(n):
            diff[t] = {"db": int(got), "sim": int(n)}
    if diff:
        raise invalid_state("DB 시연 기준점이 시뮬레이터 시작점과 다름 — 되돌리지 않음 (기준점을 다시 찍거나 생성기 시작점을 맞춘다)",
                            reason="BASELINE_MISMATCH", diff=diff)


def apply(db: Db, tables: dict[str, dict]) -> dict[str, Any]:
    """tables[표] = {"columns": [...], "upsert": [[칸 값…]], "delete": [[기본 키 값…]]}. 칸 값은 CSV 글자 (빈칸·None = NULL).
    반환: 표마다 넣거나 고친 줄·지운 줄 수, 새 알람 번호"""
    m = meta(db)
    unknown = sorted(set(tables) - set(TABLES))
    if unknown:
        raise validation(f"맞출 수 없는 표: {unknown}", tables=unknown)
    db.exec("ingest.sync_loading", value="on")
    out: dict[str, Any] = {"tables": {}, "new_alarms": []}
    for t in TABLES:
        if t not in tables:
            continue
        body = tables[t]
        columns = list(body.get("columns") or [])
        bad = [c for c in columns if c not in m["cols"][t]]
        if bad or not columns:
            raise validation(f"{t}: DB에 없는 칸 {bad}" if bad else f"{t}: 칸 이름이 없음", table=t, columns=bad)
        pk = m["pk"][t]
        res = {"written": 0, "deleted": 0}
        dels = body.get("delete") or []
        if dels:
            if t not in DELETABLE:
                raise validation(f"{t}: 지울 수 없는 표", table=t)
            keys = [dict(zip(pk, k)) for k in dels]
            cond = " AND ".join(f"x.{_q(c)} = k.{_q(c)}" for c in pk)
            res["deleted"] = db.conn.execute(text(
                f"DELETE FROM {_q(t)} x USING jsonb_populate_recordset(NULL::{_q(t)}, CAST(:rows AS jsonb)) k WHERE {cond}"),
                {"rows": json.dumps(keys, ensure_ascii=False)}).rowcount
        rows = body.get("upsert") or []
        if rows:
            res.update(_upsert(db, t, columns, rows, m))
            if t == "alarm_event":
                out["new_alarms"] = res.pop("new_ids")
            else:
                res.pop("new_ids", None)
        out["tables"][t] = res
    # 일련번호를 넣은 데이터의 최대값 다음으로 (플랫폼이 새로 만드는 줄이 시뮬레이터 번호와 겹치지 않게)
    for t in tables:
        c = m["ident"].get(t)
        if c:
            db.conn.execute(text(f"SELECT setval(pg_get_serial_sequence(:t, :c), "
                                 f"coalesce((SELECT max({_q(c)}) FROM {_q(t)}), 0) + 1, false)"), {"t": t, "c": c})
    db.one("ingest.sync_after")
    # 새 알람의 뒷일은 실제 알람 받기와 같게 (알림 켬)
    db.exec("ingest.sync_loading", value="off")
    for aid in sorted(out["new_alarms"]):
        db.all("ingest.sync_alarm_notify", alarm_event_id=aid)
        if m["auto_wo"]:
            db.all("ingest.sync_alarm_auto_wo", alarm_event_id=aid)
        db.all("ingest.sync_alarm_repeat", alarm_event_id=aid)
    return out


def _upsert(db: Db, t: str, columns: list[str], rows: list[list], m: dict) -> dict[str, Any]:
    pk = m["pk"][t]
    dflt = m["cols"][t]
    recs = [{c: (None if v in (None, "") else v) for c, v in zip(columns, r)} for r in rows]
    if len(recs) != len(rows) or any(len(r) != len(columns) for r in rows):
        raise validation(f"{t}: 칸 수가 맞지 않는 줄", table=t)
    vals = [f"coalesce(x.{_q(c)}, {dflt[c]})" if dflt.get(c) else f"x.{_q(c)}" for c in columns]
    sql = (f"INSERT INTO {_q(t)} ({', '.join(_q(c) for c in columns)}) "
           f"SELECT {', '.join(vals)} FROM jsonb_populate_recordset(NULL::{_q(t)}, CAST(:rows AS jsonb)) "
           f"WITH ORDINALITY AS x ORDER BY x.ordinality ")
    setc = [c for c in columns if c not in pk]
    if t in APPEND_ONLY or not setc:
        sql += f"ON CONFLICT ({', '.join(_q(c) for c in pk)}) DO NOTHING "
    else:
        # 칸이 같으면 고치지 않는다 — 확정 문서 잠금(trg_doc_lock)은 생성 칼럼 때문에 같은 값 UPDATE도 "바뀜"으로 본다
        sql += (f"ON CONFLICT ({', '.join(_q(c) for c in pk)}) DO UPDATE SET "
                + ", ".join(f"{_q(c)} = EXCLUDED.{_q(c)}" for c in setc)
                + f" WHERE ({', '.join(f'{_q(t)}.{_q(c)}' for c in setc)}) IS DISTINCT FROM "
                  f"({', '.join(f'EXCLUDED.{_q(c)}' for c in setc)}) ")
    # 새로 들어간 번호는 알람만 (뒷일을 부르려고). 파티션 표(sensor_sample)는 xmax를 못 읽는다
    if t == "alarm_event":
        sql += f"RETURNING {_q(pk[0])} AS k, (xmax = 0) AS inserted"
    if t in LIVE:
        db.exec("ingest.sync_loading", value="off")
    try:
        res = db.conn.execute(text(sql), {"rows": json.dumps(recs, ensure_ascii=False)})
        got = res.mappings().all() if t == "alarm_event" else None
        n = res.rowcount if got is None else len(got)
    finally:
        if t in LIVE:
            db.exec("ingest.sync_loading", value="on")
    ins = [g["k"] for g in got if g["inserted"]] if got is not None else []
    return {"written": n, "new_ids": ins}
