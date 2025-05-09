import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  webpack: (config) => {
    // This rule prevents issues with pdf.js and canvas
    config.externals = [...(config.externals || []), { canvas: 'canvas' }];

    // Ensure node native modules are ignored
    config.resolve.fallback = {
      ...config.resolve.fallback,
      canvas: false,
    };

    return config;
  },
  images: {
    domains: ['localhost', 'localhost:3000', '127.0.0.1', '127.0.0.1:3000', 'lh3.googleusercontent.com'],
  },
};

export default nextConfig;
