import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from backend.llm import external as EXT   # 요청 단위 공급자 선택(2026-10-15). backend의 다른 모듈을 import하지 않아 순환이 없다
from backend.llm import think as THINK    # Qwen "깊게 생각" 버튼의 요청 단위 상태(2026-10-15). 같은 방식

ROOT = Path(__file__).resolve().parent.parent   # 11_automotive/assistant — .env를 읽는 곳
# [11_automotive 이식 2026-10-16] 원본은 ROOT/simulator·참고문서/…를 읽었다. 이 폴더에서는 한 칸 위(11_automotive)의 생성기·가상사내문서를 본다
PROJECT_ROOT = ROOT.parent
SIM_OUT = PROJECT_ROOT / "생성기" / "out"
SIM_MASTERS = PROJECT_ROOT / "생성기" / "masters"
DOCS_DIR = PROJECT_ROOT / "가상사내문서"
EXPECTED_DOC_FILES = 8  # 용어집 + DOC-01~07 (ai-operations-assistant 규칙 3.1)
REFERENCE_AT = "2026-10-01T08:00:00+09:00"  # 시연 기준 시각 (가상 데이터 마지막 날 다음 교대 시작)
DATA_LABEL = "가상 운영 데이터"
SIM_CONFIG = PROJECT_ROOT / "생성기" / "config.json"   # [11_automotive 이식 2026-10-16]


def targets() -> dict[str, int]:
    """교대 목표·하루 목표 [가상] (simulator/config.json "targets", 가상데이터설계서 5.3·ERD shift.target_qty·daily_target_qty).
    브리핑의 총 목표 = 교대 목표 + 이월 (FR-PRD-01-15, 2026-10-11 P3)."""
    import json
    t = json.loads(SIM_CONFIG.read_text(encoding="utf-8"))["targets"]
    return {"shift": int(t["shift"]), "day": int(t["day"])}

# ---------------------------------------------------------------- 로컬 LLM·검색 설정 (2026-10-08)
# 모델 = Qwen3.5-9B (2026-10-08 사용자 결정), 실행 도구 = llama.cpp llama-server, 임베딩 = bge-m3 (4단계에서 KURE-v1과 비교).
# 값은 환경 변수 → 프로젝트 루트 .env 순으로 읽는다. 요청 때마다 읽으므로 시험·평가가 바꿀 수 있다.
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def _float(v: str, default: float) -> float:
    try:
        return float(v)
    except ValueError:
        return default


def _int_clamped(v: str, default: int, lo: int, hi: int) -> int:
    """정수로 읽고 lo~hi로 제한한다. 정수가 아니면 기본값."""
    try:
        return max(lo, min(hi, int(str(v).strip())))
    except ValueError:
        return default


def _dotenv() -> dict[str, str]:
    p = ROOT / ".env"
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


