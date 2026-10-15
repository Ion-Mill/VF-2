"""AI 비서 조회 도구 14개 (FR-MNT-01-04, FR-AST-COM-14).

  · 비서(LLM)는 SQL을 쓰지 않는다. 여기 정해진 도구만 부르고, 숫자는 DB가 계산한다 (FR-AST-COM-05).
  · 도구는 읽기 전용 연결(mom_ai_ro / default_transaction_read_only)에서 돈다.
  · 누구를 대신해 묻는지(on_behalf_of)의 역할 권한으로 도구를 거른다 — OPR은 일일 보고서·정식 작업기록을 못 봄 (13.1).
  · 3D 라인 뷰에서 뺀 MTTR·MTBF·센서 추세·설비 사양·정지 원인 순위는 비서 질문으로 본다 (2026-10-07 팀 UI 검토):
    reliability · sensor_trend · equipment_spec · stop_reasons
JSON Schema는 LLM 도구 정의(tool_use)에 그대로 넣을 수 있는 모양이다.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..db import Db
from ..errors import AppError

DATE = {"type": "string", "format": "date"}
DATETIME = {"type": "string", "format": "date-time"}
EQUIPMENT = {"type": "string", "description": "설비 ID (예: VF2-01). 비우면 전체"}


# 채팅 권한 (2026-10-13 팀 결정 [가상, 바뀔 수 있음], 논리 ERD 5.G.7·R-87): MTTR(지표)·센서 데이터(센서 추세)는 MNT·MGR만.
# 서버가 조회 도구를 부르기 전에 역할을 확인한다. 막는 범위는 채팅 답뿐 (일일 보고서 정비 칸 MTTR 같은 화면 권한은 그대로)
CHAT_MNT_MGR = ("MNT", "MGR")
OUT_OF_ROLE_TEXT = {"reliability": "MTTR·MTBF", "sensor_trend": "센서 데이터"}


@dataclass(frozen=True)
class Tool:
    name: str
    query: str
    description: str
    permission: tuple[str, str]
    properties: dict[str, Any] = field(default_factory=dict)
    required: tuple[str, ...] = ()
    max_days: int | None = None          # 기간 도구의 최대 기간 (너무 넓은 조회 막기)
    chat_roles: tuple[str, ...] | None = None   # 채팅 답에 쓸 수 있는 역할 (None = 권한 표대로). 2026-10-13 팀 결정

    def schema(self) -> dict:
        return {"name": self.name, "description": self.description,
                "input_schema": {"type": "object", "properties": self.properties, "required": list(self.required),
                                 "additionalProperties": False}}


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("equipment_status", "assistant.equipment_status", "설비 지금 상태 (상태·경과 분·열린 알람·잠금 여부·가공 중 로트)",
         ("LINE_VIEW", "VIEW"), {"equipment_id": EQUIPMENT}),
    Tool("alarms", "assistant.alarms", "기간 안 알람 횟수·처음·마지막·정지 분 (설비·알람 번호로 거르기)",
         ("LINE_VIEW", "VIEW"), {"from": DATETIME, "to": DATETIME, "equipment_id": EQUIPMENT,
                                 "alarm_code": {"type": "string"}}, ("from", "to"), max_days=31),
    Tool("kpi", "assistant.kpi", "교대·설비별 가동률·성능·품질·OEE와 시간·수량 (계산된 값)",
         ("KPI", "VIEW"), {"from_date": DATE, "to_date": DATE, "equipment_id": EQUIPMENT,
                           "shift_type": {"type": "string", "enum": ["DAY", "NIGHT"]}}, ("from_date", "to_date"), max_days=31),
    Tool("production", "assistant.production",
         "교대별 총 목표(목표 + 이월, 이월은 같은 날 주간 → 야간만)·실적·불량·예측·부족·손실(고장 + 속도, 추정)과 작업지시 번호. "
         "하루 목표는 180 고정 (하루 부족 = 180 − 두 교대 실적 합). 확정 전 교대 값·이월은 잠정",
         ("PRODUCTION", "VIEW"), {"from_date": DATE, "to_date": DATE}, ("from_date", "to_date"), max_days=31),
    Tool("lot", "assistant.lot", "로트 1개의 상태·수량·검사 방식·출하와 추적(공정·설비·작업자·검사)",
         ("LOT_TRACE", "VIEW"), {"lot_no": {"type": "string", "description": "예: LOT-2609-041-1"}}, ("lot_no",)),
    Tool("work_orders", "assistant.work_orders", "작업지시서 목록 (최근 20건, 진행 중만 거르기 가능)",
         ("WORK_ORDER", "VIEW"), {"equipment_id": EQUIPMENT, "open_only": {"type": "boolean"}}),
    Tool("work_records", "assistant.work_records", "확정된 작업기록의 원인·조치 (같은 알람 지난 사례 찾기)",
         ("WORK_RECORD", "VIEW"), {"equipment_id": EQUIPMENT, "alarm_code": {"type": "string"}}),
    Tool("pm_due", "assistant.pm_due", "예방 정비 기한이 다가오거나 넘긴 항목",
         ("PM_SCHEDULE", "VIEW"), {"within_days": {"type": "integer", "minimum": 0, "maximum": 31}, "equipment_id": EQUIPMENT},
         ("within_days",)),
    Tool("tool_life", "assistant.tool_life", "공구 사용률·남은 부품 수 (OP-30)",
         ("TOOL_LIFE", "VIEW"), {"equipment_id": EQUIPMENT}),
    Tool("inventory", "assistant.inventory", "재고·안전 재고·부족 여부·최근 7일 출하",
         ("INVENTORY", "VIEW"), {"item_no": {"type": "string"}}),
    Tool("reliability", "assistant.reliability",
         "설비별 최근 30일 MTTR(분)·MTBF(시간)·고장 횟수 (정지 등급 고장만). 고장 0건이면 값 없음(—), MTTR 120분 초과는 주의",
         ("KPI", "VIEW"), {"equipment_id": EQUIPMENT}, chat_roles=CHAT_MNT_MGR),
    Tool("stop_reasons", "assistant.stop_reasons", "기간 안 정지 원인 순위 (설비·사유별 횟수·분·손실 수량 추정, 계획 정지 제외)",
         ("KPI", "VIEW"), {"from": DATETIME, "to": DATETIME, "equipment_id": EQUIPMENT}, ("from", "to"), max_days=31),
    Tool("sensor_trend", "assistant.sensor_trend",
         "OP-30 설비 센서 값 최근 N분(기본 60분) 최소·평균·최대·마지막 값과 정상 범위([참고]). 알람 기준값은 없다",
         ("LINE_VIEW", "VIEW"), {"equipment_id": {"type": "string", "description": "OP-30 설비 ID (VF2-01·VF2-02)"},
                                 "sensor_code": {"type": "string", "description": "비우면 전체 센서"},
                                 "minutes": {"type": "integer", "minimum": 1, "maximum": 360}}, ("equipment_id",),
         chat_roles=CHAT_MNT_MGR),
    Tool("equipment_spec", "assistant.equipment_spec", "설비 사양 (모델·제어기·기준 사이클·외형 크기 mm와 크기 근거 실제/참고/가상)",
         ("LINE_VIEW", "VIEW"), {"equipment_id": EQUIPMENT}),
]}


def schemas(allowed: set[str] | None = None) -> list[dict]:
    return [t.schema() for t in TOOLS.values() if allowed is None or t.name in allowed]


def _parse(value: Any, kind: dict, name: str):
    if value is None:
        return None
    try:
        if kind.get("format") == "date":
            return dt.date.fromisoformat(str(value))
        if kind.get("format") == "date-time":
            t = dt.datetime.fromisoformat(str(value))
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone(dt.timedelta(hours=9)))   # 시간대 없으면 한국 시간
            return t
        if kind.get("type") == "integer":
            return int(value)
        if kind.get("type") == "boolean":
            return bool(value)
    except (TypeError, ValueError):
        raise AppError(422, "VALIDATION", f"{name} 값 형식이 맞지 않음: {value!r}") from None
    return str(value)


def validate(tool: Tool, args: dict) -> dict:
    unknown = set(args) - set(tool.properties)
    if unknown:
        raise AppError(422, "VALIDATION", f"{tool.name}: 모르는 입력 {sorted(unknown)}")
    missing = [r for r in tool.required if args.get(r) in (None, "")]
    if missing:
        raise AppError(422, "VALIDATION", f"{tool.name}: 필요한 입력 {missing}")
    out = {k: _parse(args.get(k), spec, k) for k, spec in tool.properties.items()}
    enum = {k: spec.get("enum") for k, spec in tool.properties.items() if spec.get("enum")}
    for k, allowed in enum.items():
        if out[k] is not None and out[k] not in allowed:
            raise AppError(422, "VALIDATION", f"{k}는 {allowed} 중 하나")
    if "within_days" in out and out["within_days"] is not None and not 0 <= out["within_days"] <= 31:
        raise AppError(422, "VALIDATION", "within_days는 0~31")
    for k, spec in tool.properties.items():
        v = out[k]
        if isinstance(v, int) and not isinstance(v, bool) and (
                v < spec.get("minimum", v) or v > spec.get("maximum", v)):
            raise AppError(422, "VALIDATION", f"{k}는 {spec.get('minimum')}~{spec.get('maximum')}")
    if tool.max_days:
        a, b = (out.get("from"), out.get("to")) if "from" in out else (out.get("from_date"), out.get("to_date"))
        if a and b:
            if b < a:
                raise AppError(422, "VALIDATION", "기간: 시작이 끝보다 늦음")
            days = (b - a).days if isinstance(a, dt.date) and not isinstance(a, dt.datetime) else (b - a).total_seconds() / 86400
            if days > tool.max_days:
                raise AppError(422, "VALIDATION", f"{tool.name}: 기간은 {tool.max_days}일까지")
    return out


def run(db: Db, name: str, args: dict) -> list[dict]:
    tool = TOOLS.get(name)
    if tool is None:
        raise AppError(404, "NOT_FOUND", f"도구 {name} 없음")
    return db.all(tool.query, **validate(tool, args))
