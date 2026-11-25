import { env } from 'node:process'
import { URL } from 'node:url'

const upstream = env.RENDER_API_ORIGIN?.trim()
if (upstream) {
  const url = new URL(upstream)
  if (url.protocol !== 'https:' || url.origin !== upstream) {
    throw new Error('RENDER_API_ORIGIN must be an HTTPS origin without a trailing slash.')
  }
}

if (env.VERCEL === '1') {
  const api = env.VITE_API_BASE_URL?.trim()
  if (!upstream || !api) {
    throw new Error('Set RENDER_API_ORIGIN and VITE_API_BASE_URL for the staging deployment.')
  }
  if (api !== '/api/v1') {
    const url = new URL(api)
    if (url.protocol !== 'https:' || url.origin === upstream || api !== `${url.origin}/api/v1`) {
      throw new Error('Set VITE_API_BASE_URL to /api/v1 or to that path on the staging frontend HTTPS origin.')
    }
  }
}

export const config = {
  framework: 'vite',
  installCommand: 'npm ci',
  buildCommand: 'npm run build',
  outputDirectory: 'dist',
  rewrites: [
    ...(upstream ? [{ source: '/api/v1/:path*', destination: `${upstream}/api/v1/:path*` }] : []),
    { source: '/(.*)', destination: '/index.html' },
  ],
}
