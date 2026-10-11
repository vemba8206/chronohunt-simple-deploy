import assert from 'node:assert/strict'
import { isolatedDatabase, rpc } from '../scripts/simple-db.mjs'
const db = await isolatedDatabase()
let count = 0
const check = (name, fn) => { fn(); count++; console.log('PASS ' + name) }
const call = (name, args) => rpc(db, 'ch_simple_' + name, args)
try {
  check('minimal policy version', () => {})
  assert.deepEqual(await call('policy'), {simple_competition:3})
  assert.deepEqual(await call('status'), {submissions_enabled:true})
  const start=(await db.query('select clock_timestamp() as time')).rows[0].time
  assert.equal((await call('submit',{p_team_id:' new team ',p_code:' arbitrary PIN '})).accepted,true)
  const original=(await db.query('select * from chronohunt_simple.submissions')).rows[0]
  const end=(await db.query('select clock_timestamp() as time')).rows[0].time
  check('unregistered ID, arbitrary PIN and database receipt',()=> {
    assert.equal(original.team_id,'NEW TEAM');assert.equal(original.pin,'arbitrary PIN')
    assert.ok(original.accepted_at>=start && original.accepted_at<=end)
  })
  assert.equal((await call('submit',{p_team_id:' NeW tEaM ',p_code:'replacement'})).error,'duplicate_submission')
  check('trim/case duplicate preserves first PIN and time',()=>{})
  assert.deepEqual((await db.query('select * from chronohunt_simple.submissions')).rows[0],original)
  for(const [team,pin,error] of [[' ','x','invalid_team'],[null,'x','invalid_team'],['x'.repeat(33),'x','invalid_team'],['OK','','invalid_code'],['OK','  ','invalid_code'],['OK','x\ny','invalid_code'],['OK','x'.repeat(257),'invalid_code']]) {
    assert.equal((await call('submit',{p_team_id:team,p_code:pin})).error,error);count++
  }
  await db.exec("update chronohunt_simple.settings set status='ENDED',cutoff_at='2000-01-01Z',finalized_at='2000-01-02Z'")
  assert.equal((await call('submit',{p_team_id:'AFTER OLD CUTOFF',p_code:'x'})).accepted,true)
  check('historical cutoff/finalization cannot block acceptance',()=>{})
  await db.exec("update chronohunt_simple.submissions set accepted_at='2026-01-01Z';insert into chronohunt_simple.submissions(team_id,pin,accepted_at) values('EARLIEST','private-fixture','2025-01-01Z')")
  const board=await call('leaderboard')
  check('acceptance-time ordering with deterministic Team ID tie',()=>assert.deepEqual(board.map(r=>r.team_id),['EARLIEST','AFTER OLD CUTOFF','NEW TEAM']))
  check('public projection contains timestamp, never PIN',()=>assert.deepEqual(Object.keys(board[0]).sort(),['accepted_at','rank','team_id']))
  check('no qualification slots or frozen rank selection',()=>assert.deepEqual(board.map(r=>r.rank),[1,2,3]))
  assert.equal((await call('overview')).accepted,3)
  const overview=await call('overview')
  check('overview excludes competition deadlines',()=>assert.deepEqual(Object.keys(overview).sort(),['accepted','submissions_enabled','teams']))
  await db.exec("insert into chronohunt_simple.submissions(team_id,pin,accepted_at) select 'EXTRA-'||n,'private-fixture',clock_timestamp() from generate_series(1,16) n")
  assert.equal((await call('leaderboard')).length,19);count++
  const audit=(await db.query('select details from chronohunt_simple.audit')).rows
  check('audit contains no submitted PIN',()=>assert.ok(!JSON.stringify(audit).includes('arbitrary PIN')))
  for(const role of ['anon','authenticated']) {
    await db.exec('set role '+role)
    for(const sql of ['select * from chronohunt_simple.submissions','select public.ch_simple_leaderboard()',"select public.ch_simple_submit('ATTACK','x')",'select public.ch_simple_reset()']) {
      let denied=false;try {await db.exec(sql)}catch {denied=true}
      check(role+' denied table/RPC access',()=>assert.ok(denied))
    }
    await db.exec('reset role')
  }
  await db.exec('set role service_role')
  assert.equal((await call('leaderboard')).length,19)
  for(const sql of ['select public.ch_simple_cutoff()','select public.ch_simple_finalize()',"select public.ch_simple_deadline('2099-01-01Z')"]) {
    let denied=false;try{await db.exec(sql)}catch{denied=true}
    check('retired workflow unavailable to backend role',()=>assert.ok(denied))
  }
  await db.exec('reset role')
  await db.exec("create table public.unrelated_fixture(id integer primary key, original text);insert into public.unrelated_fixture values(1,'preserved');")
  const saved = (await db.query('select * from public.unrelated_fixture')).rows
  const oldSettings = (await db.query('select * from chronohunt_simple.settings')).rows
  // Force audit failure to prove DELETE and audit are one transaction.
  await db.exec("create function public.fail_reset_fixture() returns trigger language plpgsql as $$begin if new.event='submissions_reset' then raise exception 'fixture audit failure';end if;return new;end$$;create trigger fail_reset_fixture before insert on chronohunt_simple.audit for each row execute function public.fail_reset_fixture();")
  let failed=false;try{await call('reset')}catch{failed=true}
  check('failed reset rolls back deletion',()=>assert.ok(failed))
  assert.equal((await call('leaderboard')).length,19)
  await db.exec('drop trigger fail_reset_fixture on chronohunt_simple.audit;drop function public.fail_reset_fixture()')
  await db.exec('set role service_role')
  assert.deepEqual(await call('reset'),{reset:true,deleted:19})
  assert.deepEqual(await call('leaderboard'),[])
  check('authenticated-role reset clears only simplified submissions',()=>{})
  assert.equal((await call('overview')).accepted,0)
  assert.equal((await call('submit',{p_team_id:' new team ',p_code:'new private fixture'})).accepted,true)
  const fresh=await call('leaderboard')
  check('same team can submit after reset with rank starting at one',()=>assert.equal(fresh[0].rank,1))
  assert.deepEqual(await call('reset'),{reset:true,deleted:1})
  assert.deepEqual(await call('reset'),{reset:true,deleted:0})
  await db.exec('reset role')
  check('unrelated data and historical settings preserved',()=>{})
  assert.deepEqual((await db.query('select * from public.unrelated_fixture')).rows,saved)
  assert.deepEqual((await db.query('select * from chronohunt_simple.settings')).rows,oldSettings)
  const events=(await db.query("select details from chronohunt_simple.audit where event='submissions_reset' order by id")).rows
  check('reset audit retains only deleted counts',()=>assert.deepEqual(events.map(e=>e.details),[{deleted:19},{deleted:1},{deleted:0}]))
} finally {await db.close()}
console.log(count+' isolated SQL checks passed.')
