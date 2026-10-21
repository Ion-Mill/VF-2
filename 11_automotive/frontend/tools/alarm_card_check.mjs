// 알람 답 리치 카드 파서 시험 — 프레임워크 없이 Node 20으로 돈다 (이 화면 폴더에는 시험 도구가 없다).
//   실행: node 11_automotive/frontend/tools/alarm_card_check.mjs     (frontend 폴더에서는 node tools/alarm_card_check.mjs)
// src/shell/parseAlarmAnswer.ts(React 없는 순수 함수)를 typescript 패키지로 그 자리에서 변환해 불러온다 — 빌드·설치 없음.
// 고정 자료 = 실제 알람 답 5개 (비서가 만든 글: 11_automotive/assistant 의 answer() → chat_mapping.to_answer_text, 가상 사내 문서 기준).
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const file = fileURLToPath(new URL('../src/shell/parseAlarmAnswer.ts', import.meta.url));
const js = ts.transpileModule(readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const { parseAlarmAnswer, cardPlainText } = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));

const A2075 = "■ 알람 설명\n알람 2075 축 윤활유 저장소 비워짐(AXIS LUBRICATION RESERVOIR EMPTY): 윤활 압력이 정상보다 빨리 떨어졌다. 윤활유 탱크를 채운다. 막 채운 뒤에는 공기가 빠질 때까지 몇 번 더 뜰 수 있다. 심각도는 주의 [가상], 조치는 작업자 [가상]입니다.\n\n■ 점검 순서 (사내 문서)\n★1 (작업자) 윤활유 저장소 수위를 본다\n★2 (작업자) 보충: 전원 끄기 → 공기 주 밸브 닫기 → 공기·윤활 매니폴드의 압력 해제 밸브 링을 당겨 압력 빼기 → 저장소 분리(너무 꽉 끼면 자동차용 오일 필터 렌치) → 나사산 아래 1/2\" (13 mm)까지 채움 → 개스킷이 닿을 때까지 손으로 조인 뒤 3/4 바퀴 더\n★3 (작업자) [DIAGNOSTICS] → Maintenance 탭 → Lube 탭 → [F2]로 축 윤활 시험. 알람이 안 뜰 때까지 반복하고, 시험 사이에 최소 1분 기다린다\n★4 (작업자) 막 채웠다면 공기가 빠질 때까지 몇 주기 더 뜰 수 있다. 계속 뜨면 보전 담당자를 부른다\n5 (보전) 저장소 조립체의 체크밸브가 걸리지 않는지, O-링이 제자리인지 본다. 매니폴드와 압력 스위치 주변을 청소한다\n6 (보전) 매니폴드 누설 시험: 오일 라인을 모두 빼고 포트를 막은 뒤 윤활 주기 → 15초 전에 압력이 떨어지면 매니폴드 누설\n7 (보전) 라인 하나씩 시험해 누설 라인을 찾고, 해당 축의 매니폴드·트럭·볼너트 연결부를 청소해 누설을 본다\n8 (보전) 프라이밍(공기 빼기): 저장소를 채움 → 축 라인을 하나씩 빼고 솔레노이드를 수동 작동해 공기 제거 → 다시 꽂고 10초씩 5번, 15초 간격 수동 작동 → 윤활 주기로 재현 여부 확인\n\n이 알람은 최근 7일 5번, 30일 5번 났습니다 [가상 운영 데이터]\n\n주의: 근거 안내이며 실행 지시가 아닙니다.";   // 실제 답: 2075 알람 뭐야
const A992DOC = "■ 알람 설명\n알람 992 전류가 높은 증폭기(AMPLIFIER OVER CURRENT): 서보 앰프가 모터에 너무 큰 전류가 흐르는 것을 감지했다. 공구 파손·무거운 절삭·충돌이 원인일 수 있다. 바로 앞의 108·994 알람과 함께 뜨면 충돌을 먼저 의심한다. 심각도는 정지 [가상], 조치는 보전 담당자 [가상]입니다.\n\n■ 점검 순서 (사내 문서)\n★1 (작업자) 축을 움직이지 말고 알람 이력을 본다. 바로 앞에 108·994(과부하)가 있으면 충돌 신호\n★2 (작업자) 도어 밖에서 공구·고정구·공작물이 외함과 부딪혔는지 본다\n★3 (작업자) 외함·주축·공구·고정구에 손상이 있는지 본다 (손상 = 충돌 징후)\n★4 (작업자) 공구가 무뎌지거나 부러졌는지, 프로그램의 속도·이송을 확인하고 보전 담당자를 부른다\n5 (보전) 잠금·표지 후, 충돌 징후가 없으면 볼스크류와 리니어 가이드가 손으로 자유롭게 움직이거나 도는지 본다\n6 (보전) 충돌이 확인되면 볼스크류 커플링 정렬도 본다 (§2.5 점검 8)\n7 (보전) 서보 모터 케이블이 오염·끼임 없는지, 모터 쪽 커넥터에 절삭유 오염이 없는지 보고 아래 표대로 저항을 잰다\n8 (보전) 이송을 낮춰 MDI로 해당 축을 움직이는 시험을 한다. 어떤 이송에서도 알람이 뜨면 서보 앰프 문제\n\n■ 문서에서 더 찾은 줄\nOP-30 (VF2-01·02, 알람 15개) — 만드는 것: 원인 점검 작업지시서 AI비서 초안 (작업지시서 \"계기\" 칸 = 반복 알람 2단계). 심각도가 주의(예: 108, 2075)여도 만든다 · 바탕: §2 해당 절의 보전 담당자 줄(★ 아닌 줄) 과 아직 확인하지 않은 원인을 작업 순서로 정리. 잠금·표지가 필요한 줄은 DOC-05 §7 고정 서식이 붙는다 · 누가: 보전 담당자(MNT)가 초안을 고치고, 반장(SUP)이 승인 (보통 작업지시서 흐름과 같음) · 처리된 것으로 보는 때: 원인 점검 작업기록서 확정 → 자동 처리\n다른 공정 (OP-10·20·40·50) — 만드는 것: 작업지시서는 만들지 않는다 (DOC-02 §2 범위 그대로). 2단계 주의 알림 + 보전 담당자에게 원인 점검 요청 · 바탕: §3 해당 절의 간이 대응 (점검·원인 후보) · 누가: 보전 담당자(MNT)가 원인 점검을 하고 간이 작업기록에 남긴다 (\"한 일\" 칸에 \"원인 점검\"과 1단계 조치 계획을 적음) · 처리된 것으로 보는 때: 원인 점검 간이 작업기록 확정 → 자동 처리\n\n이 알람은 최근 7일 0번, 30일 0번 났습니다 [가상 운영 데이터]\n\n주의: 근거 안내이며 실행 지시가 아닙니다. 잠금·표지와 고전압 대기는 안전 작업 기준서 DOC-05 고정 서식을 따르고, 전기 측정·수리는 자격자/HFO 작업입니다. 현장 담당자 확인이 필요합니다.";   // 실제 답: 992 알람 점검 순서 알려줘
const A992OPS = "■ 알람 설명\n알람 992 전류가 높은 증폭기(AMPLIFIER OVER CURRENT): 서보 앰프가 모터에 너무 큰 전류가 흐르는 것을 감지했다. 공구 파손·무거운 절삭·충돌이 원인일 수 있다. 바로 앞의 108·994 알람과 함께 뜨면 충돌을 먼저 의심한다. 심각도는 정지 [가상], 조치는 보전 담당자 [가상]입니다.\n\n■ 점검 순서 (사내 문서)\n★1 (작업자) 축을 움직이지 말고 알람 이력을 본다. 바로 앞에 108·994(과부하)가 있으면 충돌 신호\n★2 (작업자) 도어 밖에서 공구·고정구·공작물이 외함과 부딪혔는지 본다\n★3 (작업자) 외함·주축·공구·고정구에 손상이 있는지 본다 (손상 = 충돌 징후)\n★4 (작업자) 공구가 무뎌지거나 부러졌는지, 프로그램의 속도·이송을 확인하고 보전 담당자를 부른다\n5 (보전) 잠금·표지 후, 충돌 징후가 없으면 볼스크류와 리니어 가이드가 손으로 자유롭게 움직이거나 도는지 본다\n6 (보전) 충돌이 확인되면 볼스크류 커플링 정렬도 본다 (§2.5 점검 8)\n7 (보전) 서보 모터 케이블이 오염·끼임 없는지, 모터 쪽 커넥터에 절삭유 오염이 없는지 보고 아래 표대로 저항을 잰다\n8 (보전) 이송을 낮춰 MDI로 해당 축을 움직이는 시험을 한다. 어떤 이송에서도 알람이 뜨면 서보 앰프 문제\n\n■ 운영 기록 [가상]\n2026-09-01 ~ 2026-09-30 알람 992 발생: 없음\n\n이 알람은 최근 7일 0번, 30일 0번 났습니다 [가상 운영 데이터]\n\n주의: 근거 안내이며 실행 지시가 아닙니다. 잠금·표지와 고전압 대기는 안전 작업 기준서 DOC-05 고정 서식을 따르고, 전기 측정·수리는 자격자/HFO 작업입니다. 현장 담당자 확인이 필요합니다.";   // 실제 답: VF2-01 992 알람 최근에 몇 번 났어?
const A230 = "■ 알람 설명\n알람 230 도어 열림(DOOR OPEN) 심각도는 조작 안내, 조치는 작업자입니다.\n\n■ 점검 순서 (사내 문서)\n★1 (작업자) 알람 번호·이름을 본다\n★2 (작업자) 아래 표의 \"볼 곳\"을 확인해 고친다\n★2-1 (작업자) 알람 230 — 볼 곳: 도어 · 고치는 법: 도어 장치에 고장이나 걸림이 없는지 보고 닫는다\n★3 (작업자) [RESET] 후 다시 시작한다. 같은 알람이 되풀이되면 반장에게 알린다.\n\n이 알람은 최근 7일 0번, 30일 0번 났습니다 [가상 운영 데이터]\n\n주의: 근거 안내이며 실행 지시가 아닙니다. 잠금·표지와 고전압 대기는 안전 작업 기준서 DOC-05 고정 서식을 따르고, 전기 측정·수리는 자격자/HFO 작업입니다. 현장 담당자 확인이 필요합니다.";   // 실제 답: 230 알람 뭐야
const PLAIN = "6.1 · ① 해당 설비의 §3 표를 연다 (차단 지점, 저장 에너지) ② 작업지시서에 적힌 차단 지점과 맞는지 본다 ③ 해당 작업자(OPR)와 반장에게 \"정비로 정지한다\"고 알린다 (5.9 \"문서화된 방법으로 알려야\") ④ 정지하기 전에 에너지의 크기, 형태, 위험 정도, 관리 방법을 알고 있어야 한다\n6.2 · ① 가공 중이면 사이클을 멈추고 주축·축·톱날이 완전히 멈춘 것을 눈으로 본다 ② 제어기 전원을 끈다 (Haas: [POWER OFF])\n6.3 · §3의 차단 지점을 순서대로 끈다: 주 차단기 OFF → 공압 주 밸브 닫음 → (해당되면) 공급 쪽 분전반 차단기 OFF. 제조사는 \"기계로 가는 모든 전원을 공급원에서\" 끄라고 한다\n6.4 · ① 차단 지점마다 내 자물쇠를 건다 ② 표지를 자물쇠에 묶는다 ③ 일하는 사람이 여러 명이면 §2.3 ④ 각각의 차단장치에 단다. 잠금장치는 \"안전\" 또는 \"오프(Off)\" 상태를 계속 유지시키는 수단이다\n6.5 · §3의 \"저장 에너지\" 칸대로: 고전압 대기(§4), 공압 잔압 빼기, 주축 헤드 받치기, 회전체 멈춤 확인, 세척조 식히기. 법 제92조 ④ \"미리 방출\". 남은 에너지는 방출·분리·제한하거나 안전한 상태로 두고, 다시 쌓일 수 있으면 작업이 끝날 때까지 계속 확인한다\n6.6 · ① 전기: 교류 검전기로 들어오는 선 전부를 확인 ② 공압: 압력계가 0인지 ③ 기동 버튼을 눌러 켜지지 않는지 본 뒤 다시 정지 위치로 둔다 ④ 작업을 시작하기 전에 승인작업자가 에너지가 차단되었는지 확인한다\n\n주의: 근거 안내이며 실행 지시가 아닙니다. 잠금·표지와 고전압 대기는 안전 작업 기준서 DOC-05 고정 서식을 따르고, 전기 측정·수리는 자격자/HFO 작업입니다. 현장 담당자 확인이 필요합니다.";   // 실제 답: 안전 작업 순서 알려줘
const CARRY2075 = "2075 알람 기준으로 답해요.\n\n■ 알람 설명\n알람 2075 축 윤활유 저장소 비워짐(AXIS LUBRICATION RESERVOIR EMPTY): 윤활 압력이 정상보다 빨리 떨어졌다. 윤활유 탱크를 채운다. 막 채운 뒤에는 공기가 빠질 때까지 몇 번 더 뜰 수 있다. 심각도는 주의 [가상], 조치는 작업자 [가상]입니다.\n\n■ 점검 순서 (사내 문서)\n★1 (작업자) 윤활유 저장소 수위를 본다\n★2 (작업자) 보충: 전원 끄기 → 공기 주 밸브 닫기 → 공기·윤활 매니폴드의 압력 해제 밸브 링을 당겨 압력 빼기 → 저장소 분리(너무 꽉 끼면 자동차용 오일 필터 렌치) → 나사산 아래 1/2\" (13 mm)까지 채움 → 개스킷이 닿을 때까지 손으로 조인 뒤 3/4 바퀴 더\n★3 (작업자) [DIAGNOSTICS] → Maintenance 탭 → Lube 탭 → [F2]로 축 윤활 시험. 알람이 안 뜰 때까지 반복하고, 시험 사이에 최소 1분 기다린다\n★4 (작업자) 막 채웠다면 공기가 빠질 때까지 몇 주기 더 뜰 수 있다. 계속 뜨면 보전 담당자를 부른다\n5 (보전) 저장소 조립체의 체크밸브가 걸리지 않는지, O-링이 제자리인지 본다. 매니폴드와 압력 스위치 주변을 청소한다\n6 (보전) 매니폴드 누설 시험: 오일 라인을 모두 빼고 포트를 막은 뒤 윤활 주기 → 15초 전에 압력이 떨어지면 매니폴드 누설\n7 (보전) 라인 하나씩 시험해 누설 라인을 찾고, 해당 축의 매니폴드·트럭·볼너트 연결부를 청소해 누설을 본다\n8 (보전) 프라이밍(공기 빼기): 저장소를 채움 → 축 라인을 하나씩 빼고 솔레노이드를 수동 작동해 공기 제거 → 다시 꽂고 10초씩 5번, 15초 간격 수동 작동 → 윤활 주기로 재현 여부 확인\n\n이 알람은 최근 7일 5번, 30일 5번 났습니다 [가상 운영 데이터]\n\n주의: 근거 안내이며 실행 지시가 아닙니다.";   // 실제 답: [2075 이어받기] 원인은?
const CAUSE2075 = "■ 알람 설명\n알람 2075 축 윤활유 저장소 비워짐(AXIS LUBRICATION RESERVOIR EMPTY): 윤활 압력이 정상보다 빨리 떨어졌다. 윤활유 탱크를 채운다. 막 채운 뒤에는 공기가 빠질 때까지 몇 번 더 뜰 수 있다. 심각도는 주의 [가상], 조치는 작업자 [가상]입니다.\n\n■ 가능한 원인 (사내 문서)\n윤활유 저장소가 비어 있음\n윤활 라인에 공기가 들어감 (빈 저장소가 가장 흔한 공기 유입 원인)\n체크밸브가 걸려 오일을 많이 씀\nHALO 매니폴드나 압력 센서 앞의 이물\n매니폴드·윤활 라인 누설\n월 1회 점검을 하지 않고 알람을 방치 → 라인에 공기 유입\n\n■ 점검 순서 (사내 문서)\n★1 (작업자) 윤활유 저장소 수위를 본다\n★2 (작업자) 보충: 전원 끄기 → 공기 주 밸브 닫기 → 공기·윤활 매니폴드의 압력 해제 밸브 링을 당겨 압력 빼기 → 저장소 분리(너무 꽉 끼면 자동차용 오일 필터 렌치) → 나사산 아래 1/2\" (13 mm)까지 채움 → 개스킷이 닿을 때까지 손으로 조인 뒤 3/4 바퀴 더\n★3 (작업자) [DIAGNOSTICS] → Maintenance 탭 → Lube 탭 → [F2]로 축 윤활 시험. 알람이 안 뜰 때까지 반복하고, 시험 사이에 최소 1분 기다린다\n★4 (작업자) 막 채웠다면 공기가 빠질 때까지 몇 주기 더 뜰 수 있다. 계속 뜨면 보전 담당자를 부른다\n5 (보전) 저장소 조립체의 체크밸브가 걸리지 않는지, O-링이 제자리인지 본다. 매니폴드와 압력 스위치 주변을 청소한다\n6 (보전) 매니폴드 누설 시험: 오일 라인을 모두 빼고 포트를 막은 뒤 윤활 주기 → 15초 전에 압력이 떨어지면 매니폴드 누설\n7 (보전) 라인 하나씩 시험해 누설 라인을 찾고, 해당 축의 매니폴드·트럭·볼너트 연결부를 청소해 누설을 본다\n8 (보전) 프라이밍(공기 빼기): 저장소를 채움 → 축 라인을 하나씩 빼고 솔레노이드를 수동 작동해 공기 제거 → 다시 꽂고 10초씩 5번, 15초 간격 수동 작동 → 윤활 주기로 재현 여부 확인\n\n이 알람은 최근 7일 5번, 30일 5번 났습니다 [가상 운영 데이터]\n\n주의: 근거 안내이며 실행 지시가 아닙니다.";   // 실제 답: 2075 알람 원인은?
const CAUSE_CARRY = "2075 알람 기준으로 답해요.\n\n■ 알람 설명\n알람 2075 축 윤활유 저장소 비워짐(AXIS LUBRICATION RESERVOIR EMPTY): 윤활 압력이 정상보다 빨리 떨어졌다. 윤활유 탱크를 채운다. 막 채운 뒤에는 공기가 빠질 때까지 몇 번 더 뜰 수 있다. 심각도는 주의 [가상], 조치는 작업자 [가상]입니다.\n\n■ 가능한 원인 (사내 문서)\n윤활유 저장소가 비어 있음\n윤활 라인에 공기가 들어감 (빈 저장소가 가장 흔한 공기 유입 원인)\n체크밸브가 걸려 오일을 많이 씀\nHALO 매니폴드나 압력 센서 앞의 이물\n매니폴드·윤활 라인 누설\n월 1회 점검을 하지 않고 알람을 방치 → 라인에 공기 유입\n\n■ 점검 순서 (사내 문서)\n★1 (작업자) 윤활유 저장소 수위를 본다\n★2 (작업자) 보충: 전원 끄기 → 공기 주 밸브 닫기 → 공기·윤활 매니폴드의 압력 해제 밸브 링을 당겨 압력 빼기 → 저장소 분리(너무 꽉 끼면 자동차용 오일 필터 렌치) → 나사산 아래 1/2\" (13 mm)까지 채움 → 개스킷이 닿을 때까지 손으로 조인 뒤 3/4 바퀴 더\n★3 (작업자) [DIAGNOSTICS] → Maintenance 탭 → Lube 탭 → [F2]로 축 윤활 시험. 알람이 안 뜰 때까지 반복하고, 시험 사이에 최소 1분 기다린다\n★4 (작업자) 막 채웠다면 공기가 빠질 때까지 몇 주기 더 뜰 수 있다. 계속 뜨면 보전 담당자를 부른다\n5 (보전) 저장소 조립체의 체크밸브가 걸리지 않는지, O-링이 제자리인지 본다. 매니폴드와 압력 스위치 주변을 청소한다\n6 (보전) 매니폴드 누설 시험: 오일 라인을 모두 빼고 포트를 막은 뒤 윤활 주기 → 15초 전에 압력이 떨어지면 매니폴드 누설\n7 (보전) 라인 하나씩 시험해 누설 라인을 찾고, 해당 축의 매니폴드·트럭·볼너트 연결부를 청소해 누설을 본다\n8 (보전) 프라이밍(공기 빼기): 저장소를 채움 → 축 라인을 하나씩 빼고 솔레노이드를 수동 작동해 공기 제거 → 다시 꽂고 10초씩 5번, 15초 간격 수동 작동 → 윤활 주기로 재현 여부 확인\n\n이 알람은 최근 7일 5번, 30일 5번 났습니다 [가상 운영 데이터]\n\n주의: 근거 안내이며 실행 지시가 아닙니다.";   // 실제 답: [2075 이어받기] 원인은?
const CAUSE_WSH = "■ 알람 설명\n알람 WSH-01 과열 정지(Overheat condition): 세척조가 과열돼 초음파가 멈췄다 (75 ℃에서 정지, 69 ℃로 내려가면 다시 가능). 세척액 수위를 확인한다. 심각도는 정지 [가상], 조치는 보전 담당자 [가상]입니다.\n\n■ 가능한 원인 (사내 문서)\n원인 후보: 과열 / 세척액 수위 낮음 [참고]\n\n■ 점검 순서 (사내 문서)\n★1 (작업자) 세척액 수위를 본다\n★2 (작업자) 식을 때까지 기다린다\n★3 (작업자) 보전 담당자를 부른다\n4 (보전) 과열 차단기가 있는 기종은 세척액이 식었고 수위가 맞는지 확인한 뒤 리셋 버튼을 누른다\n\n이 알람은 최근 7일 0번, 30일 0번 났습니다 [가상 운영 데이터]\n\n주의: 근거 안내이며 실행 지시가 아닙니다. 잠금·표지와 고전압 대기는 안전 작업 기준서 DOC-05 고정 서식을 따르고, 전기 측정·수리는 자격자/HFO 작업입니다. 현장 담당자 확인이 필요합니다.";   // 실제 답: WSH-01 알람 원인은?
const SOURCES = [{"doc_name": "알람 코드집", "doc_no": "DOC-02", "rev": "Rev.1 (2026-10-07)", "section": "4.11"}, {"doc_name": "고장 대응 매뉴얼", "doc_no": "DOC-03", "rev": "Rev.1 (2026-10-07)", "section": "2.11"}];

