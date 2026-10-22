import type { Config } from 'tailwindcss';

// 화이트 카드 · 파스텔 블루 (2026-10-21, 디자인 통일 C안을 바꿈) — 색 · 글자 · 모서리 토큰. 화면 코드는 이 이름만 쓴다 (text-[13px] · bg-[#...] 대신).
// 규칙: 카드는 흰색 + 얇은 선, 색은 아이콘 칸 · 태그에만 파랑 계열 파스텔, 꽉 찬 파랑은 화면마다 주 버튼, 초록 · 주황 · 빨강은 상태에만.
// 글꼴 = Pretendard 하나. mono도 같은 글꼴로 돌려서 기존 font-mono는 손대지 않아도 된다 (숫자 폭 맞춤은 tabular-nums, globals.css).
const PRETENDARD = ['"Pretendard Variable"', 'Pretendard', 'system-ui', '"Malgun Gothic"', 'sans-serif'];

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: { sans: PRETENDARD, mono: PRETENDARD },
      colors: {
        brand: { DEFAULT: '#3d6fe0', ink: '#2a55b8', line: '#cbdcfb', tint: '#e5effe' }, // 파랑 — 누르는 것 · 링크 · 주 버튼 · 고른 것(옅은 tint)
        point: { DEFAULT: '#3d6fe0', ink: '#2a55b8', deep: '#1f4596', tint: '#e5effe', line: '#cbdcfb' }, // 로트 추적 포인트도 같은 파랑
        crit: { DEFAULT: '#c23042', bg: '#fdecee', line: '#f6c9cf' },                    // ⚠ 긴급
        warn: { DEFAULT: '#a35a0c', bg: '#fff3e3', line: '#f6d6a8', mark: '#e0a300', ondark: '#ffd36a' }, // ▲ 주의 (mark = 막대 · 아이콘, ondark = 진한 바탕 위 글자)
        ok: { DEFAULT: '#157a4f', bg: '#e6f6ef', line: '#bfe6cf', dot: '#2bb673' },     // 정상 · 완료
        info: { DEFAULT: '#56667d', bg: '#f1f4f8' },                                     // ⓘ 참고 · 할 일 · 진행
        ink: { DEFAULT: '#1b2a41', 2: '#56667d', 3: '#7d8ca1' },                         // 글자 · 보조 글자 · 흐린 글자 (짙은 남색 쪽)
        bar: '#9fb4d6',                                                                   // 정상 막대 · 비활성 글자
        line: { DEFAULT: '#e3e9f2', soft: '#edf1f7' },                                    // 카드 선 · 칸 안 줄
        tile: '#f3f6fb',                                                                  // 흰 버튼 hover · 옅은 칸
        ground: '#f5f8fc',                                                                // 화면 바탕 (아주 옅은 하늘빛 흰색)
        track: '#edf1f7',                                                                 // 막대 바탕
        // 공정 색 — 파랑 계열 안에서 이웃끼리 번갈아 다르게 (칸 바탕 / i 아이콘 · 막대 / b 시간표 막대 바탕 / t 막대 글자)
        op1: { DEFAULT: '#dff3f7', i: '#0f8299', b: '#c2e7ef', t: '#0a5a6b' }, // OP-10 절단 · 청록
        op2: { DEFAULT: '#e6eefe', i: '#3a6fe0', b: '#cfdcfb', t: '#234fae' }, // OP-20 황삭 · 파랑
        op3: { DEFAULT: '#f0e9fd', i: '#7b4fe0', b: '#e0d1fb', t: '#5532b6' }, // OP-30 정밀 가공 · 보라
        op4: { DEFAULT: '#eceff4', i: '#57677e', b: '#d6dde7', t: '#344157' }, // OP-40 디버링·세척 · 회청
        op5: { DEFAULT: '#e3f3fd', i: '#1f8ad2', b: '#c4e4f9', t: '#135f96' }, // OP-50 측정 · 하늘
      },
      boxShadow: { card: '0 1px 2px rgba(27,42,65,.04), 0 10px 26px -18px rgba(27,42,65,.22)' }, // 큰 카드에만 아주 옅은 그림자
      fontSize: {
        tablet: ['40px', { lineHeight: '1.2' }], // 작업자 태블릿 숫자만
        num: ['32px', { lineHeight: '1.2' }],    // 숫자 칸
        title: ['22px', { lineHeight: '1.35' }], // 화면 제목 · 팝업 제목
        band: ['20px', { lineHeight: '1.35' }],  // 결론 띠 첫 줄
        card: ['17px', { lineHeight: '1.4' }],   // 칸 카드 제목 · 띠 둘째 줄
        body: ['16px', { lineHeight: '1.5' }],   // 본문 · 표 · 버튼 · 입력
        small: ['15px', { lineHeight: '1.5' }],  // 보조 · 칩 · 표 머리 · 출처 · 범례
      },
      borderRadius: { stage: '24px', pop: '20px', card: '16px', tile: '12px', ctl: '10px' },
    },
  },
  plugins: [],
};
export default config;
