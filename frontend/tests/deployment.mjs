import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { deploymentConfig } from '../scripts/prepare-vercel.mjs'

let count = 0
const check = (name, fn) => { fn(); count++; console.log('PASS ' + name) }
check('missing deployed API origin blocks configuration', () => assert.throws(() => deploymentConfig(undefined)))
for (const origin of ['http://localhost:8000', 'https://127.0.0.1', 'https://192.168.1.2', 'https://api.example.org', 'https://fixture.onrender.com/api', 'https://user:secret@fixture.onrender.com', 'https://fixture.onrender.com?token=secret']) {
  check('unusable or credential-bearing API origin rejected', () => assert.throws(() => deploymentConfig(origin)))
}
// Test-only origin, never written to production configuration or published.
const config = deploymentConfig('https://fixture.onrender.com')
check('API proxy preserves API path before SPA routes', () => assert.deepEqual(config.rewrites[0], { source:'/api/:path*', destination:'https://fixture.onrender.com/api/:path*' }))
check('protected page refresh routes have explicit SPA fallback', () => assert.deepEqual(config.rewrites.slice(1).map(x=>x.source), ['/admin','/leaderboard']))
check('no wildcard rewrite can turn API failures into SPA success', () => assert.ok(config.rewrites.every(x=>x.source !== '/(.*)')))
const spec = JSON.parse(await readFile(new URL('../../render.yaml', import.meta.url),'utf8'))
const service = spec.services[0]
check('single-process policy and correct ASGI entry point', () => {assert.equal(service.numInstances,1);assert.match(service.startCommand,/app\.asgi:app/);assert.match(service.startCommand,/--workers 1/);assert.doesNotMatch(service.startCommand,/--reload/);assert.equal(service.autoDeployTrigger,'off')})
check('secrets require provider input and SQL never runs on deployment', () => {assert.ok(service.envVars.filter(x=>['ADMIN_PASSWORD','SESSION_SECRET','SUPABASE_SECRET_KEY','GOOGLE_SHEET_API_TOKEN'].includes(x.key)).every(x=>x.sync===false && x.value===undefined));assert.equal(service.preDeployCommand,undefined);assert.equal(service.initialDeployHook,undefined)})
const main = await readFile(new URL('../../backend/app/main.py', import.meta.url),'utf8')
check('both leaderboard aliases require backend admin authentication',()=> {
  assert.match(main,/async def leaderboard\(claims=Depends\(admin\)\)/)
  assert.match(main,/async def admin_leaderboard\(claims=Depends\(admin\)\)/)
})
check('reset requires backend admin authentication and explicit body',()=>assert.match(main,/async def reset\(body: Reset, request: Request, claims=Depends\(admin\)\)/))
const sql = await readFile(new URL('../../backend/sql/007_organizer_reset.sql', import.meta.url),'utf8')
check('migration installs reset without executing or truncating data',()=> {
  assert.match(sql,/delete from chronohunt_simple\.submissions;/)
  assert.doesNotMatch(sql,/\btruncate\s+|select\s+public\.ch_simple_reset\(\)/i)
  assert.match(sql,/revoke all on function public\.ch_simple_reset/)
})
console.log(`\n${count} deployment preparation checks passed.`)