@dataclass(frozen=True)
class Settings:
    llm_enabled: bool
    llm_jobs: frozenset
    llm_url: str
    llm_model: str
    api_key: str | None
    connect_s: float
    read_s: float
    budget_s: float
    retrieval: str          # bm25 | hybrid
    embed_url: str
    embed_model: str
    database_url: str | None
    problem: str | None     # 설정이 규칙에 어긋나 LLM을 끈 이유 (예: 루프백이 아닌 주소)
    # 앞단 개선 스위치 (2026-10-10 계획). 기본값 = 그 전 동작. 평가 모드·시험 고정물이 모두 명시한다.
    num_match: str = "token"      # token | value  (검사관: 숫자를 글자로 / 값으로 비교)
    parse_v2: bool = False        # 규칙 보강: 시간 말·설비 별명·요청 꼴 안전장치·화면 알람 문맥·빠진 항목 되묻기
    route_policy: str = "rescue"  # rescue | llm_primary | llm_guarded  (표지판)
    doc_gate: str = "lexical"     # lexical | veto(AI가 답할 수 없다고 하면 거부) | tiered(veto + 2차 문지기)  (문지기)
    # 2차 (2026-10-10, 봉인 시험 E2로 판단): 규칙 보강 2차 · LLM 질문 나누기. PARSE_V3는 PARSE_V2=1일 때만 동작
    parse_v3: bool = False        # 날짜만 있는 말·상대 날짜, 붙은 말 제외, 조작 요청 꼴, 화면 알람 주제, 섞인 질문 문서 쪽, 알람 세부 검사
    split_q: bool = False         # 분류에 문서 쪽 질문 칸(doc_question), 2차 문지기 앞머리 검사 건너뜀
    # 3차 (2026-10-10, 봉인 시험 E3로 판단): 규칙 보강 3차 · 2차 문지기 후보 순서(실험) · LLM 앞부분 재사용(흔들림 확인용)
    parse_v4: bool = False        # 지난주+요일 날짜, 답 종류의 분 단위, 대명사 경계, 알람 횟수 꼴, 업무 밖 부탁, 알람 기준값, 가정 질문
    cand_order: str = "rank"      # rank | doc | dual  (2차 문지기 후보 순서 — 실험, research_notes 앞단개선3)
    cache_prompt: bool = True     # True = llama-server 기본(요청에 넣지 않음). False면 cache_prompt=false를 보낸다
    # 4차 (2026-10-11, 봉인 시험 E4로 판단): 규칙 보강 4차 — 조작 요청 사이 낀 말, 단위 값 알람 질문, 경계 결함 등 (앞단개선4 노트)
    parse_v5: bool = False
    # 5차 (2026-10-11, 봉인 시험 E5로 판단): 규칙 보강 5차 — "~해 줄래?" 요청 꼴, 1차 문지기 답 종류 검사 등 (앞단개선5 노트)
    parse_v6: bool = False
    # 6차 (2026-10-12, 봉인 시험 E6로 판단): 규칙 보강 6차 — 답 모양 낱말 빼기·전제 마디·"무슨 모델" 꼴 (앞단개선6 노트)
    parse_v7: bool = False
    # 6차 (2026-10-12, 사용자 결정 "3번까지"): 이어 묻기 — 앞 답을 가리키는 질문 감지·되묻기·앞 답 쉽게 다시 쓰기 [제안]
    followup: bool = False
    # 7차 (2026-10-12, 봉인 시험 E7로 판단): 안전 3개(알람 카드 길 답 종류·이어 묻기 끝말·허락 꼴)·결함 고침·정직한 표시 (앞단개선7 노트)
    parse_v8: bool = False
    # 7차: 이어 묻기가 실제로 일하게 — 칸 단위 안전 판정·자리표·보인 글 기억·"쉽게" = 낱말 풀이 [제안]
    followup_v2: bool = False
    # 8차 (2026-10-12, 봉인 시험 E8로 판단, 앞단개선8 노트) — 셋 다 PARSE_V8이 켜졌을 때만 동작
    parse_v9: bool = False        # 규칙 보강 8차: "얘기해"·"몇 건씩"·"리스트 줘" 좁은 예외·모양 이어 묻기·용어집 풀이 정리
    flow_v9: bool = False         # 흐름 바꾸기: 알람 + 문서 함께(카드 영문명)·섞인 질문의 문서 쪽 따로 답하기·줄 고르기 대상 한정
    blocks_v2: bool = False       # 줄 목록 칸 2판 (표시만): 운영 항목 목록·표 줄 칸·줄마다 출처 — conclusion 글자는 그대로
    # 9차 (2026-10-13, 봉인 시험 E9로 판단, 앞단개선9 노트 — 1부 화면 대화 원인 A~J) — 셋 다 PARSE_V8이 켜졌을 때만 동작
    parse_v10: bool = False       # 띄어쓰기: 사내 문서 낱말 + 조사 + 묻는 말이 붙은 낱말을 나눔 (원인 H)
    flow_v10: bool = False        # 섞인 알람 질문의 운영 조회를 마디마다 (I)·카드 칸 "원문 설명" 빼기 (D)·알람 답 "짧게"는 프로그램이 (B)
    blocks_v3: bool = False       # 줄 목록 칸 3판 (표시만): 앞 답 그대로 답의 줄 목록 (A)·덩어리 제목·점검 순서 자리 (C)·정지 기준 따로 (F)·꼬리표 (G)
    # 10차 (2026-10-13 사용자 결정): 문서 답을 AI가 찾은 줄로 새로 씀 (해요체 1~3문장, 원문 줄은 아래에 접음) — 알람·DOC-03·DOC-05·절차·안전 낱말은 빼고
    doc_write: bool = False
    # 10차 보강 (2026-10-14 사용자 결정): 표준 용어 질문은 용어집 줄을 2차 문지기 후보 맨 앞에 (MTBF "?" 흔들림의 뿌리),
    # 새로 쓴 답의 영문 약어 뒤 조사 ("MTBF은" → "MTBF는") — PARSE_V8이 켜졌을 때만
    parse_v11: bool = False
    # 10차 보강 (2026-10-14 사용자 결정): 1차 문지기 길의 AI 앞머리 한 문장에도 새로 쓴 답과 같은 검사 (허락·조작 지시·"~해야 한다"·안전 낱말 + 따로 판정)
    # — 못 지나면 앞머리를 빼고 원문 줄만. "~해야 한다"는 새로 쓴 답에도 건다. PARSE_V8이 켜졌을 때만
    lead_v12: bool = False
    # 10차 보강 (2026-10-14 사용자 결정): ① 화면에 나가는 AI 글에 용어집 "쓰지 않는 말"이 원문·질문에 없는데 새로 나오면 막음
    # ② 용어를 묻는 질문은 검사를 다 지난 뒤 보일 줄을 용어집 줄만 남김 — PARSE_V8이 켜졌을 때만
    term_v13: bool = False
    # 안전 영역 새로쓰기 (2026-10-14 사용자 결정 "대체 방식·단계적·엄격·짝 질문 수준 확인" — 안전 규칙 2.5·3.4·4.1이 바뀐 것, 결정 바뀜):
    # 쉬운 말로 1:1 다시 쓴 점검 순서·안전 줄을 먼저 보이고 원문은 [원문 보기]로 접는다. 하나라도 검사에 실패하면 새 글은 버리고 원문만.
    # 고정 서식(LOTO 6+3·고전압 5분 문구·보호구·차단 지점 표)은 대체하지 않는다. PARSE_V8이 켜졌을 때만. 모두 꺼진 채 시작, 단계마다 사용자가 켠다.
    safe_write_card: bool = False    # 1단계: 알람 번호 질문의 지침카드 길(DOC-02·03 점검 순서)
    safe_write_doc: bool = False     # 2단계: DOC-03·DOC-05 문서 질문 줄
    safe_write_proc: bool = False    # 3단계: 절차 줄
    safe_write_words: bool = False   # 4단계: 안전 낱말이 든 줄
    # 비교 실험 (2026-10-14 사용자 결정): LLM 공급자 local(기본, llama.cpp) | claude(Anthropic API). claude는 시험용 복사본의 비교 실험 전용이다 —
    # 환경변수 MOM_EXTERNAL_LLM_OK=1(os.environ에서만 읽음)이 없으면 꺼진다. 열쇠(ANTHROPIC_API_KEY)는 여기에 담지 않는다 (claude_client가 os.environ에서 읽음).
    # 지시문 후보 (2026-10-14 비교 실험 C단계, 둘 다 DOC_WRITE가 켜졌을 때만 동작, 기본 꺼짐): 새로 쓰기 지시문에 좋은 답 예시·안전 낱말 남기기 한 줄 / 줄의 절 제목
    write_shots: bool = False
    write_titles: bool = False
    # 새 글 규칙 정밀도 (2026-10-14 시급한 문제 2 "원문 복사", 계획 승인): 코드 규칙이 맞는 새 글을 막는 곳을 좁히고(질문이 받은 "~해야 한다" 꼴,
    # "~만 가능"+부정, 불 끄기 "끄세요", 안전 낱말은 답에 쓴 칸에서만) 뜻이 뒤집힌 글은 먼저 조인다(원문에 없는 "수 있"·접근 금지 경고 줄 제외).
    # DOC_WRITE·PARSE_V8이 켜졌을 때만. 기본 꺼짐
    write_rules_v17: bool = False
    # 답 문지기 (2026-10-14 시급한 문제 1 "지어낸 답", 사용자 결정 D1·D2): 문서 길(1차·2차 문지기)의 답 종류 표에 부품번호·기본값을 더하고(CMP-022),
    # 낱말 겹침 문턱을 0.2 → 0.1로 낮춘다(구어체 질문의 맞는 답). PARSE_V8이 켜졌을 때만. 기본 꺼짐
    answer_gate_v17: bool = False
    # 번호 붙은 절차 표 채우기 (2026-10-15, 사용자 승인 계획 "전원 켜기 표 1·6번 빠짐"): 문서 답으로 고른 줄이 번호 붙은 절차 표(첫 칸 1·2·3…, 12줄 이하)의
    # 줄이면 같은 표의 나머지 줄도 문서 순서대로 함께 보인다(LLM 단계는 건드리지 않고 검사를 다 지난 뒤 보일 줄에서만). PARSE_V8이 켜졌을 때만. 기본 꺼짐
    table_fill_v18: bool = False
    # "해야 할 일 꼴" 코드 검사 끄기 실험 (2026-10-15, research_notes/OBLIGE_끄기_실험_20261015.md): 기본 켜짐(True = 지금 동작).
    # False면 새로 쓴 답(일반 새로 쓰기, safe=False)의 check_answer_v11에서 OBLIGE_V12 검사만 건너뛴다. 앞머리 검사·안전 영역 새로쓰기(safe=True)·이어 묻기는 그대로.
    oblige_check: bool = True
    # 순수 외부 LLM 연결 (2026-10-15, research_notes/순수외부LLM_연결_20261015.md — 시험용 복사본 전용): PURE_EXTERNAL=1이고 **외부 Claude를 고른 요청**일 때만,
    # 위험한 부탁·권한·화면 설명·불량 원인·이어 묻기로 걸러지지 않은 질문을 "낱말 검색 상위 조각 + 질문 → 외부 Claude 1번 → 답을 그대로" 길로 보낸다
    # (줄 고르기·따로 검증·새 글 검사·분류 LLM 없음). 기본 꺼짐 = 지금 동작. 로컬 요청이면 이 스위치와 상관없이 지금 동작 그대로.
    # pure_keep_signals: 0(기본) = 알람 번호·날짜·설비·운영 낱말 길도 끄고 전부 순수 길 / 1 = 그 신호가 있는 질문은 기존 길 그대로(신호 없는 질문만 순수 길)
    # pure_topk: 순수 길에서 Claude에 주는 조각 수 (1~20, 기본 8)
    pure_external: bool = False
    pure_keep_signals: bool = False
    pure_topk: int = 8
    # pure_style: 1이면 순수 길(위 pure_external)의 Claude 지시문·답 형식을 "옆자리 선배가 풀어서 말하는" 대화체로 바꾼다
    # (opening·points·closing 짜임 — 서버가 화면의 번호 목록·본문 블록으로 조립. 코드 검사·재시도는 더하지 않는다). 기본 꺼짐 = 지금 말투 그대로.
    pure_style: bool = False
    # pure_layout: 1이면(그리고 pure_style=1일 때만 뜻이 있다) 순수 길의 답 형식을 "묶음 목록(sections: title·text·items)"으로 바꿔, 서로 다른 말을 묶음으로 나눠 담게 하고
    # 서버가 묶음마다 화면 블록 하나씩(소제목 · 머리 + 번호 목록 · 한 문장)을 만든다. 코드 검사·재시도는 더하지 않는다. 기본 꺼짐 = PURE_STYLE=1의 지금 동작 그대로.
    pure_layout: bool = False
    # pure_expand: 1이면 순수 길에서 Claude에 주는 조각에 "아래 절"을 더한다 — 검색 상위 조각에 직계 아래 절이 있으면 짧은 것부터 몇 개(최대 4개·2,500자) 같이 준다.
    # "잠금 표지 순서" 결함의 수정: DOC-05 §2.1 "작업 전 6단계"가 검색 66위라 Claude에게 안 가서 "문서에 없다"고 틀리게 답했다 (부모 §2는 상위 8개에 있다).
    # 기본 꺼짐 = 지금 동작 그대로 (순수 길 PURE_EXTERNAL=1일 때만 뜻이 있다).
    pure_expand: bool = False
    # pure_safety: 1이면 순수 길의 **안전 질문**에 거짓 "문서에 없다"가 나오지 않게 한다 (2026-10-18, "톱 정비 전에 어디를 차단해야 해?"가 문서에 있는 §3.1을 못 찾아 NOT_IN_DOCS).
    # ① 안전 낱말이 든 질문에는 안전 작업 기준서(DOC-05) 조각을 통째로 더한다 ①-b PURE_KEEP_SIGNALS=1에서 신호가 설비 이름뿐인 안전 질문은 순수 길로 보낸다
    # ② 안전 질문의 "답 없음"은 "문서에 없다" 대신 "자동으로 확인하지 못했어요(문서에 없다는 뜻이 아님)" + 가까운 절 (상태는 기존 "확인 필요"). 기본 꺼짐 = 지금 동작 그대로.
    pure_safety: bool = False
    llm_provider: str = "local"
    # 스위치 이름은 MOM_CLAUDE_* — 이 PC의 Claude Code 환경에 CLAUDE_EFFORT 같은 값이 이미 있어(2026-10-14 확인) 같은 이름을 쓰면 섞인다.
    claude_model: str = "claude-opus-5-5"
    claude_effort: str = "low"           # low | medium | high | xhigh | max
    claude_cost_cap_usd: float = 20.0    # 이 값에 닿으면 외부 호출을 멈춘다 (cli 방식에서는 API 가격표로 환산한 값 — 청구가 아니라 폭주 방지)
    claude_via: str = "cli"              # cli = 이 PC의 Claude Code(`claude -p`, 구독 로그인) | api = Anthropic API(ANTHROPIC_API_KEY)
    # 앱의 외부 LLM 선택 스위치 (2026-10-15 사용자 결정, research_notes/외부LLM_스위치_최종기획서_20261014.md): 서버 끄는 스위치 EXTERNAL_LLM_APP
    # (코드 기본 꺼짐 — .env에서 켠다), 동시 claude 프로세스 상한 EXTERNAL_PROC_LIMIT(PC 보호용, 사용량 제한이 아님), claude_app = 이 요청이 외부(Claude)로 가는지
    external_app: bool = False
    proc_limit: int = 8
    claude_app: bool = False
    # Qwen "깊게 생각" 버튼 (2026-10-15 사용자 결정, 생각 예산 6,000토큰): 서버 허용 스위치 THINK_APP(코드 기본 꺼짐 — .env에서 켠다),
    # think_budget = 이 요청이 실제로 쓰는 생각 예산(버튼을 눌렀고 서버가 허용했고 로컬 Qwen일 때만 6000, 아니면 0 = 예전과 같음)
    think_app: bool = False
    think_budget: int = 0
    # 단계별 로그 (2026-10-15, research_notes/단계별로그_STEP_LOG_총기획서_20261015.md): 켜면 질문마다 단계별 기록 한 줄을 step_log_dir의 steps_YYYYMMDD.jsonl에 남긴다
    # (읽기만 한다 — 답은 같다). 코드 기본 꺼짐 — 앱 .env에서만 켠다. 평가·시험은 늘 끈다. 폴더는 저장소 밖이다
    step_log: bool = False
    step_log_dir: str = r"C:\llm\logs"

    @property
    def llm_label(self) -> str:
        """화면·평가 기록에 쓰는 LLM 이름표 — 외부로 나가는 모드를 로컬이라고 적지 않는다 (정직한 표시)."""
        if self.claude_app:
            return "외부 LLM(Claude Sonnet 5.5)"   # 앱 스위치로 고른 외부 모드 (평가 경로의 "(Claude, 실험)"과 구분)
        return "외부 LLM(Claude, 실험)" if self.llm_provider == "claude" else "로컬 LLM"

    @property
    def llm_model_name(self) -> str:
        return self.claude_model if self.llm_provider == "claude" else self.llm_model

    def job(self, name: str) -> bool:
        return self.llm_enabled and name in self.llm_jobs

    def flags(self) -> dict:
        return {"num_match": self.num_match, "parse_v2": self.parse_v2, "route_policy": self.route_policy, "doc_gate": self.doc_gate,
                "parse_v3": self.parse_v3, "split_q": self.split_q, "parse_v4": self.parse_v4, "cand_order": self.cand_order,
                "cache_prompt": self.cache_prompt, "parse_v5": self.parse_v5, "parse_v6": self.parse_v6,
                "parse_v7": self.parse_v7, "followup": self.followup, "parse_v8": self.parse_v8, "followup_v2": self.followup_v2,
                "parse_v9": self.parse_v9, "flow_v9": self.flow_v9, "blocks_v2": self.blocks_v2,
                "parse_v10": self.parse_v10, "flow_v10": self.flow_v10, "blocks_v3": self.blocks_v3,
                "doc_write": self.doc_write, "parse_v11": self.parse_v11, "lead_v12": self.lead_v12, "term_v13": self.term_v13,
                "safe_write_card": self.safe_write_card, "safe_write_doc": self.safe_write_doc,
                "safe_write_proc": self.safe_write_proc, "safe_write_words": self.safe_write_words,
                "write_shots": self.write_shots, "write_titles": self.write_titles, "write_rules_v17": self.write_rules_v17,
                "answer_gate_v17": self.answer_gate_v17, "table_fill_v18": self.table_fill_v18, "oblige_check": self.oblige_check,
                "pure_external": self.pure_external, "pure_keep_signals": self.pure_keep_signals, "pure_topk": self.pure_topk, "pure_style": self.pure_style,
                "pure_layout": self.pure_layout, "pure_expand": self.pure_expand, "pure_safety": self.pure_safety,
                "llm_provider": self.llm_provider, "claude_via": self.claude_via, "claude_model": self.claude_model,
                "claude_effort": self.claude_effort,
                "external_app": self.external_app, "proc_limit": self.proc_limit, "claude_app": self.claude_app,
                "think_app": self.think_app, "think_budget": self.think_budget, "step_log": self.step_log}


