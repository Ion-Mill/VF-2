"""AI 비서 채팅 (API-AST-02 POST) — 로컬 LLM 연결 전 "규칙 답".

LLM 모델·실행 도구는 [선택 필요: 기술 회의]라서, 여기서는 질문 낱말로 조회 도구를 골라 프로그램 숫자·사내 문서 절을 그대로 돌려준다.
- 채팅 권한: MTTR(지표)·센서 데이터는 MNT·MGR만 (2026-10-13 팀 결정). 권한 밖이면 값 없이 누가 볼 수 있는지만.
- 센서는 정상 범위 [참고]만 말하고 알람 기준값은 말하지 않는다 (DOC-07 §3).
- 출처는 사내 문서 이름·번호·개정·§절만 (D-03).
"""
from __future__ import annotations

import re
import uuid

SRC = lambda P, doc, sec: {"doc_no": doc, "doc_name": P.docs[doc]["doc_name"], "rev": P.docs[doc]["rev"], "section": sec}
EQ_RE = re.compile(r"(SAW-01|MIL-01|VF2-01|VF2-02|WSH-01|CMM-01|VF2\s*-?\s*0?[12]|VF-?2)", re.I)


def norm_eq(s: str | None):
    if not s:
        return None
    s = s.upper().replace(" ", "")
    if s in ("VF2-1", "VF21", "VF2-01"):
        return "VF2-01"
    if s in ("VF2-2", "VF22", "VF2-02"):
        return "VF2-02"
    return s if s in ("SAW-01", "MIL-01", "VF2-01", "VF2-02", "WSH-01", "CMM-01") else None


