// 자동 생성 파일 — tools/build_data.py 로 다시 만든다. 직접 고치지 않는다.
export const GENERATED = {
 "users": [
  {
   "id": "U01",
   "name": "작업자 주간 1",
   "role": "OPR",
   "shift": "DAY",
   "procs": [
    "OP-10",
    "OP-20"
   ]
  },
  {
   "id": "U02",
   "name": "작업자 주간 2",
   "role": "OPR",
   "shift": "DAY",
   "procs": [
    "OP-30"
   ]
  },
  {
   "id": "U03",
   "name": "작업자 주간 3",
   "role": "OPR",
   "shift": "DAY",
   "procs": [
    "OP-50",
    "OP-40"
   ]
  },
  {
   "id": "U04",
   "name": "작업자 야간 1",
   "role": "OPR",
   "shift": "NIGHT",
   "procs": [
    "OP-10",
    "OP-20"
   ]
  },
  {
   "id": "U05",
   "name": "작업자 야간 2",
   "role": "OPR",
   "shift": "NIGHT",
   "procs": [
    "OP-30"
   ]
  },
  {
   "id": "U06",
   "name": "작업자 야간 3",
   "role": "OPR",
   "shift": "NIGHT",
   "procs": [
    "OP-50",
    "OP-40"
   ]
  },
  {
   "id": "U07",
   "name": "보전 담당 1",
   "role": "MNT",
   "shift": "DAY",
   "procs": []
  },
  {
   "id": "U08",
   "name": "보전 담당 2",
   "role": "MNT",
   "shift": "DAY",
   "procs": []
  },
  {
   "id": "U09",
   "name": "보전 담당 3",
   "role": "MNT",
   "shift": "NIGHT",
   "procs": []
  },
  {
   "id": "U10",
   "name": "반장 주간",
   "role": "SUP",
   "shift": "DAY",
   "procs": []
  },
  {
   "id": "U11",
   "name": "반장 야간",
   "role": "SUP",
   "shift": "NIGHT",
   "procs": []
  },
  {
   "id": "U12",
   "name": "공장 관리자",
   "role": "MGR",
   "shift": "DAY",
   "procs": []
  }
 ],
 "alarms": {
  "992": {
   "code": "992",
   "process": "OP-30",
   "nameKo": "전류가 높은 증폭기(AMPLIFIER OVER CURRENT)",
   "nameEn": "AMPLIFIER OVER CURRENT",
   "easy": "서보 앰프가 모터에 너무 큰 전류가 흐르는 것을 감지했다. 공구 파손·무거운 절삭·충돌이 원인일 수 있다. 바로 앞의 108·994 알람과 함께 뜨면 충돌을 먼저 의심한다",
   "severity": "STOP",
   "responder": "MNT",
   "note": "",
   "lockout": "FULL",
   "chain": "108 → 994 → 992 (과부하 뒤 과전류는 충돌 신호)",
   "doc02": "DOC-02 §4.1",
   "doc03": [
    "DOC-03 §2.1"
   ],
   "steps": [
    "축을 움직이지 말고 알람 이력을 본다. 바로 앞에 108·994(과부하)가 있으면 충돌 신호",
    "도어 밖에서 공구·고정구·공작물이 외함과 부딪혔는지 본다",
    "외함·주축·공구·고정구에 손상이 있는지 본다 (손상 = 충돌 징후)",
    "공구가 무뎌지거나 부러졌는지, 프로그램의 속도·이송을 확인하고 보전 담당자를 부른다"
   ],
   "symptom": "서보 앰프가 모터에 너무 큰 전류가 흐르는 것을 감지",
   "maint": [
    "잠금·표지 후, 충돌 징후가 없으면 볼스크류와 리니어 가이드가 손으로 자유롭게 움직이거나 도는지 본다",
    "충돌이 확인되면 볼스크류 커플링 정렬도 본다 (§2.5 점검 8)",
    "서보 모터 케이블이 오염·끼임 없는지, 모터 쪽 커넥터에 절삭유 오염이 없는지 보고 아래 표대로 저항을 잰다",
    "이송을 낮춰 MDI로 해당 축을 움직이는 시험을 한다. 어떤 이송에서도 알람이 뜨면 서보 앰프 문제"
   ],
   "actions": [
    "막힘 제거",
    "공구 교체·이송 낮춤",
    "불량 케이블·모터 교체",
    "앰프 교체는 부품 교체 전에 앰프 점검 보고서 체크리스트(ID0003)를 쓴다"
   ]
  },
  "994": {
   "code": "994",
   "process": "OP-30",
   "nameKo": "증폭기 과부하",
   "nameEn": "AMPLIFIER OVERLOAD",
   "easy": "서보 앰프에 높은 부하가 오래 걸렸다. 속도·이송이 공구·재료에 맞는지, 공구가 무뎌지거나 부러졌는지 본다",
   "severity": "STOP",
   "responder": "MNT",
   "note": "",
   "lockout": "FULL",
   "chain": "",
   "doc02": "DOC-02 §4.2",
   "doc03": [
    "DOC-03 §2.2"
   ],
   "steps": [
    "알람 이력을 본다. 994 뒤에 992가 이어지면 충돌 신호 → §2.1",
    "공구가 무뎌지거나 부서졌는지, 용도에 맞는 공구인지 본다",
    "프로그램의 속도·이송이 재료와 공구에 맞는지 확인하고 보전 담당자를 부른다"
   ],
   "symptom": "서보 앰프에 높은 부하가 오래 걸렸다",
   "maint": [
    "막힘 점검은 §2.1 점검 2~5와 같다"
   ],
   "actions": [
    "속도를 바꾸고 공구 손상을 확인한다",
    "막힘을 없앤다."
   ]
  },
  "991": {
   "code": "991",
   "process": "OP-30",
   "nameKo": "온도가 초과한 증폭기",
   "nameEn": "AMPLIFIER OVER TEMPERATURE",
   "easy": "서보 앰프 온도가 한계를 넘었다. 축에 높은 부하가 오래 걸린 것이 원인일 수 있다. 앰프가 식을 때까지 기다린 뒤 부하를 줄인다",
   "severity": "STOP",
   "responder": "MNT",
   "note": "",
   "lockout": "FULL",
   "chain": "",
   "doc02": "DOC-02 §4.3",
   "doc03": [
    "DOC-03 §2.3"
   ],
   "steps": [
    "가공을 멈춘 채 앰프가 식을 시간을 준다 (기다리는 시간은 원문에 없음)",
    "앞의 축 알람으로 어느 축인지 확인하고, 993이 함께 떴는지 본다 (함께 떴으면 §2.4)",
    "프로그램을 조정해 축 부하를 줄일 수 있는지 반장·보전 담당자와 확인한다"
   ],
   "symptom": "서보 앰프 온도가 한계를 넘었다",
   "maint": [
    "서보 앰프 냉각 팬이 제대로 도는지 본다",
    "팬이 안 돌면 팬 케이블을 분리하고 리드 사이 전압을 잰다. 정상 120 VAC. 전압이 정상이면 팬 불량"
   ],
   "actions": [
    "식힌 뒤 모든 알람을 지운다",
    "축 부하를 줄이게 프로그램 조정",
    "팬 불량이면 팬 교체."
   ]
  },
  "993": {
   "code": "993",
   "process": "OP-30",
   "nameKo": "단락",
   "nameEn": "AMPLIFIER SHORT CIRCUIT",
   "easy": "서보 앰프 쪽에서 단락이 감지됐다. 앞의 축 알람이 어느 축인지 알려 준다. 모터 케이블·커넥터를 점검해야 하므로 잠금·표지가 필요하다",
   "severity": "STOP",
   "responder": "MNT",
   "note": "",
   "lockout": "FULL",
   "chain": "",
   "doc02": "DOC-02 §4.4",
   "doc03": [
    "DOC-03 §2.4"
   ],
   "steps": [
    "앞의 축 알람으로 축을 확인하고, 다시 돌리지 않고 보전 담당자를 부른다",
    "잠금·표지, 고전압 대기, AC 전압 검출기로 전원 차단 확인",
    "케이블의 오염·손상·굳음, 모터 쪽 커넥터와 앰프 쪽 단자의 헐거움·오염을 본다 (앰프 쪽 케이블은 살살 당겨 본다)"
   ],
   "symptom": "단락이 감지됐다",
   "maint": [
    "모든 단자 연결이 단단히 조여 있는지 본다",
    "케이블·모터 저항을 잰다 (§2.1의 표)",
    "부위 구분 시험: 모터에서 파워 케이블 분리 → [RESET] → 조그. 103이면 모터 불량, 993이면 케이블 또는 앰프 → 모터·앰프 양쪽에서 분리 → [RESET] → 조그. 993이면 앰프 불량, 103이면 케이블 불량",
    "앰프 단락 점검: 전원 끔 → 해당 축 모터 케이블을 앰프에서 분리 → 멀티미터 Ω(가능하면 MΩ) → 접지 나사와 RED·WHT·BLK·HV(+)·HV(-) 단자 사이가 모두 O.L이어야 정상. HV(-)와 WHT·BLK, HV(+)와 RED·WHT·BLK 사이는 MΩ 범위여야 하고 매우 낮으면 앰프 손상"
   ],
   "actions": [
    "손상 케이블 교체",
    "모터 교체 (절삭유 침투 시 VMC용 개선 서보 케이블이 있음, 서비스 알림 SA0018)",
    "앰프에서 단락이 나오면 새 앰프를 달기 전에 케이블과 모터의 단락도 확인한다"
   ]
  },
  "103": {
   "code": "103",
   "process": "OP-30",
   "nameKo": "축 서보 오류가 너무 큼",
   "nameEn": "AXIS SERVO ERROR TOO LARGE",
   "easy": "축이 명령한 위치로 가지 못하고 오차가 너무 커졌다. 칩 끼임, 프로그램의 속도·이송, 무뎌진 공구, 충돌을 확인한다",
   "severity": "STOP",
   "responder": "MNT",
   "note": "",
   "lockout": "FULL",
   "chain": "",
   "doc02": "DOC-02 §4.5",
   "doc03": [
    "DOC-03 §2.5"
   ],
   "steps": [
    "원점 복귀 중이었는지, 충돌 흔적(§2.1 점검 2~3)이 있는지 본다",
    "기계 안의 칩, 공구·공구 홀더의 칩, 무뎌진 공구를 본다",
    "프로그램 오류와 속도·이송을 확인하고 보전 담당자를 부른다"
   ],
   "symptom": "축이 명령된 위치로 가지 못해 오차가 너무 커졌다",
   "maint": [
    "원점 복귀 중이었으면 홈 스위치 센서 위에 금속 칩이 없는지 본다",
    "잠금·표지 후 볼스크류 표면에 얇은 기름막이 있는지 본다. 없으면 윤활 계통의 누설·막힘을 찾는다 (한 축의 누설이 다른 축의 윤활 부족을 만든다)",
    "볼너트를 손으로 돌려 걸림·저항을 보고, 볼스크류를 손으로 돌려 지지 베어링을 본다",
    "파워 케이블을 점검한다 (§2.1의 표)",
    "케이블에 문제가 없을 때만 커플링 정렬을 본다",
    "모터 브레이크: I/O 기판 P3·P4·P5 커넥터 다시 꽂기 → 빨강·검정 선 전압: [EMERGENCY STOP] 때 0, [RESET] 뒤 20~30 VDC → 브레이크·파워 커넥터 오염 확인",
    "노이즈: 접지선 규격과 제어반까지의 배선, 다른 설비와 전원 공유 여부, 엔코더·접지·고전압 단자 체결, 엔코더 케이블과 X·Y·Z 모터 파워 케이블의 페라이트 필터(P/N 64-1252), 엔코더 케이블을 고전력 케이블과 떼어 배선"
   ],
   "actions": [
    "칩 제거·프로그램 수정",
    "윤활 계통 수리(§2.10·§2.11)",
    "볼스크류·볼너트·베어링 교체",
    "커플링 재정렬 — 모터를 볼스크류에서 떼면 그리드 오프셋과 공작물 오프셋(G54 등)을 다시 설정해야 한다"
   ]
  },
  "108": {
   "code": "108",
   "process": "OP-30",
   "nameKo": "축 서보 과부하",
   "nameEn": "AXIS SERVO OVERLOAD",
   "easy": "축 모터 부하가 몇 초~몇 분 동안 100%를 넘었다. 이송·속도를 낮추고 공구를 확인한다. 108 뒤에 994·992가 이어지면 충돌 신호",
   "severity": "WARN",
   "responder": "OPR",
   "note": "작업자 (반복되면 보전 담당자)",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §4.6",
   "doc03": [
    "DOC-03 §2.6"
   ],
   "steps": [
    "알람 이력을 본다. 108 뒤에 994·992가 이어지면 충돌 신호 → 정지 등급처럼 §2.1로 간다",
    "공구가 무뎌지거나 부서졌는지 보고, 그렇다면 새 공구·새 인서트로 바꾼다",
    "이송·속도를 조정해 축 부하를 줄인 뒤 다시 돌린다"
   ],
   "symptom": "축 모터 부하가 몇 초~몇 분 동안 100%를 넘었다",
   "maint": [
    "반복되면 볼스크류 정렬 확인: 축을 전체 행정으로 조그하며 서보 부하가 일정한지 본다. 일정하지 않으면 원문 정렬 절차를 따른다"
   ],
   "actions": [
    "공구 교체, 이송·속도 조정",
    "반복 시 볼스크류 정렬."
   ]
  },
  "966": {
   "code": "966",
   "process": "OP-30",
   "nameKo": "과도한 공구 불균형",
   "nameEn": "EXCESSIVE TOOL IMBALANCE",
   "easy": "진동 센서가 큰 진동을 감지해 모든 축이 멈췄다. 공구가 휘거나 손상됐는지 확인한다. 손상되거나 균형이 맞지 않는 공구는 쓰지 않는다",
   "severity": "STOP",
   "responder": "MNT",
   "note": "",
   "lockout": "FULL",
   "chain": "",
   "doc02": "DOC-02 §4.7",
   "doc03": [
    "DOC-03 §2.7"
   ],
   "steps": [
    "공구가 구부러지거나 손상됐는지 본다. 손상되거나 균형이 맞지 않는 공구는 절대 쓰지 않는다",
    "공구 길이를 본다. 가능한 한 짧은 공구를 쓰고, 홀더 밖으로 나온 길이는 공구 지름의 3배를 넘지 않게 한다",
    "고정구가 공작물을 잘 받치는지 보고 보전 담당자를 부른다"
   ],
   "symptom": "메인 프로세서에 내장된 진동 센서가 큰 진동을 감지해 모든 기계 운동이 멈췄다",
   "maint": [
    "공구를 홀더에 꽂은 채로 균형을 맞춘다. 맞출 수 없으면 균형이 맞는 조립체로 바꾼다",
    "잠금·표지 후 공구에 다이얼 인디케이터를 대고 주축을 손으로 돌려 런아웃을 잰다. 0.0003\" (0.0076 mm)를 넘으면 안 된다",
    "드로바 힘 게이지로 클램프 힘을 잰다 (원문 기준표 참조)",
    "구동 벨트(해짐·늘어남·끊김·이 빠짐)와 엔코더 벨트·풀리(세트 스크류 조임)를 본다",
    "메인 프로세서 기판 스탠드오프 볼트를 조이고, 제어반 장착 볼트를 풀었다 가볍게 조인 뒤 규정 토크로 조인다",
    "위에서 원인이 없으면 진동 분석(베어링)과 주축 균형을 HFO에 맡긴다"
   ],
   "actions": [
    "공구 교체·균형 맞춤·짧은 공구",
    "고정 보강, 절삭 부하·프로그램 조정",
    "벨트 교체",
    "볼트 조임",
    "주축 수리는 HFO"
   ]
  },
  "174": {
   "code": "174",
   "process": "OP-30",
   "nameKo": "공구 부하가 초과됨",
   "nameEn": "TOOL LOAD EXCEEDED",
   "easy": "이송 중 공구 부하가 사용자가 정한 한계를 넘었다. 고급 공구 관리(ATM)의 부하 한계 설정, 공구 마모, 프로그램 속도·이송을 확인한다",
   "severity": "WARN",
   "responder": "OPR",
   "note": "",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §4.8",
   "doc03": [
    "DOC-03 §2.8"
   ],
   "steps": [
    "고급 공구 관리(ATM) 탭(현재 명령 아래)에서 공구 부하 한계가 맞게 설정됐는지 본다",
    "공구 마모를 보고 필요하면 바꾼다",
    "프로그램 오류와 속도·이송을 본다. 이송은 더 보수적으로 조정한다",
    "필요하면 주축 공구의 부하 한도를 리셋하고, 알람을 리셋한 뒤 프로그램을 다시 시작한다"
   ],
   "symptom": "이송 중 공구 부하가 사용자가 정한 공구 부하 한계를 넘었다",
   "maint": [
    "표면 거칠기 문제가 함께 있으면 주축 점검 보고서의 다른 항목을 모두 한 뒤에만 주축 처짐 시험(예압 확인)을 한다"
   ],
   "actions": [
    "한계 조정, 공구 교체, 이송 조정"
   ]
  },
  "254": {
   "code": "254",
   "process": "OP-30",
   "nameKo": "스핀들 모터 과열",
   "nameEn": "SPINDLE MOTOR OVERHEAT",
   "easy": "주축 모터가 과열됐다. 100%를 넘는 부하로 오래 돌렸거나, 고속에서 짧게 자주 켜고 끈 것이 원인일 수 있다. 식힌 뒤 부하를 낮춘다",
   "severity": "STOP",
   "responder": "MNT",
   "note": "",
   "lockout": "FULL",
   "chain": "",
   "doc02": "DOC-02 §4.9",
   "doc03": [
    "DOC-03 §2.9"
   ],
   "steps": [
    "주축을 멈추고 식힌다 (기다리는 시간은 원문에 없음)",
    "무뎌지거나 손상된 공구를 본다",
    "프로그램의 평균 부하·부하 주기를 낮출 수 있는지(이송 낮춤, 회전수 조정) 반장·보전 담당자와 확인한다"
   ],
   "symptom": "주축 모터가 과열됐다",
   "maint": [
    "주축을 돌릴 때 주축 외함 위쪽으로 공기가 나가는지 본다",
    "MDI에서 `S50 M03;` 실행 → I/O 기판 P32의 검정·빨강 선 전압 120 VAC 확인. 없으면 I/O 기판 불량",
    "I/O 기판 P39 연결 케이블에 페라이트 필터(P/N 64-1252)가 있는지 본다. 없으면 단다. 온도 값은 DIAGNOSTIC > I/O 탭 아날로그 입력 #9"
   ],
   "actions": [
    "프로그램 조정, 공구 교체",
    "팬·케이블 수리",
    "페라이트 필터 설치."
   ]
  },
  "2073": {
   "code": "2073",
   "process": "OP-30",
   "nameKo": "축 윤활 압력이 감지 불능",
   "nameEn": "AXIS LUBRICATION PRESSURE NOT DETECTED",
   "easy": "축 윤활 압력이 감지되지 않았다. 윤활유 탱크를 먼저 보고, 스위치·펌프·배관 고장일 수 있으므로 보전 담당자가 점검한다. 윤활이 안 되는 상태로 축을 움직이지 않는다",
   "severity": "STOP",
   "responder": "MNT",
   "note": "",
   "lockout": "FULL",
   "chain": "",
   "doc02": "DOC-02 §4.10",
   "doc03": [
    "DOC-03 §2.10"
   ],
   "steps": [
    "가공을 다시 시작하지 말고 윤활유 저장소가 차 있는지 본다",
    "기계의 공기 압력 게이지와 제어기 게이지 화면의 공기 압력을 보고 보전 담당자를 부른다",
    "솔레노이드를 수동으로 작동시켜 HALO 매니폴드로 공기가 가는지, 솔레노이드~매니폴드 공기 라인에 누설이 없는지 본다"
   ],
   "symptom": "축 윤활 압력이 감지되지 않았다",
   "maint": [
    "축 윤활 시험(DIAGNOSTIC > MAINTENANCE > LUBE) 중 솔레노이드 전압 120 VAC 확인. 솔레노이드를 커넥터에서 뺀 채로 재지 않는다. 커넥터 위치, 느슨하거나 끊어진 배선, I/O 기판 연결을 본다",
    "I/O 탭에서 윤활 주기 동안 압력 입력이 1→0→1, 솔레노이드 출력이 0→1→0으로 바뀌는지 본다",
    "압력 스위치: NGC 소프트웨어 100.16.000.1020 이상인지 → 스위치 케이블을 점퍼로 이어 입력이 1→0으로 바뀌면 스위치 정상 → I/O 기판~스위치 도통 → 윤활 주기 중 스위치 저항이 OL→값→OL이면 정상",
    "저장소를 채울 때 바닥 필터가 찌그러져 있으면 보강형 필터(P/N 58-2072A)로 바꾼다"
   ],
   "actions": [
    "솔레노이드·배선·I/O 연결 수리, 압력 스위치 교체, 필터 교체"
   ]
  },
  "2075": {
   "code": "2075",
   "process": "OP-30",
   "nameKo": "축 윤활유 저장소 비워짐",
   "nameEn": "AXIS LUBRICATION RESERVOIR EMPTY",
   "easy": "윤활 압력이 정상보다 빨리 떨어졌다. 윤활유 탱크를 채운다. 막 채운 뒤에는 공기가 빠질 때까지 몇 번 더 뜰 수 있다",
   "severity": "WARN",
   "responder": "OPR",
   "note": "",
   "lockout": "TWO_POINT",
   "chain": "",
   "doc02": "DOC-02 §4.11",
   "doc03": [
    "DOC-03 §2.11"
   ],
   "steps": [
    "윤활유 저장소 수위를 본다",
    "보충: 전원 끄기 → 공기 주 밸브 닫기 → 공기·윤활 매니폴드의 압력 해제 밸브 링을 당겨 압력 빼기 → 저장소 분리(너무 꽉 끼면 자동차용 오일 필터 렌치) → 나사산 아래 1/2\" (13 mm)까지 채움 → 개스킷이 닿을 때까지 손으로 조인 뒤 3/4 바퀴 더",
    "[DIAGNOSTICS] → Maintenance 탭 → Lube 탭 → [F2]로 축 윤활 시험. 알람이 안 뜰 때까지 반복하고, 시험 사이에 최소 1분 기다린다",
    "막 채웠다면 공기가 빠질 때까지 몇 주기 더 뜰 수 있다. 계속 뜨면 보전 담당자를 부른다"
   ],
   "symptom": "윤활 압력이 정상보다 빨리 떨어졌다",
   "maint": [
    "저장소 조립체의 체크밸브가 걸리지 않는지, O-링이 제자리인지 본다. 매니폴드와 압력 스위치 주변을 청소한다",
    "매니폴드 누설 시험: 오일 라인을 모두 빼고 포트를 막은 뒤 윤활 주기 → 15초 전에 압력이 떨어지면 매니폴드 누설",
    "라인 하나씩 시험해 누설 라인을 찾고, 해당 축의 매니폴드·트럭·볼너트 연결부를 청소해 누설을 본다",
    "프라이밍(공기 빼기): 저장소를 채움 → 축 라인을 하나씩 빼고 솔레노이드를 수동 작동해 공기 제거 → 다시 꽂고 10초씩 5번, 15초 간격 수동 작동 → 윤활 주기로 재현 여부 확인"
   ],
   "actions": [
    "보충",
    "체크밸브 청소·교체",
    "누설 수리",
    "프라이밍"
   ]
  },
  "120": {
   "code": "120",
   "process": "OP-30",
   "nameKo": "공기 압력 또는 흐름 낮음",
   "nameEn": "LOW AIR PRESSURE OR FLOW",
   "easy": "공급되는 압축 공기의 압력이나 유량이 부족하다. 공장 공기 공급(압력 100 psi (약 6.9 bar) 필요, 최소 80 psi (약 5.5 bar))과 배관을 확인한다",
   "severity": "WARN",
   "responder": "OPR",
   "note": "작업자 → 계속되면 보전 담당자",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §4.12",
   "doc03": [
    "DOC-03 §2.12"
   ],
   "steps": [
    "기계의 공기 압력 게이지와 제어기 진단의 Gauges 탭 값을 본다",
    "공장 공기 공급(컴프레서, 공급 배관, 주 밸브 열림)을 확인한다. 압력뿐 아니라 유량도 본다",
    "레귤레이터가 맞는 압력을 내보내는지 본다",
    "계속되면 보전 담당자를 부른다"
   ],
   "symptom": "기계에 들어오는 압축 공기의 압력이나 유량이 최소 요구치보다 낮다",
   "maint": [
    "제어기 값과 기계 게이지가 다르면 I/O 탭의 아날로그 값을 보고, 센서 케이블을 흔들 때 값이 바뀌는지 본다 → 센서 교체",
    "센서가 오염됐으면 교체한다. 다시 생기지 않게 공급 공기를 깨끗하고 건조하게 유지한다"
   ],
   "actions": [
    "공기 공급 개선, 레귤레이터 조정·청소·교체, 센서 교체."
   ]
  },
  "362": {
   "code": "362",
   "process": "OP-30",
   "nameKo": "공구 수명 한계 도달",
   "nameEn": "TOOL-LIFE LIMIT REACHED",
   "easy": "공구 수명이 다 됐는데 바꿔 쓸 예비 공구가 없다. 공구를 확인·교체하고, 공구 오프셋을 고친 뒤 고급 공구 관리(ATM)에서 수명을 리셋한다",
   "severity": "WARN",
   "responder": "OPR",
   "note": "",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §4.13",
   "doc03": [
    "DOC-03 §2.13"
   ],
   "steps": [
    "만료된 공구를 검사하고 필요하면 바꾼다",
    "공구 오프셋을 업데이트한다",
    "고급 공구 관리(ATM) 탭(현재 명령 아래)에서 만료 공구의 사용 계수기를 선택 → [0] → [ENTER]로 수명을 리셋한다"
   ],
   "symptom": "공구 수명이 다 됐고 대신 쓸 공구가 없다",
   "maint": [],
   "actions": [
    "공구 교체와 수명 리셋"
   ]
  },
  "552": {
   "code": "552",
   "process": "OP-30",
   "nameKo": "트립된 회로 차단기",
   "nameEn": "TRIPPED CIRCUIT BREAKER",
   "easy": "제어반 안의 회로 차단기가 떨어졌다. CB3는 절삭유 펌프용. 케이블 손상, 펌프 걸림, 모터 단락을 확인하고 차단기를 다시 올려야 알람이 풀린다. 제어반을 열어야 하므로 잠금·표지가 필요하다",
   "severity": "STOP",
   "responder": "MNT",
   "note": "",
   "lockout": "FULL",
   "chain": "",
   "doc02": "DOC-02 §4.14",
   "doc03": [
    "DOC-03 §2.14"
   ],
   "steps": [
    "제어반은 열지 않는다. 절삭유 펌프·칩 컨베이어가 칩에 막히거나 걸렸는지 겉으로 보고 보전 담당자를 부른다",
    "잠금·표지, 고전압 대기, AC 전압 검출기로 확인한 뒤 제어반을 연다",
    "PSUP 기판에서 어느 차단기가 떨어졌는지 본다. 안 떨어졌으면 점검 8로"
   ],
   "symptom": "제어반 안 배전 기판의 회로 차단기가 떨어졌다",
   "maint": [
    "펌프 결함 점검: 펌프 케이블을 기계에서 분리 → 옴미터로 각 선 단자와 접지 단자 사이(3상 L1·L2·L3+접지, 단상 L1·L2+접지) → 모두 O.L이면 단락 없음. 단락이 나오면 모터 커버를 열고 케이블을 모터에서 분리 → 모터 리드와 접지 사이: 단락이면 펌프 불량, 아니면 케이블 불량",
    "단락이 없으면 펌프 걸림을 본다: 펌프 아래 임펠러 캡 분리 → 임펠러를 빼서 청소(강철 임펠러는 왼나사) → 마모·손상·균열 → 펌프 축을 손으로 돌려 자유롭게 도는지(안 돌면 모터 베어링 손상) → 다시 달고 펌프 몸체·캡에 닿지 않는지(심으로 조정)",
    "원인을 고친 뒤 차단기를 다시 올리고 알람을 지운다",
    "다시 떨어지면 AC 클램프 미터로 돌입 전류와 트립까지 시간, 정상 운전 전류를 재어 원문 표와 비교한다 (원문 값 ±20%)",
    "차단기가 안 떨어졌는데 552면 PSUP 기판 고장 대응 안내를 따른다"
   ],
   "actions": [
    "케이블 교체",
    "임펠러 청소·교체(서비스 부품 93-2609)",
    "펌프 교체",
    "차단기 교체",
    "PSUP 기판 점검"
   ]
  },
  "314": {
   "code": "314",
   "process": "OP-30",
   "nameKo": "메모리에 있지 않은 서브프로그램",
   "nameEn": "SUBPROGRAM NOT IN MEMORY",
   "easy": "M98·G65로 부른 서브프로그램이 메모리에 없다. 파일 위치·이름(대문자 O, 소문자 확장자)을 확인한다",
   "severity": "GUIDE",
   "responder": "OPR",
   "note": "",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §4.15",
   "doc03": [
    "DOC-03 §2.15",
    "DOC-03 §4"
   ],
   "steps": [
    "P코드가 부르는 서브프로그램이 메모리에 있는지 본다",
    "FNC로 부를 때는 메인 프로그램과 같은 장치·같은 디렉터리에 있는지 본다",
    "USB에서 하드 드라이브로 옮긴 파일이면 이름이 대문자 O + 소문자 확장자인지 본다 (예: `O1234.nc`)"
   ],
   "symptom": "M98 또는 G65의 P코드로 부른 서브프로그램이 메모리에 없다",
   "maint": [],
   "actions": [
    "파일 위치·이름을 고치고 [RESET] 후 다시 시작한다 (공통 처리는 4장)."
   ]
  },
  "6302.00": {
   "code": "6302.00",
   "process": "OP-10",
   "nameKo": "톱날 모터 전류가 경보 한계를 초과함",
   "nameEn": "Saw blade motor current exceeds alarm limit",
   "easy": "톱날 모터에 큰 전류가 흐른다. 톱날 마모·이송 과다·재료 걸림을 의심한다",
   "severity": "STOP",
   "responder": "MNT",
   "note": "",
   "lockout": "FULL",
   "chain": "",
   "doc02": "DOC-02 §5.1",
   "doc03": [
    "DOC-03 §3.1"
   ],
   "steps": [
    "[EMERGENCY STOP] 상태를 확인하고 절단 중인 재료가 톱날에 끼었는지 본다",
    "톱날 상태를 본다 (일일 점검 항목)",
    "보전 담당자를 부른다"
   ],
   "symptom": "",
   "maint": [],
   "actions": [
    "톱날 교체: [EMERGENCY STOP] + 전원 [OFF] → 전면 도어를 열고 톱날 접근 도어 M8 볼트 4개 분리 → M14 톱날 고정 볼트 분리 → 접촉면을 닦고 새 톱날의 이가 절단 영역 쪽(아래)을 향하게 설치 → 톱날을 반시계 방향으로 돌려 둔 채 조임 → 고정 볼트 40 ft-lbs (약 54 N·m)"
   ]
  },
  "5303.00": {
   "code": "5303.00",
   "process": "OP-10",
   "nameKo": "가이드 레일 윤활유 레벨 낮음",
   "nameEn": "Guide rail lubrication level low",
   "easy": "가이드 레일 윤활유가 부족하다. 보충한다",
   "severity": "WARN",
   "responder": "OPR",
   "note": "",
   "lockout": "ONE_POINT",
   "chain": "",
   "doc02": "DOC-02 §5.2",
   "doc03": [
    "DOC-03 §3.2"
   ],
   "steps": [
    "HMI 오른쪽 윤활 캐비닛 안의 윤활유 저장소·펌프를 찾는다",
    "수위를 본다",
    "지정 윤활유로 보충한다: Haas P/N 93-5656 또는 Mobil Vactra No. 2 (Way Oil 68)"
   ],
   "symptom": "",
   "maint": [],
   "actions": [
    "보충 후 알람 해제"
   ]
  },
  "25050": {
   "code": "25050",
   "process": "OP-20",
   "nameKo": "축 %1 추종오차(Following Error) 과대",
   "nameEn": "Axis %1 contour monitoring",
   "easy": "계산한 축 위치와 실제 위치의 차이가 허용치를 넘어 프로그램이 취소되고 NC가 멈췄다",
   "severity": "STOP",
   "responder": "MNT",
   "note": "",
   "lockout": "FULL",
   "chain": "",
   "doc02": "DOC-02 §5.3",
   "doc03": [
    "DOC-03 §3.3"
   ],
   "steps": [
    "알람의 축 이름(%1)을 확인하고 다시 시작하지 않는다",
    "보전 담당자를 부른다",
    "보전: 기계 부분이 원활하게 움직이는지 본다"
   ],
   "symptom": "계산한 실제값과 기계 실제값의 차이가 MD36400 $MA_CONTOUR_TOL보다 커서 프로그램이 취소됐다",
   "maint": [],
   "actions": [
    "원인 해결 뒤 이 모드 그룹의 모든 채널에서 RESET → 가공 프로그램 재시작"
   ]
  },
  "10720": {
   "code": "10720",
   "process": "OP-20",
   "nameKo": "[채널 %1:] 축 %2 블록 %3 소프트웨어 리미트 스위치 %4",
   "nameEn": "Software limit switch",
   "easy": "프로그램 경로가 소프트웨어 리미트 스위치를 넘는다. NC 프로그램의 위치와 공작물 오프셋을 확인한다",
   "severity": "GUIDE",
   "responder": "OPR",
   "note": "",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §5.4",
   "doc03": [
    "DOC-03 §3.4"
   ],
   "steps": [
    "NC 프로그램의 위치를 점검·수정한다",
    "현재 프레임의 활성 공작물 오프셋, 오버레이 이동($AA_OFF), DRF, 변환 컴포넌트를 본다"
   ],
   "symptom": "축에 프로그램된 경로가 현재 유효한 소프트웨어 리미트 스위치를 넘는다",
   "maint": [],
   "actions": [
    "NC START 또는 RESET 키로 알람을 지우고 프로그램을 계속한다"
   ]
  },
  "WSH-01": {
   "code": "WSH-01",
   "process": "OP-40",
   "nameKo": "과열 정지",
   "nameEn": "Overheat condition",
   "easy": "세척조가 과열돼 초음파가 멈췄다 (75 ℃에서 정지, 69 ℃로 내려가면 다시 가능). 세척액 수위를 확인한다",
   "severity": "STOP",
   "responder": "MNT",
   "note": "",
   "lockout": "FULL",
   "chain": "",
   "doc02": "DOC-02 §5.5",
   "doc03": [
    "DOC-03 §3.5"
   ],
   "steps": [
    "세척액 수위를 본다",
    "식을 때까지 기다린다",
    "보전 담당자를 부른다"
   ],
   "symptom": "운전이 멈추고 화면에 알람 아이콘만 켜짐",
   "maint": [],
   "actions": [
    "수위를 맞추고 재시작"
   ]
  },
  "WSH-02": {
   "code": "WSH-02",
   "process": "OP-40",
   "nameKo": "세정력 저하",
   "nameEn": "Decreased ultrasonic activity",
   "easy": "초음파 세정력이 떨어졌다. 세척액이 오래됐거나, 수위가 맞지 않거나, 바닥에 이물이 쌓였을 수 있다. 세척액을 갈거나 수위를 맞춘다",
   "severity": "WARN",
   "responder": "OPR",
   "note": "",
   "lockout": "UNPLUG",
   "chain": "",
   "doc02": "DOC-02 §5.6",
   "doc03": [
    "DOC-03 §3.6"
   ],
   "steps": [
    "세척액 상태를 본다 (고형물·변색이 보이면 오염)",
    "부하를 넣은 상태에서 수위가 운전 수위선 3/8 inch (1 cm) 안인지 본다",
    "새로 채웠으면 따뜻한 수돗물 + 세척액으로 5~10분 운전해 탈기했는지 본다"
   ],
   "symptom": "",
   "maint": [],
   "actions": [
    "세척액 교체, 수위 조정, 탱크를 비우고 따뜻한 물로 청소 후 부드러운 천으로 닦음"
   ]
  },
  "MP-170": {
   "code": "MP-170",
   "process": "OP-50",
   "nameKo": "접촉 프로브가 다시 준비되지 않음",
   "nameEn": "Touch probe will not rearm",
   "easy": "접촉 프로브가 측정 뒤 다시 준비 상태가 되지 않아 측정을 이어 갈 수 없다",
   "severity": "STOP",
   "responder": "MNT",
   "note": "",
   "lockout": "FULL",
   "chain": "",
   "doc02": "DOC-02 §5.7",
   "doc03": [
    "DOC-03 §3.7"
   ],
   "steps": [
    "측정을 멈추고 프로브·스타일러스가 부딪히거나 손상됐는지 본다",
    "스타일러스 끝과 기준구의 먼지를 닦는다",
    "보전 담당자를 부른다"
   ],
   "symptom": "",
   "maint": [],
   "actions": [
    "충돌 등 큰 사건 뒤에는 바로 중간 점검을 한다 → DOC-04"
   ]
  },
  "TempComp-202": {
   "code": "TempComp-202",
   "process": "OP-50",
   "nameKo": "온도 기울기 한계 초과",
   "nameEn": "Gradient temperature limit exceeded",
   "easy": "측정실 온도가 너무 빨리 변해 온도 보정 한계를 넘었다. 온도가 안정될 때까지 측정을 기다린다 (측정 기준 온도 20 ℃)",
   "severity": "WARN",
   "responder": "OPR",
   "note": "",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §5.8",
   "doc03": [
    "DOC-03 §3.8"
   ],
   "steps": [
    "측정을 멈추고 측정실 온도가 안정될 때까지 기다린다",
    "측정실 문·공조 상태를 본다",
    "공작물의 부품 온도가 16~26 ℃ 안인지 본다 (부품 온도 보정을 쓸 수 없으면 측정실 온도와 차이 2 ℃ 이하, DOC-06 §6)"
   ],
   "symptom": "",
   "maint": [],
   "actions": [
    "안정된 뒤 다시 측정"
   ]
  },
  "230": {
   "code": "230",
   "process": "OP-30",
   "nameKo": "도어 열림(DOOR OPEN)",
   "nameEn": "DOOR OPEN",
   "easy": "도어가 열려 있다. 도어 장치에 고장이나 걸림이 없는지 확인하고 닫는다",
   "severity": "GUIDE",
   "responder": "OPR",
   "note": "",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §6",
   "doc03": [
    "DOC-03 §4"
   ],
   "steps": [],
   "symptom": "",
   "maint": [],
   "actions": []
  },
  "302": {
   "code": "302",
   "process": "OP-30",
   "nameKo": "G02 또는 G03의 잘못된 R",
   "nameEn": "INVALID R IN G02 OR G03",
   "easy": "원호(G02·G03)의 반지름 R이 너무 작다. 프로그램을 고친다",
   "severity": "GUIDE",
   "responder": "OPR",
   "note": "",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §6",
   "doc03": [
    "DOC-03 §4"
   ],
   "steps": [],
   "symptom": "",
   "maint": [],
   "actions": []
  },
  "304": {
   "code": "304",
   "process": "OP-30",
   "nameKo": "G02 또는 G03의 잘못된 I, J 또는 K",
   "nameEn": "INVALID I, J, OR K IN G02 OR G03",
   "easy": "원호(G02·G03)의 중심 I·J·K 값이나 평면 선택이 틀렸다. 프로그램을 고친다",
   "severity": "GUIDE",
   "responder": "OPR",
   "note": "",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §6",
   "doc03": [
    "DOC-03 §4"
   ],
   "steps": [],
   "symptom": "",
   "maint": [],
   "actions": []
  },
  "306": {
   "code": "306",
   "process": "OP-30",
   "nameKo": "고정 사이클의 잘못된 I, J, K 또는 Q",
   "nameEn": "INVALID I, J, K OR Q IN CANNED CYCLE",
   "easy": "고정 사이클의 I·J·K·Q 값이 틀렸다(0이면 안 됨). 프로그램을 고친다",
   "severity": "GUIDE",
   "responder": "OPR",
   "note": "",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §6",
   "doc03": [
    "DOC-03 §4"
   ],
   "steps": [],
   "symptom": "",
   "maint": [],
   "actions": []
  },
  "315": {
   "code": "315",
   "process": "OP-30",
   "nameKo": "잘못된 P코드",
   "nameEn": "INVALID P CODE",
   "easy": "P 코드 값이 잘못됐다 (예: M97의 P와 N 번호 불일치). 프로그램을 고친다",
   "severity": "GUIDE",
   "responder": "OPR",
   "note": "",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §6",
   "doc03": [
    "DOC-03 §4"
   ],
   "steps": [],
   "symptom": "",
   "maint": [],
   "actions": []
  },
  "613": {
   "code": "613",
   "process": "OP-30",
   "nameKo": "컷터 보정에 허용되지 않는 명령",
   "nameEn": "COMMAND NOT ALLOWED IN CUTTER COMPENSATION",
   "easy": "공구 지름 보정(G41·G42) 중에 쓸 수 없는 코드가 있다. 보정 앞뒤로 옮긴다",
   "severity": "GUIDE",
   "responder": "OPR",
   "note": "",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §6",
   "doc03": [
    "DOC-03 §4"
   ],
   "steps": [],
   "symptom": "",
   "maint": [],
   "actions": []
  },
  "814": {
   "code": "814",
   "process": "OP-30",
   "nameKo": "툴 오프셋 없음",
   "nameEn": "NO TOOL OFFSET",
   "easy": "공구 오프셋이 정해지지 않았다. 자동 운전 전에 공구 오프셋을 입력한다",
   "severity": "GUIDE",
   "responder": "OPR",
   "note": "",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §6",
   "doc03": [
    "DOC-03 §4"
   ],
   "steps": [],
   "symptom": "",
   "maint": [],
   "actions": []
  },
  "970": {
   "code": "970",
   "process": "OP-30",
   "nameKo": "이송 코드에 명령이 없는 축",
   "nameEn": "NO AXIS COMMANDED IN FEED CODE",
   "easy": "이송 코드에 움직일 축이 없다. 프로그램을 확인하고 리셋한다",
   "severity": "GUIDE",
   "responder": "OPR",
   "note": "",
   "lockout": "NONE",
   "chain": "",
   "doc02": "DOC-02 §6",
   "doc03": [
    "DOC-03 §4"
   ],
   "steps": [],
   "symptom": "",
   "maint": [],
   "actions": []
  }
 },
 "safety": {
  "SAW-01": {
   "points": [
    "SAW-01-E1 SAW-01 주 차단기",
    "SAW-01-E2 SAW-01 공급 분전반 차단기"
   ],
   "energy": [
    "회전체 관성",
    "유압"
   ]
  },
  "MIL-01": {
   "points": [
    "MIL-01-E1 MIL-01 주 차단기",
    "MIL-01-P1 MIL-01 공압 주 밸브",
    "MIL-01-E2 MIL-01 공급 분전반 차단기"
   ],
   "energy": [
    "중력",
    "회전체 관성",
    "공압 잔압"
   ]
  },
  "VF2-01": {
   "points": [
    "VF2-01-E1 VF2-01 주 차단기",
    "VF2-01-P1 VF2-01 공압 주 밸브",
    "VF2-01-E2 VF2-01 공급 분전반 차단기"
   ],
   "energy": [
    "전기",
    "중력",
    "회전체 관성",
    "공압 잔압",
    "열"
   ]
  },
  "VF2-02": {
   "points": [
    "VF2-02-E1 VF2-02 주 차단기",
    "VF2-02-P1 VF2-02 공압 주 밸브",
    "VF2-02-E2 VF2-02 공급 분전반 차단기"
   ],
   "energy": []
  },
  "WSH-01": {
   "points": [
    "WSH-01-E1 WSH-01 세척기 전원 플러그",
    "WSH-01-E2 WSH-01 진동 바렐 전원 차단기"
   ],
   "energy": [
    "전기",
    "열",
    "회전체 관성"
   ]
  },
  "CMM-01": {
   "points": [
    "CMM-01-E1 CMM-01 주 전원 차단기",
    "CMM-01-P1 CMM-01 공압 주 밸브"
   ],
   "energy": [
    "공압",
    "기계 움직임"
   ]
  }
 },
 "short": {
  "2075": {
   "work": "축 윤활유 저장소 보충 (알람 2075, DOC-04 2.3 매월)",
   "judge": "보충용 2점 잠금",
   "todo": "VF2-0x-E1·P1 자물쇠 + 표지 → 압력 해제 링 당김 → 공압 게이지 0 확인 → 저장소 분리·보충 → 잠금 해제 → 축 윤활 시험"
  },
  "5303": {
   "work": "가이드 레일 윤활유 보충 (알람 5303, DOC-04 3.1 매주)",
   "judge": "1점 잠금 (SAW-01-E1)",
   "todo": "[EMERGENCY STOP] → 전원 끄기 → SAW-01-E1 자물쇠 + 표지 → 기동 버튼을 눌러 안 켜짐 확인 → 캐비닛을 열고 Mobil Vactra No. 2를 채운다 → 닫고 잠금 해제 → 경보 5303이 꺼졌는지 본다. 공기는 잠그지 않는다: VF는 공기로 탱크에 압력을 거는 방식이라 공기를 막지만, HCS-80 자료에는 윤활 펌프가 공기식이라는 말이 없고 공압 차단 지점도 없다(§3.1). 실제 기계에서 펌프·탱크에 공기 배관이 들어가 있으면 공기도 잠그고, 매뉴얼에 방법이 생기면 그것을 따른다"
  }
 },
 "block": [
  "━━━━━━━━━━ 안전 작업 (고정 서식 · AI 작성 아님) ━━━━━━━━━━",
  "설비: {설비 ID}    차단 지점: {§3 차단 지점 목록}",
  "저장 에너지: {§3 저장 에너지 목록}",
  "",
  "[작업 전]  KOSHA GUIDE B-M-25-2026 6장",
  " □ 6.1 기기 등의 운전정지 준비",
  " □ 6.2 기기 등의 운전정지",
  " □ 6.3 기기 등의 차단",
  " □ 6.4 잠금장치 또는 표지의 설치",
  " □ 6.5 저장 또는 축적된 에너지의 관리",
  " □ 6.6 차단 확인",
  "",
  "[고전압 대기]  (VF2-01·VF2-02 제어반 작업 때)",
  " □ 고전압 표시등이 꺼진 뒤 최소 5분 기다린 뒤 제어반 작업 시작",
  "   (안전 작업 기준서 DOC-05 §4.1)",
  "",
  "[보호구]",
  " □ 보안경 · 안전화 · (소음 구역) 청력 보호구",
  " □ 회전체를 다룰 때 면장갑 금지 — 손에 밀착되는 장갑만 (법 제95조)",
  " □ 톱날·칩·공작물을 멈춘 상태에서 다룰 때 베임 방지 장갑",
  "",
  "[작업 후]  KOSHA GUIDE B-M-25-2026 7장",
  " □ 7.1 기기 등의 점검",
  " □ 7.2 작업자 확인",
  " □ 7.3 잠금장치·표지의 제거",
  "",
  "근거: 산업안전보건기준에 관한 규칙 제92조·제95조, KOSHA B-M-25-2026",
  "출처: DOC-05 안전 작업 기준서 Rev.2 §2·§4·§5",
  "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
 ],
 "inventory": [
  {
   "no": "TL-EM10",
   "name": "엔드밀 Ø10",
   "unit": "개",
   "owner": "SUP",
   "safety": 9.0,
   "stock": 17.0
  },
  {
   "no": "TL-DR50",
   "name": "드릴 Ø5.0 (M6 탭 아랫구멍)",
   "unit": "개",
   "owner": "SUP",
   "safety": 5.0,
   "stock": 8.0
  },
  {
   "no": "TL-TAP6",
   "name": "M6 탭",
   "unit": "개",
   "owner": "SUP",
   "safety": 8.0,
   "stock": 6.0
  },
  {
   "no": "TL-BB45",
   "name": "보링바 인서트",
   "unit": "개",
   "owner": "SUP",
   "safety": 4.0,
   "stock": 5.0
  },
  {
   "no": "TL-FM50",
   "name": "페이스밀 인서트",
   "unit": "개",
   "owner": "SUP",
   "safety": 14.0,
   "stock": 18.0
  },
  {
   "no": "CS-WLUB",
   "name": "축 윤활유",
   "unit": "L",
   "owner": "MNT",
   "safety": 4.0,
   "stock": 3.6
  },
  {
   "no": "CS-COOL",
   "name": "절삭유 원액",
   "unit": "L",
   "owner": "MNT",
   "safety": 20.0,
   "stock": 31.619999999999997
  },
  {
   "no": "CS-CFLT",
   "name": "절삭유 필터",
   "unit": "개",
   "owner": "MNT",
   "safety": 2.0,
   "stock": 2.0
  },
  {
   "no": "CS-AFLT",
   "name": "공기 필터",
   "unit": "개",
   "owner": "MNT",
   "safety": 2.0,
   "stock": 2.0
  },
  {
   "no": "CS-SLUB",
   "name": "주축 윤활유",
   "unit": "L",
   "owner": "MNT",
   "safety": 4.0,
   "stock": 7.63
  },
  {
   "no": "CS-GRS",
   "name": "그리스",
   "unit": "개",
   "owner": "MNT",
   "safety": 2.0,
   "stock": 2.0
  }
 ],
 "briefing": {
  "last": {
   "id": "2026-09-30-N",
   "target": 90,
   "actual": 94,
   "defect": 1,
   "notable": "실적 94개 / 총 목표 90개 (+4개). 필수 정지(고장 그룹 5분 이상) 없음. 병목은 기준 병목(OP-30) 그대로. 불량(폐기) 1개. 주의 알람 없음. 세척기 세척액 보충함."
  },
  "ranked": [
   {
    "rank": "0",
    "name": "안전",
    "items": [
     "잠금·표지 중인 설비 없음"
    ]
   },
   {
    "rank": "0-1",
    "name": "오래 방치",
    "items": [
     "VF2-02 알람 2075 축 윤활유 저장소 비워짐 — 7일 안 3번 (24시간 넘게 처리 안 됨)",
     "M6 탭 재고가 안전 재고(8) 이하 (24시간 넘게 처리 안 됨)",
     "축 윤활유 재고가 안전 재고(4) 이하 (24시간 넘게 처리 안 됨)",
     "VF2-02 윤활유 저장소 양 점검·보충 — 기한 넘김 (기한 09/28) (24시간 넘게 처리 안 됨)",
     "VF2-02 주축 윤활 탱크 양 점검 — 기한 넘김 (기한 09/29) (24시간 넘게 처리 안 됨)"
    ]
   },
   {
    "rank": "1",
    "name": "긴급",
    "items": []
   },
   {
    "rank": "2",
    "name": "생산 위험",
    "items": []
   },
   {
    "rank": "3",
    "name": "주의",
    "items": [
     "VF2-01-T05 사용률 90% — 교체 준비"
    ]
   },
   {
    "rank": "4",
    "name": "참고",
    "items": [
     "VF2-02 윤활유 저장소 양 점검·보충 — 기한 하루 전 (기한 09/28)",
     "VF2-02 주축 윤활 탱크 양 점검 — 기한 하루 전 (기한 09/29) / 추가: 다음 교대 첫 작업지시 순서 확인"
    ]
   }
  ],
  "orders": [
   {
    "no": "PO-2609-127",
    "qty": 60,
    "status": "IN_PROGRESS"
   },
   {
    "no": "PO-2609-128",
    "qty": 31,
    "status": "IN_PROGRESS"
   },
   {
    "no": "PO-2609-129",
    "qty": 55,
    "status": "WAITING"
   }
  ],
  "reports": [
   {
    "id": "2026-09-01-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 70,
    "defect": 1
   },
   {
    "id": "2026-09-01-N",
    "status": "CONFIRMED",
    "target": 110,
    "actual": 85,
    "defect": 0
   },
   {
    "id": "2026-09-02-D",
    "status": "REVISED",
    "target": 90,
    "actual": 98,
    "defect": 0
   },
   {
    "id": "2026-09-02-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 86,
    "defect": 0
   },
   {
    "id": "2026-09-03-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 88,
    "defect": 1
   },
   {
    "id": "2026-09-03-N",
    "status": "CONFIRMED",
    "target": 92,
    "actual": 95,
    "defect": 0
   },
   {
    "id": "2026-09-04-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 95,
    "defect": 0
   },
   {
    "id": "2026-09-04-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 85,
    "defect": 0
   },
   {
    "id": "2026-09-05-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 93,
    "defect": 0
   },
   {
    "id": "2026-09-05-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 93,
    "defect": 1
   },
   {
    "id": "2026-09-07-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 107,
    "defect": 1
   },
   {
    "id": "2026-09-07-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 84,
    "defect": 0
   },
   {
    "id": "2026-09-08-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 99,
    "defect": 0
   },
   {
    "id": "2026-09-08-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 93,
    "defect": 1
   },
   {
    "id": "2026-09-09-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 96,
    "defect": 0
   },
   {
    "id": "2026-09-09-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 99,
    "defect": 0
   },
   {
    "id": "2026-09-10-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 88,
    "defect": 0
   },
   {
    "id": "2026-09-10-N",
    "status": "CONFIRMED",
    "target": 92,
    "actual": 90,
    "defect": 0
   },
   {
    "id": "2026-09-11-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 98,
    "defect": 0
   },
   {
    "id": "2026-09-11-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 87,
    "defect": 0
   },
   {
    "id": "2026-09-12-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 91,
    "defect": 1
   },
   {
    "id": "2026-09-12-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 99,
    "defect": 0
   },
   {
    "id": "2026-09-14-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 45,
    "defect": 0
   },
   {
    "id": "2026-09-14-N",
    "status": "CONFIRMED",
    "target": 135,
    "actual": 101,
    "defect": 1
   },
   {
    "id": "2026-09-15-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 99,
    "defect": 0
   },
   {
    "id": "2026-09-15-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 100,
    "defect": 0
   },
   {
    "id": "2026-09-16-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 94,
    "defect": 0
   },
   {
    "id": "2026-09-16-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 90,
    "defect": 1
   },
   {
    "id": "2026-09-17-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 91,
    "defect": 1
   },
   {
    "id": "2026-09-17-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 96,
    "defect": 0
   },
   {
    "id": "2026-09-18-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 53,
    "defect": 2
   },
   {
    "id": "2026-09-18-N",
    "status": "CONFIRMED",
    "target": 127,
    "actual": 137,
    "defect": 1
   },
   {
    "id": "2026-09-19-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 84,
    "defect": 0
   },
   {
    "id": "2026-09-19-N",
    "status": "CONFIRMED",
    "target": 96,
    "actual": 93,
    "defect": 2
   },
   {
    "id": "2026-09-21-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 95,
    "defect": 0
   },
   {
    "id": "2026-09-21-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 90,
    "defect": 0
   },
   {
    "id": "2026-09-22-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 88,
    "defect": 0
   },
   {
    "id": "2026-09-22-N",
    "status": "CONFIRMED",
    "target": 92,
    "actual": 92,
    "defect": 1
   },
   {
    "id": "2026-09-23-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 101,
    "defect": 2
   },
   {
    "id": "2026-09-23-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 92,
    "defect": 1
   },
   {
    "id": "2026-09-24-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 94,
    "defect": 0
   },
   {
    "id": "2026-09-24-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 92,
    "defect": 0
   },
   {
    "id": "2026-09-25-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 98,
    "defect": 1
   },
   {
    "id": "2026-09-25-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 98,
    "defect": 2
   },
   {
    "id": "2026-09-26-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 88,
    "defect": 0
   },
   {
    "id": "2026-09-26-N",
    "status": "CONFIRMED",
    "target": 92,
    "actual": 102,
    "defect": 0
   },
   {
    "id": "2026-09-28-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 97,
    "defect": 1
   },
   {
    "id": "2026-09-28-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 99,
    "defect": 1
   },
   {
    "id": "2026-09-29-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 92,
    "defect": 0
   },
   {
    "id": "2026-09-29-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 91,
    "defect": 0
   },
   {
    "id": "2026-09-30-D",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 90,
    "defect": 0
   },
   {
    "id": "2026-09-30-N",
    "status": "CONFIRMED",
    "target": 90,
    "actual": 94,
    "defect": 1
   }
  ]
 },
 "reasons": [
  {
   "group": "고장",
   "code": "F01",
   "name": "서보·앰프"
  },
  {
   "group": "고장",
   "code": "F02",
   "name": "주축"
  },
  {
   "group": "고장",
   "code": "F03",
   "name": "공구 교환장치"
  },
  {
   "group": "고장",
   "code": "F04",
   "name": "윤활"
  },
  {
   "group": "고장",
   "code": "F05",
   "name": "공압"
  },
  {
   "group": "고장",
   "code": "F06",
   "name": "절삭유"
  },
  {
   "group": "자재·흐름",
   "code": "M01",
   "name": "소재 대기"
  },
  {
   "group": "자재·흐름",
   "code": "M02",
   "name": "앞 공정 대기"
  },
  {
   "group": "자재·흐름",
   "code": "M03",
   "name": "뒤 공정 막힘"
  },
  {
   "group": "준비",
   "code": "S01",
   "name": "작업지시 교체"
  },
  {
   "group": "준비",
   "code": "S02",
   "name": "공구 교체"
  },
  {
   "group": "준비",
   "code": "S03",
   "name": "초품 검사"
  },
  {
   "group": "준비",
   "code": "S04",
   "name": "교대 시작·끝 점검"
  },
  {
   "group": "조작",
   "code": "O01",
   "name": "프로그램 오류"
  },
  {
   "group": "조작",
   "code": "O02",
   "name": "모드 오류"
  },
  {
   "group": "조작",
   "code": "O03",
   "name": "도어 열림"
  },
  {
   "group": "조작",
   "code": "O04",
   "name": "부품 교체 대기"
  },
  {
   "group": "계획",
   "code": "P01",
   "name": "예방 정비"
  },
  {
   "group": "계획",
   "code": "P02",
   "name": "휴식"
  },
  {
   "group": "계획",
   "code": "P03",
   "name": "계획 없음"
  }
 ],
 "layout": {
  "plant": {
   "width_x_mm": 28000.0,
   "depth_y_mm": 8000.0,
   "ceiling_z_mm": 4000.0,
   "aisle_width_mm": 2000.0,
   "work_band_mm": 1000.0,
   "equipment_gap_mm": 1000.0
  },
  "equipment": {
   "SAW-01": {
    "process": "OP-10",
    "model": "Haas HCS-80",
    "size": [
     2256.0,
     1999.0,
     1938.0
    ],
    "center": [
     6022.0,
     4950.0
    ],
    "facing": "POS_X",
    "tag": "REAL",
    "ref": "",
    "std_cycle_min": 1.0,
    "batch_qty": null,
    "batch_time_min": null
   },
   "MIL-01": {
    "process": "OP-20",
    "model": "3축 머시닝센터",
    "size": [
     1990.0,
     2757.0,
     2935.0
    ],
    "center": [
     9145.0,
     5179.0
    ],
    "facing": "NEG_Y",
    "tag": "REFERENCE",
    "ref": "DMG MORI CMX 600 V 기본형 (칩 컨베이어 없음)",
    "std_cycle_min": 3.5,
    "batch_qty": null,
    "batch_time_min": null
   },
   "VF2-01": {
    "process": "OP-30",
    "model": "Haas VF-2",
    "size": [
     3147.0,
     2249.0,
     2724.0
    ],
    "center": [
     12714.0,
     4925.0
    ],
    "facing": "NEG_Y",
    "tag": "REAL",
    "ref": "",
    "std_cycle_min": 7.0,
    "batch_qty": null,
    "batch_time_min": null
   },
   "VF2-02": {
    "process": "OP-30",
    "model": "Haas VF-2",
    "size": [
     3147.0,
     2249.0,
     2724.0
    ],
    "center": [
     16861.0,
     4925.0
    ],
    "facing": "NEG_Y",
    "tag": "REAL",
    "ref": "",
    "std_cycle_min": 7.0,
    "batch_qty": null,
    "batch_time_min": null
   },
   "WSH-01": {
    "process": "OP-40",
    "model": "초음파 세척기 + 텀블러(진동 바렐)",
    "size": [
     3000.0,
     1500.0,
     1291.0
    ],
    "center": [
     20935.0,
     4550.0
    ],
    "facing": "NEG_Y",
    "tag": "VIRTUAL",
    "ref": "진동 바렐 Kalamazoo KVF3급 + 초음파 세척기 Branson CPX8800H-E급",
    "std_cycle_min": null,
    "batch_qty": 30,
    "batch_time_min": 25.0
   },
   "CMM-01": {
    "process": "OP-50",
    "model": "3차원 측정기",
    "size": [
     1110.0,
     1266.0,
     2414.0
    ],
    "center": [
     24857.0,
     4433.0
    ],
    "facing": "NEG_Y",
    "tag": "REFERENCE",
    "ref": "Hexagon TIGO SF 05.06.05",
    "std_cycle_min": 0.9,
    "batch_qty": null,
    "batch_time_min": null
   }
  },
  "objects": {
   "RACK-01": {
    "kind": "MATERIAL_RACK",
    "name": "봉재 랙 (외팔보 랙)",
    "x": [
     1000.0,
     4814.0
    ],
    "y": [
     6300.0,
     7020.0
    ],
    "h": 2000.0,
    "tag": "REFERENCE",
    "buffer": null
   },
   "INF-01": {
    "kind": "INFEED",
    "name": "SAW-01 투입 베드 2대",
    "x": [
     1000.0,
     4894.0
    ],
    "y": [
     3617.0,
     5124.0
    ],
    "h": 925.0,
    "tag": "REAL",
    "buffer": null
   },
   "WIP-1": {
    "kind": "WIP_SPOT",
    "name": "재공 OP-10→20 (한도 30, 상자 1)",
    "x": [
     7050.0,
     8250.0
    ],
    "y": [
     2000.0,
     2800.0
    ],
    "h": null,
    "tag": "VIRTUAL",
    "buffer": "WIP-10-20"
   },
   "WIP-2": {
    "kind": "WIP_SPOT",
    "name": "재공 OP-20→30 (한도 30, 상자 1) — VF2-01·02 사이 앞",
    "x": [
     13188.0,
     14388.0
    ],
    "y": [
     2000.0,
     2800.0
    ],
    "h": null,
    "tag": "VIRTUAL",
    "buffer": "WIP-20-30"
   },
   "WIP-3": {
    "kind": "WIP_SPOT",
    "name": "재공 OP-30→40 (한도 60, 상자 2) — VF2-01·02 사이 앞",
    "x": [
     15188.0,
     16388.0
    ],
    "y": [
     2000.0,
     2800.0
    ],
    "h": null,
    "tag": "VIRTUAL",
    "buffer": "WIP-30-40"
   },
   "WIP-4": {
    "kind": "WIP_SPOT",
    "name": "재공 OP-40→50 (한도 30, 상자 1)",
    "x": [
     22335.0,
     23535.0
    ],
    "y": [
     2000.0,
     2800.0
    ],
    "h": null,
    "tag": "VIRTUAL",
    "buffer": "WIP-40-50"
   },
   "SOAK-01": {
    "kind": "SOAK_SHELF",
    "name": "온도 맞춤 선반 (재공에 안 셈) — CMM 앞 재공 띠",
    "x": [
     24248.0,
     25467.0
    ],
    "y": [
     2000.0,
     2457.0
    ],
    "h": 1385.0,
    "tag": "REFERENCE",
    "buffer": null
   },
   "FG-01": {
    "kind": "FG_SPOT",
    "name": "완성품 자리",
    "x": [
     26412.0,
     27612.0
    ],
    "y": [
     2000.0,
     2800.0
    ],
    "h": null,
    "tag": "VIRTUAL",
    "buffer": null
   },
   "AISLE-1": {
    "kind": "AISLE",
    "name": "주 통로",
    "x": [
     0.0,
     28000.0
    ],
    "y": [
     0.0,
     2000.0
    ],
    "h": null,
    "tag": "VIRTUAL",
    "buffer": null
   },
   "DOOR-1": {
    "kind": "DOOR",
    "name": "반입문 (동쪽 벽, 높이 2,600 이상)",
    "x": [
     28000.0,
     28000.0
    ],
    "y": [
     0.0,
     2600.0
    ],
    "h": 2600.0,
    "tag": "VIRTUAL",
    "buffer": null
   },
   "EXIT-1": {
    "kind": "EXIT",
    "name": "비상구 (서쪽 벽)",
    "x": [
     0.0,
     0.0
    ],
    "y": [
     500.0,
     1500.0
    ],
    "h": 2000.0,
    "tag": "VIRTUAL",
    "buffer": null
   }
  },
  "wip": {
   "WIP-10-20": {
    "from": "OP-10",
    "to": "OP-20",
    "limit": 30,
    "warn_over": 20,
    "warn": true
   },
   "WIP-20-30": {
    "from": "OP-20",
    "to": "OP-30",
    "limit": 30,
    "warn_over": 29,
    "warn": true
   },
   "WIP-30-40": {
    "from": "OP-30",
    "to": "OP-40",
    "limit": 60,
    "warn_over": null,
    "warn": false
   },
   "WIP-40-50": {
    "from": "OP-40",
    "to": "OP-50",
    "limit": 30,
    "warn_over": 20,
    "warn": true
   }
  }
 },
 "masters": {
  "product": {
   "product_code": "BRK-A100",
   "product_name": "엔진 마운트 브래킷",
   "material": "알루미늄 6061-T6",
   "line_base_cycle_min": "3.5",
   "material_item_no": "RM-6061"
  },
  "processes": [
   {
    "process_code": "OP-10",
    "process_name": "절단",
    "seq": "1",
    "is_base_bottleneck": "false"
   },
   {
    "process_code": "OP-20",
    "process_name": "황삭",
    "seq": "2",
    "is_base_bottleneck": "false"
   },
   {
    "process_code": "OP-30",
    "process_name": "정밀 가공",
    "seq": "3",
    "is_base_bottleneck": "true"
   },
   {
    "process_code": "OP-40",
    "process_name": "세척·디버링",
    "seq": "4",
    "is_base_bottleneck": "false"
   },
   {
    "process_code": "OP-50",
    "process_name": "측정",
    "seq": "5",
    "is_base_bottleneck": "false"
   }
  ],
  "tools": [
   {
    "tool_id": "VF2-01-T01",
    "equipment_id": "VF2-01",
    "tool_no": "T01",
    "item_no": "TL-FM50",
    "tool_role": "IN_USE",
    "cum_usage": "140",
    "last_changed_at": ""
   },
   {
    "tool_id": "VF2-01-T02",
    "equipment_id": "VF2-01",
    "tool_no": "T02",
    "item_no": "TL-EM10",
    "tool_role": "IN_USE",
    "cum_usage": "120",
    "last_changed_at": ""
   },
   {
    "tool_id": "VF2-01-T03",
    "equipment_id": "VF2-01",
    "tool_no": "T03",
    "item_no": "TL-BB45",
    "tool_role": "IN_USE",
    "cum_usage": "80",
    "last_changed_at": ""
   },
   {
    "tool_id": "VF2-01-T04",
    "equipment_id": "VF2-01",
    "tool_no": "T04",
    "item_no": "TL-DR50",
    "tool_role": "IN_USE",
    "cum_usage": "440",
    "last_changed_at": ""
   },
   {
    "tool_id": "VF2-01-T05",
    "equipment_id": "VF2-01",
    "tool_no": "T05",
    "item_no": "TL-TAP6",
    "tool_role": "IN_USE",
    "cum_usage": "280",
    "last_changed_at": ""
   },
   {
    "tool_id": "VF2-02-T01",
    "equipment_id": "VF2-02",
    "tool_no": "T01",
    "item_no": "TL-FM50",
    "tool_role": "IN_USE",
    "cum_usage": "280",
    "last_changed_at": ""
   },
   {
    "tool_id": "VF2-02-T02",
    "equipment_id": "VF2-02",
    "tool_no": "T02",
    "item_no": "TL-EM10",
    "tool_role": "IN_USE",
    "cum_usage": "30",
    "last_changed_at": ""
   },
   {
    "tool_id": "VF2-02-T03",
    "equipment_id": "VF2-02",
    "tool_no": "T03",
    "item_no": "TL-BB45",
    "tool_role": "IN_USE",
    "cum_usage": "220",
    "last_changed_at": ""
   },
   {
    "tool_id": "VF2-02-T04",
    "equipment_id": "VF2-02",
    "tool_no": "T04",
    "item_no": "TL-DR50",
    "tool_role": "IN_USE",
    "cum_usage": "800",
    "last_changed_at": ""
   },
   {
    "tool_id": "VF2-02-T05",
    "equipment_id": "VF2-02",
    "tool_no": "T05",
    "item_no": "TL-TAP6",
    "tool_role": "IN_USE",
    "cum_usage": "120",
    "last_changed_at": ""
   }
  ],
  "tool_types": [
   {
    "item_no": "TL-FM50",
    "usage_unit": "FEED",
    "usage_per_part": "0.5",
    "life_limit": "400",
    "limit_basis": "[가상]",
    "deduct_qty_per_change": "5"
   },
   {
    "item_no": "TL-EM10",
    "usage_unit": "FEED",
    "usage_per_part": "2.5",
    "life_limit": "200",
    "limit_basis": "[참고] 알루미늄(Al7050) 엔드밀 시험에서 약 200분에 급마모 단계 진입 (PMC10056421)",
    "deduct_qty_per_change": "1"
   },
   {
    "item_no": "TL-BB45",
    "usage_unit": "HOLES",
    "usage_per_part": "1",
    "life_limit": "400",
    "limit_basis": "[가상]",
    "deduct_qty_per_change": "1"
   },
   {
    "item_no": "TL-DR50",
    "usage_unit": "HOLES",
    "usage_per_part": "4",
    "life_limit": "1000",
    "limit_basis": "[가상] (품질·재고 담당 제안값)",
    "deduct_qty_per_change": "1"
   },
   {
    "item_no": "TL-TAP6",
    "usage_unit": "HOLES",
    "usage_per_part": "4",
    "life_limit": "400",
    "limit_basis": "[참고] 알루미늄 M6 탭 수백~500구멍 (OSG M6 500구멍 × 0.8)",
    "deduct_qty_per_change": "1"
   }
  ],
  "items": [
   {
    "item_no": "TL-EM10",
    "category": "TOOL",
    "item_name": "엔드밀 Ø10",
    "unit": "개",
    "owner_role": "SUP",
    "safety_stock": "9",
    "product_note": ""
   },
   {
    "item_no": "TL-DR50",
    "category": "TOOL",
    "item_name": "드릴 Ø5.0 (M6 탭 아랫구멍)",
    "unit": "개",
    "owner_role": "SUP",
    "safety_stock": "5",
    "product_note": ""
   },
   {
    "item_no": "TL-TAP6",
    "category": "TOOL",
    "item_name": "M6 탭",
    "unit": "개",
    "owner_role": "SUP",
    "safety_stock": "8",
    "product_note": ""
   },
   {
    "item_no": "TL-BB45",
    "category": "TOOL",
    "item_name": "보링바 인서트",
    "unit": "개",
    "owner_role": "SUP",
    "safety_stock": "4",
    "product_note": ""
   },
   {
    "item_no": "TL-FM50",
    "category": "TOOL",
    "item_name": "페이스밀 인서트",
    "unit": "개",
    "owner_role": "SUP",
    "safety_stock": "14",
    "product_note": ""
   },
   {
    "item_no": "CS-WLUB",
    "category": "CONSUMABLE",
    "item_name": "축 윤활유",
    "unit": "L",
    "owner_role": "MNT",
    "safety_stock": "4",
    "product_note": "Haas 축 윤활유 (1 gallon 통, 탱크 약 0.95 L)"
   },
   {
    "item_no": "CS-COOL",
    "category": "CONSUMABLE",
    "item_name": "절삭유 원액",
    "unit": "L",
    "owner_role": "MNT",
    "safety_stock": "20",
    "product_note": "TRIM SC538 (Master Fluid Solutions, 반합성, 20 L 통)"
   },
   {
    "item_no": "CS-CFLT",
    "category": "CONSUMABLE",
    "item_name": "절삭유 필터",
    "unit": "개",
    "owner_role": "MNT",
    "safety_stock": "2",
    "product_note": "VF-2 표준 절삭유 필터"
   },
   {
    "item_no": "CS-AFLT",
    "category": "CONSUMABLE",
    "item_name": "공기 필터",
    "unit": "개",
    "owner_role": "MNT",
    "safety_stock": "2",
    "product_note": "VF-2 공기/물 분리기 필터"
   },
   {
    "item_no": "CS-SLUB",
    "category": "CONSUMABLE",
    "item_name": "주축 윤활유",
    "unit": "L",
    "owner_role": "MNT",
    "safety_stock": "4",
    "product_note": "Mobil 1 0W-20 (128 oz 통)"
   },
   {
    "item_no": "CS-GRS",
    "category": "CONSUMABLE",
    "item_name": "그리스",
    "unit": "개",
    "owner_role": "MNT",
    "safety_stock": "2",
    "product_note": "Mobil Grease XHP 222 (14 oz 카트리지) — VF-2·SAW-01 앞 바이스·OP-40 텀블러 공용"
   },
   {
    "item_no": "RM-6061",
    "category": "MATERIAL",
    "item_name": "6061-T6 봉재",
    "unit": "개분",
    "owner_role": "SUP",
    "safety_stock": "200",
    "product_note": "압출 평각봉 19.05 × 57.15 mm, 12 ft (3,658 mm), ASTM B221 — 봉 1개 = 약 23개분"
   },
   {
    "item_no": "FG-BRK-A100",
    "category": "FINISHED",
    "item_name": "BRK-A100 완제품",
    "unit": "개",
    "owner_role": "SUP",
    "safety_stock": "",
    "product_note": ""
   }
  ],
  "inspection_items": [
   {
    "product_code": "BRK-A100",
    "item_seq": "1",
    "item_name": "부싱 압입 구멍 지름",
    "spec_text": "Ø45 H7 (+0.025 / 0 mm)",
    "nominal": "45.000",
    "lsl": "45.000",
    "usl": "45.025",
    "method": "CMM",
    "char_class": "SPECIAL",
    "cpk_min": "1.67",
    "in_sampling": "true",
    "enhanced_extension": "위·중간·아래 3단 높이에서 측정 (기록만, 판정은 이 항목 기준)",
    "is_full_check_by_cpk": "false"
   },
   {
    "product_code": "BRK-A100",
    "item_seq": "2",
    "item_name": "전체 길이",
    "spec_text": "150 ± 0.5 mm",
    "nominal": "150.0",
    "lsl": "149.5",
    "usl": "150.5",
    "method": "CMM",
    "char_class": "GENERAL",
    "cpk_min": "1.33",
    "in_sampling": "true",
    "enhanced_extension": "",
    "is_full_check_by_cpk": "false"
   },
   {
    "product_code": "BRK-A100",
    "item_seq": "3",
    "item_name": "두께",
    "spec_text": "12 ± 0.2 mm",
    "nominal": "12.0",
    "lsl": "11.8",
    "usl": "12.2",
    "method": "CMM",
    "char_class": "GENERAL",
    "cpk_min": "1.33",
    "in_sampling": "true",
    "enhanced_extension": "",
    "is_full_check_by_cpk": "false"
   },
   {
    "product_code": "BRK-A100",
    "item_seq": "4",
    "item_name": "구멍 간 거리",
    "spec_text": "± 0.1 mm (도면 값과의 차이로 기록)",
    "nominal": "0.0",
    "lsl": "-0.1",
    "usl": "0.1",
    "method": "CMM",
    "char_class": "GENERAL",
    "cpk_min": "1.33",
    "in_sampling": "true",
    "enhanced_extension": "모든 구멍의 구멍 간 거리",
    "is_full_check_by_cpk": "false"
   },
   {
    "product_code": "BRK-A100",
    "item_seq": "5",
    "item_name": "평면도 (부착면)",
    "spec_text": "0.05 mm 이하",
    "nominal": "",
    "lsl": "",
    "usl": "0.05",
    "method": "CMM",
    "char_class": "GENERAL",
    "cpk_min": "1.33",
    "in_sampling": "true",
    "enhanced_extension": "",
    "is_full_check_by_cpk": "false"
   },
   {
    "product_code": "BRK-A100",
    "item_seq": "6",
    "item_name": "M6 나사 (6H)",
    "spec_text": "통과 게이지가 끝까지 들어가고, 정지 게이지는 2회전 넘게 들어가지 않음",
    "nominal": "",
    "lsl": "",
    "usl": "",
    "method": "GAUGE",
    "char_class": "GENERAL",
    "cpk_min": "",
    "in_sampling": "true",
    "enhanced_extension": "",
    "is_full_check_by_cpk": "false"
   },
   {
    "product_code": "BRK-A100",
    "item_seq": "7",
    "item_name": "외관",
    "spec_text": "버·찍힘·구성인선 흔적(뜯긴 면)이 없음",
    "nominal": "",
    "lsl": "",
    "usl": "",
    "method": "VISUAL",
    "char_class": "GENERAL",
    "cpk_min": "",
    "in_sampling": "false",
    "enhanced_extension": "확대경으로 구성인선 흔적 확인",
    "is_full_check_by_cpk": "false"
   },
   {
    "product_code": "BRK-A100",
    "item_seq": "8",
    "item_name": "폭",
    "spec_text": "55 ± 0.3 mm",
    "nominal": "55.0",
    "lsl": "54.7",
    "usl": "55.3",
    "method": "CMM",
    "char_class": "GENERAL",
    "cpk_min": "1.33",
    "in_sampling": "true",
    "enhanced_extension": "",
    "is_full_check_by_cpk": "false"
   }
  ],
  "defect_codes": [
   {
    "defect_code": "DIM-01",
    "defect_name": "치수 큼 (상한 넘음)",
    "related_items": "1~3, 8",
    "grade": "MAJOR",
    "grade_rule": "1번(부싱 압입 구멍, 특별 특성)이면 치명, 나머지 중",
    "common_cause": "공구 마모, 공구 오프셋"
   },
   {
    "defect_code": "DIM-02",
    "defect_name": "치수 작음 (하한 밑)",
    "related_items": "1~3, 8",
    "grade": "MAJOR",
    "grade_rule": "1번(부싱 압입 구멍, 특별 특성)이면 치명, 나머지 중",
    "common_cause": "공구 오프셋, 충돌 뒤 위치 틀어짐"
   },
   {
    "defect_code": "DIM-03",
    "defect_name": "구멍 간 거리 벗어남",
    "related_items": "4",
    "grade": "MAJOR",
    "grade_rule": "",
    "common_cause": "공작물 오프셋, 고정 불량"
   },
   {
    "defect_code": "DIM-04",
    "defect_name": "평면도 벗어남",
    "related_items": "5",
    "grade": "MAJOR",
    "grade_rule": "",
    "common_cause": "고정 변형, 떨림"
   },
   {
    "defect_code": "THR-01",
    "defect_name": "나사 통과 게이지 안 들어감",
    "related_items": "6",
    "grade": "MAJOR",
    "grade_rule": "",
    "common_cause": "탭 마모·파손, 기초 구멍 작음"
   },
   {
    "defect_code": "THR-02",
    "defect_name": "나사 정지 게이지 2회전 넘게 들어감",
    "related_items": "6",
    "grade": "MAJOR",
    "grade_rule": "",
    "common_cause": "탭 크기·흔들림"
   },
   {
    "defect_code": "SUR-01",
    "defect_name": "버 남음",
    "related_items": "7",
    "grade": "MINOR",
    "grade_rule": "",
    "common_cause": "OP-40 디버링 부족"
   },
   {
    "defect_code": "SUR-02",
    "defect_name": "구성인선 흔적 (뜯긴 면)",
    "related_items": "7",
    "grade": "MINOR",
    "grade_rule": "치수에 영향 있으면 중",
    "common_cause": "알루미늄이 날 끝에 붙는 구성인선"
   },
   {
    "defect_code": "SUR-03",
    "defect_name": "찍힘·긁힘",
    "related_items": "7",
    "grade": "MINOR",
    "grade_rule": "",
    "common_cause": "운반·세척 중 부딪힘"
   },
   {
    "defect_code": "MAT-01",
    "defect_name": "원자재 성적서 불일치",
    "related_items": "§7 (원자재 입고 검사)",
    "grade": "MAJOR",
    "grade_rule": "",
    "common_cause": "로트 코드·성분 불일치"
   }
  ],
  "sensors": [
   {
    "sensor_code": "SpindleLoadPct",
    "sensor_name": "주축 부하",
    "unit": "%",
    "normal_min": "0",
    "normal_max": "185",
    "normal_median": "38",
    "linked_alarm_code": "174"
   },
   {
    "sensor_code": "SpindleMotorTemp",
    "sensor_name": "주축 모터 온도",
    "unit": "℃",
    "normal_min": "28",
    "normal_max": "42",
    "normal_median": "",
    "linked_alarm_code": "254"
   },
   {
    "sensor_code": "AirPressure",
    "sensor_name": "공기 압력",
    "unit": "psi",
    "normal_min": "100",
    "normal_max": "110",
    "normal_median": "105.3",
    "linked_alarm_code": "120"
   },
   {
    "sensor_code": "Xload",
    "sensor_name": "X축 부하",
    "unit": "%",
    "normal_min": "0",
    "normal_max": "65",
    "normal_median": "",
    "linked_alarm_code": "108"
   },
   {
    "sensor_code": "Yload",
    "sensor_name": "Y축 부하",
    "unit": "%",
    "normal_min": "0",
    "normal_max": "65",
    "normal_median": "",
    "linked_alarm_code": "108"
   },
   {
    "sensor_code": "Zload",
    "sensor_name": "Z축 부하",
    "unit": "%",
    "normal_min": "0",
    "normal_max": "65",
    "normal_median": "",
    "linked_alarm_code": "108"
   },
   {
    "sensor_code": "DcVolt",
    "sensor_name": "직류 버스 전압",
    "unit": "V",
    "normal_min": "300",
    "normal_max": "330",
    "normal_median": "317",
    "linked_alarm_code": ""
   }
  ],
  "rules": [
   {
    "rule_code": "ALARM_STOP",
    "rule_name": "알람 발생 (정지)",
    "condition_text": "정지 등급 알람 발생 → 로그인한 전원에게 중앙 팝업 (처리 책임은 그 설비 OPR·MNT)",
    "importance": "URGENT",
    "delivery_kind": "POPUP",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "ALARM_WARN",
    "rule_name": "알람 발생 (주의)",
    "condition_text": "주의 등급 알람 발생",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "ALARM_GUIDE",
    "rule_name": "알람 발생 (조작 안내)",
    "condition_text": "조작 안내 등급 알람 발생",
    "importance": "INFO",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "REPEAT_ALARM",
    "rule_name": "반복 알람 (1단계)",
    "condition_text": "같은 설비·같은 알람(주의·정지 등급)이 7일 안에 3번 이상 → MNT·SUP",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "REPEAT_ALARM_2",
    "rule_name": "반복 알람 2단계 (지난 조치 효과 없음)",
    "condition_text": "1단계 조치 계획을 저장한 뒤 7일 안에 같은 설비·같은 알람이 다시 남 → MNT·SUP",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "CAUSE_CHECK_REQUEST",
    "rule_name": "원인 점검 요청 (다른 공정)",
    "condition_text": "다른 공정의 반복 알람 2단계 → MNT에게 원인 점검 요청",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "TARGET_RISK",
    "rule_name": "목표 미달 위험",
    "condition_text": "예측 실적 < 총 목표(목표 + 이월)의 90%. 교대 시작 1시간 뒤부터 판단, 교대에 처음 1번",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "BOTTLENECK_MOVE",
    "rule_name": "병목 발생·이동",
    "condition_text": "병목 공정(또는 원인)이 바뀜. 관련 정보 = DOC-07 §7.5의 해당 원인 조치 줄",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "WIP_WARN",
    "rule_name": "재공 경고",
    "condition_text": "공정 사이 재공이 경고 기준(wip_buffer.warn_over_qty) 초과 — 20개, WIP-20-30은 한도 30 도달(OP-20 막힘). WIP-30-40 제외. 재공 위치마다 교대에 처음 1번",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "LOT_DUE_RISK",
    "rule_name": "로트 납기 지연 위험",
    "condition_text": "로트 예상 완료 시각 > 납기",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "STOCK_LOW",
    "rule_name": "재고 부족",
    "condition_text": "재고 수량 ≤ 안전 재고 → 그 품목의 관리 역할 + MGR",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "PM_DUE_SOON",
    "rule_name": "예방 정비 기한 하루 전",
    "condition_text": "기한 하루 전 (주 1회 이상 주기 항목만 — 매일·교대 점검은 점검표)",
    "importance": "INFO",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "PM_OVERDUE",
    "rule_name": "예방 정비 기한 넘김",
    "condition_text": "기한 넘김 (주 1회 이상 주기 항목만)",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "TOOL_LIFE_90",
    "rule_name": "공구 수명",
    "condition_text": "사용률 90%",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "APPROVAL_WAIT_30M",
    "rule_name": "승인 대기",
    "condition_text": "작업지시서 승인 대기 30분 이상",
    "importance": "INFO",
    "delivery_kind": "BUBBLE",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "APPROVAL_WAIT_2H",
    "rule_name": "승인 대기",
    "condition_text": "작업지시서 승인 대기 2시간 이상",
    "importance": "CAUTION",
    "delivery_kind": "BUBBLE",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "WO_ASSIGNED",
    "rule_name": "작업지시서 배정",
    "condition_text": "작업지시서가 승인됨 → 담당 MNT",
    "importance": "INFO",
    "delivery_kind": "BUBBLE",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "WO_DRAFT_READY",
    "rule_name": "작업지시서 초안 검토",
    "condition_text": "작업지시서 AI비서 초안이 생길 때 → 그 설비 MNT",
    "importance": "INFO",
    "delivery_kind": "BUBBLE",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "DAILY_REPORT_PENDING",
    "rule_name": "일일 보고서 확정 요청",
    "condition_text": "일일 보고서 AI비서 초안이 생길 때 (야간 교대 보고서 확정 즉시, 늦어도 06:00) → MGR",
    "importance": "INFO",
    "delivery_kind": "BUBBLE",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "DOC_REVISED",
    "rule_name": "문서 수정",
    "condition_text": "작업지시서 수정 → 담당 보전원, 보고서 수정 → 관리자, 사내 문서 개정 → 관련 역할 전체",
    "importance": "INFO",
    "delivery_kind": "BUBBLE",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "SPC_OUT",
    "rule_name": "관리도 이상",
    "condition_text": "점 1개가 +3σ 위 또는 −3σ 아래 → 반장",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "SHIFT_REPORT_PENDING",
    "rule_name": "교대 보고서 확정 요청",
    "condition_text": "교대 끝(주간 17:00, 야간 05:00) 교대 보고서 AI비서 초안이 생길 때 → 그 교대 반장",
    "importance": "INFO",
    "delivery_kind": "BUBBLE",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "CMM_FILE_ERROR",
    "rule_name": "CMM 결과 파일 오류",
    "condition_text": "결과 파일을 읽지 못함 또는 확인 필요 → 작업자·반장",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "CMM_JUDGE_MISMATCH",
    "rule_name": "CMM 판정 불일치",
    "condition_text": "측정기 판정 ≠ 플랫폼 판정 → 반장",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   },
   {
    "rule_code": "CMM_NO_RESULT",
    "rule_name": "CMM 결과 미수신",
    "condition_text": "측정 시작 뒤 정한 시간 안에 결과 파일이 오지 않음 → 작업자·반장 (시간은 [선택 필요: 기술 회의])",
    "importance": "CAUTION",
    "delivery_kind": "LIST",
    "is_enabled": "true",
    "updated_by": "",
    "updated_at": ""
   }
  ],
  "docs": [
   {
    "doc_no": "DOC-01",
    "doc_kind": "MANUAL_DOC",
    "doc_name": "공정별 운영 매뉴얼",
    "current_rev": "Rev.9",
    "rev_date": "2026-10-14",
    "status": "APPROVED",
    "approved_by": "U12",
    "approved_at": "2026-10-14T09:00:00+09:00",
    "is_search_target": "true",
    "file_ref": "가상사내문서/DOC-01_공정별운영매뉴얼.md"
   },
   {
    "doc_no": "DOC-02",
    "doc_kind": "MANUAL_DOC",
    "doc_name": "알람 코드집",
    "current_rev": "Rev.2",
    "rev_date": "2026-10-13",
    "status": "APPROVED",
    "approved_by": "U12",
    "approved_at": "2026-10-13T09:00:00+09:00",
    "is_search_target": "true",
    "file_ref": "가상사내문서/DOC-02_알람코드집.md"
   },
   {
    "doc_no": "DOC-03",
    "doc_kind": "MANUAL_DOC",
    "doc_name": "고장 대응 매뉴얼",
    "current_rev": "Rev.2",
    "rev_date": "2026-10-13",
    "status": "APPROVED",
    "approved_by": "U12",
    "approved_at": "2026-10-13T09:00:00+09:00",
    "is_search_target": "true",
    "file_ref": "가상사내문서/DOC-03_고장대응매뉴얼.md"
   },
   {
    "doc_no": "DOC-04",
    "doc_kind": "MANUAL_DOC",
    "doc_name": "예방 정비 기준서",
    "current_rev": "Rev.2",
    "rev_date": "2026-10-10",
    "status": "APPROVED",
    "approved_by": "U12",
    "approved_at": "2026-10-10T09:00:00+09:00",
    "is_search_target": "true",
    "file_ref": "가상사내문서/DOC-04_예방정비기준서.md"
   },
   {
    "doc_no": "DOC-05",
    "doc_kind": "MANUAL_DOC",
    "doc_name": "안전 작업 기준서",
    "current_rev": "Rev.2",
    "rev_date": "2026-10-10",
    "status": "APPROVED",
    "approved_by": "U12",
    "approved_at": "2026-10-10T09:00:00+09:00",
    "is_search_target": "true",
    "file_ref": "가상사내문서/DOC-05_안전작업기준서.md"
   },
   {
    "doc_no": "DOC-06",
    "doc_kind": "MANUAL_DOC",
    "doc_name": "검사 기준서",
    "current_rev": "Rev.3",
    "rev_date": "2026-10-13",
    "status": "APPROVED",
    "approved_by": "U12",
    "approved_at": "2026-10-13T09:00:00+09:00",
    "is_search_target": "true",
    "file_ref": "가상사내문서/DOC-06_검사기준서.md"
   },
   {
    "doc_no": "DOC-07",
    "doc_kind": "MANUAL_DOC",
    "doc_name": "설비 데이터·지표 정의서",
    "current_rev": "Rev.10",
    "rev_date": "2026-10-14",
    "status": "APPROVED",
    "approved_by": "U12",
    "approved_at": "2026-10-14T09:00:00+09:00",
    "is_search_target": "true",
    "file_ref": "가상사내문서/DOC-07_설비데이터지표정의서.md"
   },
   {
    "doc_no": "GLOSSARY",
    "doc_kind": "GLOSSARY",
    "doc_name": "용어집",
    "current_rev": "Rev.4",
    "rev_date": "2026-10-13",
    "status": "APPROVED",
    "approved_by": "U12",
    "approved_at": "2026-10-13T09:00:00+09:00",
    "is_search_target": "true",
    "file_ref": "가상사내문서/00_용어집.md"
   }
  ],
  "downtime": [
   {
    "reason_code": "F01",
    "reason_group": "FAILURE",
    "reason_name": "서보·앰프",
    "usual_state": "DOWN",
    "six_loss": "고장 정지 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "F02",
    "reason_group": "FAILURE",
    "reason_name": "주축",
    "usual_state": "DOWN",
    "six_loss": "고장 정지 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "F03",
    "reason_group": "FAILURE",
    "reason_name": "공구 교환장치",
    "usual_state": "DOWN",
    "six_loss": "고장 정지 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "F04",
    "reason_group": "FAILURE",
    "reason_name": "윤활",
    "usual_state": "DOWN",
    "six_loss": "고장 정지 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "F05",
    "reason_group": "FAILURE",
    "reason_name": "공압",
    "usual_state": "DOWN",
    "six_loss": "고장 정지 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "F06",
    "reason_group": "FAILURE",
    "reason_name": "절삭유",
    "usual_state": "DOWN",
    "six_loss": "고장 정지 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "M01",
    "reason_group": "MATERIALS",
    "reason_name": "소재 대기",
    "usual_state": "IDLE",
    "six_loss": "6대 로스 밖 (설비 밖 원인)",
    "is_loss": "true"
   },
   {
    "reason_code": "M02",
    "reason_group": "MATERIALS",
    "reason_name": "앞 공정 대기",
    "usual_state": "IDLE",
    "six_loss": "흐름 손실 (병목의 영향)",
    "is_loss": "true"
   },
   {
    "reason_code": "M03",
    "reason_group": "MATERIALS",
    "reason_name": "뒤 공정 막힘",
    "usual_state": "BLOCKED",
    "six_loss": "흐름 손실 (병목의 영향)",
    "is_loss": "true"
   },
   {
    "reason_code": "S01",
    "reason_group": "SETUP",
    "reason_name": "작업지시 교체 (로트 교체)",
    "usual_state": "SETUP",
    "six_loss": "준비 교체 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "S02",
    "reason_group": "SETUP",
    "reason_name": "공구 교체",
    "usual_state": "SETUP",
    "six_loss": "준비 교체 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "S03",
    "reason_group": "SETUP",
    "reason_name": "초품 검사",
    "usual_state": "SETUP",
    "six_loss": "준비 교체 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "S04",
    "reason_group": "SETUP",
    "reason_name": "교대 시작·끝 점검",
    "usual_state": "SETUP",
    "six_loss": "준비 교체 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "O01",
    "reason_group": "OPERATION",
    "reason_name": "프로그램 오류",
    "usual_state": "IDLE",
    "six_loss": "순간 정지 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "O02",
    "reason_group": "OPERATION",
    "reason_name": "모드 오류",
    "usual_state": "IDLE",
    "six_loss": "순간 정지 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "O03",
    "reason_group": "OPERATION",
    "reason_name": "도어 열림",
    "usual_state": "IDLE",
    "six_loss": "순간 정지 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "O04",
    "reason_group": "OPERATION",
    "reason_name": "부품 교체 대기",
    "usual_state": "IDLE",
    "six_loss": "순간 정지 로스",
    "is_loss": "true"
   },
   {
    "reason_code": "P01",
    "reason_group": "PLANNED",
    "reason_name": "예방 정비",
    "usual_state": "MAINT",
    "six_loss": "계획 정지 (손실 아님)",
    "is_loss": "false"
   },
   {
    "reason_code": "P02",
    "reason_group": "PLANNED",
    "reason_name": "휴식",
    "usual_state": "IDLE",
    "six_loss": "계획 가동 시간 밖",
    "is_loss": "false"
   },
   {
    "reason_code": "P03",
    "reason_group": "PLANNED",
    "reason_name": "계획 없음",
    "usual_state": "IDLE",
    "six_loss": "계획 가동 시간 밖",
    "is_loss": "false"
   }
  ],
  "pm_tasks": [
   {
    "pm_task_id": "PM-VF2-01-2.1-01",
    "equipment_id": "VF2-01",
    "doc04_section": "2.1",
    "area": "외함",
    "item_name": "창(유리) 손상 점검",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.1-02",
    "equipment_id": "VF2-01",
    "doc04_section": "2.1",
    "area": "외함",
    "item_name": "도어 인터록 작동 점검",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.1-03",
    "equipment_id": "VF2-01",
    "doc04_section": "2.1",
    "area": "교대 시작",
    "item_name": "절삭유 양 확인",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "CS-COOL",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.1-04",
    "equipment_id": "VF2-01",
    "doc04_section": "2.1",
    "area": "교대 시작",
    "item_name": "공기 압력 확인",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.1-05",
    "equipment_id": "VF2-01",
    "doc04_section": "2.1",
    "area": "교대 시작",
    "item_name": "공기 배관 물 빼기",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.1-06",
    "equipment_id": "VF2-01",
    "doc04_section": "2.1",
    "area": "공구",
    "item_name": "공구 홀더·풀 스터드·테이퍼 손상 점검",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.1-07",
    "equipment_id": "VF2-01",
    "doc04_section": "2.1",
    "area": "교대 끝",
    "item_name": "웨이 커버 칩 청소, 탱크 위 칩 필터 확인",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.2-01",
    "equipment_id": "VF2-01",
    "doc04_section": "2.2",
    "area": "공구 교환장치",
    "item_name": "공구 교환장치의 칩 청소",
    "cycle_code": "WEEKLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.2-02",
    "equipment_id": "VF2-01",
    "doc04_section": "2.2",
    "area": "공압",
    "item_name": "주축 공기 조절기 압력 점검",
    "cycle_code": "WEEKLY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.2-03",
    "equipment_id": "VF2-01",
    "doc04_section": "2.2",
    "area": "절삭유",
    "item_name": "절삭유 양 점검",
    "cycle_code": "WEEKLY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "CS-COOL",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.2-04",
    "equipment_id": "VF2-01",
    "doc04_section": "2.2",
    "area": "절삭유",
    "item_name": "절삭유 농도 점검, 혼합·정비 기록지 작성",
    "cycle_code": "WEEKLY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "CS-COOL",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.2-05",
    "equipment_id": "VF2-01",
    "doc04_section": "2.2",
    "area": "절삭유",
    "item_name": "혼입유 제거, 필터 칩 제거",
    "cycle_code": "WEEKLY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.3-01",
    "equipment_id": "VF2-01",
    "doc04_section": "2.3",
    "area": "축 윤활",
    "item_name": "윤활유 저장소 양 점검·보충",
    "cycle_code": "MONTHLY",
    "lockout_level": "TWO_POINT",
    "default_role": "MNT",
    "default_item_no": "CS-WLUB",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.3-02",
    "equipment_id": "VF2-01",
    "doc04_section": "2.3",
    "area": "전기함",
    "item_name": "벡터 드라이브 환기구·필터 청소",
    "cycle_code": "MONTHLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.3-03",
    "equipment_id": "VF2-01",
    "doc04_section": "2.3",
    "area": "외함",
    "item_name": "웨이 커버 점검·윤활",
    "cycle_code": "MONTHLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "CS-GRS",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.3-04",
    "equipment_id": "VF2-01",
    "doc04_section": "2.3",
    "area": "공구 교환장치",
    "item_name": "모터와 근접 센서 점검",
    "cycle_code": "MONTHLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.3-05",
    "equipment_id": "VF2-01",
    "doc04_section": "2.3",
    "area": "공구 교환장치",
    "item_name": "가이드 레일 그리스 주입",
    "cycle_code": "MONTHLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "CS-GRS",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.3-06",
    "equipment_id": "VF2-01",
    "doc04_section": "2.3",
    "area": "공구 교환장치",
    "item_name": "공구 빼기 핑거 그리스 주입",
    "cycle_code": "MONTHLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "CS-GRS",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.3-07",
    "equipment_id": "VF2-01",
    "doc04_section": "2.3",
    "area": "주축 윤활",
    "item_name": "주축 윤활 탱크 양 점검",
    "cycle_code": "MONTHLY",
    "lockout_level": "TWO_POINT",
    "default_role": "MNT",
    "default_item_no": "CS-SLUB",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.3-08",
    "equipment_id": "VF2-01",
    "doc04_section": "2.3",
    "area": "주축",
    "item_name": "주축 테이퍼 점검",
    "cycle_code": "MONTHLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.5-01",
    "equipment_id": "VF2-01",
    "doc04_section": "2.5",
    "area": "축 윤활",
    "item_name": "호스 갈라짐 점검",
    "cycle_code": "HALF_YEAR",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.5-02",
    "equipment_id": "VF2-01",
    "doc04_section": "2.5",
    "area": "축 윤활",
    "item_name": "축 윤활 시험 실시",
    "cycle_code": "HALF_YEAR",
    "lockout_level": "NONE",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.5-03",
    "equipment_id": "VF2-01",
    "doc04_section": "2.5",
    "area": "공압",
    "item_name": "호스 갈라짐 점검",
    "cycle_code": "HALF_YEAR",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.5-04",
    "equipment_id": "VF2-01",
    "doc04_section": "2.5",
    "area": "절삭유",
    "item_name": "절삭유 탱크 완전 청소, 절삭유 교체",
    "cycle_code": "HALF_YEAR",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "CS-COOL",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.5-05",
    "equipment_id": "VF2-01",
    "doc04_section": "2.5",
    "area": "절삭유",
    "item_name": "표준 절삭유 필터 청소 (+ 교체)",
    "cycle_code": "HALF_YEAR",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "CS-CFLT",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.5-06",
    "equipment_id": "VF2-01",
    "doc04_section": "2.5",
    "area": "주축 윤활",
    "item_name": "주축 윤활 시험 실시",
    "cycle_code": "HALF_YEAR",
    "lockout_level": "NONE",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.6-01",
    "equipment_id": "VF2-01",
    "doc04_section": "2.6",
    "area": "공압",
    "item_name": "공기 퍼지 솔레노이드 청소",
    "cycle_code": "YEARLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.6-02",
    "equipment_id": "VF2-01",
    "doc04_section": "2.6",
    "area": "주축",
    "item_name": "주축 드로바 힘 측정",
    "cycle_code": "YEARLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.6-03",
    "equipment_id": "VF2-01",
    "doc04_section": "2.6",
    "area": "공압",
    "item_name": "공기 필터 교체",
    "cycle_code": "YEARLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "CS-AFLT",
    "on_calendar": "true",
    "source_tag": "REFERENCE"
   },
   {
    "pm_task_id": "PM-VF2-01-2.7-01",
    "equipment_id": "VF2-01",
    "doc04_section": "2.7",
    "area": "절삭유",
    "item_name": "필터 스크린 청소",
    "cycle_code": "AS_REQUIRED",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.7-02",
    "equipment_id": "VF2-01",
    "doc04_section": "2.7",
    "area": "주축",
    "item_name": "주축 테이퍼 청소·윤활",
    "cycle_code": "AS_REQUIRED",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-01-2.7-03",
    "equipment_id": "VF2-01",
    "doc04_section": "2.7",
    "area": "공구",
    "item_name": "풀 스터드 그리스 바르기",
    "cycle_code": "AS_REQUIRED",
    "lockout_level": "NONE",
    "default_role": "MNT",
    "default_item_no": "CS-GRS",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.1-01",
    "equipment_id": "VF2-02",
    "doc04_section": "2.1",
    "area": "외함",
    "item_name": "창(유리) 손상 점검",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.1-02",
    "equipment_id": "VF2-02",
    "doc04_section": "2.1",
    "area": "외함",
    "item_name": "도어 인터록 작동 점검",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.1-03",
    "equipment_id": "VF2-02",
    "doc04_section": "2.1",
    "area": "교대 시작",
    "item_name": "절삭유 양 확인",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "CS-COOL",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.1-04",
    "equipment_id": "VF2-02",
    "doc04_section": "2.1",
    "area": "교대 시작",
    "item_name": "공기 압력 확인",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.1-05",
    "equipment_id": "VF2-02",
    "doc04_section": "2.1",
    "area": "교대 시작",
    "item_name": "공기 배관 물 빼기",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.1-06",
    "equipment_id": "VF2-02",
    "doc04_section": "2.1",
    "area": "공구",
    "item_name": "공구 홀더·풀 스터드·테이퍼 손상 점검",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.1-07",
    "equipment_id": "VF2-02",
    "doc04_section": "2.1",
    "area": "교대 끝",
    "item_name": "웨이 커버 칩 청소, 탱크 위 칩 필터 확인",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.2-01",
    "equipment_id": "VF2-02",
    "doc04_section": "2.2",
    "area": "공구 교환장치",
    "item_name": "공구 교환장치의 칩 청소",
    "cycle_code": "WEEKLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.2-02",
    "equipment_id": "VF2-02",
    "doc04_section": "2.2",
    "area": "공압",
    "item_name": "주축 공기 조절기 압력 점검",
    "cycle_code": "WEEKLY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.2-03",
    "equipment_id": "VF2-02",
    "doc04_section": "2.2",
    "area": "절삭유",
    "item_name": "절삭유 양 점검",
    "cycle_code": "WEEKLY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "CS-COOL",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.2-04",
    "equipment_id": "VF2-02",
    "doc04_section": "2.2",
    "area": "절삭유",
    "item_name": "절삭유 농도 점검, 혼합·정비 기록지 작성",
    "cycle_code": "WEEKLY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "CS-COOL",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.2-05",
    "equipment_id": "VF2-02",
    "doc04_section": "2.2",
    "area": "절삭유",
    "item_name": "혼입유 제거, 필터 칩 제거",
    "cycle_code": "WEEKLY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.3-01",
    "equipment_id": "VF2-02",
    "doc04_section": "2.3",
    "area": "축 윤활",
    "item_name": "윤활유 저장소 양 점검·보충",
    "cycle_code": "MONTHLY",
    "lockout_level": "TWO_POINT",
    "default_role": "MNT",
    "default_item_no": "CS-WLUB",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.3-02",
    "equipment_id": "VF2-02",
    "doc04_section": "2.3",
    "area": "전기함",
    "item_name": "벡터 드라이브 환기구·필터 청소",
    "cycle_code": "MONTHLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.3-03",
    "equipment_id": "VF2-02",
    "doc04_section": "2.3",
    "area": "외함",
    "item_name": "웨이 커버 점검·윤활",
    "cycle_code": "MONTHLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "CS-GRS",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.3-04",
    "equipment_id": "VF2-02",
    "doc04_section": "2.3",
    "area": "공구 교환장치",
    "item_name": "모터와 근접 센서 점검",
    "cycle_code": "MONTHLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.3-05",
    "equipment_id": "VF2-02",
    "doc04_section": "2.3",
    "area": "공구 교환장치",
    "item_name": "가이드 레일 그리스 주입",
    "cycle_code": "MONTHLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "CS-GRS",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.3-06",
    "equipment_id": "VF2-02",
    "doc04_section": "2.3",
    "area": "공구 교환장치",
    "item_name": "공구 빼기 핑거 그리스 주입",
    "cycle_code": "MONTHLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "CS-GRS",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.3-07",
    "equipment_id": "VF2-02",
    "doc04_section": "2.3",
    "area": "주축 윤활",
    "item_name": "주축 윤활 탱크 양 점검",
    "cycle_code": "MONTHLY",
    "lockout_level": "TWO_POINT",
    "default_role": "MNT",
    "default_item_no": "CS-SLUB",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.3-08",
    "equipment_id": "VF2-02",
    "doc04_section": "2.3",
    "area": "주축",
    "item_name": "주축 테이퍼 점검",
    "cycle_code": "MONTHLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.5-01",
    "equipment_id": "VF2-02",
    "doc04_section": "2.5",
    "area": "축 윤활",
    "item_name": "호스 갈라짐 점검",
    "cycle_code": "HALF_YEAR",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.5-02",
    "equipment_id": "VF2-02",
    "doc04_section": "2.5",
    "area": "축 윤활",
    "item_name": "축 윤활 시험 실시",
    "cycle_code": "HALF_YEAR",
    "lockout_level": "NONE",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.5-03",
    "equipment_id": "VF2-02",
    "doc04_section": "2.5",
    "area": "공압",
    "item_name": "호스 갈라짐 점검",
    "cycle_code": "HALF_YEAR",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.5-04",
    "equipment_id": "VF2-02",
    "doc04_section": "2.5",
    "area": "절삭유",
    "item_name": "절삭유 탱크 완전 청소, 절삭유 교체",
    "cycle_code": "HALF_YEAR",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "CS-COOL",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.5-05",
    "equipment_id": "VF2-02",
    "doc04_section": "2.5",
    "area": "절삭유",
    "item_name": "표준 절삭유 필터 청소 (+ 교체)",
    "cycle_code": "HALF_YEAR",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "CS-CFLT",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.5-06",
    "equipment_id": "VF2-02",
    "doc04_section": "2.5",
    "area": "주축 윤활",
    "item_name": "주축 윤활 시험 실시",
    "cycle_code": "HALF_YEAR",
    "lockout_level": "NONE",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.6-01",
    "equipment_id": "VF2-02",
    "doc04_section": "2.6",
    "area": "공압",
    "item_name": "공기 퍼지 솔레노이드 청소",
    "cycle_code": "YEARLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.6-02",
    "equipment_id": "VF2-02",
    "doc04_section": "2.6",
    "area": "주축",
    "item_name": "주축 드로바 힘 측정",
    "cycle_code": "YEARLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.6-03",
    "equipment_id": "VF2-02",
    "doc04_section": "2.6",
    "area": "공압",
    "item_name": "공기 필터 교체",
    "cycle_code": "YEARLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "CS-AFLT",
    "on_calendar": "true",
    "source_tag": "REFERENCE"
   },
   {
    "pm_task_id": "PM-VF2-02-2.7-01",
    "equipment_id": "VF2-02",
    "doc04_section": "2.7",
    "area": "절삭유",
    "item_name": "필터 스크린 청소",
    "cycle_code": "AS_REQUIRED",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.7-02",
    "equipment_id": "VF2-02",
    "doc04_section": "2.7",
    "area": "주축",
    "item_name": "주축 테이퍼 청소·윤활",
    "cycle_code": "AS_REQUIRED",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-VF2-02-2.7-03",
    "equipment_id": "VF2-02",
    "doc04_section": "2.7",
    "area": "공구",
    "item_name": "풀 스터드 그리스 바르기",
    "cycle_code": "AS_REQUIRED",
    "lockout_level": "NONE",
    "default_role": "MNT",
    "default_item_no": "CS-GRS",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-SAW-01-3.1-01",
    "equipment_id": "SAW-01",
    "doc04_section": "3.1",
    "area": "",
    "item_name": "절단 구역 칩·찌꺼기 청소",
    "cycle_code": "DAILY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-SAW-01-3.1-02",
    "equipment_id": "SAW-01",
    "doc04_section": "3.1",
    "area": "",
    "item_name": "톱날 상태 점검",
    "cycle_code": "DAILY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-SAW-01-3.1-03",
    "equipment_id": "SAW-01",
    "doc04_section": "3.1",
    "area": "",
    "item_name": "가이드 레일 윤활유 레벨 점검·보충",
    "cycle_code": "WEEKLY",
    "lockout_level": "ONE_POINT",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REFERENCE"
   },
   {
    "pm_task_id": "PM-SAW-01-3.1-04",
    "equipment_id": "SAW-01",
    "doc04_section": "3.1",
    "area": "",
    "item_name": "기어박스 오일 / 유압유 레벨 점검",
    "cycle_code": "WEEKLY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-SAW-01-3.1-05",
    "equipment_id": "SAW-01",
    "doc04_section": "3.1",
    "area": "",
    "item_name": "앞 바이스 리니어 가이드 그리스 주입",
    "cycle_code": "MONTHLY",
    "lockout_level": "ONE_POINT",
    "default_role": "MNT",
    "default_item_no": "CS-GRS",
    "on_calendar": "true",
    "source_tag": "REFERENCE"
   },
   {
    "pm_task_id": "PM-SAW-01-3.1-06",
    "equipment_id": "SAW-01",
    "doc04_section": "3.1",
    "area": "",
    "item_name": "공기 필터 교체, 유압유·기어 오일 교체",
    "cycle_code": "YEARLY",
    "lockout_level": "FULL",
    "default_role": "MNT",
    "default_item_no": "",
    "on_calendar": "false",
    "source_tag": "REAL"
   },
   {
    "pm_task_id": "PM-MIL-01-3.2-01",
    "equipment_id": "MIL-01",
    "doc04_section": "3.2",
    "area": "",
    "item_name": "윤활 레벨·습동면 점검",
    "cycle_code": "DAILY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "VIRTUAL"
   },
   {
    "pm_task_id": "PM-WSH-01-3.3-01",
    "equipment_id": "WSH-01",
    "doc04_section": "3.3",
    "area": "",
    "item_name": "텀블러 베어링 그리스 주입",
    "cycle_code": "EVERY_8H_USE",
    "lockout_level": "ONE_POINT",
    "default_role": "MNT",
    "default_item_no": "CS-GRS",
    "on_calendar": "true",
    "source_tag": "REFERENCE"
   },
   {
    "pm_task_id": "PM-WSH-01-3.3-02",
    "equipment_id": "WSH-01",
    "doc04_section": "3.3",
    "area": "",
    "item_name": "세척액 상태 점검",
    "cycle_code": "DAILY",
    "lockout_level": "UNPLUG",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "REFERENCE"
   },
   {
    "pm_task_id": "PM-CMM-01-3.4-01",
    "equipment_id": "CMM-01",
    "doc04_section": "3.4",
    "area": "",
    "item_name": "측정기 중간 점검 (기준물 측정)",
    "cycle_code": "WEEKLY",
    "lockout_level": "NONE",
    "default_role": "OPR",
    "default_item_no": "",
    "on_calendar": "true",
    "source_tag": "VIRTUAL"
   }
  ],
  "isolation": [
   {
    "isolation_point_id": "SAW-01-E1",
    "equipment_id": "SAW-01",
    "point_name": "SAW-01 주 차단기",
    "energy_type": "ELEC",
    "location": "주 차단기 문 안",
    "lock_method": "손잡이에 자물쇠 + 표지",
    "seq": "1"
   },
   {
    "isolation_point_id": "SAW-01-E2",
    "equipment_id": "SAW-01",
    "point_name": "SAW-01 공급 분전반 차단기",
    "energy_type": "ELEC_SUPPLY",
    "location": "공장 분전반",
    "lock_method": "분전반 차단기에 자물쇠 + 표지",
    "seq": "2"
   },
   {
    "isolation_point_id": "MIL-01-E1",
    "equipment_id": "MIL-01",
    "point_name": "MIL-01 주 차단기",
    "energy_type": "ELEC",
    "location": "제어반 문",
    "lock_method": "손잡이에 자물쇠 + 표지",
    "seq": "1"
   },
   {
    "isolation_point_id": "MIL-01-P1",
    "equipment_id": "MIL-01",
    "point_name": "MIL-01 공압 주 밸브",
    "energy_type": "AIR",
    "location": "공기 공급 입구",
    "lock_method": "밸브를 닫고 잠금 + 잔압 빼기",
    "seq": "2"
   },
   {
    "isolation_point_id": "MIL-01-E2",
    "equipment_id": "MIL-01",
    "point_name": "MIL-01 공급 분전반 차단기",
    "energy_type": "ELEC_SUPPLY",
    "location": "공장 분전반",
    "lock_method": "자물쇠 + 표지",
    "seq": "3"
   },
   {
    "isolation_point_id": "VF2-01-E1",
    "equipment_id": "VF2-01",
    "point_name": "VF2-01 주 차단기",
    "energy_type": "ELEC",
    "location": "기계 뒤쪽 제어반의 오른쪽 위",
    "lock_method": "주 차단기를 OFF로 두고 승인된 자물쇠와 안전 표지로 잠금",
    "seq": "1"
   },
   {
    "isolation_point_id": "VF2-01-P1",
    "equipment_id": "VF2-01",
    "point_name": "VF2-01 공압 주 밸브",
    "energy_type": "AIR",
    "location": "윤활 패널 공기 입구 앞 공급 배관",
    "lock_method": "밸브를 닫고 잠금 + 잔압 빼기",
    "seq": "2"
   },
   {
    "isolation_point_id": "VF2-01-E2",
    "equipment_id": "VF2-01",
    "point_name": "VF2-01 공급 분전반 차단기",
    "energy_type": "ELEC_SUPPLY",
    "location": "공장 분전반",
    "lock_method": "자물쇠 + 표지",
    "seq": "3"
   },
   {
    "isolation_point_id": "VF2-02-E1",
    "equipment_id": "VF2-02",
    "point_name": "VF2-02 주 차단기",
    "energy_type": "ELEC",
    "location": "기계 뒤쪽 제어반의 오른쪽 위",
    "lock_method": "주 차단기를 OFF로 두고 승인된 자물쇠와 안전 표지로 잠금",
    "seq": "1"
   },
   {
    "isolation_point_id": "VF2-02-P1",
    "equipment_id": "VF2-02",
    "point_name": "VF2-02 공압 주 밸브",
    "energy_type": "AIR",
    "location": "윤활 패널 공기 입구 앞 공급 배관",
    "lock_method": "밸브를 닫고 잠금 + 잔압 빼기",
    "seq": "2"
   },
   {
    "isolation_point_id": "VF2-02-E2",
    "equipment_id": "VF2-02",
    "point_name": "VF2-02 공급 분전반 차단기",
    "energy_type": "ELEC_SUPPLY",
    "location": "공장 분전반",
    "lock_method": "자물쇠 + 표지",
    "seq": "3"
   },
   {
    "isolation_point_id": "WSH-01-E1",
    "equipment_id": "WSH-01",
    "point_name": "WSH-01 세척기 전원 플러그",
    "energy_type": "ELEC",
    "location": "세척기 뒤 콘센트",
    "lock_method": "플러그를 뽑고 플러그 잠금 덮개 + 표지",
    "seq": "1"
   },
   {
    "isolation_point_id": "WSH-01-E2",
    "equipment_id": "WSH-01",
    "point_name": "WSH-01 진동 바렐 전원 차단기",
    "energy_type": "ELEC",
    "location": "진동 바렐 옆 차단기",
    "lock_method": "자물쇠 + 표지",
    "seq": "2"
   },
   {
    "isolation_point_id": "CMM-01-E1",
    "equipment_id": "CMM-01",
    "point_name": "CMM-01 주 전원 차단기",
    "energy_type": "ELEC",
    "location": "측정기 제어함",
    "lock_method": "자물쇠 + 표지",
    "seq": "1"
   },
   {
    "isolation_point_id": "CMM-01-P1",
    "equipment_id": "CMM-01",
    "point_name": "CMM-01 공압 주 밸브",
    "energy_type": "AIR",
    "location": "측정기 공기 공급 입구",
    "lock_method": "밸브를 닫고 잠금 + 잔압 빼기",
    "seq": "2"
   }
  ],
  "roles": [
   {
    "role_code": "OPR",
    "role_name": "현장 작업자"
   },
   {
    "role_code": "MNT",
    "role_name": "보전 담당자"
   },
   {
    "role_code": "SUP",
    "role_name": "라인 반장"
   },
   {
    "role_code": "MGR",
    "role_name": "공장 관리자"
   }
  ]
 }
} as const;
