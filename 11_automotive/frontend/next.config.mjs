/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false, // 3D 장면이 개발 모드에서 두 번 만들어지는 것을 막음
  transpilePackages: ['three'],
  // 데이터적용본: /api/* 는 시연 데이터 서버(tools/sim_server.py, 생성기 실시간 모드)로 넘긴다
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${process.env.SIM_SERVER ?? 'http://127.0.0.1:8765'}/api/:path*` }];
  },
};
export default nextConfig;
