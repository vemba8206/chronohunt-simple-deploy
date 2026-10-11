// Isolated testing/development only; no remote DB or environment credentials.
import { PGlite } from '@electric-sql/pglite'
import { readFile } from 'node:fs/promises'

export async function isolatedDatabase() {
  const db = new PGlite()
  await db.exec('create role anon; create role authenticated; create role service_role bypassrls;')
  await db.exec(await readFile(new URL('../../backend/sql/004_simple_competition.sql', import.meta.url), 'utf8'))
  await db.exec(await readFile(new URL('../../backend/sql/006_minimal_submissions.sql', import.meta.url), 'utf8'))
  await db.exec(await readFile(new URL('../../backend/sql/007_organizer_reset.sql', import.meta.url), 'utf8'))
  return db
}

export const rpcArguments = {
  ch_simple_policy: [], ch_simple_status: [], ch_simple_team: ['p_team_id'],
  ch_simple_submit: ['p_team_id', 'p_code'], ch_simple_leaderboard: [],
  ch_simple_reset: [], ch_simple_overview: [], ch_simple_teams: ['p_offset'],
}

export async function rpc(db, name, args = {}) {
  if (!Object.hasOwn(rpcArguments, name)) throw new Error('Unsupported isolated RPC')
  const keys = rpcArguments[name]
  const result = await db.query(`select public.${name}(${keys.map((_, i) => '$' + (i + 1)).join(',')}) as value`, keys.map(key => args[key] ?? null))
  return result.rows[0].value
}
