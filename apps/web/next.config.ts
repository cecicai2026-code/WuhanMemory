import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@wuhanmemory/shared", "@wuhanmemory/map-core"]
};

export default nextConfig;
