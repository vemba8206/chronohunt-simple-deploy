# Exact database change for review — no remote application performed

New file: backend/sql/007_organizer_reset.sql. Read that complete SQL before approval.

It checks existing simplified policy version 2/3, changes it to 3, replaces only ch_simple_submit to acquire a shared transaction advisory lock, and creates ch_simple_reset with an exclusive lock on the same simplified namespace. Reset executes exactly:

```sql
delete from chronohunt_simple.submissions;
```

That DELETE is **inside the function definition**; the migration does not call the function and does not delete existing rows. The function stores only a deleted-row count in the existing simplified audit table. It uses security invoker with an empty search_path, grants DELETE solely on the exact simplified table to service_role and denies browser/public reset execution. Existing backend authentication/Origin/CSRF protects the HTTP endpoint. Audit failure rolls the entire RPC back, including deletion. No TRUNCATE, CASCADE, schema drop, database reset or settings/sequence reset is used.

Conditional prerequisites after live audit: absent simplified schema requires reviewed standalone 004 followed by 006 then 007. Existing schema at version 1 requires 006 then 007; version 2 requires only 007. Inspect any unexpected schema before choosing SQL. 004 explicitly aborts on namespace/function collisions. Existing advanced 001/002 are not prerequisites to run remotely and must not be rerun. Read-only audits 003/005 support grant review; do not display private PIN rows or paste secrets in chat. Back up existing records privately first.

Local tests verified preservation of advanced team/settings/audit/RPC definitions with 001 alone and 001+002, preservation of pre-upgrade simplified receipts/settings/ranks, anonymous/authenticated role denial, reset rollback on forced audit failure, isolated clearing and re-submission. Live schema/grants remain unverified until provider sign-in.

Required approval: applying the reviewed, necessary migrations to the existing target project after its live audit. Installing reset is distinct from invoking reset; no live practice/event data may be cleared by the agent without explicit approval of that action. User event-day confirmation is provided in the authenticated organizer dialog.
