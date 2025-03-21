/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_BASE_URL: process.env.NEXT_PUBLIC_BASE_URL || '',
  },
  // 如果网站部署在子路径下，可以设置basePath
  // basePath: '/your-base-path',

  // 配置静态资源路径
  assetPrefix: process.env.NEXT_PUBLIC_BASE_URL || '',

  // 图像优化配置
  images: {
    domains: ['memory-test.smartapetech.com'],
  },
}

module.exports = nextConfig