import asyncio
import os
import threading
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.config import Config
from app.domain import Problem, inspect_sheet, parse_sheet
from app.main import create_app
from app.services import SheetClient, SupabaseStore
from tests.fakes import FixtureSheet, FixtureStore

CONFIG = Config(
    "https://example.supabase.co",
    "test-secret-not-real",
    "https://script.google.com/macros/s/TEST/exec",
    "test-password-only",
    "a-test-signing-secret-of-at-least-32-characters",
)

ORIGIN = {"Origin": "http://localhost:5173"}

ROW = {"team_id": " ch01 ", "form_timestamp": "2026-10-09T18:00:00+05:30"}


class ParsingTests(unittest.TestCase):
    def test_normalize_and_utc(self):

        result = parse_sheet({"success": True, "count": 1, "data": [ROW]})

        self.assertEqual(result[0]["team_id"], "CH01")

        self.assertEqual(result[0]["form_timestamp"], "2026-10-09T12:30:00Z")

    def test_empty(self):

        self.assertEqual(parse_sheet({"success": True, "count": 0, "data": []}), [])

    def test_irrelevant_question_fields(self):

        rows = parse_sheet(
            {"success": True, "count": 1, "data": [{**ROW, "New question heading": "anything"}]}
        )

        self.assertEqual(set(rows[0]), {"team_id", "form_timestamp"})

    def test_duplicates_after_normalization(self):

        with self.assertRaises(Problem) as ctx:
            parse_sheet({"success": True, "count": 2, "data": [ROW, {**ROW, "team_id": "CH01"}]})

        self.assertEqual(ctx.exception.code, "sheet_duplicates")

    def test_invalid_timestamps(self):

        for value in [None, "", "bad", "2026-10-09T12:00:00", 12345]:
            with self.subTest(value=value), self.assertRaises(Problem):
                parse_sheet({"success": True, "count": 1, "data": [{**ROW, "form_timestamp": value}]})

    def test_missing_timestamp(self):

        with self.assertRaises(Problem):
            parse_sheet({"success": True, "count": 1, "data": [{"team_id": "CH01"}]})

    def test_invalid_envelopes(self):

        for payload in [
            {},
            {"success": False, "count": 0, "data": []},
            {"success": True, "count": 2, "data": []},
            {"success": "true", "count": 0, "data": []},
        ]:
            with self.subTest(payload=payload), self.assertRaises(Problem):
                parse_sheet(payload)

    def test_missing_configuration_names_only(self):

        with patch.dict(os.environ, {}, clear=True), patch("app.config.load_dotenv"):
            with self.assertRaisesRegex(RuntimeError, "SUPABASE_URL"):
                Config.load()

    def test_invalid_configuration(self):

        for config in [
            replace(CONFIG, supabase_url="http://wrong"),
            replace(CONFIG, origins=("*",)),
            replace(CONFIG, sheet_url="https://untrusted.test/exec"),
            replace(CONFIG, cookie_samesite="none"),
            replace(CONFIG, session_secret="short"),
            replace(CONFIG, session_ttl=1),
        ]:
            with self.subTest(config=config), self.assertRaises(RuntimeError):
                config.validate()