const STEPS992 = "■ 점검 순서 (사내 문서)\n★1 (작업자) 축을 움직이지 말고 알람 이력을 봐요. 바로 앞에 108·994(과부하)가 있으면 충돌 신호예요.\n★2 (작업자) 도어 밖에서 공구·고정구·공작물이 외함과 부딪혔는지 봐요.\n★3 (작업자) 외함·주축·공구·고정구에 손상이 있는지 봐요 (손상 = 충돌 징후).\n★4 (작업자) 공구가 무뎌지거나 부러졌는지, 프로그램의 속도·이송을 확인하고 보전 담당자를 불러요.\n5 (보전) 잠금·표지 후, 충돌 징후가 없으면 볼스크류와 리니어 가이드가 손으로 자유롭게 움직이거나 도는지 봐요.\n6 (보전) 충돌이 확인되면 볼스크류 커플링 정렬도 봐요 (§2.5 점검 8).\n7 (보전) 서보 모터 케이블이 오염·끼임 없는지, 모터 쪽 커넥터에 절삭유 오염이 없는지 보고 아래 표대로 저항을 재요.\n8 (보전) 이송을 낮춰 MDI로 해당 축을 움직이는 시험을 해요. 어떤 이송에서도 알람이 뜨면 서보 앰프 문제예요.\n\n주의: 근거 안내이며 실행 지시가 아닙니다. 잠금·표지와 고전압 대기는 안전 작업 기준서 DOC-05 고정 서식을 따르고, 전기 측정·수리는 자격자/HFO 작업입니다. 현장 담당자 확인이 필요합니다.";   // 실제 답: 992 뜨면 뭐부터 해? (질문대로 답하기 — 점검 순서만 남김, 2026-10-21 시연)
const CAUSE_ONLY2075 = "■ 가능한 원인 (사내 문서)\n윤활유 저장소가 비어 있음\n윤활 라인에 공기가 들어감 (빈 저장소가 가장 흔한 공기 유입 원인)\n체크밸브가 걸려 오일을 많이 씀\nHALO 매니폴드나 압력 센서 앞의 이물\n매니폴드·윤활 라인 누설\n월 1회 점검을 하지 않고 알람을 방치 → 라인에 공기 유입\n\n주의: 근거 안내이며 실행 지시가 아닙니다.";   // 실제 답: 2075 원인은? (원인만 남김, 2026-10-21 시연)

