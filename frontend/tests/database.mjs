// Production SQL executed in a fresh in-memory PostgreSQL (PGlite).
// No Supabase credentials or live competition DB are read or used.
import { PGlite } from '@electric-sql/pglite'
import { readFile } from 'node:fs/promises'
import assert from 'node:assert/strict'

const db = new PGlite()
let count = 0
const check = (name, fn) => { fn(); count++; console.log('PASS ' + name) }
await db.exec(`
  create role anon; create role authenticated; create role service_role bypassrls;
  create table public.teams (
    id uuid primary key default gen_random_uuid(), team_id text unique,
    form_timestamp timestamptz, tinkercad_code text, tinkercad_timestamp timestamptz,
    tinkercad_valid boolean default false, qualified boolean default false, rank integer,
    created_at timestamptz default now(), updated_at timestamptz default now()
  );
  create table public.competition_settings (
    id integer primary key, tinkercad_status text, tinkercad_end_time timestamptz,
    qualification_slots integer, updated_at timestamptz default now()
  );
  insert into public.competition_settings values (1, 'ACTIVE', null, 15, now());
`)
await db.exec(await readFile(new URL('../../backend/sql/001_competition.sql', import.meta.url), 'utf8'))
await db.exec(await readFile(new URL('../../backend/sql/002_registration_integrity.sql', import.meta.url), 'utf8'))
const rpc = async (name, ...args) => {
  const placeholders = args.map((_, i) => '$' + (i + 1)).join(',')
  return (await db.query(`select public.${name}(${placeholders}) as value`, args)).rows[0].value
}
const rows = ids => ids.map((id, i) => ({ team_id: id, form_timestamp: `2026-10-09T12:${String(i).padStart(2,'0')}:00Z` }))
const reset = async (slots = 15) => {
  await db.exec('delete from public.teams; delete from public.ch_audit;')
  await db.query("update public.competition_settings set tinkercad_status='ACTIVE', tinkercad_end_time=null, finalized_at=null, last_synced_at=null, qualification_slots=$1", [slots])
}
try {
  const snapshot = rows(['CH01', 'CH02', 'CH03'])
  await rpc('ch_sync', JSON.stringify(snapshot))
  const accepted = await rpc('ch_submit',' ch02 ','TEST')
  check('registered PIN submission recorded without correctness verification', () => assert.equal(accepted.accepted, true))
  const before = (await db.query("select * from teams where team_id='CH02'")).rows[0]
  await rpc('ch_sync', JSON.stringify(snapshot))
  await rpc('ch_sync', JSON.stringify(snapshot))
  const after = (await db.query("select * from teams where team_id='CH02'")).rows[0]
  const teamCount = (await db.query('select count(*)::integer as n from teams')).rows[0].n
  check('repeated sync creates no duplicates', () => assert.equal(teamCount, snapshot.length))
  check('sync preserves code and accepted timestamp', () => { assert.equal(after.tinkercad_code,'TEST'); assert.equal(String(before.tinkercad_timestamp), String(after.tinkercad_timestamp)); assert.equal(after.tinkercad_valid,true) })
  const edited = snapshot.map(row=>({...row,form_timestamp:'2026-10-10T20:00:00Z'}))
  const conflict = await rpc('ch_sync',JSON.stringify(edited))
  check('source timestamp edits are flagged instead of overwriting originals', () => assert.equal(conflict.error,'registration_timestamp_conflict'))
  const originalAfterConflict = (await db.query("select form_timestamp from teams where team_id='CH01'")).rows[0].form_timestamp
  check('original registration time unchanged after conflict', () => assert.equal(new Date(originalAfterConflict).toISOString(), '2026-10-09T12:00:00.000Z'))
  const duplicate = await rpc('ch_submit','CH02','DIFFERENT')
  check('duplicate submission rejected', () => assert.equal(duplicate.error,'duplicate_submission'))
  const unknown = await rpc('ch_submit','CH99','TEST')
  check('unknown team rejected', () => assert.equal(unknown.error,'unknown_team'))
  await rpc('ch_cutoff')
  const finalizeConflict = await rpc('ch_finalize',JSON.stringify(edited))
  check('finalization propagates timestamp conflict', () => assert.equal(finalizeConflict.error,'registration_timestamp_conflict'))
  const stillPending = await rpc('ch_status')
  check('conflict never commits finalized ranks', () => assert.equal(stillPending.finalized,false))
  const cutoff = (await db.query('select tinkercad_end_time from competition_settings')).rows[0].tinkercad_end_time
  const late = await rpc('ch_submit','CH01','TEST')
  check('late submission rejected', () => assert.equal(late.error,'round_closed'))
  await rpc('ch_finalize',JSON.stringify(snapshot))
  let board = await rpc('ch_leaderboard')
  check('submitted teams precede registration fallback', () => assert.deepEqual(board.map(x=>x.team_id), ['CH02','CH01','CH03']))
  check('fewer candidates than slots', () => assert.equal(board.length,3))
  check('leaderboard privacy', () => assert.deepEqual(Object.keys(board[0]).sort(),['rank','team_id']))
  await rpc('ch_cutoff'); await rpc('ch_finalize',JSON.stringify([])); await rpc('ch_sync',JSON.stringify([]))
  const cutoffAgain = (await db.query('select tinkercad_end_time from competition_settings')).rows[0].tinkercad_end_time
  check('cutoff timestamp immutable on retry', () => assert.equal(String(cutoff),String(cutoffAgain)))
  const publishedAgain = await rpc('ch_leaderboard')
  check('published results immutable on retry and sync', () => assert.deepEqual(publishedAgain,board))

  await reset()
  await rpc('ch_sync', JSON.stringify(snapshot))
  for (const id of ['CH03','CH02','CH01']) await rpc('ch_submit', id, 'any-nonempty-pin')
  let provisional = await rpc('ch_leaderboard')
  check('provisional board orders by original registration despite reversed website order', () => assert.deepEqual(provisional.map(x=>x.team_id), ['CH01','CH02','CH03']))
  await rpc('ch_cutoff')
  await rpc('ch_finalize', JSON.stringify(snapshot))
  let byRegistration = await rpc('ch_leaderboard')
  check('final board orders submitted teams by Form time, not website acceptance', () => assert.deepEqual(byRegistration.map(x=>x.team_id), ['CH01','CH02','CH03']))

  await reset()
  await rpc('ch_sync', JSON.stringify(snapshot))
  await rpc('ch_submit','CH01','any-pin')
  await rpc('ch_submit','CH02','any-pin')
  await rpc('ch_cutoff')
  await db.exec("update teams set tinkercad_timestamp=(select tinkercad_end_time from competition_settings) where team_id='CH02'")
  await rpc('ch_finalize', JSON.stringify(snapshot.slice(1)))
  let excluded = await rpc('ch_leaderboard')
  check('submission at exact cutoff and removed source team cannot qualify', () => assert.deepEqual(excluded.map(x=>x.team_id), ['CH03']))

  await reset()
  await rpc('ch_sync', JSON.stringify(snapshot))
  const emptyPin = await rpc('ch_submit','CH01','   ')
  check('empty PIN never records a website receipt', () => assert.equal(emptyPin.error,'invalid_code'))

  await reset(2)
  const tiedSnapshot = snapshot.map(row => ({...row, form_timestamp:'2026-10-09T12:00:00Z'}))
  await rpc('ch_sync',JSON.stringify(tiedSnapshot))
  for (const id of ['CH03','CH02','CH01']) await rpc('ch_submit',id,'TEST')
  await rpc('ch_cutoff')
  const exceeded = await rpc('ch_finalize',JSON.stringify(tiedSnapshot))
  board = await rpc('ch_leaderboard')
  check('slot limit applied to excess accepted submissions', () => assert.equal(board.length,2))
  check('deterministic tied Form timestamp order', () => assert.deepEqual(board.map(x=>x.team_id), ['CH01','CH02']))
  check('excess-accepted warning to administrator', () => assert.match(exceeded.warning,/exceed/))

  await reset(2)
  await rpc('ch_sync',JSON.stringify(snapshot))
  await db.exec("insert into teams(team_id,source_present,form_timestamp) values ('MISSING',true,null)")
  await rpc('ch_cutoff')
  await rpc('ch_finalize',JSON.stringify(snapshot))
  board = await rpc('ch_leaderboard')
  check('fallback by original form timestamp', () => assert.deepEqual(board.map(x=>x.team_id), ['CH01','CH02']))
  check('missing form time excluded', () => assert.equal(board.some(x=>x.team_id==='MISSING'),false))
  const storedQualifiers = (await db.query('select team_id, rank from teams where qualified order by rank')).rows
  check('qualification flags/ranks consistent', () => assert.deepEqual(storedQualifiers,board.map(x=>({team_id:x.team_id,rank:x.rank}))))

  await reset()
  await db.exec("insert into teams(team_id,source_present,form_timestamp) values ('MISSING',true,null)")
  const missingReceipt = await rpc('ch_submit','MISSING','TEST')
  check('website submission requires original registration timestamp', () => assert.equal(missingReceipt.error,'unknown_team'))
  await reset()
  await rpc('ch_sync',JSON.stringify(snapshot))
  await rpc('ch_sync',JSON.stringify(snapshot.slice(0,1)))
  const removed = await rpc('ch_submit','CH02','TEST')
  check('removed source team cannot submit or become fallback', () => assert.equal(removed.error,'unknown_team'))
  let rejected = false
  try { await rpc('ch_sync',JSON.stringify([snapshot[0],snapshot[0]])) } catch { rejected = true }
  check('duplicate Sheet IDs reject whole transaction', () => assert.equal(rejected,true))
  rejected = false
  try { await rpc('ch_sync',JSON.stringify([{team_id:'CH01',form_timestamp:'invalid'}])) } catch { rejected = true }
  check('invalid Sheet timestamp rejects whole transaction', () => assert.equal(rejected,true))
  await rpc('ch_cutoff')
  rejected = false
  try { await rpc('ch_finalize',JSON.stringify([{team_id:'CH01',form_timestamp:'invalid'}])) } catch { rejected = true }
  const pending = await rpc('ch_status')
  check('failed finalization leaves round ENDED and pending', () => { assert.equal(rejected,true); assert.equal(pending.status,'ENDED'); assert.equal(pending.finalized,false) })
  await rpc('ch_finalize',JSON.stringify(snapshot))
  const retried = await rpc('ch_status')
  check('failed finalization safely retries', () => assert.equal(retried.finalized,true))

  await reset()
  await rpc('ch_sync','[]'); await rpc('ch_cutoff'); await rpc('ch_finalize','[]')
  const emptyBoard = await rpc('ch_leaderboard')
  check('empty sheet finalizes empty leaderboard', () => assert.deepEqual(emptyBoard,[]))

  await reset()
  const fifteenSlots = rows(Array.from({length:17},(_,i)=>'LIMIT'+String(i).padStart(2,'0')))
  await rpc('ch_sync',JSON.stringify(fifteenSlots))
  for (const row of [...fifteenSlots].reverse()) await rpc('ch_submit',row.team_id,'nonempty-pin')
  await rpc('ch_cutoff'); await rpc('ch_finalize',JSON.stringify(fifteenSlots))
  const limited = await rpc('ch_leaderboard')
  check('default fifteen slots selects earliest fifteen Form registrations',()=>assert.deepEqual(limited.map(x=>x.team_id),fifteenSlots.slice(0,15).map(x=>x.team_id)))
  const privateTeams = await rpc('ch_teams',0)
  check('organizer team RPC omits submitted PIN values',()=>assert.ok(privateTeams.every(row=>!('tinkercad_code' in row))))

  for (const role of ['anon','authenticated']) {
    const privileges = (await db.query("select has_table_privilege($1,'public.teams','SELECT') as read, has_function_privilege($1,'public.ch_submit(text,text)','EXECUTE') as submit",[role])).rows[0]
    check(role + ' cannot read teams or call submission RPC', () => { assert.equal(privileges.read,false); assert.equal(privileges.submit,false) })
    const functionPrivileges = (await db.query("select p.proname, has_function_privilege($1,p.oid,'EXECUTE') as allowed from pg_proc p join pg_namespace n on p.pronamespace=n.oid where n.nspname='public' and left(p.proname,3)='ch_'",[role])).rows
    check(role + ' cannot call ANY privileged competition RPC',()=>assert.equal(functionPrivileges.every(row=>row.allowed===false),true))
  }
  const secure = (await db.query("select relrowsecurity from pg_class where oid='public.teams'::regclass")).rows[0]
  check('RLS enabled', () => assert.equal(secure.relrowsecurity,true))
  // Verify the read-only audit detects alternate exposures in a disposable database.
  await db.exec(`
    create view public.audit_fixture_view as select team_id from public.teams;
    grant select on public.audit_fixture_view to anon;
    grant select (team_id) on public.teams to authenticated;
    create function public.audit_fixture_rpc() returns text language sql security definer
      as $$ select team_id from public.teams limit 1 $$;
  `)
  const beforeAudit = await rpc('ch_overview')
  const audit = await db.exec(await readFile(new URL('../../backend/sql/003_security_audit.sql', import.meta.url), 'utf8'))
  const auditRows = audit.flatMap(result => result.rows)
  check('audit includes browser-readable preexisting views', () => assert.ok(auditRows.some(row => row.relation === 'audit_fixture_view' && row.role_name === 'anon' && row.can_select)))
  check('audit detects column-only read grants', () => assert.ok(auditRows.some(row => row.relation === 'teams' && row.role_name === 'authenticated' && !row.can_select && row.can_select_any_column)))
  check('audit includes noncompetition security-definer RPC exposures', () => assert.ok(auditRows.some(row => row.function_name === 'audit_fixture_rpc()' && row.role_name === 'anon' && row.can_execute && row.security_definer)))
  const afterAudit = await rpc('ch_overview')
  check('audit leaves competition settings and counts unchanged', () => assert.deepEqual(afterAudit, beforeAudit))
  console.log(`\n${count} production SQL checks passed in isolated PostgreSQL.`)
} finally { await db.close() }