class ApiTests(unittest.TestCase):
    def setUp(self):

        self.store, self.sheet = FixtureStore(), FixtureSheet()

        self.app = create_app(CONFIG, self.store, self.sheet)

        self.context = TestClient(self.app)

        self.client = self.context.__enter__()

    def tearDown(self):

        self.context.__exit__(None, None, None)

    def login(self):

        response = self.client.post(
            "/api/admin/login", json={"password": CONFIG.admin_password}, headers=ORIGIN
        )

        self.assertEqual(response.status_code, 200)

        return {**ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]}

    def submit(self, team="CH01", code="TEST-VALID-CODE", **extra):

        return self.client.post("/api/submissions", json={"team_id": team, "code": code, **extra})

    def test_health(self):

        self.assertTrue(self.client.get("/api/health").json()["ok"])

    def test_server_generated_timestamp_and_normalization(self):

        before = datetime.now(timezone.utc)

        response = self.submit(" ch01 ")

        self.assertEqual(response.status_code, 201)

        timestamp = self.store.data["CH01"]["tinkercad_timestamp"]

        self.assertIsNotNone(timestamp.tzinfo)

        self.assertGreaterEqual(timestamp, before)

        self.assertNotIn("timestamp", response.text)

    def test_unknown_team(self):

        response = self.submit("CH99")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Complete the Google Form first", response.json()["error"]["message"])

    def test_arbitrary_nonempty_pin_is_accepted_without_correctness_claim(self):
        response = self.submit(code=" any-nonempty-PIN ")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.store.data["CH01"]["tinkercad_code"], "any-nonempty-PIN")
        self.assertEqual(set(response.json()), {"accepted", "team_id", "message"})
        self.assertNotIn("PIN", response.text)
        self.assertNotIn("verified", response.text.lower())

    def test_unconfirmed_database_result_never_shows_success(self):
        async def unconfirmed(team_id, code):
            return {"accepted": False}

        self.store.submit = unconfirmed
        self.assertEqual(self.submit().status_code, 503)

    def test_invalid_team_id(self):

        self.assertEqual(self.submit(team="bad id!").status_code, 422)

    def test_blank_code(self):

        self.assertEqual(self.submit(code=" ").status_code, 422)

    def test_browser_cannot_set_authoritative_fields(self):

        for field in [
            "tinkercad_timestamp",
            "website_submission_timestamp",
            "form_timestamp",
            "rank",
            "qualified",
            "tinkercad_valid",
            "status",
        ]:
            self.assertEqual(self.submit(**{field: True}).status_code, 422)

    def test_duplicate(self):

        self.assertEqual(self.submit().status_code, 201)

        self.assertEqual(self.submit().status_code, 409)

    def test_closed(self):

        self.store.closed = True

        self.assertEqual(self.submit().status_code, 409)

    def test_unauthorized_admin_routes(self):

        for path in ["overview", "teams"]:
            self.assertEqual(self.client.get("/api/admin/" + path).status_code, 401)

        for path in ["end-round", "sync-sheet", "logout"]:
            self.assertEqual(self.client.post("/api/admin/" + path, json={}).status_code, 401)

    def test_login_origin_required(self):

        self.assertEqual(
            self.client.post("/api/admin/login", json={"password": CONFIG.admin_password}).status_code, 403
        )

    def test_csrf_required(self):

        self.login()

        self.assertEqual(self.client.post("/api/admin/end-round", json={}, headers=ORIGIN).status_code, 403)

        self.assertFalse(self.store.closed)

    def test_wrong_origin(self):

        headers = self.login()

        headers["Origin"] = "https://attacker.test"

        self.assertEqual(self.client.post("/api/admin/end-round", json={}, headers=headers).status_code, 403)

    def test_login_cookie_security(self):

        response = self.client.post(
            "/api/admin/login", json={"password": CONFIG.admin_password}, headers=ORIGIN
        )

        cookie = response.headers["set-cookie"].lower()

        self.assertIn("httponly", cookie)

        self.assertIn("samesite=lax", cookie)

        self.assertIn("path=/api;", cookie)

    def test_login_rate_limit(self):

        for _ in range(5):
            self.assertEqual(
                self.client.post("/api/admin/login", json={"password": "wrong"}, headers=ORIGIN).status_code,
                401,
            )

        self.assertEqual(
            self.client.post("/api/admin/login", json={"password": "wrong"}, headers=ORIGIN).status_code, 429
        )

    def test_logout_revokes_session(self):

        headers = self.login()

        cookie = self.client.cookies.get("ch_session")

        self.assertEqual(self.client.post("/api/admin/logout", json={}, headers=headers).status_code, 200)

        self.client.cookies.set("ch_session", cookie)

        self.assertEqual(self.client.get("/api/admin/overview").status_code, 401)

    def test_cutoff_authorized_and_repeat_immutable(self):

        headers = self.login()

        self.assertEqual(self.client.post("/api/admin/end-round", json={}, headers=headers).status_code, 200)

        cutoff = self.store.cutoff_time

        self.assertEqual(self.client.post("/api/admin/end-round", json={}, headers=headers).status_code, 200)

        self.assertEqual(self.store.cutoff_time, cutoff)

        self.assertEqual(self.store.finalize_calls, 1)

        self.assertEqual(self.submit().status_code, 409)

    def test_cutoff_sync_failure_and_retry(self):

        headers = self.login()

        self.sheet.fail = True

        response = self.client.post("/api/admin/end-round", json={}, headers=headers)

        self.assertEqual(response.status_code, 502)

        self.assertEqual(response.json()["error"]["code"], "finalization_pending")

        self.assertTrue(self.store.closed)

        self.assertFalse(self.store.finalized)

        cutoff = self.store.cutoff_time

        self.sheet.fail = False

        self.assertEqual(self.client.post("/api/admin/end-round", json={}, headers=headers).status_code, 200)

        self.assertEqual(self.store.cutoff_time, cutoff)

        self.assertTrue(self.store.finalized)

    def test_repeated_sync_preserves_submission(self):

        self.submit()

        timestamp = self.store.data["CH01"]["tinkercad_timestamp"]

        self.sheet.rows = parse_sheet({"success": True, "count": 1, "data": [ROW]})

        headers = self.login()

        for _ in range(2):
            self.assertEqual(
                self.client.post("/api/admin/sync-sheet", json={}, headers=headers).status_code, 200
            )

        self.assertEqual(len(self.store.data), 1)

        self.assertEqual(self.store.data["CH01"]["tinkercad_timestamp"], timestamp)

        self.assertTrue(self.store.data["CH01"]["tinkercad_valid"])

    def test_leaderboard_privacy(self):

        self.assertEqual(self.client.get("/api/leaderboard").status_code, 401)

        self.assertEqual(self.client.get("/api/admin/leaderboard").status_code, 401)

        self.login()

        response = self.client.get("/api/leaderboard")

        self.assertEqual(response.json(), [{"rank": 1, "team_id": "CH01"}])

    def test_status_privacy(self):

        self.assertEqual(
            set(self.client.get("/api/competition/status").json()),
            {"status", "submissions_enabled"},
        )

    def test_website_timestamp_alias(self):

        self.login()

        response = self.client.get("/api/admin/teams")

        self.assertEqual(response.status_code, 200)

    def test_read_only_sheet_report(self):

        self.login()

        self.assertEqual(self.client.get("/api/admin/sheet-report").status_code, 200)

        self.assertEqual(len(self.store.data), 1)

        self.assertEqual(self.store.submission_calls, 0)

    def test_sheet_report_authentication(self):

        self.assertEqual(self.client.get("/api/admin/sheet-report").status_code, 401)

    def test_public_status_blocks_old_sql_policy(self):
        async def unavailable():
            return False

        self.store.policy_ready = unavailable
        self.assertFalse(self.client.get("/api/competition/status").json()["submissions_enabled"])

    def test_reject_unverified_source_before_sync(self):

        async def unverified():

            return inspect_sheet({"success": True, "count": 1, "data": [ROW]})

        self.sheet.inspect = unverified

        headers = self.login()

        response = self.client.post("/api/admin/sync-sheet", json={}, headers=headers)

        self.assertEqual(response.status_code, 409)

        self.assertEqual(response.json()["error"]["code"], "sheet_coverage_unverified")

        self.assertNotIn("form_timestamp", self.store.data["CH01"])

    def test_concurrent_duplicate_requests(self):

        async def run():

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app), base_url="http://test"
            ) as client:
                body = {"team_id": "CH01", "code": "TEST-VALID-CODE"}

                return await asyncio.gather(
                    client.post("/api/submissions", json=body), client.post("/api/submissions", json=body)
                )

        self.assertEqual(sorted(r.status_code for r in asyncio.run(run())), [201, 409])

    def test_in_flight_submission_loses_to_cutoff(self):
        entered, release = threading.Event(), threading.Event()
        original_submit = self.store.submit

        async def slow_submit(team_id, code):
            entered.set()
            await asyncio.to_thread(release.wait, 5)
            return await original_submit(team_id, code)

        self.store.submit = slow_submit
        with TestClient(create_app(CONFIG, self.store, self.sheet)) as client:
            result = []
            thread = threading.Thread(
                target=lambda: result.append(
                    client.post("/api/submissions", json={"team_id": "CH01", "code": "unverified-pin"})
                )
            )
            thread.start()
            self.assertTrue(entered.wait(5))
            asyncio.run(self.store.cutoff())
            release.set()
            thread.join(5)
            self.assertEqual(result[0].status_code, 409)
            self.assertFalse(self.store.data["CH01"]["tinkercad_valid"])


