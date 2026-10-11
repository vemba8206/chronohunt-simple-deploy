-- READ ONLY: run in the existing Supabase project's SQL editor BEFORE 001.
select table_name, column_name, data_type, is_nullable, column_default
from information_schema.columns
where table_schema = 'public' and table_name in ('teams', 'competition_settings')
order by table_name, ordinal_position;

select tablename, rowsecurity from pg_tables
where schemaname = 'public' and tablename in ('teams', 'competition_settings');
select tablename, policyname, roles, cmd, qual, with_check from pg_policies
where schemaname = 'public' and tablename in ('teams', 'competition_settings');
select table_name, grantee, privilege_type from information_schema.role_table_grants
where table_schema = 'public' and table_name in ('teams', 'competition_settings');
select conrelid::regclass as table_name, conname, pg_get_constraintdef(oid)
from pg_constraint where conrelid in ('public.teams'::regclass, 'public.competition_settings'::regclass);
select id, tinkercad_status, tinkercad_end_time, qualification_slots
from public.competition_settings;
select upper(btrim(team_id)) as normalized_id, count(*) from public.teams
group by upper(btrim(team_id)) having count(*) > 1;

-- REVIEW: existing triggers may modify timestamps/ranking. Do not remove blindly.
select event_object_table, trigger_name, action_statement
from information_schema.triggers where event_object_schema = 'public'
and event_object_table in ('teams', 'competition_settings');
