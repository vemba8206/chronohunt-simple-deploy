-- Additive migration for EXISTING tables, after reviewing 000_inspect.sql.
-- Never creates/replaces teams or competition_settings; no reset or data deletion.
begin;

do $$
begin
  if not exists (select 1 from public.competition_settings where id = 1) then
    raise exception 'Missing competition_settings id=1; configure the existing round first';
  end if;
  if exists (select 1 from public.teams where team_id is null
    or team_id !~ '^[A-Z0-9][A-Z0-9_-]{0,31}$') then
    raise exception 'Review and normalize existing Team IDs before migration';
  end if;
  if exists (select 1 from public.competition_settings where id=1
    and (qualification_slots is null or qualification_slots < 1
      or tinkercad_status not in ('ACTIVE','ENDED')
      or (tinkercad_status='ENDED' and tinkercad_end_time is null))) then
    raise exception 'Invalid existing competition settings';
  end if;
end $$;

alter table public.teams add column if not exists source_present boolean not null default false;
alter table public.competition_settings add column if not exists finalized_at timestamptz;
alter table public.competition_settings add column if not exists last_synced_at timestamptz;
create table if not exists public.ch_audit (
  id bigint generated always as identity primary key,
  event text not null,
  occurred_at timestamptz not null default clock_timestamp(),
  details jsonb not null default '{}'::jsonb
);

alter table public.teams enable row level security;
alter table public.competition_settings enable row level security;
alter table public.ch_audit enable row level security;
-- Backend-only tables: no browser role grants, regardless of existing policies.
revoke all on public.teams, public.competition_settings, public.ch_audit from public, anon, authenticated;
grant all on public.teams, public.competition_settings, public.ch_audit to service_role;
revoke all on sequence public.ch_audit_id_seq from public, anon, authenticated;
grant usage, select on sequence public.ch_audit_id_seq to service_role;

-- All functions use invoker security. Only service_role can execute them.
create or replace function public.ch_status() returns jsonb
language sql security invoker set search_path = '' as $$
  select jsonb_build_object('status', tinkercad_status, 'finalized', finalized_at is not null)
  from public.competition_settings where id=1
$$;

create or replace function public.ch_team(p_team_id text) returns jsonb
language sql security invoker set search_path = '' as $$
  select jsonb_build_object('tinkercad_valid', coalesce(tinkercad_valid, false))
  from public.teams where team_id=p_team_id and source_present
$$;

create or replace function public.ch_submit(p_team_id text, p_code text) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare s public.competition_settings%rowtype; t public.teams%rowtype; accepted timestamptz;
begin
  select * into strict s from public.competition_settings where id=1 for update;
  if s.tinkercad_status <> 'ACTIVE' then
    return jsonb_build_object('error','round_closed');
  end if;
  select * into t from public.teams where team_id=p_team_id and source_present for update;
  if not found then return jsonb_build_object('error','unknown_team'); end if;
  if coalesce(t.tinkercad_valid,false) then
    return jsonb_build_object('error','duplicate_submission');
  end if;
  accepted := clock_timestamp();
  update public.teams set tinkercad_code=p_code, tinkercad_timestamp=accepted,
    tinkercad_valid=true, updated_at=accepted where id=t.id;
  return jsonb_build_object('accepted',true);
end $$;

-- Complete validated snapshot, not a partial import. Invalid/duplicate source aborts.
create or replace function public.ch_sync(p_rows jsonb) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare s public.competition_settings%rowtype; n integer;
begin
  select * into strict s from public.competition_settings where id=1 for update;
  if s.finalized_at is not null then
    return jsonb_build_object('count',0,'skipped',true,'message','Finalized results are immutable.');
  end if;
  if jsonb_typeof(p_rows) <> 'array' then raise exception 'Expected source array'; end if;
  if exists (select 1 from jsonb_array_elements(p_rows) r
    where r->>'team_id' is null or r->>'team_id' !~ '^[A-Z0-9][A-Z0-9_-]{0,31}$'
      or r->>'form_timestamp' is null
      or r->>'form_timestamp' !~ '(Z|[+-][0-9]{2}:[0-9]{2})$') then
    raise exception 'Invalid source identifiers/timestamps';
  end if;
  if exists (select 1 from jsonb_array_elements(p_rows) r
    group by r->>'team_id' having count(*) > 1) then raise exception 'Duplicate source identifiers'; end if;
  update public.teams set source_present=false where source_present;
  insert into public.teams (id, team_id, form_timestamp, source_present, created_at, updated_at)
  select gen_random_uuid(), r->>'team_id', (r->>'form_timestamp')::timestamptz, true, clock_timestamp(), clock_timestamp()
    from jsonb_array_elements(p_rows) r
  on conflict (team_id) do update set
    form_timestamp=excluded.form_timestamp, source_present=true, updated_at=excluded.updated_at;
  n := jsonb_array_length(p_rows);
  update public.competition_settings set last_synced_at=clock_timestamp(), updated_at=clock_timestamp() where id=1;
  insert into public.ch_audit(event,details) values ('sheet_sync',jsonb_build_object('count',n));
  return jsonb_build_object('count',n,'skipped',false);
