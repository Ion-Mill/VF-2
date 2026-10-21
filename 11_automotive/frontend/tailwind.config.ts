import type { Config } from 'tailwindcss';

// 디자인 통일 C안 (2026-10-20) — 색 · 글자 · 모서리 토큰. 화면 코드는 이 이름만 쓴다 (text-[13px] · bg-[#...] 대신).
// 글꼴 = Noto Sans KR 하나. mono도 같은 글꼴로 돌려서 기존 font-mono 148곳은 손대지 않아도 된다
// (Noto Sans KR 숫자 0~9는 원래 같은 폭이라 줄 맞춤이 그대로 됨 — 글꼴 파일로 확인).
const NOTO = ['"Noto Sans KR Variable"', '"Noto Sans KR"', 'system-ui', 'sans-serif'];

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: { sans: NOTO, mono: NOTO },
      colors: {
        brand: { DEFAULT: '#6a43e0', ink: '#5a3bc8', line: '#c4b3f5', tint: '#f0ebff' }, // 누르는 것 · 링크 · AI비서 초안
        crit: { DEFAULT: '#c62a2f', bg: '#fdeeee', line: '#e8b4b5' },                    // ⚠ 긴급
        warn: { DEFAULT: '#9a6200', bg: '#fff6e0', line: '#ecd29a', mark: '#e0b000', ondark: '#ffd36a' }, // ▲ 주의 (mark = 막대 · 아이콘, ondark = 차콜 위 글자)
        ok: { DEFAULT: '#127a46', bg: '#e0f2e8', line: '#b7dcc6' },                      // 정상 · 완료
        info: { DEFAULT: '#4b5563', bg: '#f1f2f4' },                                     // ⓘ 참고 · 할 일 · 진행
        ink: { DEFAULT: '#26303a', 2: '#5f6b7a', 3: '#8a94a3' },                         // 글자 · 보조 글자 · 흐린 글자 / 차콜 = ink
        bar: '#6b7380',                                                                   // 정상 막대
        line: { DEFAULT: '#dcdde1', soft: '#eef0f2' },                                    // 카드 선 · 칸 안 줄
        tile: '#f4f4f6',                                                                  // 숫자 칸 · 흰 버튼 hover
        ground: '#f2f3f5',                                                                // 화면 바탕
        track: '#e8eaed',                                                                 // 막대 바탕
      },
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
