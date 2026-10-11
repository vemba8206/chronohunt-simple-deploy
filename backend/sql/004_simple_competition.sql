-- SIMPLIFIED VERSION ONLY. Review + backup + explicit approval before remote use.
-- Standalone: never execute 001/002 as prerequisites against production.
-- New isolated schema/RPCs; does not replace ch_* or alter existing competition data.
-- One-time migration: existing namespace/RPC collisions abort, never reset anything.
begin;
do $$
begin
  if exists (select 1 from pg_namespace where nspname='chronohunt_simple')
    or exists (select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
      where n.nspname='public' and p.proname like 'ch_simple_%') then
    raise exception 'Simplified objects already exist. Review them; do not reset or blindly reapply.';
  end if;
end $$;

create schema chronohunt_simple;
create table chronohunt_simple.settings (
  id integer primary key check (id=1),
  status text not null default 'ACTIVE' check (status in ('ACTIVE','ENDED')),
  cutoff_at timestamptz,
  finalized_at timestamptz
);
insert into chronohunt_simple.settings(id) values (1);
create table chronohunt_simple.submissions (
  team_id text primary key check (team_id ~ '^[A-Z0-9][A-Z0-9_-]{0,31}$'),
  pin text not null check (length(btrim(pin)) between 1 and 256 and pin !~ '[[:cntrl:]]'),
  accepted_at timestamptz not null,
  rank integer unique check (rank>0)
);
create table chronohunt_simple.audit (
  id bigint generated always as identity primary key,
  event text not null,
  occurred_at timestamptz not null default clock_timestamp(),
  details jsonb not null default '{}'::jsonb
);
revoke all on schema chronohunt_simple from public, anon, authenticated;
grant usage on schema chronohunt_simple to service_role;
alter table chronohunt_simple.settings enable row level security;
alter table chronohunt_simple.submissions enable row level security;
alter table chronohunt_simple.audit enable row level security;
revoke all on all tables in schema chronohunt_simple from public, anon, authenticated;
grant select, insert, update on all tables in schema chronohunt_simple to service_role;
revoke all on all sequences in schema chronohunt_simple from public, anon, authenticated;
grant usage, select on all sequences in schema chronohunt_simple to service_role;

create function public.ch_simple_policy() returns jsonb
language sql security invoker set search_path='' as $$
  select jsonb_build_object('simple_competition',1)
$$;

create function public.ch_simple_status() returns jsonb
language sql security invoker set search_path='' as $$
  select jsonb_build_object(
    'status',case when status='ENDED' or cutoff_at<=clock_timestamp() then 'ENDED' else 'ACTIVE' end,
    'finalized',finalized_at is not null,
    'submissions_enabled',status='ACTIVE' and finalized_at is null
      and cutoff_at is not null and clock_timestamp()<cutoff_at)
  from chronohunt_simple.settings where id=1
$$;

create function public.ch_simple_team(p_team_id text) returns jsonb
language sql security invoker set search_path='' as $$
  select jsonb_build_object('accepted',true)
  from chronohunt_simple.submissions where team_id=upper(btrim(p_team_id))
$$;

create function public.ch_simple_submit(p_team_id text,p_code text) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare s chronohunt_simple.settings%rowtype; received timestamptz; normalized text;
begin
  select * into strict s from chronohunt_simple.settings where id=1 for update;
  normalized:=upper(btrim(p_team_id));
  if normalized is null or normalized !~ '^[A-Z0-9][A-Z0-9_-]{0,31}$' then
    return jsonb_build_object('error','invalid_team');
  end if;
  if p_code is null or length(btrim(p_code)) not between 1 and 256 or p_code ~ '[[:cntrl:]]' then
    return jsonb_build_object('error','invalid_code');
  end if;
  -- Read the actual database clock AFTER acquiring the same lock as cutoff/finalize.
  received:=clock_timestamp();
  if s.status<>'ACTIVE' or s.finalized_at is not null
    or (s.cutoff_at is not null and received>=s.cutoff_at) then
    return jsonb_build_object('error','round_closed');
  end if;
  if s.cutoff_at is null then return jsonb_build_object('error','deadline_required'); end if;
  if exists (select 1 from chronohunt_simple.submissions where team_id=normalized) then
    return jsonb_build_object('error','duplicate_submission');
  end if;
  insert into chronohunt_simple.submissions(team_id,pin,accepted_at)
    values (normalized,btrim(p_code),received);
  insert into chronohunt_simple.audit(event,details)
    values ('submission_accepted',jsonb_build_object('team_id',normalized));
  return jsonb_build_object('accepted',true);
end $$;

