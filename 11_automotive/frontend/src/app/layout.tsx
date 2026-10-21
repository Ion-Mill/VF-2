import '@fontsource-variable/noto-sans-kr'; // 글꼴 Noto Sans KR 하나 (디자인 통일 C안, 2026-10-20) — 빌드에 들어가 공장 PC가 인터넷 없이도 같은 글꼴
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
