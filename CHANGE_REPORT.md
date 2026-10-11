# Final participant/organizer/reset change report

All changes are inside simplified. Branding, challenge URL, inputs, SQL acceptance clock and duplicate protection remain. Public leaderboard access is replaced by backend-authenticated organizer access, as requested.

## Source files changed or added for this request

- backend/app/main.py — protects both leaderboard aliases; sanitizes team inspection; adds authenticated, Origin/CSRF-checked, rate-limited and explicitly confirmed reset.
- backend/app/domain.py — strict Reset confirmation model.
- backend/app/simple_store.py — version-3 gate and simplified reset RPC.
- backend/sql/007_organizer_reset.sql — new reviewed upgrade; shared/exclusive transaction lock, exact-table reset function, scoped grants, audit count; no deletion during installation.
- backend/scripts/smoke_isolated.py — private board and full transactional-reset/re-submission integration test.
- backend/scripts/check_public.py — HTTPS authentication/privacy checks, invalid non-destructive reset probe.
- backend/scripts/package_source.py — includes database review document in the safe source archive.
- backend/tests/simple_fakes.py — isolated reset fixture.
- backend/tests/test_simple_application.py — private board/reset/authentication/protection/failure tests.
- frontend/src/App.tsx — minimal participant confirmation, no public board navigation, guarded organizer/compatibility routes, reset warning/cancel/confirm/feedback/refresh.
- frontend/src/test/App.test.tsx — privacy, organizer and confirmation/reset UI tests.
- frontend/scripts/simple-db.mjs — disposable bootstrap includes 007 and reset RPC allowlist.
- frontend/tests/simple-database.mjs — actual transactional reset, rollback, access restriction and unrelated-data preservation tests.
- frontend/tests/simple-upgrade.mjs — includes 007 preservation checks.
- frontend/tests/deployment.mjs — verifies backend board/reset guards and safe migration installation.
- README.md, OWNER_SETUP.md, VERIFICATION.md, CHANGE_REPORT.md — current behavior, precise local tests, deployment and event-day procedures/results.
- deployment/DATABASE_REVIEW.md — exact migration review, conditional prerequisites and required approval.

Generated frontend/dist and deployment/artifacts/chronohunt-source.zip were refreshed; local reset-dialog evidence is saved as deployment/artifacts/reset-confirmation.jpg. Existing render.yaml, Vercel routing generator, logo, styles, 001–006 migrations and other useful references remain unchanged.

Prior source package is retained privately under backups/pre-organizer-source-20261011.zip, excluded from delivery. All 52 tracked original files still match their preservation hashes. No live services, production rows, secrets or credentials changed. Deployment remains pending account access, live database review/approval and secret configuration.
