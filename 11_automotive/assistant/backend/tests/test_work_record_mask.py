"""작업기록 글의 제조사 매뉴얼 번호 떼기 (2026-10-21 시연 "992 지난 조치") 최소 시험 — 진짜 Claude·네트워크·DB를 부르지 않는다.

문제: 작업기록 조치 글에 "체크리스트(ID0003)"가 있어 "992 지난 조치" 답 전체가 "원문 출처 표기가 섞여 내보내지 않았습니다"로 막혔다.
지키는 것: 조회 결과를 만들 때 그 번호만 떼고(문장은 이어짐), 번호가 없는 글은 그대로이며, 답은 막히지 않는다.
"""
from types import SimpleNamespace

import pytest

from backend.rag.sanitize import FORBIDDEN
from backend.tools import query_tools as T


@pytest.mark.parametrize("src,want", [
    ("앰프 점검 보고서 체크리스트(ID0003)를 쓴다.", "앰프 점검 보고서 체크리스트를 쓴다."),
    ("체크리스트 (ID0003) 확인", "체크리스트 확인"),
    ("ID0003 참고해 교체", "참고해 교체"),
    ("케이블이 있음, 서비스 알림 SA0018) 확인", "케이블이 있음) 확인"),
    ("교체 전 체크리스트: 앰프 ID0003, 서보 모터 ID0009. 조치", "교체 전 체크리스트: 앰프, 서보 모터. 조치"),
    ("막힘 제거 / 공구 교체·이송 낮춤", "막힘 제거 / 공구 교체·이송 낮춤"),
    ("", ""),
])
def test_manual_ids_are_removed_and_plain_text_is_unchanged(src, want):
    assert T.mask_manual_ids(src) == want
    assert not FORBIDDEN.search(T.mask_manual_ids(src))


def test_work_records_rows_carry_no_manual_id(monkeypatch):
    row = {"record_no": "MR-0903", "record_type": "REPAIR", "equipment_id": "VF2-01", "alarm_code": "992", "confirmed_at": "2026-09-14T10:00:00",
           "repair_min": 172, "cause": "축의 기계적 막힘", "action": "앰프 교체는 체크리스트(ID0003)를 쓴다."}
    monkeypatch.setattr(T, "_call", lambda name, args: SimpleNamespace(rows=[row], now="2026-10-01T08:00:00+09:00"))
    out = T.work_records("MNT", "VF2-01", "992")
    assert out["rows"][0]["action"] == "앰프 교체는 체크리스트를 쓴다." and out["rows"][0]["cause"] == "축의 기계적 막힘"
