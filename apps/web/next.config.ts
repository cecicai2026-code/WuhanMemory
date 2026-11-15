import type { NextConfig } from "next";

// 后端地址，只在服务器上用，不会进浏览器（lib/backend.ts）
const apiBase = (process.env.API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  transpilePackages: ["@wuhanmemory/shared", "@wuhanmemory/map-core"],
  // 浏览器只连网站自己的地址：接口、高德安全密钥代理、照片转给后端。
  // 服务器上 Caddy 会直接把这三类路径转给后端，不经过这里（docs/operations/deploy-hk.md）；本机开发时靠这里。
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiBase}/api/:path*` },
      { source: "/_AMapService/:path*", destination: `${apiBase}/_AMapService/:path*` },
      { source: "/media/:path*", destination: `${apiBase}/media/:path*` }
    ];
  }
};

export default nextConfig;
