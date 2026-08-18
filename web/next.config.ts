import type { NextConfig } from '@/next'
import createMDX from '@next/mdx'
import { codeInspectorPlugin } from 'code-inspector-plugin'
import { env } from './env'

const isDev = process.env.NODE_ENV === 'development'
const withMDX = createMDX()
const allowedDevOrigins = process.env.NEXT_ALLOWED_DEV_ORIGINS?.split(',')
  .map((origin) => origin.trim())
  .filter(Boolean)

const nextConfig: NextConfig = {
  basePath: env.NEXT_PUBLIC_BASE_PATH,
  ...(allowedDevOrigins?.length ? { allowedDevOrigins } : {}),
  transpilePackages: ['@t3-oss/env-core', '@t3-oss/env-nextjs', 'echarts', 'zrender'],
  serverExternalPackages: ['loro-crdt'],
  turbopack: {
    rules: codeInspectorPlugin({
      bundler: 'turbopack',
    }),
  },
  experimental: {
    // TODO: Remove when the `typescript` package can point to TypeScript 7.
    // Next.js resolves that package, while compiler-API consumers still require TypeScript 6.
    useTypeScriptCli: false,
  },
  productionBrowserSourceMaps: false, // enable browser source map generation during the production build
  // Configure pageExtensions to include md and mdx
  pageExtensions: ['ts', 'tsx', 'js', 'jsx', 'md', 'mdx'],
  typescript: {
    // https://nextjs.org/docs/api-reference/next.config.js/ignoring-typescript-errors
    ignoreBuildErrors: true,
  },
  async redirects() {
    return [
      {
        source: '/explore/apps',
        destination: '/',
        permanent: true,
      },
      {
        // TODO(2026-11-11): Remove after external education CTAs and active campaign links use the canonical route.
        source: '/education-apply',
        destination: '/education/apply',
        permanent: true,
      },
    ]
  },
  async rewrites() {
    // Dev-only: proxy API / WebSocket traffic to the local backend so the
    // browser always talks to the same origin (http://localhost:3000) and never
    // hits CORS. Production (Docker/nginx) does this with its own reverse proxy.
    if (!isDev) return []
    const target = process.env.DEV_API_TARGET || 'http://localhost:5001'
    return [
      {
        source: '/console/api/:path*',
        destination: `${target}/console/api/:path*`,
      },
      {
        source: '/api/:path*',
        destination: `${target}/api/:path*`,
      },
      {
        source: '/socket.io/:path*',
        destination: `${target}/socket.io/:path*`,
      },
    ]
  },
  output: 'standalone',
  compiler: {
    removeConsole: isDev ? false : { exclude: ['warn', 'error'] },
  },
}

export default withMDX(nextConfig)
