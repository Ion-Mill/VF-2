# Handoff: Lot Trace (로트 추적) — 시안 6c "Sky Blue"

## Overview
공장 MOM 플랫폼의 **로트 추적 상세 화면**입니다. 한 생산 로트(LOT-2610-003-1)의 상태, 공정 진행, 같은 원자재에서 나온 로트 계보, 설비별 작업 시간표를 한 화면에서 보여줍니다. 밝은 배경, 단색 포인트(#5C7FFF), 높은 가독성이 핵심입니다.

## About the Design Files
`Lot Trace 6c.dc.html`은 **HTML로 만든 디자인 레퍼런스**입니다. 그대로 배포할 코드가 아니라 의도한 모양과 동작을 보여주는 프로토타입입니다. 대상 코드베이스(React/Next.js 등)의 기존 컴포넌트·스타일 방식으로 **다시 구현**해 주세요. 기존 환경이 없다면 React + CSS Modules(또는 Tailwind)를 권장합니다.
- 브라우저에서 열 때 같은 폴더의 `support.js`가 필요합니다(프로토타입 런타임 전용, 프로덕션에 포함하지 않음).
- 파일 안의 데이터(로트 번호, 시간, 수량)는 예시입니다. **알람(VF2-01 03:46–04:04)과 보류(CMM-01 04:48)는 표현 예시로 임의 배치한 값**이므로 실제 데이터로 대체하세요.

## Fidelity
**High-fidelity.** 색, 타이포, 간격, 라운드, 그림자, 호버 상태가 최종값입니다. 픽셀 단위로 재현해 주세요.

## 규칙: 그라데이션
- 페이지 배경에만 사용: `linear-gradient(180deg, #FFFFFF 0%, #F2F4FA 55%, #EAEEF7 100%)`
- **글씨, 데이터(막대·칩·버튼·진행 바)에는 그라데이션 금지.** 모두 단색.

## Layout
- 페이지: `min-height:100vh`, 하단 padding 64px. 콘텐츠 `max-width:1360px; margin:0 auto; padding:14px 32px 0`.
- 세로 스택(gap 18px): ① 헤더 → ② 로트 요약 카드 → ③ 검색·계보 카드 → ④ 설비별 시간표 카드.
- 카드 공통: `border-radius:24px; border:1px solid rgba(255,255,255,.95)`, 배경 흰색 반투명(0.92 / 0.78 / 0.82), 그림자 `inset 0 1px 0 #fff, 0 1px 2px rgba(16,24,40,.04), 0 18–24px 40–48px -24px rgba(40,36,90,.16–.18)`.

## Screens / Components

### ① 헤더 (padding 22px 32px 6px, 양끝 정렬)
- 로고 마크: 30×30, radius 9, `#5C7FFF`, shadow `0 6px 16px -6px rgba(92,127,255,.7)`.
- 경로: `Lot Trace / 추적 / LOT-2610-003-1` — 14px, "Lot Trace" 700, 구분자 `#B4B8C2`, "추적" `#6B7080`, 로트번호 mono 13px.
- 실시간 표시(우측): pill(radius 999, padding 7px 12px, bg `rgba(255,255,255,.6)`), 6px 초록 점 `#22B07D` + "실시간 · 10/2 08:00 기준" 12.5px `#6B7080`.

### ② 로트 요약 카드 (padding 28px 32px 26px)
- 상단 좌측:
  - 상태 칩 "생산 중": pill, padding 5px 12px 5px 10px, bg `rgba(92,127,255,.10)`, 글자 `#3F5FE0` 12.5px/600, 7px 점 `#5C7FFF` + pulse 애니메이션.
  - "OP-50 판정 9 / 24" 13px `#6B7080`, 숫자 mono 600 `#16181D`.
  - 제목 h1: `clamp(30px,4vw,44px)`, 800, line-height 1.05, letter-spacing -0.035em. "LOT-2610-" `#16181D` + "003-1" `#5C7FFF`.
  - 태그: `PO-2610-003`, `MAT-2609-11` — mono 12px/500, padding 5px 10px, radius 8, bg `rgba(22,24,29,.05)`, 글자 `#3A3E48`.
- 상단 우측 버튼 "생산 중 · 출하 금지"(자물쇠 아이콘 15px): padding 13px 20px, radius 14, bg `#26282F`, 흰 글자 14.5px/700, shadow `inset 0 1px 0 rgba(255,255,255,.12), 0 0 0 1px rgba(92,127,255,.35), 0 12px 28px -10px rgba(92,127,255,.55)`. hover: `translateY(-1px)`.
- 공정 트래커(margin-top 26px): 5열 grid(gap 10px). 각 열 = 4px 바(radius 4) + 코드(mono 12px `#8A8F9C`) + 이름(14px/600).
  - 완료(OP-10 절단 · SAW-01 / OP-20 황삭 · MIL-01 / OP-30 정밀 가공 · VF2-01/02 / OP-40 디버링·세척 · WSH-01): 바 `#5C7FFF`, 이름 뒤 ✓ `#5C7FFF`.
  - 진행 중(OP-50 측정 · CMM-01): 트랙 `rgba(22,24,29,.08)`, 채움 37.5%(=9/24) `#5C7FFF` + glow `0 0 10px rgba(92,127,255,.8)`, "9 / 24 판정" mono 12px/600 `#3F5FE0`.

### ③ 검색 · 계보 카드 (padding 22px 24px, 세로 gap 18px)
- 검색 줄(flex wrap, gap 12px):
  - 라벨 "번호로 찾기" 14px/700.
  - 입력: flex `0 1 340px`, min 220px, 높이 44, radius 13, bg `#F4F5F8`, border `1px solid rgba(22,24,29,.06)`, 돋보기 아이콘 `#9AA0AC`, placeholder "LOT · MAT · SHP 번호"(`#A3A8B3`), 입력 글자 mono 13px.
  - "찾기" 버튼: 높이 44, padding 0 22px, radius 13, bg `#5C7FFF`, 흰 글자 14px/700. hover `brightness(1.06)`.
  - "예시" 12.5px `#8A8F9C` + 칩 3개(`MAT-2609-11`, `SHP-2609-001`, `LOT-2609-001-1`): mono 12px, padding 7px 11px, pill, 흰 배경, border `rgba(22,24,29,.08)`. hover: border `rgba(92,127,255,.5)`, 글자 `#3F5FE0`. 클릭 시 입력값에 채움.
- 계보 패널(radius 18, bg `#F3F4F7`, padding 18px):
  - 좌측: 원자재 블록(bg `#26282F`, radius 13, padding 10px 14px, "원자재" 11px `#A6A9B4` + `MAT-2609-11` mono 13px/600 흰색) → 28px 연결선(2px `#26282F`) → "생산 로트" 12.5px/600.
  - 우측: 로트 칩들(flex wrap, gap 8px). 칩 공통: padding 9px 12px, radius 12, 코드 mono 12.5px/600, 상태 라벨 11.5px/600 + 6px 점. hover: `translateY(-1px)` + shadow.

  | 상태 | 배경 | 테두리 | 코드 색 | 라벨/점 |
  |---|---|---|---|---|
  | 합격 | #FFFFFF | 1px rgba(22,24,29,.07) | #16181D | #178A63 / #22B07D |
  | 판정 대기 | #FFF7E8 | 1px #F2CB8C | #7A4A00 | #A86200 / #F0A23B |
  | 생산 중 (현재 로트) | #FFFFFF | 1.5px #5C7FFF + shadow 0 10px 22px -12px rgba(92,127,255,.7) | #16181D, 700 | #3F5FE0 / #5C7FFF (pulse) |
  | 생산 중 (다른 로트) | rgba(255,255,255,.4) | 1px dashed rgba(22,24,29,.2) | #3A3E48 | #6B7080, 점 없음 |

  - 칩 순서: LOT-2609-128-3(합격), LOT-2609-129-1(합격), LOT-2610-001-1(합격), LOT-2610-001-2(합격), LOT-2610-002-1(판정 대기), LOT-2610-003-1(현재), LOT-2610-004-1(생산 중).
  - 하단 주석: "원자재 1 : 생산 로트 7 (DOC-06 §7)" 12px `#8A8F9C`.
- 메타 줄(gap 28px, 1px×30px 구분선 `rgba(22,24,29,.08)`): LOT / 작업지시(PO-2610-003 · 10/01 야간) / 원자재 — 라벨 11.5px `#8A8F9C`, 값 mono 15px/700. 우측 끝 링크 "검사 발췌 →" 13px/600 `#3F5FE0`, bg `rgba(92,127,255,.08)`, radius 10, padding 8px 12px.

### ④ 설비별 시간표 카드 (padding 22px 24px 18px)
- 헤더: "설비별 시간표" 16px/700 + "LOT-2610-003-1" mono 12.5px `#8A8F9C`. 우측 범례 12px `#6B7080`: 이 로트(16×8 `#5C7FFF`), 알람(사선 패턴), 보류(1.5px 점선), 지금(2px 세로선).
- 가로 스크롤 컨테이너, 내부 `min-width:860px`.
- Grid: 좌측 라벨 열 168px + 타임라인 `minmax(0,1fr)`.
- 시간축: 23:00(10/1) ~ 08:30(10/2), **총 570분**. 1시간마다 눈금(mono 11.5px `#8A8F9C`), 라벨 "23:00", "10/2 00:00", "01:00" … "07:00". 첫 라벨만 왼쪽 정렬, 나머지 가운데 정렬.
- 행: 높이 60px(compact 46px), 하단 border `rgba(22,24,29,.05)`, 홀수 행 bg `rgba(244,245,248,.6)`. 세로 격자 1px `rgba(22,24,29,.055)`가 1시간 간격.
  - 라벨: 설비코드 mono 13px/700 + "OP-xx 공정명" 12px `#8A8F9C`.
- 작업 막대: 높이 30px(compact 24px), 세로 중앙, radius 9, bg `#5C7FFF`, shadow `inset 0 1px 0 rgba(255,255,255,.35), 0 8px 18px -8px rgba(92,127,255,.75)`. 텍스트 "003-1 · N개" mono 11.5px/700 흰색, 넘치면 말줄임.
  - left = 시작분/570, width = 소요분/570 (%).
- 알람 구간: top/bottom 4px, radius 6, `repeating-linear-gradient(135deg, rgba(240,82,82,.22) 0 4px, rgba(240,82,82,.08) 4px 8px)`, border `1px solid rgba(240,82,82,.35)`. 막대 뒤에 깔림(z-index 0).
- 보류: 1.5px dashed `#5F6472` 세로선 + "보류" 배지(11px/600, 흰 배경, border `rgba(22,24,29,.1)`, radius 6).
- "지금" 선: 08:00 위치, 2px `#16181D` 세로선, 상단 배지 "지금 08:00"(10.5px/700, 흰 글자, bg `#16181D`, pill). 포인트색이 아니라 잉크색으로 구분.
- 툴팁(막대 hover): 막대 위 10px, min-width 200, padding 12px 14px, radius 12, bg `rgba(22,24,29,.94)`. 내용: "설비 · OP 공정명" / "시작 → 종료 (소요)" — 소요는 `#CCD7FF` / "수량 N개".

예시 데이터:
| 설비 | 공정 | 시작 | 종료 | 수량 | 이벤트 |
|---|---|---|---|---|---|
| SAW-01 | OP-10 절단 | 00:00 | 02:12 | 24 | |
| MIL-01 | OP-20 황삭 | 01:27 | 03:01 | 24 | |
| VF2-01 | OP-30 정밀 가공 | 03:01 | 04:42 | 12 | 알람 03:46–04:04 (예시) |
| VF2-02 | OP-30 정밀 가공 | 03:15 | 04:44 | 10 | |
| WSH-01 | OP-40 디버링·세척 | 03:30 | 04:45 | 14 | |
| CMM-01 | OP-50 측정 | 03:54 | 04:48 | 9 | 보류 04:48 (예시) |

## Interactions & Behavior
- 막대 hover → 툴팁 표시, mouse leave → 숨김.
- 예시 칩 클릭 → 검색 입력값 설정. "찾기"는 해당 번호로 로트 조회(실제 API 연결 필요).
- 로트 칩 클릭 → 해당 로트 상세로 이동(라우팅 연결 필요).
- 애니메이션:
  - `pulse`: 1.8s ease-out infinite, box-shadow 0→8px, `rgba(92,127,255,.55)`→0. 현재 로트 상태 점에만.
  - `barIn`: 0.7s `cubic-bezier(.2,.8,.2,1)`, scaleX 0→1 + opacity, transform-origin left. 행마다 delay 0.1s + i×0.08s.
  - `prefers-reduced-motion`이면 두 애니메이션 끄기 권장.
- 반응형: 카드 내부 flex-wrap. 시간표는 860px 미만에서 가로 스크롤.

## State Management
- `query: string` (검색 입력)
- `hoveredRow: number | null` (툴팁)
- 서버 데이터: 로트 요약(상태, 출하 가능 여부, 판정 n/total, PO, MAT, 교대), 공정 단계 목록(코드, 이름, 설비, 완료 여부), 원자재 계보 로트 목록(코드, 상태), 설비별 작업 구간(설비, 공정, 시작/종료, 수량, 알람 구간[], 보류 시각), 현재 시각.
- 상태 enum: `PASS`(합격) · `PENDING`(판정 대기) · `IN_PRODUCTION`(생산 중). 현재 보고 있는 로트는 별도로 강조.
- 옵션: `density: 'comfortable' | 'compact'`, `showEvents: boolean`.

## Design Tokens
**Color**
- Accent: `#5C7FFF` (막대, 버튼, 진행, 현재 로트)
- Accent text: `#3F5FE0` (작은 글씨, 링크) / hover `#2E48B8`
- Accent tint: `rgba(92,127,255,.10)` 칩 배경, `.08` 링크 배경
- Tooltip accent: `#CCD7FF`
- Ink: `#16181D` (본문, 지금 선) / Dark surface `#26282F`
- Text: `#3A3E48`(보조 진함) · `#6B7080`(보조) · `#8A8F9C`(라벨) · `#A3A8B3`(placeholder) · `#B4B8C2`(구분자)
- Surface: `#FFFFFF` · `#F4F5F8`(입력) · `#F3F4F7`(패널)
- Page bg: `linear-gradient(180deg,#FFFFFF 0%,#F2F4FA 55%,#EAEEF7 100%)`, fallback `#EEF1F8`
- Status: 합격 `#22B07D`/`#178A63` · 판정 대기 `#F0A23B`/`#A86200`/`#FFF7E8`/`#F2CB8C`/`#7A4A00` · 알람 `rgb(240,82,82)` 계열

**Typography**
- Sans: Pretendard Variable (`https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css`)
- Mono(번호·시간·코드): JetBrains Mono 400–700 (Google Fonts)
- Scale: 44(h1, clamp 30–44) · 16(h2) · 15 · 14.5 · 14 · 13 · 12.5 · 12 · 11.5 · 11 · 10.5
- 한국어 줄바꿈 `word-break: keep-all`. 번호·시간·라벨은 `white-space: nowrap`.

**Radius**: 24(카드) · 18(패널) · 14(주 버튼) · 13(입력·검색 버튼·원자재 블록) · 12(로트 칩·툴팁) · 10 · 9(막대·로고) · 8(태그) · 6 · 999(pill)

**Spacing**: 카드 사이 18 · 카드 padding 22–32 · 요소 gap 6 / 8 / 10 / 12 / 14 / 16 / 28

## Assets
- 아이콘: 자물쇠, 돋보기 — 인라인 SVG(stroke 2.2, round cap). 프로젝트 아이콘 세트(Lucide `Lock`, `Search` 등)로 대체해도 됩니다.
- 이미지 없음.

## Files
- `Lot Trace 6c.dc.html` — 디자인 레퍼런스(템플릿 + 하단 `<script>`에 데이터·로직)
- `support.js` — 레퍼런스를 브라우저에서 열기 위한 런타임(프로덕션 불필요)
