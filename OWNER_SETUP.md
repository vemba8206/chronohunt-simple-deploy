# ChronoHunt organizer deployment and event handover

## Deployment status

**Not deployed.** The available Render browser session redirects to sign-in. No Vercel/Render/Supabase CLI authorization or provider API token is available, there is no Git repository here, and simplified/.env is absent. No fake HTTPS URLs are provided. Local implementation, build, source package and tests are ready. The original project must remain outside the deployed source.

## Smallest reliable deployment

One Vercel Vite frontend serves two distinct links: its HTTPS root is the public participant application; its `/admin` is the authenticated organizer application. Backend authentication protects both leaderboard APIs and reset regardless of URL guessing. One Render FastAPI instance connects to the existing Supabase project. Do not create a new database or unnecessary organizer backend. A second Vercel project can use the same frontend/proxy if a separate host is later preferred; add only that exact organizer origin to CORS.

## Steps requiring your account/approval

1. Sign in yourself at https://dashboard.render.com/, https://vercel.com/dashboard and https://supabase.com/dashboard. Never send passwords, keys or tokens in chat. Keep production secrets in provider settings only.
2. Review the existing Supabase live schema/grants (retained 003 and simplified 005 audits; 005 requires the simplified schema). Back up existing data privately. Read deployment/DATABASE_REVIEW.md and approve the exact necessary SQL files before application. 007 installs reset but never executes it. If the namespace is absent, reviewed 004 then 006 then 007 are required; if it exists at policy 2, only 007 is needed. Never rerun 001, drop/reset the database or blindly reapply 004.
3. Unpack deployment/artifacts/chronohunt-source.zip into a separate private Git repository using the extracted contents as its root. The artifact includes source and blank examples, not real .env, backups, dependencies or original credentials. Preserve existing work in this local folder; the prior package is saved in backups/pre-organizer-source-20261011.zip. Authorize Render/Vercel to access only that deployment repository.
4. In Render, import the extracted render.yaml or create a Python web service with root directory backend, build `pip install -r requirements.txt`, health `/api/health`, and the supplied start command. Keep one instance/worker and manual deployments. The existing blueprint's `0.5c-512mb` compute plan is a paid plan: review your account's price before creating it. No paid service was created here. Set server secrets privately using your existing approved credentials. Do not copy the isolated fixture password to production.
5. Reserve the intended Vercel project and its actual production origin. Set backend CORS_ORIGINS to that exact HTTPS origin (comma-separated only if two real origins are used). Set COOKIE_SECURE=true and COOKIE_SAMESITE=lax with the same-origin proxy. Supply FORWARDED_ALLOW_IPS for the trusted hosting proxy configuration; verify client IP handling on your event network so shared-IP rate limits are understood. Keep PYTHON_VERSION=3.14.3 and SESSION_TTL_SECONDS=3600 from the blueprint. Deploy persistent backend with app.asgi:app, never the isolated entry point. Validate its actual health/version before continuing.
6. With the **actual** Render HTTPS origin, prepare routing locally:

```powershell
cd C:\Users\vemba\Desktop\Chronohunt\simplified\frontend
$env:CHRONOHUNT_BACKEND_ORIGIN = '<actual Render HTTPS origin>'
npm.cmd run deploy:prepare
```

The generator refuses localhost/credentials/non-Render origins and refuses to overwrite existing vercel.json. Review this generated public routing file, then include it in the deployment repository intentionally (the local ignore file keeps it out of accidental packaging/commits). Never set any secret in VITE_*.

7. Import frontend as the Vercel project root, Vite framework, build `npm run build`, output dist, same-origin API rewrite before SPA routes. Leave VITE_API_BASE_URL blank; VITE_LOGO_URL is optional and public. Deploy, then verify the actual HTTPS root and `/admin` before sharing either URL.
8. Run `backend/scripts/check_public.py --url <actual frontend HTTPS origin>` from the backend using the existing Python interpreter. It checks public health and denied leaderboard/teams/overview plus an invalid, non-destructive reset request without authentication. It never sends a valid reset confirmation, production test record or credentials. Verify logo/challenge/participant UI and organizer login/logout in the browser. Never create fake live entries or invoke real reset as a deployment smoke test without separate explicit approval.

## Environment variables (names only)

Required backend: SUPABASE_URL, SUPABASE_SECRET_KEY, ADMIN_PASSWORD, SESSION_SECRET, CORS_ORIGINS.
Hosting/session: PYTHON_VERSION, PORT, FORWARDED_ALLOW_IPS, COOKIE_SECURE, COOKIE_SAMESITE, SESSION_TTL_SECONDS.
Deployment preparation: CHRONOHUNT_BACKEND_ORIGIN.
Optional public frontend: VITE_API_BASE_URL, VITE_LOGO_URL.

Production ADMIN_PASSWORD must be configured privately (12+ characters); SESSION_SECRET must be random and at least 32 characters. No production defaults or hardcoded credentials exist. The Supabase secret/service-role key remains exclusively on Render. Do not expose the private chronohunt_simple schema to browser roles. CORS is not authentication; protected APIs require the signed registered admin session even for direct backend requests.

## Event-day reset procedure

1. Open the verified deployed organizer `/admin` URL and sign in using the securely configured ADMIN_PASSWORD.
2. Click Reset All Submissions. Cancel preserves records; Confirm permanent reset irreversibly deletes only simplified submissions.
3. Wait for the success/deleted count and refreshed empty board. If the network response is ambiguous, refresh before deciding whether another reset is needed.
4. Reload participant pages that were already on the confirmation screen. Team IDs may submit again; ranking restarts at one from new database receipts. No cutoff/finalization step is needed. Original project, Google services and advanced Supabase records are untouched.

The operation is POST /api/admin/reset with the explicit confirmation literal, Origin validation, CSRF, backend admin authentication and rate limiting. A transactional RPC serializes reset against submission inserts; failure rolls back both DELETE and audit. Reset audit history is retained without PINs.