let opened = null;
const open = (d, s) => { opened = [d, s]; };
const parse = (a, src = SOURCES) => parseAlarmAnswer(a, src, open);
const words = (s) => s.match(/[\p{L}\p{N}]+/gu) ?? [];
const kinds = (c) => c.parts.map((p) => p.kind).join(',');
const steps = (c) => c.parts.filter((p) => p.kind === 'steps').flatMap((p) => p.steps);
/** 카드가 보이는 글자의 낱말 열 == 원래 글자의 낱말 열 */
const same = (a, c) => { const x = words(a), y = words(cardPlainText(c.parts)); return x.length === y.length && x.every((w, i) => w === y[i]); };
/** 비서가 "해요체"로 다시 쓴 글 흉내 (tests/test_card_rewrite.py의 soft와 같다): 문장 끝 "…다"를 "…어요"로 */
const soft = (s) => s.replace(/다(?=[.\s]|$)/g, '어요');

let fail = 0;
const t = (name, fn) => { try { fn(); console.log('통과  ' + name); } catch (e) { fail++; console.log('실패  ' + name + '\n      ' + String(e.message).split('\n').slice(0, 4).join('\n      ')); } };

// ---- 알람 답을 카드로 읽는다
t('알람 2075: 설명 → 점검 순서 → 운영 줄 → 주의 순서 그대로', () => { assert.equal(kinds(parse(A2075)), 'desc,steps,ops,caution'); });
t('점검 순서 8줄: 작업자 4 · 보전 4, 번호는 1~8', () => {
  const s = steps(parse(A2075));
  assert.deepEqual(s.map((x) => x.no), ['1', '2', '3', '4', '5', '6', '7', '8']);
  assert.equal(s.filter((x) => x.role === 'operator').length, 4);
  assert.equal(s.filter((x) => x.role === 'maintenance').length, 4);
  assert.equal(s[0].label, '작업자'); assert.equal(s[4].label, '보전');
});
t('운영 줄: 7일 5번 · 30일 5번 · 가상 운영 데이터', () => {
  const o = parse(A2075).parts.find((p) => p.kind === 'ops');
  assert.deepEqual([o.count7, o.count30, o.virtual], [5, 5, true]);
});
t('주의 상자: 제목 "주의", 본문은 "주의:" 뒤 글자 그대로', () => {
  const c = parse(A2075).parts.find((p) => p.kind === 'caution');
  assert.equal(c.title, '주의');
  assert.ok(c.paras[0].startsWith('근거 안내이며 실행 지시가 아닙니다.'));
  assert.ok(!c.paras.join('').includes('주의:'));
});
t('심각도·조치 문장의 "[가상]" 꼬리표가 설명 글에 남는다 (칩은 그리는 쪽이 만든다)', () => {
  const d = parse(A2075).parts.find((p) => p.kind === 'desc');
  assert.match(d.paras.join(' '), /심각도는 주의 \[가상\], 조치는 작업자 \[가상\]입니다\./);
});
t('"■ 문서에서 더 찾은 줄"은 소제목 덩어리로 순서 그대로 (설명에 이어 붙지 않는다)', () => {
  const c = parse(A992DOC);
  assert.equal(kinds(c), 'desc,steps,section,ops,caution');
  const s = c.parts.find((p) => p.kind === 'section');
  assert.equal(s.title, '문서에서 더 찾은 줄'); assert.equal(s.paras.length, 2);
  assert.ok(!c.parts[0].paras.join('').includes('OP-30'));
});
t('"■ 운영 기록 [가상]" 소제목에 [가상]이 그대로 있다', () => {
  const s = parse(A992OPS).parts.find((p) => p.kind === 'section');
  assert.equal(s.title, '운영 기록 [가상]'); assert.deepEqual(s.paras, ['2026-09-01 ~ 2026-09-30 알람 992 발생: 없음']);
});
t('점검 순서 번호 "★2-1"도 한 줄로 읽는다 (줄 수 4 = 원문 4)', () => {
  const s = steps(parse(A230));
  assert.deepEqual(s.map((x) => x.no), ['1', '2', '2-1', '3']);
  assert.match(s[2].text, /^알람 230 — 볼 곳: 도어/);
});

