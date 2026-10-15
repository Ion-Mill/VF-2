import type { Metadata } from 'next';
import '../../mom-assistant-widget/assistant-widget.css'; // 이브 겉모양 (globals.css보다 먼저 — 덮어쓰기는 globals.css)
import './globals.css';

export const metadata: Metadata = {
  title: '3D 스마트팩토리 대시보드',
  description: 'LINE A 3D Factory Process Visualization',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap" />
      </head>
      <body>{children}</body>
    </html>
  );
}
