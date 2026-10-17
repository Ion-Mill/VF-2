import pytest

# [11_automotive 이식 2026-10-16] 조회 도구는 이제 기존 백엔드의 /api/assistant/tools를 부른다. answer()를 직접 부르는 옛 시험에도
# "누구를 대신해 묻는지"와 백엔드가 필요하므로 기본으로 가짜 백엔드(tests/fake_backend.py)를 끼운다. 자기 백엔드를 직접 준비하는 새 시험은
# `pytestmark = pytest.mark.own_backend`로 이 기본을 끈다.
_ALL_TOOLS = ["equipment_status", "alarms", "kpi", "production", "lot", "work_orders", "work_records", "pm_due", "tool_life", "inventory",
              "reliability", "stop_reasons", "sensor_trend", "equipment_spec"]


def pytest_configure(config):
    config.addinivalue_line("markers", "own_backend: 이 시험은 가짜 백엔드·호출 사용자를 직접 준비한다 (기본 가짜 백엔드를 끈다)")


def pytest_collection_modifyitems(config, items):
    """이 저장소에서 통과하지 못하는 옛 시험 76개는 까닭과 함께 xfail(strict)로 표시한다 — legacy_expected_failures.py 참고."""
    from backend.tests.legacy_expected_failures import BY_ID, REASONS
    for item in items:
        key = item.nodeid.split("backend/tests/", 1)[-1]
        cat = BY_ID.get(key)
        if cat:
            item.add_marker(pytest.mark.xfail(reason=f"[{cat}] {REASONS[cat]}", strict=True))


@pytest.fixture(autouse=True)
def _default_backend(request, monkeypatch):
    if request.node.get_closest_marker("own_backend"):
        yield
        return
    from backend.repositories import backend_tools as BT
    from backend.tests.fake_backend import FakeBackend
    FakeBackend().install(monkeypatch)
    with BT.acting_as("U07", _ALL_TOOLS):
        yield