// ---- 글자가 하나도 안 사라진다 (실제 답 4개 + 변형)
for (const [n, a] of [['2075', A2075], ['992 문서 줄', A992DOC], ['992 운영 기록', A992OPS], ['230', A230]]) {
  t(`낱말 열이 원래와 같다: ${n}`, () => { assert.ok(same(a, parse(a))); });
  t(`해요체 흉내로 바뀐 글도 카드가 되고 낱말 열이 같다: ${n}`, () => { const b = soft(a); const c = parse(b); assert.ok(c, '카드가 되어야 한다'); assert.ok(same(b, c)); });
}
t('"[가상]"이 원래 글에 있는 만큼 카드 글자에도 있다 (꼬리표가 지워지지 않는다)', () => {
  for (const a of [A2075, A992DOC, A992OPS, A230]) {
    const n = words(a).filter((w) => w === '가상').length;
    assert.equal(words(cardPlainText(parse(a).parts)).filter((w) => w === '가상').length, n);
    assert.ok(n >= 3 || a === A230, '실제 답에 가상 꼬리표가 있어야 시험이 의미가 있다');
  }
});
t('"■" 기호는 카드 글자에 없다', () => { for (const a of [A2075, A992DOC, A992OPS]) assert.ok(!cardPlainText(parse(a).parts).includes('■')); });