class CoverageTests(unittest.TestCase):
    def test_legacy_count_cannot_prove_complete_sheet(self):

        snapshot = inspect_sheet({"success": True, "count": 1, "data": [ROW]})

        self.assertFalse(snapshot.coverage_verified)

        self.assertEqual(snapshot.eligible_records, 1)

        with self.assertRaises(Problem):
            snapshot.require_importable()

    def test_full_report_flags_invalid_and_duplicate_records(self):

        data = [
            ROW,
            {**ROW, "team_id": "CH01"},
            {"team_id": "CH02", "form_timestamp": None},
            {**ROW, "team_id": "CH03"},
        ]

        report = inspect_sheet({"success": True, "count": 4, "total_rows_read": 4, "data": data})

        self.assertTrue(report.coverage_verified)

        self.assertEqual(report.duplicate_ids, ["CH01"])

        self.assertEqual(report.eligible_records, 1)

        self.assertEqual(len(report.invalid_rows), 1)

        with self.assertRaises(Problem):
            report.require_importable()

    def test_invalid_timestamps_excluded_from_fallback_snapshot(self):

        data = [ROW, {"team_id": "CH02", "form_timestamp": None}]

        snapshot = inspect_sheet({"success": True, "count": 2, "total_rows_read": 2, "data": data})

        snapshot.require_importable()

        self.assertEqual([r["team_id"] for r in snapshot.records], ["CH01"])

        self.assertEqual(snapshot.invalid_rows[0]["reason"], "invalid_registration_timestamp")

    def test_partial_export_rejected(self):

        with self.assertRaises(Problem):
            inspect_sheet({"success": True, "count": 1, "total_rows_read": 2, "data": [ROW]})

    def test_complete_empty_sheet(self):

        snapshot = inspect_sheet({"success": True, "count": 0, "total_rows_read": 0, "data": []})

        snapshot.require_importable()

        self.assertEqual(snapshot.eligible_records, 0)


class ExternalClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_timestamp_labeled_as_website_receipt(self):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    200,
                    json=[
                        {
                            "team_id": "CH01",
                            "form_timestamp": "2026-10-09T12:00:00Z",
                            "tinkercad_timestamp": "2026-10-09T13:00:00Z",
                        }
                    ],
                )
            )
        ) as client:
            rows = await SupabaseStore(CONFIG, client).teams()
            self.assertNotIn("tinkercad_timestamp", rows[0])
            self.assertEqual(rows[0]["website_submission_timestamp"], "2026-10-09T13:00:00Z")
            self.assertEqual(rows[0]["form_timestamp"], "2026-10-09T12:00:00Z")

    async def test_old_database_functions_cannot_be_used_for_writes(self):
        called = []

        def respond(request):
            called.append(request.url.path)
            return httpx.Response(404, json={})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with self.assertRaises(Problem) as caught:
                await SupabaseStore(CONFIG, client).sync([])
            self.assertEqual(caught.exception.code, "integrity_update_required")
            self.assertEqual(called, ["/rest/v1/rpc/ch_integrity_status"])

    async def test_version_two_cannot_write_under_final_pin_policy(self):
        called = []

        def respond(request):
            called.append(request.url.path)
            return httpx.Response(200, json={"registration_integrity": 2})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with self.assertRaises(Problem):
                await SupabaseStore(CONFIG, client).submit("CH01", "any-pin")
            self.assertEqual(called, ["/rest/v1/rpc/ch_integrity_status"])

    async def test_google_login_html_is_failure(self):

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, text="Google login", headers={"content-type": "text/html"})
            )
        ) as client:
            with self.assertRaises(Problem) as ctx:
                await SheetClient(CONFIG, client).fetch()

            self.assertEqual(ctx.exception.code, "sheet_access")

    async def test_google_json_real_client_path(self):

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"success": True, "count": 1, "data": [ROW]})
            )
        ) as client:
            self.assertEqual((await SheetClient(CONFIG, client).fetch())[0]["team_id"], "CH01")

    async def test_google_http_error(self):

        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(403))) as client:
            with self.assertRaises(Problem):
                await SheetClient(CONFIG, client).fetch()

    async def test_database_configuration_failure(self):

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"message": "SECRET INTERNAL"}))
        ) as client:
            with self.assertRaises(Problem) as ctx:
                await SupabaseStore(CONFIG, client).status()

            self.assertNotIn("SECRET", ctx.exception.message)

    async def test_secret_key_not_sent_as_bearer(self):

        def respond(request):

            self.assertEqual(request.headers["apikey"], "sb_secret_fixture")

            self.assertNotIn("authorization", request.headers)

            return httpx.Response(200, json={"status": "ACTIVE", "finalized": False})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await SupabaseStore(replace(CONFIG, supabase_key="sb_secret_fixture"), client).status()


if __name__ == "__main__":
    unittest.main()