create function public.ch_simple_deadline(p_cutoff timestamptz) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare s chronohunt_simple.settings%rowtype; observed_at timestamptz;
begin
  select * into strict s from chronohunt_simple.settings where id=1 for update;
  observed_at:=clock_timestamp();
  if s.status<>'ACTIVE' or s.finalized_at is not null or s.cutoff_at<=observed_at then
    return jsonb_build_object('error','round_closed');
  end if;
  if p_cutoff is null or p_cutoff<=observed_at or not isfinite(p_cutoff) then
    return jsonb_build_object('error','invalid_deadline');
  end if;
  update chronohunt_simple.settings set cutoff_at=p_cutoff where id=1;
  insert into chronohunt_simple.audit(event,details)
    values ('deadline_configured',jsonb_build_object('cutoff',p_cutoff));
  return jsonb_build_object('cutoff',p_cutoff);
end $$;

create function public.ch_simple_cutoff() returns jsonb
language plpgsql security invoker set search_path='' as $$
declare s chronohunt_simple.settings%rowtype; observed_at timestamptz;
begin
  select * into strict s from chronohunt_simple.settings where id=1 for update;
  if s.status='ACTIVE' and s.finalized_at is null then
    observed_at:=clock_timestamp();
    update chronohunt_simple.settings set status='ENDED',
      cutoff_at=case when cutoff_at is null then observed_at else least(cutoff_at,observed_at) end
      where id=1;
    insert into chronohunt_simple.audit(event) values ('round_ended');
  end if;
  return public.ch_simple_status();
end $$;

create function public.ch_simple_finalize() returns jsonb
language plpgsql security invoker set search_path='' as $$
declare s chronohunt_simple.settings%rowtype; eligible integer;
begin
  select * into strict s from chronohunt_simple.settings where id=1 for update;
  if s.finalized_at is not null then
    return jsonb_build_object('status','ENDED','finalized',true,'already_finalized',true);
  end if;
  if s.cutoff_at is null or clock_timestamp()<s.cutoff_at then
    return jsonb_build_object('error','round_active');
  end if;
  -- Only this version's accepted submissions; no Google rows or qualifier fallback.
  with ordered as (
    select team_id,row_number() over(order by accepted_at,team_id collate "C") as position
    from chronohunt_simple.submissions where accepted_at<s.cutoff_at
  )
  update chronohunt_simple.submissions t set rank=o.position::integer
    from ordered o where t.team_id=o.team_id;
  get diagnostics eligible=row_count;
  update chronohunt_simple.settings set status='ENDED',finalized_at=clock_timestamp() where id=1;
  insert into chronohunt_simple.audit(event,details)
    values ('results_finalized',jsonb_build_object('submissions',eligible));
  return jsonb_build_object('status','ENDED','finalized',true,'submissions',eligible);
end $$;

create function public.ch_simple_leaderboard() returns jsonb
language sql security invoker set search_path='' as $$
  select coalesce(jsonb_agg(jsonb_build_object('rank',position,'team_id',team_id) order by position),'[]'::jsonb)
  from (
    select t.team_id,t.rank::bigint as position from chronohunt_simple.submissions t
      cross join chronohunt_simple.settings s where s.id=1 and s.finalized_at is not null and t.rank is not null
    union all
    select t.team_id,row_number() over(order by t.accepted_at,t.team_id collate "C") as position
      from chronohunt_simple.submissions t cross join chronohunt_simple.settings s
      where s.id=1 and s.finalized_at is null and t.accepted_at<s.cutoff_at
  ) board
$$;

create function public.ch_simple_overview() returns jsonb
language sql security invoker set search_path='' as $$
  select public.ch_simple_status() || jsonb_build_object('cutoff',s.cutoff_at,
    'teams',(select count(*) from chronohunt_simple.submissions),
    'accepted',(select count(*) from chronohunt_simple.submissions where accepted_at<s.cutoff_at))
  from chronohunt_simple.settings s where id=1
$$;

create function public.ch_simple_teams(p_offset integer default 0) returns jsonb
language sql security invoker set search_path='' as $$
  select coalesce(jsonb_agg(to_jsonb(t) order by t.accepted_at,t.team_id collate "C"),'[]'::jsonb)
  from (select team_id,accepted_at,rank from chronohunt_simple.submissions
    order by accepted_at,team_id collate "C" limit 100 offset greatest(p_offset,0)) t
$$;

revoke all on function public.ch_simple_policy(),public.ch_simple_status(),public.ch_simple_team(text),
  public.ch_simple_submit(text,text),public.ch_simple_deadline(timestamptz),public.ch_simple_cutoff(),
  public.ch_simple_finalize(),public.ch_simple_leaderboard(),public.ch_simple_overview(),
  public.ch_simple_teams(integer) from public,anon,authenticated;
grant execute on function public.ch_simple_policy(),public.ch_simple_status(),public.ch_simple_team(text),
  public.ch_simple_submit(text,text),public.ch_simple_deadline(timestamptz),public.ch_simple_cutoff(),
  public.ch_simple_finalize(),public.ch_simple_leaderboard(),public.ch_simple_overview(),
  public.ch_simple_teams(integer) to service_role;
commit;
