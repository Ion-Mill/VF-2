/** @type {import('next').NextConfig} */
// /api/* 를 어디로 넘길지 (2026-10-24 — 기본 = 백엔드, src/shell/backendApi.ts backendMode):
//   NEXT_PUBLIC_MOM_BACKEND가 0이 아니면(기본) → 백엔드 MOM_BACKEND_URL (기본 http://127.0.0.1:8000). 화면 → 백엔드 → DB
//   NEXT_PUBLIC_MOM_BACKEND=0 → 예전처럼 시연 데이터 서버 SIM_SERVER (기본 http://127.0.0.1:8765, tools/sim_server.py)
const backend = process.env.NEXT_PUBLIC_MOM_BACKEND !== '0';
const target = backend
  ? (process.env.MOM_BACKEND_URL ?? 'http://127.0.0.1:8000')
  : (process.env.SIM_SERVER ?? 'http://127.0.0.1:8765');

const nextConfig = {
  reactStrictMode: false, // 3D 장면이 개발 모드에서 두 번 만들어지는 것을 막음
  transpilePackages: ['three'],
  // 비서(외부 LLM) 답은 130초까지 걸릴 수 있다 — 화면 서버가 넘기는 요청을 30초(기본)에 끊지 않게
  experimental: { proxyTimeout: 150_000 },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${target.replace(/\/+$/, '')}/api/:path*` }];
  },
};
export default nextConfig;
