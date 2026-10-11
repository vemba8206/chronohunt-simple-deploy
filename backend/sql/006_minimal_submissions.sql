-- Reviewed locally only. Additive upgrade of 004; never reset existing submissions.
-- No remote application without explicit approval. Advanced ch_* objects untouched.
begin;
do $$ begin
  if public.ch_simple_policy()->>'simple_competition' not in ('1','2') then
    raise exception 'Expected simplified schema version 1 or 2';
  end if;
end $$;

alter table chronohunt_simple.submissions drop constraint submissions_team_id_check;
alter table chronohunt_simple.submissions add constraint submissions_team_id_check
  check (length(team_id) between 1 and 32 and length(btrim(team_id))>0 and team_id !~ '[[:cntrl:]]');

create or replace function public.ch_simple_policy() returns jsonb
language sql security invoker set search_path='' as $$
  select jsonb_build_object('simple_competition',2)
$$;

create or replace function public.ch_simple_status() returns jsonb
language sql security invoker set search_path='' as $$
  -- Query the configured submission table; old settings no longer control acceptance.
  select jsonb_build_object('submissions_enabled',true) from
    (select count(*) from chronohunt_simple.submissions) available
$$;

create or replace function public.ch_simple_submit(p_team_id text,p_code text) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare normalized text;
begin
  normalized:=upper(btrim(p_team_id));
  if normalized is null or length(normalized) not between 1 and 32
    or length(btrim(normalized))=0 or normalized ~ '[[:cntrl:]]' then
    return jsonb_build_object('error','invalid_team');
  end if;
  if p_code is null or length(btrim(p_code)) not between 1 and 256 or p_code ~ '[[:cntrl:]]' then
    return jsonb_build_object('error','invalid_code');
  end if;
  -- The primary key serializes competing inserts. Neither PIN nor timestamp is replaced.
  insert into chronohunt_simple.submissions(team_id,pin,accepted_at)
    values (normalized,btrim(p_code),clock_timestamp()) on conflict(team_id) do nothing;
  if not found then return jsonb_build_object('error','duplicate_submission'); end if;
  insert into chronohunt_simple.audit(event,details)
    values ('submission_accepted',jsonb_build_object('team_id',normalized));
  return jsonb_build_object('accepted',true);
end $$;

create or replace function public.ch_simple_leaderboard() returns jsonb
language sql security invoker set search_path='' as $$
  select coalesce(jsonb_agg(jsonb_build_object('rank',position,'team_id',team_id,
    'accepted_at',accepted_at) order by position),'[]'::jsonb)
  from (select team_id,accepted_at,row_number() over(order by accepted_at,team_id collate "C") position
    from chronohunt_simple.submissions) board
$$;

create or replace function public.ch_simple_overview() returns jsonb
language sql security invoker set search_path='' as $$
  select public.ch_simple_status() || jsonb_build_object('teams',count(*),'accepted',count(*))
    from chronohunt_simple.submissions
$$;

-- Keep historical settings/ranks/data intact, but retire the old workflow RPC permissions.
revoke all on function public.ch_simple_deadline(timestamptz),public.ch_simple_cutoff(),
  public.ch_simple_finalize() from public,anon,authenticated,service_role;
revoke all on function public.ch_simple_policy(),public.ch_simple_status(),
  public.ch_simple_submit(text,text),public.ch_simple_leaderboard(),public.ch_simple_overview()
  from public,anon,authenticated;
grant execute on function public.ch_simple_policy(),public.ch_simple_status(),
  public.ch_simple_submit(text,text),public.ch_simple_leaderboard(),public.ch_simple_overview()
  to service_role;
notify pgrst, 'reload schema';
commit;
