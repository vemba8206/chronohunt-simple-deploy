import { writeFile } from 'node:fs/promises'
import { pathToFileURL } from 'node:url'
import { isIP } from 'node:net'

export function deploymentConfig(origin) {
  let url
  try { url = new URL(origin) } catch { throw new Error('Set CHRONOHUNT_BACKEND_ORIGIN to the actual deployed Render HTTPS origin.') }
  if (url.protocol !== 'https:' || url.username || url.password || url.port || url.search || url.hash || url.pathname !== '/' ||
      isIP(url.hostname) || !url.hostname.endsWith('.onrender.com') || url.hostname === 'onrender.com') {
    throw new Error('Use the actual Render service HTTPS origin, without credentials, port, path or query.')
  }
  return {
    $schema: 'https://openapi.vercel.sh/vercel.json',
    framework: 'vite', buildCommand: 'npm run build', outputDirectory: 'dist',
    rewrites: [
      { source: '/api/:path*', destination: url.origin + '/api/:path*' },
      { source: '/admin', destination: '/index.html' },
      { source: '/leaderboard', destination: '/index.html' },
    ],
    headers: [{ source: '/(.*)', headers: [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'no-referrer' },
      { key: 'X-Frame-Options', value: 'DENY' },
    ] }],
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const config = deploymentConfig(process.env.CHRONOHUNT_BACKEND_ORIGIN)
    await writeFile(new URL('../vercel.json', import.meta.url), JSON.stringify(config, null, 2) + '\n', { flag: 'wx' })
    console.log('Prepared frontend/vercel.json using the supplied HTTPS API origin. No deployment performed.')
  } catch (error) {
    console.error(error.message)
    process.exitCode = 1
  }
}
