-- REVIEW/APPROVAL REQUIRED before applying remotely. Installs reset; does NOT run it.
-- Changes only the existing simplified namespace/RPCs. Never touches advanced tables.
begin;
do $$ begin
  if coalesce(public.ch_simple_policy()->>'simple_competition','') not in ('2','3') then
    raise exception 'Apply reviewed simplified 006 first; do not reset/recreate any database';
  end if;
end $$;

create or replace function public.ch_simple_policy() returns jsonb
language sql security invoker set search_path='' as $$
  select jsonb_build_object('simple_competition',3)
$$;

create or replace function public.ch_simple_submit(p_team_id text,p_code text) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare normalized text;
begin
  -- Submission and reset share a namespace-specific transaction lock.
  perform pg_advisory_xact_lock_shared(hashtextextended('chronohunt_simple.submissions',0));
  normalized:=upper(btrim(p_team_id));
  if normalized is null or length(normalized) not between 1 and 32
    or length(btrim(normalized))=0 or normalized ~ '[[:cntrl:]]' then
    return jsonb_build_object('error','invalid_team');
  end if;
  if p_code is null or length(btrim(p_code)) not between 1 and 256 or p_code ~ '[[:cntrl:]]' then
    return jsonb_build_object('error','invalid_code');
  end if;
  insert into chronohunt_simple.submissions(team_id,pin,accepted_at)
    values (normalized,btrim(p_code),clock_timestamp()) on conflict(team_id) do nothing;
  if not found then return jsonb_build_object('error','duplicate_submission'); end if;
  insert into chronohunt_simple.audit(event,details)
    values ('submission_accepted',jsonb_build_object('team_id',normalized));
  return jsonb_build_object('accepted',true);
end $$;

create or replace function public.ch_simple_reset() returns jsonb
language plpgsql security invoker set search_path='' as $$
declare removed bigint;
begin
  perform pg_advisory_xact_lock(hashtextextended('chronohunt_simple.submissions',0));
  -- Exact isolated table only. No TRUNCATE, cascade, schema reset or sequence reset.
  delete from chronohunt_simple.submissions;
  get diagnostics removed=row_count;
  -- Preserve audit history; never record IDs, PINs or credentials in the reset event.
  insert into chronohunt_simple.audit(event,details)
    values ('submissions_reset',jsonb_build_object('deleted',removed));
  return jsonb_build_object('reset',true,'deleted',removed);
end $$;

grant delete on chronohunt_simple.submissions to service_role;
revoke all on function public.ch_simple_reset(),public.ch_simple_submit(text,text),
  public.ch_simple_policy() from public,anon,authenticated;
grant execute on function public.ch_simple_reset(),public.ch_simple_submit(text,text),
  public.ch_simple_policy() to service_role;
notify pgrst, 'reload schema';
commit;
