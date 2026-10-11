// Explicit loopback-only throwaway SQL bridge for the simplified local API.
// No Supabase/Google credentials or data are loaded. Restart discards test entries.
import { createServer } from 'node:http'
import { isolatedDatabase, rpc, rpcArguments } from './simple-db.mjs'

const db = await isolatedDatabase()
const server = createServer(async (request, response) => {
  const name = request.url?.replace('/rest/v1/rpc/', '')
  if (request.method !== 'POST' || !request.url?.startsWith('/rest/v1/rpc/') || !Object.hasOwn(rpcArguments, name)) {
    response.writeHead(404); response.end(); return
  }
  try {
    let body = ''
    for await (const chunk of request) {
      body += chunk
      if (Buffer.byteLength(body) > 16384) throw new Error('Oversized isolated request')
    }
    await db.exec('set role service_role')
    const result = await rpc(db, name, JSON.parse(body || '{}'))
    response.writeHead(200, { 'Content-Type': 'application/json' }); response.end(JSON.stringify(result))
  } catch {
    response.writeHead(500, { 'Content-Type': 'application/json' }); response.end(JSON.stringify({ error: 'isolated_rpc_failed' }))
  }
})
server.listen(8091, '127.0.0.1', () => console.log('Disposable SQL bridge: 127.0.0.1:8091. No live services. Data disappears on restart.'))
server.on('error', () => { console.error('Isolated bridge could not bind port 8091.'); process.exitCode = 1 })
