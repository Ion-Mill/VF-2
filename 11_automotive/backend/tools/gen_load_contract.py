"""생성기 CSV ↔ DB 칼럼 대조 표 만들기 → docs/04_데이터적재_약속.md 3장.

쓰는 법: python tools/gen_load_contract.py --psql "psql -d mom" [--gen <생성기 폴더>] > /tmp/contract.md
tools/load_generated.py 와 같은 규칙 (논리 ERD 11.1): 머리 줄은 이름으로 맞춘다 (생성기는 ERD 5장 속성 순서).
  · DB가 채우는 칼럼 = 테이블에 있지만 CSV에 없는 칼럼 (생성 칼럼·기본값·물리 추가, DERIVED 계산)
  · 넣지 않는 칼럼 = CSV에 있지만 DB가 계산으로 보이는 칼럼 (IGNORE — 넣은 뒤 같은지 확인)
--gen 이 없으면 DB 칼럼만 보인다.
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from load_generated import COLS_SQL, DERIVED, EXCLUDE_ALWAYS, FK_SQL, IGNORE, load_order, psql_rows  # noqa: E402

# 생성기가 넣지 않는 표: 시드(apply.sh)가 넣음 / 운영 중에만 생김 / 보관 작업이 만듦
NOT_FROM_GENERATOR = {
    "role_permission": "시드", "code_label": "시드",
    "dataset_info": "시드 (적재 도구가 manifest로 갱신)", "sim_clock": "시드", "doc_number_seq": "적재 도구가 맞춤",
    "access_log": "운영 중에만", "qr_scan": "운영 중에만 (QR 찍은 기록)", "chat_log": "운영 중에만 (시연 시작 때 0행)",
    "cmm_instruction": "운영 중에만 (측정 지시)", "sensor_hourly": "보관 작업", "wip_hourly": "보관 작업",
    "alarm_related_item": "적재 도구가 fn_seed_alarm_related_items로 채움 (사내 문서 근거)",
    "doc_chunk": "tools/load_docs.py 가 가상사내문서에서 만듦",
}


def gen_headers(gen):
    out = {}
    if not gen:
        return out
    for sub in ("masters", "out"):
        folder = os.path.join(gen, sub)
        if not os.path.isdir(folder):
            continue
        rows = {}
        mp = os.path.join(folder, "manifest.json")
        if os.path.exists(mp):
            rows = json.load(open(mp, encoding="utf-8")).get("rows") or {}
        for name in sorted(os.listdir(folder)):
            if name.endswith(".csv"):
                t = name[:-4]
                with open(os.path.join(folder, name), encoding="utf-8-sig", newline="") as fh:
                    hdr = next(csv.reader(fh))
                    n = rows.get(t)
                    if n is None:
                        n = sum(1 for _ in csv.reader(fh))
                out[t] = (sub, hdr, n)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psql", default="psql -d mom")
    ap.add_argument("--gen", help="생성기 폴더 (masters/·out/)")
    a = ap.parse_args()
    cols = {}
    for row in psql_rows(a.psql, COLS_SQL):
        table, col, gen = row[0], row[1], row[2]
        if table.startswith("sensor_sample_"):
            continue
        cols.setdefault(table, []).append((col, gen == "t" or (table, col) in EXCLUDE_ALWAYS))
    heads = gen_headers(a.gen)
    tables = [t for t in cols if t not in NOT_FROM_GENERATOR]
    order = load_order(tables, psql_rows(a.psql, FK_SQL))
    print(f"<!-- tools/gen_load_contract.py 가 실제 DB{'와 생성기 CSV' if heads else ''}에서 만든 표: 테이블 {len(order)}개 (넣는 순서) -->\n")
    print("| # | 파일 (= 테이블) | 어디 | 행 (9월) | CSV 칼럼 | DB가 채우는 칼럼 | 넣지 않는 칼럼 (계산 확인) |")
    print("|---|---|---|---|---|---|---|")
    for i, t in enumerate(order, 1):
        db_cols = [c for c, _g in cols[t]]
        if t in heads:
            sub, hdr, n = heads[t]
            filled = [c for c in db_cols if c not in hdr]
            ignored = [h for h in hdr if (t, h) in IGNORE]
            extra = [h for h in hdr if h not in db_cols and (t, h) not in IGNORE]
            col_txt = f"`{','.join(hdr)}`" + (f" **DB에 없음: {extra}**" if extra else "")
            filled_txt = ", ".join(f"{c}{' (계산)' if c in DERIVED.get(t, {}) else ''}" for c in filled) or "—"
            print(f"| {i} | `{t}.csv` | {sub} | {n:,} | {col_txt} | {filled_txt} | {', '.join(ignored) or '—'} |")
        else:
            gen_only = [c for c, g in cols[t] if g]
            print(f"| {i} | `{t}.csv` | {'(생성기 없음)' if heads else '—'} | — | "
                  f"`{','.join(c for c, g in cols[t] if not g)}` | {', '.join(gen_only) or '—'} | — |")
    print("\n생성기가 넣지 않는 표: " + ", ".join(f"`{t}` ({w})" for t, w in NOT_FROM_GENERATOR.items()))


if __name__ == "__main__":
    main()
