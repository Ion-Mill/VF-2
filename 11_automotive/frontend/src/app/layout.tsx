import 'pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css'; // 글꼴 Pretendard 하나 (화이트 카드 · 파스텔 블루, 2026-10-21) — 빌드에 들어가 공장 PC가 인터넷 없이도 같은 글꼴, 쓰는 글자 묶음만 내려받음
import type { Metadata } from 'next';
import '../../mom-assistant-widget/assistant-widget.css'; // 이브 겉모양 (globals.css보다 먼저 — 덮어쓰기는 globals.css)
import './globals.css';

export const metadata: Metadata = {
  title: '이브테크 · 제조운영관리',
  description: 'LINE A 3D Factory Process Visualization',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
