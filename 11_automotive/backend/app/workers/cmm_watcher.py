"""CMM 결과 파일 감시 (DOC-06 Rev.2 §3.6, R-80). 측정기 PC가 공유 폴더(inbox)에 CSV를 떨군다.

  · 다 써졌는지: 두 번 연속 같은 크기·수정 시각이면 처리 (쓰는 중인 파일을 읽지 않게)
  · 양식이 깨짐·DB가 거절(없는 로트·측정자 모름) → "오류" 칸(error), 기록됨(지시와 다름·빠짐 = 확인 필요 포함) → "처리됨" 칸(processed).
    원본은 지우지 않는다
  · 옮길 곳에 같은 이름이 있으면 이름 뒤에 _2, _3…
파일 1개 = 트랜잭션 1개. DB가 예상 밖 오류를 내면 파일은 error 칸 + 옆에 .error.txt (DB 기록 없음, 로그 남김).
감시는 서버 한 곳에서만 돌린다 (MOM_RUN_WORKERS=true 인 인스턴스 1개). 다른 곳이 먼저 옮긴 파일은 건너뛴다.
"""
from __future__ import annotations

import asyncio
import logging
import traceback
from pathlib import Path
from typing import Any, Callable

from ..config import get_settings
from ..domain.cmm_csv import CmmFormatError, parse
from ..services import cmm

RunTx = Callable[[Callable[[Any], dict]], dict]   # 트랜잭션 하나 안에서 fn(db)를 돌려 결과를 돌려줌

log = logging.getLogger("mom.cmm_watcher")


def free_path(folder: Path, name: str) -> Path:
    target = folder / name
    n = 2
    while target.exists():
        target = folder / f"{Path(name).stem}_{n}{Path(name).suffix}"
        n += 1
    return target


def classify(raw: bytes) -> tuple[str | None, CmmFormatError | None]:
    """파이썬에서 먼저 읽어 본다 → (글, 양식 오류). 옮길 칸을 DB 기록 전에 정하려고."""
    try:
        text = cmm.decode(raw)
        parse(text)
        return text, None
    except CmmFormatError as e:
        return None, e


def run_in_db(fn: Callable[[Any], dict]) -> dict:
    from ..db import Db, engine          # 시험에서는 run_tx를 바꿔 끼운다
    with engine().begin() as conn:
        return fn(Db(conn))


def process_file(path: Path, processed_dir: Path, error_dir: Path, run_tx: RunTx = run_in_db) -> dict:
    raw = path.read_bytes()
    text, err = classify(raw)
    dest = free_path(error_dir if err else processed_dir, path.name)
    # 보관 위치는 "/"로 적는다 (Windows도 읽음 — 운영체제마다 다르게 저장되지 않게, 2026-10-20)
    try:
        result = run_tx(lambda db: cmm.record_failure(db, path.name, dest.as_posix(), err) if err
                        else cmm.import_text(db, path.name, text or "", dest.as_posix()))
    except Exception:
        dest = free_path(error_dir, path.name)
        path.replace(dest)
        dest.with_suffix(dest.suffix + ".error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        log.exception("CMM 파일 기록 실패 → %s", dest)
        return {"file_name": path.name, "status": "DB_ERROR", "moved_to": dest.as_posix()}
    if result.get("status") == "FAILED" and dest.parent != error_dir:
        # 양식은 맞지만 DB가 기록을 거절한 경우(없는 로트·측정자 모름) → 오류 칸으로, 보관 위치도 고친다
        dest = free_path(error_dir, path.name)
        run_tx(lambda db: {"n": db.exec("quality.import_set_ref", cmm_import_id=result["cmm_import_id"], file_ref=dest.as_posix())})
    path.replace(dest)
    log.info("CMM 파일 %s → %s (%s)", path.name, dest.parent.name, result.get("status"))
    return {**result, "moved_to": dest.as_posix()}


def scan_once(inbox: Path, processed_dir: Path, error_dir: Path, seen: dict[str, tuple[int, float]],
              run_tx: RunTx = run_in_db) -> list[dict]:
    out = []
    for d in (processed_dir, error_dir):
        d.mkdir(parents=True, exist_ok=True)
    for path in sorted(p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() == ".csv"):
        st = path.stat()
        sig = (st.st_size, st.st_mtime)
        if seen.get(path.name) != sig:
            seen[path.name] = sig          # 다음 번에도 같으면 처리
            continue
        seen.pop(path.name, None)
        try:
            out.append(process_file(path, processed_dir, error_dir, run_tx))
        except FileNotFoundError:
            continue
    for gone in set(seen) - {p.name for p in inbox.iterdir()}:
        seen.pop(gone, None)
    return out


async def run_forever() -> None:
    s = get_settings()
    inbox, processed, error = Path(s.cmm_inbox_dir), Path(s.cmm_processed_dir), Path(s.cmm_error_dir)
    seen: dict[str, tuple[int, float]] = {}
    log.info("CMM 감시 시작: %s (%.1f초마다)", inbox, s.cmm_poll_seconds)
    while True:
        try:
            if inbox.is_dir():
                await asyncio.to_thread(scan_once, inbox, processed, error, seen)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("CMM 감시 오류")
        await asyncio.sleep(s.cmm_poll_seconds)
