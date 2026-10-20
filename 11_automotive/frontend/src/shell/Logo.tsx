// 이브테크 글자 로고 (사용자 선택 2026-10-18, 시안 L): eVe | TECH — 가운데 V = 프레스로 꺾은 브래킷 단면, 보라 세로선 = 이브 (네온 바이올렛 포인트, 2026-10-19)
export default function Logo({ height = 28 }: { height?: number }) {
  return (
    <svg height={height} width={Math.round((height * 250) / 60)} viewBox="0 0 250 60" aria-label="이브테크 EVETECH" role="img" className="shrink-0" style={{ overflow: 'visible' }}>
      <text x="0" y="46" fontWeight="800" fontSize="46" fill="#1c232b">e</text>
      <path d="M30 14l11 30h8l11-30" fill="none" stroke="#1c232b" strokeWidth="8" strokeLinejoin="round" />
      <text x="62" y="46" fontWeight="800" fontSize="46" fill="#1c232b">e</text>
      <rect x="94" y="14" width="3.5" height="32" fill="#8f6bff" />
      <text x="105" y="46" fontWeight="300" fontSize="40" letterSpacing="3" fill="#5b6570">TECH</text>
    </svg>
  );
}
