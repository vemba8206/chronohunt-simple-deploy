# ChronoHunt participant and organizer application

All implementation changes are confined to `C:/Users/vemba/Desktop/Chronohunt/simplified`. The original application and credentials are preserved. Logo, cyan/glass styling and the existing Tinkercad challenge URL are retained.

Participants open the challenge, then submit a nonempty Team ID and PIN. No registration, Google services or PIN correctness check is made. IDs are trimmed and uppercased; the existing 32-character ID and 256-character PIN safety limits remain, with control characters rejected. Spaces/punctuation within IDs are accepted. A database primary key prevents case/whitespace variants from creating duplicate entries. The first stored PIN and acceptance time cannot be overwritten by retries.

The authenticated organizer leaderboard returns only `rank`, `team_id`, `accepted_at`. Every recorded submission appears, sorted by database acceptance time and Team ID (C collation). Browser-local date and time are displayed. Refresh occurs after organizer login, the Refresh button and every 10 seconds while visible. There are no deadlines, cutoffs, qualification slots or finalization controls.

FastAPI retains server-only Supabase credentials, database RLS/browser-role restrictions, admin HTTP-only sessions, Origin/CSRF validation, request-size limits and rate limits. PINs remain private in the existing simplified submissions table; neither leaderboard nor admin inspection returns them. Admin `/admin` provides authenticated counts, refresh, sign out and a confirmed Reset All Submissions operation. Participant success shows only a brief thank-you; no standings or another-team controls. Both `/api/leaderboard` and `/api/admin/leaderboard` require the existing backend admin session. A guessed `/leaderboard` route shows organizer login and never loads records before authentication. Run one API worker/replica because sessions and rate limits are process-local.

## Why submissions were unavailable

Migration 004 initialized `cutoff_at` to NULL, while its status and submit RPCs required a future deadline. This disabled the Submit button and returned `deadline_required`. Additive migration **006_minimal_submissions.sql** replaces those simplified RPCs with deadline-free acceptance and live timestamp ranking. It preserves all old submissions, receipt times, PINs, settings and ranks without resetting data; historical settings/ranks no longer drive the flow. The three retired workflow RPCs lose backend execute permission. Migration **007_organizer_reset.sql** adds a service-role-only reset function, a transaction lock shared with submissions, narrowly scoped DELETE permission and policy version 3. Installing it does not delete any record. The API requires policy version 3, so an old/missing migration or failed database connection cannot fake readiness or acceptance.

Deployment is now requested, but no remote migration or deployment has been performed: account sign-in, live schema audit/approval and backend secret configuration are still required. This copy currently has **no production .env**. Its existing local mode uses the actual SQL in disposable PGlite behind a loopback PostgREST-compatible RPC bridge. Tests and local previews read no production environment and make no live writes. Data disappears when the bridge restarts. **Use this mode for testing only, not event data.**

## Run locally, one step at a time

Dependencies are already available in this folder; Python commands below reuse the original virtual environment as an interpreter without modifying it. If these three services are already running, use the preview instead of starting duplicate servers. Otherwise open three PowerShell terminals.

1. Terminal 1: start the disposable database.

```powershell
cd C:\Users\vemba\Desktop\Chronohunt\simplified\frontend
npm.cmd run isolated:database
```

2. Terminal 2: start FastAPI against that database.

```powershell
cd C:\Users\vemba\Desktop\Chronohunt\simplified\backend
..\..\backend\.venv\Scripts\python.exe -m uvicorn scripts.isolated_app:app --host 127.0.0.1 --port 8001 --workers 1
```

3. Terminal 3: start the frontend.

```powershell
cd C:\Users\vemba\Desktop\Chronohunt\simplified\frontend
npm.cmd run dev -- --host localhost --port 5175 --strictPort
```

