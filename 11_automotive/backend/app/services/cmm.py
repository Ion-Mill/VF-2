"""OP-50 측정 결과 파일 받기 (DOC-06 Rev.2 §3.6, R-78·R-80).

흐름: 파일 내용 → app/domain/cmm_csv.parse →
  · 양식이 깨짐(CmmFormatError) → fn_record_cmm_failure (상태 FAILED, 종류 FORMAT) → 파일은 "오류" 칸
  · 읽힘 → fn_import_cmm: 지시와 맞는지·빠진 항목은 DB가 판단 (SUCCESS / NEEDS_CHECK)
같은 파일 이름이 이미 있으면(재측정 등) 이름 뒤에 #2, #3… 을 붙여 따로 남긴다 (file_name UNIQUE).
  → 결과 파일 이름 규칙 [제안]: cmm_csv.SUGGESTED_NAME (측정 끝 시각을 붙여 겹치지 않게)
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import get_settings
from ..domain.cmm_csv import CmmFormatError, parse

if TYPE_CHECKING:
    from ..db import Db

log = logging.getLogger("mom.cmm")
SAFE_NAME = re.compile(r"[^0-9A-Za-z가-힣._#-]")


def unique_name(db: Db, file_name: str) -> str:
    n = int(db.scalar("quality.import_exists", file_name=file_name) or 0)
    return file_name if n == 0 else f"{file_name}#{n + 1}"


def save_upload(raw: bytes, file_name: str) -> str:
    """API로 올린 원본도 지우지 않고 남긴다 (R-80). 반환: 보관 위치 (original_file_ref)"""
    safe = SAFE_NAME.sub("_", Path(file_name).name)[:150] or "upload.csv"
    stamp = dt.datetime.now().strftime("%Y%m%d%H%M%S%f")
    try:
        folder = Path(get_settings().cmm_processed_dir) / "uploads"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{stamp}_{safe}"
        path.write_bytes(raw)
        return path.as_posix()          # 보관 위치는 "/"로 (cmm_watcher와 같게, 2026-10-20)
    except OSError:
        log.warning("업로드 원본을 저장하지 못함: %s", file_name, exc_info=True)
        return f"upload-not-saved:{safe}"


def record_failure(db: Db, file_name: str, file_ref: str | None, e: CmmFormatError) -> dict:
    file_ref = file_ref or f"api:{file_name}"
    name = unique_name(db, file_name)
    cid = db.scalar("quality.import_failure", file_name=name, file_ref=file_ref, error_kind=e.error_kind,
                    error_text=e.text, header={k: str(v) for k, v in e.header.items()})
    return db.one("quality.import_get", cmm_import_id=cid) or {"cmm_import_id": cid, "file_name": name}


def import_text(db: Db, file_name: str, text: str, file_ref: str | None = None) -> dict:
    """반환: {cmm_import_id, file_name, status, error_kind, error_text, result_count, ...}"""
    file_ref = file_ref or f"api:{file_name}"
    try:
        header, rows = parse(text)
    except CmmFormatError as e:
        return record_failure(db, file_name, file_ref, e)
    name = unique_name(db, file_name)
    cid = db.scalar("quality.import_cmm", file_name=name, file_ref=file_ref, header=header, rows=rows)
    return db.one("quality.import_get", cmm_import_id=cid) or {"cmm_import_id": cid, "file_name": name}


def decode(raw: bytes) -> str:
    """측정기 PC가 UTF-8(BOM 포함) 또는 CP949로 쓸 수 있다 [확인 필요: 실제 측정기 소프트웨어]."""
    for enc in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise CmmFormatError("글자 인코딩을 읽을 수 없음 (UTF-8·CP949 아님)")
