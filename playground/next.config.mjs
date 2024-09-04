/** @type {import('next').NextConfig} */

const { AGENT_SERVER_URL } = process.env;

// Check if environment variables are available
if (!AGENT_SERVER_URL) {
  throw "Environment variables AGENT_SERVER_URL are not available";
}

const nextConfig = {
  // basePath: '/ai-agent',
  // output: 'export',
  output: 'standalone',
  reactStrictMode: false,
  async rewrites() {
    return [
      // customize agents start at /app/api/agents/start.tsx
      {
        source: '/api/agents/start',
        destination: '/api/agents/start',
      },
      // Proxy all other agents API requests
      {
        source: '/api/agents/:path*',
        destination: `${AGENT_SERVER_URL}/:path*`,
      },
      // Proxy all other documents requests
      {
        source: '/api/vector/:path*',
        destination: `${AGENT_SERVER_URL}/vector/:path*`,
      },
      // Proxy all other documents requests
      {
        source: '/api/token/:path*',
        destination: `${AGENT_SERVER_URL}/token/:path*`,
      },
    ];
  },
  webpack(config) {
    // Grab the existing rule that handles SVG imports
    const fileLoaderRule = config.module.rules.find((rule) =>
      rule.test?.test?.('.svg'),
    )

    config.module.rules.push(
      // Reapply the existing rule, but only for svg imports ending in ?url
      {
        ...fileLoaderRule,
        test: /\.svg$/i,
        resourceQuery: /url/, // *.svg?url
      },
      // Convert all other *.svg imports to React components
      {
        test: /\.svg$/i,
        issuer: fileLoaderRule.issuer,
        resourceQuery: { not: [...fileLoaderRule.resourceQuery.not, /url/] }, // exclude if *.svg?url
        use: ['@svgr/webpack'],
      },
    )

    // Modify the file loader rule to ignore *.svg, since we have it handled now.
    fileLoaderRule.exclude = /\.svg$/i

    return config
  }
};

export default nextConfig;