def answer(q: str, role: str, ctx: dict, live, P, alarms: dict) -> dict:
    q0 = q.strip()
    ql = q0.lower()
    m = EQ_RE.search(q0)
    eq = norm_eq(m.group(1)) if m else norm_eq((ctx or {}).get("equipment_id"))
    out = {"chat_id": uuid.uuid4().hex[:12], "engine": "rule", "sources": [], "related": []}

    def deny(what):
        return {**out, "status": "권한 밖", "answer": f"{what}은(는) 보전 담당자(MNT)와 관리자(MGR)만 볼 수 있어요. 반장이나 보전 담당자에게 물어봐 주세요."}

    # 1) MTTR·MTBF
    if re.search(r"mttr|mtbf|평균 ?수리|고장 ?간격|수리 ?시간", ql):
        if role not in ("MNT", "MGR"):
            return deny("MTTR·MTBF")
        mt = live.mttr()
        rows = [(k, v) for k, v in mt.items() if not eq or k == eq]
        lines = []
        for k, v in rows:
            if v["failures"]:
                lines.append(f"{k}: 고장 {v['failures']}건, MTTR {v['mttr_min']}분{' ▲ 주의(120분 초과)' if v['mttr_warn'] else ''}, MTBF {v['mtbf_h']}시간")
            else:
                lines.append(f"{k}: 고장 0건 — MTTR·MTBF \"—\"")
        return {**out, "status": "ok", "answer": "최근 30일 (정지 등급 고장만 셈)\n" + "\n".join(lines),
                "sources": [SRC(P, "DOC-07", "6")]}

    # 2) 센서
    if re.search(r"센서|부하|모터 ?온도|공기 ?압|압력|psi|전압|추세", ql):
        if role not in ("MNT", "MGR"):
            return deny("센서 데이터")
        targets = [eq] if eq in ("VF2-01", "VF2-02") else ["VF2-01", "VF2-02"]
        if eq and eq not in ("VF2-01", "VF2-02"):
            return {**out, "status": "문서에 없음", "answer": f"{eq}에는 센서 기록이 없어요 (센서는 OP-30 VF-2 두 대만 기록)."}
        rt = live.rt
        names = {s["sensor_code"]: s for s in rt.M["sensor_item"]}
        lines, series = [], {}
        for e in targets:
            mins = rt.sensor_min.get(e, {})
            ks = sorted(mins)[-60:]
            if not ks:
                lines.append(f"{e}: 아직 센서 기록이 없어요.")
                continue
            last = mins[ks[-1]]
            parts = []
            for code in ("SpindleLoadPct", "SpindleMotorTemp", "AirPressure", "Xload", "Yload", "Zload"):
                vals = [mins[k][code] for k in ks]
                s = names[code]
                unit = s["unit"]
                v = last[code]
                vtxt = f"{v} psi ({v * 0.0689476:.2f} bar)" if code == "AirPressure" else f"{v}{unit}"
                parts.append(f"{s['sensor_name']} {vtxt} (최근 60분 {min(vals)}~{max(vals)}, 정상 범위 {s['normal_min']}~{s['normal_max']} [참고])")
                series.setdefault(e, {})[code] = vals
            lines.append(f"{e} (최근 1분 평균): " + " / ".join(parts))
        return {**out, "status": "ok", "answer": "\n".join(lines), "series": series,
                "sources": [SRC(P, "DOC-07", "3")]}

    # 3) 알람 번호
    codes = [c for c in alarms if re.search(r"(?<![\w.])" + re.escape(c) + r"(?![\w])", q0)]
    if codes:
        c = max(codes, key=len)
        a = alarms[c]
        sev = {"STOP": "정지", "WARN": "주의", "GUIDE": "조작 안내"}.get(a["severity"], a["severity"])
        steps = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(a.get("steps") or [])) or "(DOC-03에 점검 순서 줄 없음)"
        srcs = [SRC(P, "DOC-02", a["doc02"].replace("DOC-02 ", "").lstrip("§"))]
        for d in a.get("doc03") or []:
            mm = re.match(r"(DOC-\d+)\s+§?([\d.]+)", d)
            if mm and mm.group(1) in P.docs:
                srcs.append(SRC(P, mm.group(1), mm.group(2)))
        return {**out, "status": "ok", "sources": srcs,
                "answer": f"알람 {c} {a['nameKo']} — {sev} 등급, {'보전 담당자 호출' if a['responder'] == 'MNT' else '작업자 조치 가능'}.\n{a['easy']}\n먼저 할 일(작업자):\n{steps}"}

    # 4) 화면 설명
    if re.search(r"설명|이 화면|무슨 뜻|뭐야", ql) and (ctx or {}).get("screen"):
        p, k = live.production(), live.kpi()["by"]
        L = k["LINE"]
        txt = (f"지금 {p['actual_qty']} / 총 목표 {p['total_target_qty']}개 (목표 {p['target_qty']} + 이월 {p['carry_over_qty']}). "
               f"예측 {p['forecast_qty']}개{' ▲ 목표 미달 위험 (총 목표의 90% 미만)' if p['risk'] else ''} — 예측 = 실적 + 최근 1시간 속도 × 남은 시간 (추정). "
               f"라인 OEE {L['oee_pct'] if L['oee_pct'] is not None else '—'}% = 가동률 {L['availability_pct']}% × 성능 {L['performance_pct']}% × 양품률 {L['quality_pct']}% (OP-30 2대 합).")
        return {**out, "status": "ok", "answer": txt, "sources": [SRC(P, "DOC-07", "6"), SRC(P, "DOC-07", "8")]}

    # 5) 지표·병목·재공·공구·재고
    if re.search(r"oee|가동률|성능|양품률", ql):
        k = live.kpi()["by"]
        lines = [f"{n}: OEE {v['oee_pct']}% (가동률 {v['availability_pct']}% · 성능 {v['performance_pct']}% · 양품률 {v['quality_pct']}%)"
                 + (" ▲ " + "·".join(v["warn"]) + " 주의" if v["warn"] else "") for n, v in k.items()]
        return {**out, "status": "ok", "answer": "이번 교대 지금까지\n" + "\n".join(lines), "sources": [SRC(P, "DOC-07", "6")]}
    if "병목" in q0:
        t = live.twin()["bottleneck"]
        cause = {"C1": "원인 ① 사이클 시간 증가 (공구 마모)", "C2": "원인 ② OP-30 1대만 가동", "C3": "원인 ③ 검사 강화",
                 "FAILURE": "고장", "BASE": "기준 병목"}.get(t["cause_code"], t["cause_code"])
        return {**out, "status": "ok", "answer": f"지금 병목: {t['process_code']} — {cause}" + (f" (시작 {t['since_at'][11:16]})" if t["since_at"] else ""),
                "sources": [SRC(P, "DOC-07", "7")]}
    if "재공" in q0:
        w = live.twin()
        lim = w["wip_limits"]
        lines = [f"{c}: {n}개 (한도 {lim[c]['limit']})" for c, n in w["wip"].items()]
        return {**out, "status": "ok", "answer": "\n".join(lines) + f"\n온도 맞춤 선반 SOAK-01: {w['soak_qty']}개 (재공에 안 셈)",
                "sources": [SRC(P, "DOC-07", "7")]}
    if "공구" in q0:
        ts = [t for t in live.tools()["tools"] if not eq or t["equipment_id"] == eq]
        lines = [f"{t['tool_id']} 사용률 {t['usage_pct']}%{' ▲' if t['warn'] else ''} · 남은 부품 약 {t['left_parts']}개" for t in ts]
        return {**out, "status": "ok", "answer": "\n".join(lines), "sources": [SRC(P, "DOC-07", "9")]}
    if "재고" in q0:
        inv = live.inventory()["items"]
        low = [i for i in inv if i["low"]]
        txt = ("안전 재고보다 적은 품목: " + ", ".join(f"{i['item_name']} {i['stock_qty']}{i['unit']} (안전 {i['safety_stock']})" for i in low)) if low else "안전 재고보다 적은 품목 없음"
        return {**out, "status": "ok", "answer": txt, "sources": []}

    # 6) 사내 문서 검색
    hits = P.search(q0)
    if not hits:
        return {**out, "status": "문서에 없음", "answer": "사내 문서에서 찾지 못했어요. 낱말을 바꿔 다시 물어봐 주세요."}
    body = "\n\n".join(f"[{h['doc_name']} {h['doc_no']} {h['rev']} §{h['section']} {h['title']}]\n{h['snippet']}" for h in hits[:3])
    return {**out, "status": "ok", "answer": "사내 문서에서 찾은 곳이에요 (문서 내용 그대로):\n\n" + body,
            "sources": [{"doc_no": h["doc_no"], "doc_name": h["doc_name"], "rev": h["rev"], "section": h["section"]} for h in hits[:3]]}
