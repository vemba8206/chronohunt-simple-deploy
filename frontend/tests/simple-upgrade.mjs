// Compatibility with both the already-applied original and unapplied advanced draft.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { PGlite } from '@electric-sql/pglite'
const sql = name => readFile(new URL('../../backend/sql/' + name, import.meta.url),'utf8')
for(const includeDraft of [false,true]) {
  const db = new PGlite()
  try {
    await db.exec(`create role anon;create role authenticated;create role service_role bypassrls;
      create table public.teams(id uuid primary key default gen_random_uuid(),team_id text unique,
        form_timestamp timestamptz,tinkercad_code text,tinkercad_timestamp timestamptz,
        tinkercad_valid boolean default false,qualified boolean default false,rank integer,
        created_at timestamptz default now(),updated_at timestamptz default now());
      create table public.competition_settings(id integer primary key,tinkercad_status text,
        tinkercad_end_time timestamptz,qualification_slots integer,updated_at timestamptz default now());
      insert into public.competition_settings values(1,'ACTIVE',null,15,now());`)
    await db.exec(await sql('001_competition.sql'))
    if(includeDraft) await db.exec(await sql('002_registration_integrity.sql'))
    await db.exec(`insert into public.teams(team_id,form_timestamp,tinkercad_valid,tinkercad_timestamp,tinkercad_code,qualified,rank,source_present)
      values('PRESERVED','2026-01-01Z',true,'2026-01-01Z','private-fixture',true,1,true);
      update public.competition_settings set tinkercad_status='ENDED',tinkercad_end_time='2026-01-02Z',finalized_at='2026-01-03Z';
      insert into public.ch_audit(event)values('preserved_event');`)
    const before=await db.query('select to_jsonb(t) team,to_jsonb(s) settings from public.teams t cross join public.competition_settings s')
    const functions=await db.query("select proname,pg_get_functiondef(p.oid) definition from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and proname like 'ch_%' order by proname")
    const audit=await db.query('select * from public.ch_audit order by id')
    await db.exec(await sql('004_simple_competition.sql'))
    await db.exec("insert into chronohunt_simple.submissions(team_id,pin,accepted_at,rank) values('SAVED','private-fixture','2026-01-01Z',1);update chronohunt_simple.settings set status='ENDED',cutoff_at='2026-01-02Z',finalized_at='2026-01-03Z'")
    const simpleBefore = await db.query('select to_jsonb(t) submission,to_jsonb(s) settings from chronohunt_simple.submissions t cross join chronohunt_simple.settings s')
    await db.exec(await sql('006_minimal_submissions.sql'))
    await db.exec(await sql('007_organizer_reset.sql'))
    assert.deepEqual((await db.query('select to_jsonb(t) submission,to_jsonb(s) settings from chronohunt_simple.submissions t cross join chronohunt_simple.settings s')).rows,simpleBefore.rows)
    assert.deepEqual((await db.query('select to_jsonb(t) team,to_jsonb(s) settings from public.teams t cross join public.competition_settings s')).rows,before.rows)
    assert.deepEqual((await db.query("select proname,pg_get_functiondef(p.oid) definition from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and proname like 'ch_%' and proname not like 'ch_simple_%' order by proname")).rows,functions.rows)
    assert.deepEqual((await db.query('select * from public.ch_audit order by id')).rows,audit.rows)
    await db.exec(await sql('005_simple_security_audit.sql'))
    let collision=false;try {await db.exec(await sql('004_simple_competition.sql'))}catch {collision=true;await db.exec('rollback')}
    assert.ok(collision)
    assert.deepEqual((await db.query('select * from public.ch_audit order by id')).rows,audit.rows)
    console.log('PASS independent migration preserves records/settings/frozen ranks/audit/RPCs after '+(includeDraft?'001 + 002':'001 only')+'; read-only 005 executes; reapplication aborts safely')
  } finally {await db.close()}
}
console.log('2 isolated compatibility scenarios passed.')
