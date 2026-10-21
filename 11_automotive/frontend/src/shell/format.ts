// 디자인 통일 C안 — 숫자 · 날짜 표기 (규칙 1의 3장). React 없는 순수 함수.
// 화면은 숫자를 직접 문자열로 만들지 말고 이 함수를 쓴다.

/** 1,000 이상 쉼표. 소수는 digits 자리 고정 (없으면 정수 그대로) — 1057 → "1,057", 3.6 → "3.6" */
export const fmtNum = (n: number | null | undefined, digits?: number): string => {
  if (n == null || Number.isNaN(n)) return '—';
  return digits == null
    ? n.toLocaleString('en-US', { maximumFractionDigits: 4 })
    : n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
};

/** 숫자 + 한 칸 + 단위 — "94 개", "3.6 L", "400 구멍" */
export const fmtQty = (n: number | null | undefined, unit: string, digits?: number): string => `${fmtNum(n, digits)} ${unit}`;

/** 퍼센트는 붙여 쓰고 소수 1자리 고정 — 80 → "80.0%", 104.44 → "104.4%" */
export const fmtPct = (n: number | null | undefined): string => (n == null || Number.isNaN(n) ? '—' : `${n.toFixed(1)}%`);

/** 분수 — "47 / 60" (빗금 앞뒤 띄움) */
export const fmtFrac = (a: number | string, b: number | string): string => `${typeof a === 'number' ? fmtNum(a) : a} / ${typeof b === 'number' ? fmtNum(b) : b}`;

/** 날짜 — 앞 0 없이 "9/28". 요일이 필요하면 withDay=true → "10/1 (목)" */
export const fmtDate = (iso: string | null | undefined, withDay = false): string => {
  if (!iso) return '';
  const m = Number(iso.slice(5, 7)), d = Number(iso.slice(8, 10));
  if (!withDay) return `${m}/${d}`;
  const day = '일월화수목금토'[new Date(`${iso.slice(0, 10)}T00:00:00`).getDay()];
  return `${m}/${d} (${day})`;
};

/** 시각 — "09:22", 모르면 "--:--" */
export const fmtTime = (iso: string | null | undefined): string => (iso ? iso.slice(11, 16) : '--:--');

/** 날짜 + 시각 — "10/1 05:35" */
export const fmtDateTime = (iso: string | null | undefined): string => (iso ? `${fmtDate(iso)} ${fmtTime(iso)}` : '');

/** 경과 — 59 → "59분째", 99 → "1시간 39분째", 120 → "2시간째" */
export const fmtElapsed = (min: number): string => {
  const m = Math.max(0, Math.round(min));
  if (m < 60) return `${m}분째`;
  const h = Math.floor(m / 60), r = m % 60;
  return r ? `${h}시간 ${r}분째` : `${h}시간째`;
};

/** 빈 값 (UI설계서 2.8): 칸 = "없음", 보고 순위 = "-", 계산 불가 = "—", 과거 기록 = "기록 없음" */
export const EMPTY = { cell: '없음', rank: '-', na: '—', history: '기록 없음' } as const;
