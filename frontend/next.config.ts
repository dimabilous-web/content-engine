import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Allow cross-origin API calls in dev
  async rewrites() {
    return [];
  },
};

export default nextConfig;
