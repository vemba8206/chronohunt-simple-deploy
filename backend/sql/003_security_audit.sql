-- READ ONLY. Run in the EXISTING project SQL editor; makes no schema changes.
select table_name, column_name, data_type, is_nullable from information_schema.columns
where table_schema='public' and table_name in ('teams','competition_settings')
order by table_name, ordinal_position;
select id, tinkercad_status, tinkercad_end_time, qualification_slots, finalized_at
from public.competition_settings where id=1;
select tablename, rowsecurity from pg_tables
where schemaname='public' and tablename in ('teams','competition_settings','ch_audit');
select tablename, policyname, roles, cmd, qual, with_check from pg_policies
where schemaname='public' and tablename in ('teams','competition_settings','ch_audit');
select role_name, relation, has_table_privilege(role_name,relation,'SELECT') as can_select,
  has_table_privilege(role_name,relation,'INSERT') as can_insert,
  has_table_privilege(role_name,relation,'UPDATE') as can_update
from (values ('anon'),('authenticated')) r(role_name)
cross join (values ('public.teams'),('public.competition_settings'),('public.ch_audit')) t(relation);
select r.role_name, p.oid::regprocedure as function_name,
  has_function_privilege(r.role_name,p.oid,'EXECUTE') as can_execute, p.prosecdef as security_definer
from pg_proc p join pg_namespace n on p.pronamespace=n.oid
cross join (values ('anon'),('authenticated')) r(role_name)
where n.nspname='public' and p.prokind='f'
order by function_name, r.role_name;
-- Include existing views/materialized views, foreign tables and column-only grants.
-- A readable owner-security view may bypass underlying table RLS.
select r.role_name, c.oid::regclass as relation, c.relkind,
  c.relrowsecurity, c.relforcerowsecurity, c.reloptions,
  has_table_privilege(r.role_name,c.oid,'SELECT') as can_select,
  has_table_privilege(r.role_name,c.oid,'INSERT') as can_insert,
  has_table_privilege(r.role_name,c.oid,'UPDATE') as can_update,
  has_table_privilege(r.role_name,c.oid,'DELETE') as can_delete,
  has_any_column_privilege(r.role_name,c.oid,'SELECT') as can_select_any_column
from pg_class c join pg_namespace n on n.oid=c.relnamespace
cross join (values ('anon'),('authenticated')) r(role_name)
where n.nspname='public' and c.relkind in ('r','p','v','m','f')
order by relation, r.role_name;
-- Inspect preexisting objects that might expose these tables outside this app.
select routine_name, security_type from information_schema.routines
where routine_schema='public';
select table_name, view_definition from information_schema.views where table_schema='public';
select event_object_table, trigger_name, action_statement from information_schema.triggers
where event_object_schema='public' and event_object_table in ('teams','competition_settings');
select pg_get_functiondef('public.ch_sync(jsonb)'::regprocedure);
select upper(btrim(team_id)) as normalized_id, count(*) from public.teams
group by upper(btrim(team_id)) having count(*) > 1;