// ---- 알람 답이 아니거나 모르는 모양이면 평문(null)
t('알람 답이 아닌 글(안전 작업 순서)은 null', () => { assert.equal(parse(PLAIN), null); });
t('빈 글·공백·undefined·숫자는 null (예외 없음)', () => { for (const x of ['', '   \n\n ', undefined, null, 5]) assert.equal(parse(x), null); });
t('"■ 알람 설명"이 아예 없는 글은 앞에 안내 줄이 있어도 null', () => { assert.equal(parse('2075 알람 기준으로 답해요.\n\n' + PLAIN), null); });
t('"■ 알람 설명" 앞에 소제목 없는 덩어리가 세 개 이상 있으면 null (모르는 모양)', () => { assert.equal(parse('가\n\n나\n\n다\n\n' + A2075), null); });
t('"■ 알람 설명" 앞 덩어리 안에 "■" 줄이 있으면 null', () => { assert.equal(parse('안내\n■ 끼어든 제목\n\n' + A2075), null); });

// ---- 직전 알람 이어받기: 비서가 맨 앞에 "N 알람 기준으로 답해요." 한 줄을 붙인다 (answer.py _with_ctx_note)
t('이어받기 답(실제 글): 안내 줄은 메모로 맨 앞에 남고 나머지는 카드 그대로', () => {
  const c = parse(CARRY2075);
  assert.ok(c, '카드가 되어야 한다');
  assert.equal(kinds(c), 'note,desc,steps,ops,caution');
  assert.deepEqual(c.parts[0].paras, ['2075 알람 기준으로 답해요.']);
  assert.equal(steps(c).length, 8);
  assert.ok(same(CARRY2075, c));
});
t('이어받기 답: "가상" 꼬리표·점검 순서 줄 수가 원문과 같다', () => {
  const c = parse(CARRY2075);
  assert.equal(words(cardPlainText(c.parts)).filter((w) => w === '가상').length, words(CARRY2075).filter((w) => w === '가상').length);
  assert.equal(steps(c).length, (CARRY2075.match(/^★?\d+(?:-\d+)?\s*\(/gm) ?? []).length);
});
t('이어받기 안내 줄 + 해요체 흉내 + ★2-1 번호도 카드가 된다', () => {
  const b = '230 알람 기준으로 답해요.\n\n' + soft(A230), c = parse(b);
  assert.ok(c); assert.ok(kinds(c).startsWith('note,desc,steps')); assert.deepEqual(c.parts[0].paras, ['230 알람 기준으로 답해요.']);   // (soft가 "…났습니다"도 바꿔 운영 줄은 문단이 된다 — 글자는 그대로)
  assert.deepEqual(steps(c).map((x) => x.no), ['1', '2', '2-1', '3']); assert.ok(same(b, c));
});
t('안내 덩어리가 둘이어도 모두 메모로 맨 앞에 남는다', () => {
  const b = '2075 알람 기준으로 답해요.\n\n짧게 줄인 글이에요.\n\n' + A2075, c = parse(b);
  assert.ok(c); assert.equal(kinds(c), 'note,desc,steps,ops,caution'); assert.deepEqual(c.parts[0].paras, ['2075 알람 기준으로 답해요.', '짧게 줄인 글이에요.']); assert.ok(same(b, c));
});
t('"■ 알람 설명 알람 992 …"처럼 소제목 줄에 글이 이어지면 null', () => { assert.equal(parse('■ 알람 설명 알람 992 설명\n\n주의: x'), null); });
t('점검 순서 줄 하나가 모르는 꼴이면 카드를 포기한다 (줄을 조용히 버리지 않는다)', () => {
  assert.equal(parse(A2075.replace('★2 (작업자)', '★2 작업자')), null);
  assert.equal(parse(A2075.replace('★1 (작업자) 윤활유 저장소 수위를 본다', '윤활유 저장소 수위를 본다')), null);
});
t('점검 순서 소제목만 있고 줄이 없으면 null', () => { assert.equal(parse('■ 알람 설명\n설명\n\n■ 점검 순서 (사내 문서)'), null); });
t('덩어리 가운데 또 "■" 줄이 있으면(모르는 모양) null', () => { assert.equal(parse('■ 알람 설명\n설명\n■ 끼어든 제목\n더 많은 글'), null); });

// ---- 모르는 덩어리도 지우지 않는다
t('소제목 없는 덩어리(고정 서식 같은 글)가 끝에 붙어도 문단으로 남는다', () => {
  const extra = '출처: DOC-05 안전 작업 기준서 Rev.3 (2026-10-18) 고정 서식\n① 차단 지점을 끈다\n② 자물쇠를 건다';
  const b = A2075 + '\n\n' + extra, c = parse(b);
  assert.ok(c); assert.equal(kinds(c), 'desc,steps,ops,caution,note');
  assert.deepEqual(c.parts[4].paras, extra.split('\n'));
  assert.ok(same(b, c));
});
t('운영 줄이 모르는 꼴(30일 없음)이면 운영 상자가 아니라 문단으로 남는다', () => {
  const b = '■ 알람 설명\n설명이에요.\n\n이 알람은 최근 7일 3번 났습니다\n\n주의: 근거 안내입니다.', c = parse(b);
  assert.ok(c && !c.parts.some((p) => p.kind === 'ops')); assert.ok(same(b, c));
  assert.deepEqual(c.parts[0].paras, ['설명이에요.', '이 알람은 최근 7일 3번 났습니다']);
});
t('주의가 여러 줄이어도 줄이 다 남는다', () => {
  const b = '■ 알람 설명\n설명\n\n주의: 첫째 줄\n둘째 줄', c = parse(b);
  assert.deepEqual(c.parts[1].paras, ['첫째 줄', '둘째 줄']); assert.ok(same(b, c));
});
t('알람 설명만 있고 점검 순서가 없는 답도 카드가 된다', () => { const c = parse('■ 알람 설명\n알람 230 설명입니다.'); assert.equal(kinds(c), 'desc'); });
t('줄 끝 공백·\\r\\n 줄바꿈·여러 빈 줄도 같은 결과다', () => {
  const crlf = A2075.replace(/\n/g, '\r\n').replace(/\r\n\r\n/g, '\r\n  \r\n\r\n');
  const a = parse(A2075), b = parse(crlf);
  assert.ok(b); assert.equal(JSON.stringify(a.parts), JSON.stringify(b.parts));
});

// ---- 알람 "가능한 원인": 원인을 물으면 비서가 설명 뒤에 소제목 "가능한 원인 (사내 문서)" 덩어리(DOC-03 원인 표 원문)를 붙인다 — 화면 코드는 그대로, 소제목 덩어리로 읽힌다
t('원인 질문 답(실제 글): 설명 → 가능한 원인 → 점검 순서 순서, 원인 6줄이 그대로', () => {
  const c = parse(CAUSE2075);
  assert.ok(c); assert.equal(kinds(c), 'desc,section,steps,ops,caution');
  const s = c.parts[1];
  assert.equal(s.title, '가능한 원인 (사내 문서)'); assert.equal(s.paras.length, 6);
  assert.equal(s.paras[0], '윤활유 저장소가 비어 있음'); assert.equal(s.paras[5], '월 1회 점검을 하지 않고 알람을 방치 → 라인에 공기 유입');
  assert.ok(same(CAUSE2075, c));
});
t('원인 질문 + 직전 알람 이어받기(실제 글): 안내 줄 → 설명 → 가능한 원인 → 점검 순서', () => {
  const c = parse(CAUSE_CARRY);
  assert.ok(c); assert.equal(kinds(c), 'note,desc,section,steps,ops,caution');
  assert.deepEqual(c.parts[0].paras, ['2075 알람 기준으로 답해요.']); assert.equal(c.parts[2].title, '가능한 원인 (사내 문서)'); assert.ok(same(CAUSE_CARRY, c));
});
t('다른 공정(§3) 원인 후보 한 줄도 [가상]·[참고] 꼬리표가 그대로 남는다', () => {
  const b = CAUSE_WSH; const c = parse(b);
  assert.ok(c); assert.ok(c.parts.some((p) => p.kind === 'section' && p.title === '가능한 원인 (사내 문서)' && p.paras[0].startsWith('원인 후보:') && p.paras[0].endsWith('[참고]')));
  assert.equal(words(cardPlainText(c.parts)).filter((w) => w === '참고').length, words(b).filter((w) => w === '참고').length);
});

// ---- 출처 (화면은 밑줄 버튼. 여기는 이름·번호·개정·절과 클릭만 본다)
t('출처 알약: 이름·문서 번호·개정·절을 그대로, 누르면 openSource(문서 번호, 절)', () => {
  const c = parse(A2075);
  assert.equal(c.sources.length, 2);
  assert.deepEqual([c.sources[0].label, c.sources[0].docNo, c.sources[0].rev, c.sources[0].section], ['알람 코드집', 'DOC-02', 'Rev.1 (2026-10-07)', '4.11']);
  opened = null; c.sources[1].onClick(); assert.deepEqual(opened, ['DOC-03', '2.11']);
});
t('출처가 비어 있거나 없어도 된다', () => { assert.deepEqual(parse(A2075, []).sources, []); assert.deepEqual(parseAlarmAnswer(A2075, undefined, open).sources, []); });

// ---- 속도 (말풍선 12개가 글자 입력마다 다시 그려진다)
t('알람 답 하나 읽는 데 1ms 안팎 (1000번 합쳐 1초 이내)', () => {
  const t0 = performance.now(); for (let i = 0; i < 1000; i++) parse(i % 2 ? A992DOC : A2075);
  const ms = performance.now() - t0; assert.ok(ms < 1000, `${ms.toFixed(0)}ms`);
});

// ---- 묻는 칸만 남긴 알람 답도 카드 (2026-10-21): 첫 덩어리가 "점검 순서"·"가능한 원인"이어도 카드로 읽는다
t('점검 순서만 남긴 답(992 뭐부터)도 카드: 점검 순서 8줄(작업자 4·보전 4) + 주의, 낱말 열이 원래와 같다', () => {
  const c = parse(STEPS992); assert.ok(c, '카드가 아님');
  assert.equal(kinds(c), 'steps,caution');
  const st = steps(c); assert.equal(st.length, 8);
  assert.equal(st.filter((x) => x.role === 'operator').length, 4); assert.equal(st.filter((x) => x.role === 'maintenance').length, 4);
  assert.deepEqual(words(cardPlainText(c.parts)), words(STEPS992));
});
t('원인만 남긴 답(2075 원인은?)도 카드: 가능한 원인 6줄 + 주의, 글자는 원문 그대로', () => {
  const c = parse(CAUSE_ONLY2075); assert.ok(c, '카드가 아님');
  assert.equal(kinds(c), 'section,caution');
  assert.equal(c.parts[0].title, '가능한 원인 (사내 문서)'); assert.equal(c.parts[0].paras.length, 6);
  assert.deepEqual(words(cardPlainText(c.parts)), words(CAUSE_ONLY2075));
});
t('점검 순서로 시작해도 알아볼 수 없는 줄이 하나라도 있으면 카드를 포기하고, 알람 전용이 아닌 소제목으로 시작하면 null', () => {
  assert.equal(parse(STEPS992.replace('★2 (작업자) 도어 밖에서', '그냥 문장 도어 밖에서')), null);
  assert.equal(parse('■ 90%의 뜻\n1. T05의 90%는 공구 수명 사용률이라, 남은 수명이 10%라는 뜻이에요.\n\n주의: 근거 안내이며 실행 지시가 아닙니다.'), null);
});

console.log(fail ? `\n실패 ${fail}개` : '\n모두 통과');
process.exit(fail ? 1 : 0);
