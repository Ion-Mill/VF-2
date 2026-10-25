"""공구 수명 원문 줄이 사용률이라고 밝히고 남은 비율을 붙이는지 (2026-10-25).

AWS 서버 시험에서 "VF2-02 공구 수명 얼마나 남았어?"에 원문 "공구 수명: … T03 보링바 인서트 60.3% (241/400.0)"를 받은 외부 LLM이
"60.3%가 남았어요"라고 쓰고, 가장 적게 남은 공구를 거꾸로(T02, 실제로는 95% 남음) 짚었다. 숫자는 백엔드 값 그대로 둔다.
가짜 백엔드(conftest 기본): VF2-01 T05 엔드밀 12mm 사용률 92.0 · 남은 8.0 (460/500), T01 사용률 20.0 · 남은 80.0.
"""
from backend.services.answer import ops_answer


def _texts(eq=None):
    p = {"intents": ["tool_life"], "equipment": [eq] if eq else [], "start": None, "end": None, "shift": None,
         "alarms": [], "raw": "공구 수명", "lot": None, "order": None}
    texts, data, _ = ops_answer("SUP", p)
    return " ".join(texts), data


def test_line_says_usage_and_remaining():
    text, data = _texts("VF2-01")
    assert data and data[0]["tool"] == "공구 수명 조회"
    assert "T05 엔드밀 12mm 사용률 92.0%·남은 8% (460/500.0)" in text
    assert "엔드밀 12mm 92.0% (" not in text          # 옛 모양 — 남은 수명으로 읽혔다


def test_numbers_unchanged_from_backend():
    _, data = _texts("VF2-01")
    t05 = next(r for r in data[0]["rows"] if r["tool_no"] == "T05")
    assert (t05["usage_pct"], float(t05["remaining_pct"])) == (92.0, 8.0)


def test_no_equipment_lists_only_90_or_more():
    text, _ = _texts()
    assert text.startswith("공구 수명: ") and "사용률 92.0%·남은 8%" in text
    assert "T01" not in text                            # 사용률 20%는 설비를 정하지 않으면 싣지 않는다 (90% 이상만)
