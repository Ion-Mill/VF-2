'use client';

import dynamic from 'next/dynamic';
import type { DashboardProps } from './types';

// three.js는 브라우저 전용이라 서버 렌더링(SSR)을 끄고 불러옵니다.
const FactoryDashboard = dynamic(() => import('./FactoryDashboard'), {
  ssr: false,
  loading: () => (
    <div className="flex h-screen w-full items-center justify-center bg-[#05080c] font-mono text-[13px] tracking-[0.2em] text-[#7fe3f5]">
      LOADING DIGITAL TWIN…
    </div>
  ),
});

export default function FactoryView(props: DashboardProps) {
  return <FactoryDashboard quality="자동" introOnLoad={true} {...props} />;
}