4. Open <http://localhost:5175/>. The badge should read SUBMISSIONS OPEN. Open the existing challenge link if desired, then enter a disposable ID such as `local-check` and any nonempty test PIN. Submit must show confirmation only after the database insert succeeds.
5. Confirm the small thank-you message contains no leaderboard/another-team link or button. The participant header also has no leaderboard link. Open `/leaderboard` while signed out: expect organizer login only.
6. Reload the participant page and submit ` local-CHECK ` with a different PIN. Expect the duplicate message; the original receipt is preserved.
7. Try a blank/whitespace PIN: expect validation, no entry. Test another Team ID; both should appear in the organizer dashboard only. Public pages must never show other teams, PINs or management controls.
8. Open `/admin` and sign in with the local-only fixture password `isolated-organizer-only` (not a production credential). Check ordered Team IDs/local receipt times without PINs. Click Reset All Submissions; first Cancel and verify nothing changes. Reopen, read the warning and click Confirm permanent reset. Expect a cleared board and deleted count; reload the participant page and submit the same ID again. There are no deadline/end/freeze controls.
9. Stop each terminal with Ctrl+C. Restarting Terminal 1 discards disposable data. Do not use live Supabase for example submissions.

## Automated checks

Run each command from the indicated folder. SQL/unit tests create their own disposable databases. Integration smoke needs a **fresh disposable bridge** (restart Terminal 1 first) and the API running. It verifies the explicit `/api/isolated` marker before any write. Do not run the archived advanced smoke scripts.

```powershell
cd C:\Users\vemba\Desktop\Chronohunt\simplified\backend
..\..\backend\.venv\Scripts\python.exe -m pytest tests/test_simple_application.py -q -p no:cacheprovider
..\..\backend\.venv\Scripts\python.exe -m ruff check app tests scripts
..\..\backend\.venv\Scripts\python.exe scripts/verify_preservation.py
..\..\backend\.venv\Scripts\python.exe scripts/smoke_isolated.py
```

```powershell
cd C:\Users\vemba\Desktop\Chronohunt\simplified\frontend
npm.cmd test
npm.cmd run test:simple-database
npm.cmd run test:simple-upgrade
npm.cmd run test:deployment
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
```

## Deployment and event-day reset

Use one Vercel frontend plus the existing FastAPI service on Render and existing Supabase. The two distinct HTTPS links will be the deployed frontend origin `/` (participants) and `/admin` (authenticated organizers). This is a clearly separated protected application with backend authentication; it needs no extra frontend service. No actual deployed URL is available yet. The `/leaderboard` compatibility route is also protected. External Vercel `/api` rewrites keep cookie authentication same-origin; VITE_API_BASE_URL should stay blank. Hosting configuration was reviewed against [Vercel rewrites](https://vercel.com/docs/routing/rewrites) and [Render Blueprints](https://render.com/docs/blueprint-spec).

Detailed account/configuration steps and exact env names are in OWNER_SETUP.md. The exact new SQL requiring approval is `backend/sql/007_organizer_reset.sql`; review `deployment/DATABASE_REVIEW.md` for conditional prerequisites. Do not blindly run 004: if the namespace already exists, inspect its policy and grants and apply only missing reviewed upgrades. Never rerun 001 or reset/recreate Supabase. No remote SQL runs automatically on deployment.

Event-day reset: open the deployed organizer `/admin`, sign in using the configured backend ADMIN_PASSWORD, click Reset All Submissions, review the permanent-deletion warning, then Confirm permanent reset. Expect a success/deleted count and empty refreshed board. This deletes only simplified submissions/PINs/timestamps/ranks and removes their duplicate barriers; audit history, unused settings and all advanced/Google records stay intact. Database transaction failure rolls back deletion. Teams can submit again after reset; reload already-completed participant pages. Unrelated anti-abuse limits remain (15 submission attempts/minute per recognized IP, reset 3/minute); do not repeatedly click retry after an ambiguous network failure—refresh the organizer board first.

Local source and production build are ready, but event use requires persistent Supabase configuration and verified HTTPS hosting. Do not deploy `scripts.isolated_app:app` or the disposable bridge. Archived advanced references remain for history. Exact changed files and actual tests are in CHANGE_REPORT.md and VERIFICATION.md.
