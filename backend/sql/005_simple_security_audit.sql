-- SELECT-only review for the isolated simplified namespace. Run alongside retained 003.
select n.nspname,c.relname,c.relrowsecurity,
  has_table_privilege('anon',c.oid,'SELECT,INSERT,UPDATE,DELETE') as anon_access,
  has_table_privilege('authenticated',c.oid,'SELECT,INSERT,UPDATE,DELETE') as authenticated_access,
  has_any_column_privilege('anon',c.oid,'SELECT') as anon_columns,
  has_any_column_privilege('authenticated',c.oid,'SELECT') as authenticated_columns
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='chronohunt_simple' and c.relkind in ('r','v','m','f');
select n.nspname,p.proname,p.prosecdef,p.proconfig,
  has_function_privilege('anon',p.oid,'EXECUTE') as anon_execute,
  has_function_privilege('authenticated',p.oid,'EXECUTE') as authenticated_execute,
  pg_get_functiondef(p.oid) as definition
from pg_proc p join pg_namespace n on n.oid=p.pronamespace
where p.prokind='f' and n.nspname='public' and p.proname like 'ch_simple_%';
select * from pg_policies where schemaname='chronohunt_simple';
select event,occurred_at from chronohunt_simple.audit order by id desc limit 20;
select status,cutoff_at,finalized_at from chronohunt_simple.settings where id=1;
select count(*) as recorded_submissions from chronohunt_simple.submissions;