end $$;

create or replace function public.ch_cutoff() returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare s public.competition_settings%rowtype; cutoff timestamptz;
begin
  select * into strict s from public.competition_settings where id=1 for update;
  if s.tinkercad_status='ACTIVE' then
    cutoff := clock_timestamp();
    update public.competition_settings set tinkercad_status='ENDED', tinkercad_end_time=cutoff,
      updated_at=cutoff where id=1;
    insert into public.ch_audit(event) values ('round_ended');
  end if;
  return jsonb_build_object('status','ENDED','finalized',s.finalized_at is not null);
end $$;

create or replace function public.ch_finalize(p_rows jsonb) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare s public.competition_settings%rowtype; valid_count integer; selected_count integer;
begin
  select * into strict s from public.competition_settings where id=1 for update;
  if s.tinkercad_status <> 'ENDED' then return jsonb_build_object('error','round_active'); end if;
  if s.finalized_at is not null then
    return jsonb_build_object('status','ENDED','finalized',true,'already_finalized',true);
  end if;
  -- Source refresh and ranking commit together. A bad snapshot leaves cutoff intact.
  perform public.ch_sync(p_rows);
  select count(*) into valid_count from public.teams
    where tinkercad_valid is true and tinkercad_timestamp < s.tinkercad_end_time;
  update public.teams set qualified=false, rank=null;
  with candidates as (
    select id, team_id, 0 as priority, tinkercad_timestamp as ordering_time
    from public.teams where tinkercad_valid is true and tinkercad_timestamp < s.tinkercad_end_time
    union all
    select id, team_id, 1 as priority, form_timestamp as ordering_time
    from public.teams where source_present and coalesce(tinkercad_valid,false)=false and form_timestamp is not null
  ), ordered as (
    select id, row_number() over (order by priority, ordering_time, team_id collate "C", id) as position
    from candidates
  )
  update public.teams t set qualified=true, rank=o.position::integer, updated_at=clock_timestamp()
    from ordered o where t.id=o.id and o.position <= s.qualification_slots;
  get diagnostics selected_count = row_count;
  update public.competition_settings set finalized_at=clock_timestamp(), updated_at=clock_timestamp() where id=1;
  insert into public.ch_audit(event,details) values ('round_finalized',
    jsonb_build_object('qualified',selected_count,'valid',valid_count,'slots',s.qualification_slots));
  return jsonb_build_object('status','ENDED','finalized',true,'qualified',selected_count,
    'warning',case when valid_count > s.qualification_slots then
      'Valid submissions exceed qualification slots; only the earliest qualify.' else null end);
end $$;

create or replace function public.ch_leaderboard() returns jsonb
language sql security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('rank',position,'team_id',team_id) order by position),'[]'::jsonb)
  from (
    select t.team_id, t.rank::bigint as position from public.teams t, public.competition_settings s
      where s.id=1 and s.finalized_at is not null and t.qualified is true
    union all
    select t.team_id, row_number() over (order by t.tinkercad_timestamp, t.team_id collate "C", t.id) as position
      from public.teams t, public.competition_settings s
      where s.id=1 and s.finalized_at is null and t.tinkercad_valid is true
        and (s.tinkercad_status='ACTIVE' or t.tinkercad_timestamp < s.tinkercad_end_time)
  ) positions
$$;

create or replace function public.ch_overview() returns jsonb
language sql security invoker set search_path = '' as $$
  select jsonb_build_object('status',s.tinkercad_status,'finalized',s.finalized_at is not null,
    'cutoff',s.tinkercad_end_time,'qualification_slots',s.qualification_slots,
    'last_synced_at',s.last_synced_at,
    'teams',(select count(*) from public.teams where source_present),
    'accepted',(select count(*) from public.teams where tinkercad_valid is true))
  from public.competition_settings s where id=1
$$;

create or replace function public.ch_teams(p_offset integer default 0) returns jsonb
language sql security invoker set search_path = '' as $$
  select coalesce(jsonb_agg(to_jsonb(t)),'[]'::jsonb) from (
    select team_id, form_timestamp, tinkercad_timestamp, tinkercad_valid, qualified, rank, source_present
    from public.teams order by team_id collate "C" limit 100 offset greatest(p_offset,0)
  ) t
$$;

-- Functions default to PUBLIC execute: revoke explicitly for EVERY application function.
revoke all on function public.ch_status(), public.ch_team(text), public.ch_submit(text,text),
  public.ch_sync(jsonb), public.ch_cutoff(), public.ch_finalize(jsonb), public.ch_leaderboard(),
  public.ch_overview(), public.ch_teams(integer) from public, anon, authenticated;
grant execute on function public.ch_status(), public.ch_team(text), public.ch_submit(text,text),
  public.ch_sync(jsonb), public.ch_cutoff(), public.ch_finalize(jsonb), public.ch_leaderboard(),
  public.ch_overview(), public.ch_teams(integer) to service_role;
commit;