@pytest.fixture(autouse=True)
def _llm_off(monkeypatch, tmp_path):
    """시험은 실제 LLM·임베딩 서버를 부르지 않는다. 서버가 필요한 계약 시험은 따로 켠다 (test_llm_contract.py)."""
    monkeypatch.setenv("LLM_ENABLED", "0")
    monkeypatch.setenv("LLM_JOBS", "write")
    monkeypatch.setenv("RETRIEVAL", "bm25")
    # 앞단 개선 스위치도 모두 기본값으로 고정한다 (.env 값이 시험을 바꾸지 않게, 2026-10-10)
    monkeypatch.setenv("NUM_MATCH", "token")
    monkeypatch.setenv("PARSE_V2", "0")
    monkeypatch.setenv("ROUTE_POLICY", "rescue")
    monkeypatch.setenv("DOC_GATE", "lexical")
    monkeypatch.setenv("PARSE_V3", "0")
    monkeypatch.setenv("SPLIT_Q", "0")
    # 3차 스위치 (2026-10-10, 봉인 시험 E3)
    monkeypatch.setenv("PARSE_V4", "0")
    monkeypatch.setenv("CAND_ORDER", "rank")
    monkeypatch.setenv("LLM_CACHE_PROMPT", "1")
    # 4차 스위치 (2026-10-11, 봉인 시험 E4)
    monkeypatch.setenv("PARSE_V5", "0")
    # 5차 스위치 (2026-10-11, 봉인 시험 E5)
    monkeypatch.setenv("PARSE_V6", "0")
    # 6차 스위치 (2026-10-12, 봉인 시험 E6): 규칙 보강 6차, 이어 묻기
    monkeypatch.setenv("PARSE_V7", "0")
    monkeypatch.setenv("FOLLOWUP", "0")
    # 7차 스위치 (2026-10-12, 봉인 시험 E7): 안전·결함 고침·정직한 표시, 이어 묻기가 실제로 일하게
    monkeypatch.setenv("PARSE_V8", "0")
    monkeypatch.setenv("FOLLOWUP_V2", "0")
    # 8차 스위치 (2026-10-12, 봉인 시험 E8): 규칙 보강 8차, 흐름 바꾸기, 줄 목록 칸 2판
    monkeypatch.setenv("PARSE_V9", "0")
    monkeypatch.setenv("FLOW_V9", "0")
    monkeypatch.setenv("BLOCKS_V2", "0")
    # 9차 스위치 (2026-10-13, 봉인 시험 E9): 띄어쓰기, 섞인 알람 질문·알람 짧게, 줄 목록 칸 3판
    monkeypatch.setenv("PARSE_V10", "0")
    monkeypatch.setenv("FLOW_V10", "0")
    monkeypatch.setenv("BLOCKS_V3", "0")
    monkeypatch.setenv("DOC_WRITE", "0")   # 10차 (2026-10-13)
    monkeypatch.setenv("PARSE_V11", "0")   # 10차 보강 (2026-10-14)
    monkeypatch.setenv("LEAD_V12", "0")    # 10차 보강 앞머리 검사 (2026-10-14)
    monkeypatch.setenv("TERM_V13", "0")    # 10차 보강 쓰지 않는 말·용어집 줄만 (2026-10-14)
    for _k in ("SAFE_WRITE_CARD", "SAFE_WRITE_DOC", "SAFE_WRITE_PROC", "SAFE_WRITE_WORDS"):
        monkeypatch.setenv(_k, "0")        # 안전 영역 새로쓰기 (2026-10-14, 단계적 — 모두 꺼진 채 시작)
    # 비교 실험 (2026-10-14): 시험은 늘 local. 외부 잠금·열쇠·기록 경로도 비운다(밖 환경에서 새어 들어오지 않게)
    monkeypatch.setenv("LLM_PROVIDER", "local")
    monkeypatch.setenv("MOM_CLAUDE_VIA", "cli")
    monkeypatch.setenv("EXTERNAL_LLM_APP", "0")     # 앱 외부 LLM 스위치 (2026-10-15): 시험 기본은 꺼짐 — 켜는 시험은 안에서 명시
    monkeypatch.setenv("EXTERNAL_PROC_LIMIT", "8")
    monkeypatch.setenv("THINK_APP", "0")            # Qwen 깊게 생각 버튼 (2026-10-15): 시험 기본은 꺼짐 — 켜는 시험은 안에서 명시
    monkeypatch.setenv("TABLE_FILL_V18", "0")       # 번호 붙은 절차 표 채우기 (2026-10-15): 시험 기본은 꺼짐 — 켜는 시험은 안에서 명시
    monkeypatch.setenv("STEP_LOG", "0")             # 단계별 로그 (2026-10-15): 시험 기본은 꺼짐 — 켜는 시험은 안에서 명시
    monkeypatch.setenv("STEP_LOG_DIR", str(tmp_path / "steplog"))   # 시험이 켜더라도 실제 로그 폴더(C:\llm\logs)에는 쓰지 않는다 — 시험마다 따로 만든 임시 폴더
    monkeypatch.setenv("WRITE_SHOTS", "0")    # 지시문 후보 (2026-10-14)
    monkeypatch.setenv("WRITE_TITLES", "0")
    monkeypatch.setenv("WRITE_RULES_V17", "0")   # 새 글 규칙 정밀도 (2026-10-14)
    monkeypatch.setenv("ANSWER_GATE_V17", "0")   # 답 문지기: 문서 길 부품번호·기본값 + 낱말 겹침 문턱 0.1 (2026-10-14)
    monkeypatch.setenv("OBLIGE_CHECK", "1")      # "해야 할 일 꼴" 검사 끄기 실험 (2026-10-15): 시험 기본은 켜짐(지금 동작) — 끄는 시험은 안에서 명시
    monkeypatch.setenv("PURE_EXTERNAL", "0")     # 순수 외부 LLM 연결 (2026-10-15): 시험 기본은 꺼짐(지금 동작) — 켜는 시험은 안에서 명시
    monkeypatch.setenv("PURE_KEEP_SIGNALS", "0")
    monkeypatch.setenv("PURE_TOPK", "8")
    monkeypatch.setenv("PURE_STYLE", "0")        # 순수 길 말투 바꾸기 (2026-10-15): 시험 기본은 꺼짐(지금 말투) — 켜는 시험은 안에서 명시
    monkeypatch.setenv("PURE_LAYOUT", "0")       # 순수 길 묶음 목록 형식 (2026-10-16): 시험 기본은 꺼짐(PURE_STYLE=1의 지금 형식) — 켜는 시험은 안에서 명시
    monkeypatch.setenv("PURE_EXPAND", "0")       # 순수 길 아래 절 확장 (2026-10-18): 시험 기본은 꺼짐 — 개발 PC의 .env가 다른 시험을 바꾸지 않게
    monkeypatch.setenv("PURE_SAFETY", "0")       # 순수 길 안전 질문 안전망 (2026-10-18): 시험 기본은 꺼짐 — 개발 PC의 .env가 다른 시험을 바꾸지 않게
    monkeypatch.setenv("PURE_PERIOD", "0")       # 순수 길 기간 낱말 보장 (2026-10-18): 시험 기본은 꺼짐 — 개발 PC의 .env가 다른 시험을 바꾸지 않게
    monkeypatch.setenv("PURE_RULE", "0")         # 순수 길 규칙 질문 라우팅 (2026-10-18): 시험 기본은 꺼짐 — 개발 PC의 .env가 다른 시험을 바꾸지 않게
    for _k in ("MOM_EXTERNAL_LLM_OK", "ANTHROPIC_API_KEY", "MOM_USAGE_LEDGER"):
        monkeypatch.delenv(_k, raising=False)