FLAG_CHOICES = {"NUM_MATCH": ("token", "value"), "ROUTE_POLICY": ("rescue", "llm_primary", "llm_guarded"),
                "DOC_GATE": ("lexical", "veto", "tiered"), "CAND_ORDER": ("rank", "doc", "dual"),
                "LLM_PROVIDER": ("local", "claude"), "MOM_CLAUDE_EFFORT": ("low", "medium", "high", "xhigh", "max"),
                "MOM_CLAUDE_VIA": ("cli", "api")}


def settings() -> Settings:
    env = {**_dotenv(), **os.environ}
    get = lambda k, d="": env.get(k, d)  # noqa: E731
    llm_url, embed_url = get("LLM_URL", "http://127.0.0.1:8080"), get("EMBED_URL", "http://127.0.0.1:8081")
    problem = None

    def choice(name, default):  # 모르는 값이면 기본값(그 전 동작)으로 둔다
        v = get(name, default).strip().lower()
        return v if v in FLAG_CHOICES[name] else default

    provider = choice("LLM_PROVIDER", "local")
    # 앱의 외부 LLM 선택 스위치 (2026-10-15): 서버 끄는 스위치가 켜져 있고 **이 요청이 'claude'를 골랐을 때만** 외부다(요청 단위 — llm/external.py).
    # 요청이 고르지 않으면(기본) 아래 모든 값이 예전과 같다.
    app_on = get("EXTERNAL_LLM_APP", "0") in ("1", "true", "yes")
    claude_app = app_on and EXT.override() == "claude"
    if claude_app:
        provider = "claude"
    try:
        proc_limit = max(1, int(get("EXTERNAL_PROC_LIMIT", "8")))
    except ValueError:
        proc_limit = 8
    # Qwen "깊게 생각" 버튼 (2026-10-15): 서버 허용 스위치가 켜져 있고 **이 요청이 버튼을 눌렀고** 로컬 Qwen일 때만 생각을 켠다(요청 단위 — llm/think.py).
    # 켜진 요청은 호출·한 답 시간 예산도 늘린다(안 늘리면 생각 도중에 끊긴다). 누르지 않으면(기본) 아래 모든 값이 예전과 같다.
    think_app = get("THINK_APP", "0") in ("1", "true", "yes")
    think_on = think_app and THINK.override() == THINK.DEEP_BUDGET and not claude_app and provider == "local"
    # 운영 데이터·사내 문서는 밖으로 나가지 않는다 (NFR-SEC-08 — 2026-10-15 사용자 결정으로 앱 스위치로 고른 요청은 예외, 결정이 바뀐 것). 로컬 LLM 주소와 임베딩 주소는 루프백만 — claude일 때도 임베딩은 검사한다.
    for u in ((llm_url, embed_url) if provider == "local" else (embed_url,)):
        if urlparse(u).hostname not in LOOPBACK:
            problem = f"루프백이 아닌 주소라 끔: {urlparse(u).hostname}"
    # 외부 LLM(claude)은 비교 실험 전용 한시 예외다 (2026-10-14 사용자 결정). 잠금은 os.environ에서만 읽는다 — .env에 적어도 켜지지 않는다.
    if provider == "claude" and not claude_app and os.environ.get("MOM_EXTERNAL_LLM_OK") != "1":   # 앱 스위치 경로는 서버 스위치가 문이다
        problem = "외부 LLM 잠금: 비교 실험 전용(MOM_EXTERNAL_LLM_OK=1 없음)이라 끔"
    enabled = get("LLM_ENABLED", "0") in ("1", "true", "yes") and problem is None

    return Settings(
        llm_enabled=enabled, llm_jobs=frozenset(j.strip() for j in get("LLM_JOBS", "write").split(",") if j.strip()),
        llm_url=llm_url.rstrip("/"), llm_model=get("LLM_MODEL", "qwen3.5-9b-q4km"), api_key=get("LLM_API_KEY") or None,
        connect_s=10.0 if claude_app else float(get("LLM_CONNECT_S", "1")),   # 외부 모드는 인터넷·프로세스 시작 시간을 감안해 늘린다(평가 모드 claude-*와 같은 값)
        read_s=60.0 if claude_app else (max(THINK.DEEP_READ_S, float(get("LLM_READ_S", "8"))) if think_on else float(get("LLM_READ_S", "8"))),
        budget_s=120.0 if claude_app else (max(THINK.DEEP_BUDGET_S, float(get("LLM_BUDGET_S", "15"))) if think_on else float(get("LLM_BUDGET_S", "15"))),
        retrieval=get("RETRIEVAL", "bm25") if problem is None else "bm25",
        embed_url=embed_url.rstrip("/"), embed_model=get("EMBED_MODEL", "bge-m3"),
        database_url=get("DATABASE_URL") or None, problem=problem,
        num_match=choice("NUM_MATCH", "token"), parse_v2=get("PARSE_V2", "0") in ("1", "true", "yes"),
        route_policy=choice("ROUTE_POLICY", "rescue"), doc_gate=choice("DOC_GATE", "lexical"),
        parse_v3=get("PARSE_V3", "0") in ("1", "true", "yes"), split_q=get("SPLIT_Q", "0") in ("1", "true", "yes"),
        parse_v4=get("PARSE_V4", "0") in ("1", "true", "yes"), cand_order=choice("CAND_ORDER", "rank"),
        cache_prompt=get("LLM_CACHE_PROMPT", "1") not in ("0", "false", "no"),
        parse_v5=get("PARSE_V5", "0") in ("1", "true", "yes"),
        parse_v6=get("PARSE_V6", "0") in ("1", "true", "yes"),
        parse_v7=get("PARSE_V7", "0") in ("1", "true", "yes"),
        followup=get("FOLLOWUP", "0") in ("1", "true", "yes"),
        parse_v8=get("PARSE_V8", "0") in ("1", "true", "yes"),
        followup_v2=get("FOLLOWUP_V2", "0") in ("1", "true", "yes"),
        parse_v9=get("PARSE_V9", "0") in ("1", "true", "yes"),
        flow_v9=get("FLOW_V9", "0") in ("1", "true", "yes"),
        blocks_v2=get("BLOCKS_V2", "0") in ("1", "true", "yes"),
        parse_v10=get("PARSE_V10", "0") in ("1", "true", "yes"),
        flow_v10=get("FLOW_V10", "0") in ("1", "true", "yes"),
        blocks_v3=get("BLOCKS_V3", "0") in ("1", "true", "yes"),
        doc_write=get("DOC_WRITE", "0") in ("1", "true", "yes"),
        parse_v11=get("PARSE_V11", "0") in ("1", "true", "yes"),
        lead_v12=get("LEAD_V12", "0") in ("1", "true", "yes"),
        term_v13=get("TERM_V13", "0") in ("1", "true", "yes"),
        safe_write_card=get("SAFE_WRITE_CARD", "0") in ("1", "true", "yes"),
        safe_write_doc=get("SAFE_WRITE_DOC", "0") in ("1", "true", "yes"),
        safe_write_proc=get("SAFE_WRITE_PROC", "0") in ("1", "true", "yes"),
        safe_write_words=get("SAFE_WRITE_WORDS", "0") in ("1", "true", "yes"),
        write_shots=get("WRITE_SHOTS", "0") in ("1", "true", "yes"), write_titles=get("WRITE_TITLES", "0") in ("1", "true", "yes"),
        write_rules_v17=get("WRITE_RULES_V17", "0") in ("1", "true", "yes"),
        answer_gate_v17=get("ANSWER_GATE_V17", "0") in ("1", "true", "yes"),
        table_fill_v18=get("TABLE_FILL_V18", "0") in ("1", "true", "yes"),
        oblige_check=get("OBLIGE_CHECK", "1").strip().lower() not in ("0", "false", "no"),   # 기본 켜짐 — 모르는 값도 켜짐(지금 동작)
        pure_external=get("PURE_EXTERNAL", "0").strip().lower() in ("1", "true", "yes"),   # 기본 꺼짐 — 모르는 값·빈 값도 꺼짐(지금 동작)
        pure_keep_signals=get("PURE_KEEP_SIGNALS", "0").strip().lower() in ("1", "true", "yes"),
        pure_topk=_int_clamped(get("PURE_TOPK", "8"), 8, 1, 20),
        pure_style=get("PURE_STYLE", "0").strip().lower() in ("1", "true", "yes"),   # 기본 꺼짐 — 모르는 값·빈 값도 꺼짐(지금 말투)
        pure_layout=get("PURE_LAYOUT", "0").strip().lower() in ("1", "true", "yes"),   # 기본 꺼짐 — 모르는 값·빈 값도 꺼짐 (PURE_STYLE=1일 때만 뜻이 있다)
        pure_expand=get("PURE_EXPAND", "0").strip().lower() in ("1", "true", "yes"),   # 기본 꺼짐 — 모르는 값·빈 값도 꺼짐(지금 동작)
        pure_safety=get("PURE_SAFETY", "0").strip().lower() in ("1", "true", "yes"),   # 기본 꺼짐 — 모르는 값·빈 값도 꺼짐(지금 동작)
        llm_provider=provider,
        claude_model="claude-sonnet-5-5" if claude_app else get("MOM_CLAUDE_MODEL", "claude-opus-5-5").strip(),   # 앱 스위치: Sonnet 5.5 medium, 구독 로그인(cli) 고정
        claude_effort="medium" if claude_app else choice("MOM_CLAUDE_EFFORT", "low"),
        claude_via="cli" if claude_app else choice("MOM_CLAUDE_VIA", "cli"),
        claude_cost_cap_usd=0.0 if claude_app else _float(get("MOM_CLAUDE_COST_CAP_USD", "20"), 20.0),   # 앱 스위치: 사용 상한 없음(사용자 결정)
        external_app=app_on, proc_limit=proc_limit, claude_app=claude_app,
        think_app=think_app, think_budget=THINK.DEEP_BUDGET if think_on else 0,
        step_log=get("STEP_LOG", "0") in ("1", "true", "yes"), step_log_dir=get("STEP_LOG_DIR", "").strip() or r"C:\llm\logs")
