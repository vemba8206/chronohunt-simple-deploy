"""Simplified API tests. No remote calls, production credentials or Sheet lookup."""

import asyncio
import os
import unittest
from datetime import timedelta
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.config import Config
from app.domain import Problem
from app.main import create_app
from app.simple_store import SimpleStore
from tests.simple_fakes import SimpleFixture

CONFIG = Config(
    "https://example.supabase.co",
    "fixture-only",
    "",
    "test-password-only",
    "test-signing-secret-at-least-32-characters",
)
ORIGIN = {"Origin": "http://localhost:5175"}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.store = SimpleFixture()
        self.client = TestClient(create_app(CONFIG, self.store))

    def tearDown(self):
        self.client.close()

    def submit(self, team="UNREGISTERED", code="any nonempty PIN"):
        return self.client.post("/api/submissions", json={"team_id": team, "code": code})

    def sign_in(self):
        result = self.client.post(
            "/api/admin/login", json={"password": CONFIG.admin_password}, headers=ORIGIN
        )
        self.assertEqual(result.status_code, 200)
        return {**ORIGIN, "X-CSRF-Token": result.json()["csrf_token"]}

    def test_team_without_registration_is_accepted(self):
        result = self.submit(" new-team ")
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json()["team_id"], "NEW-TEAM")
        self.assertTrue(result.json()["accepted"])
        self.assertNotIn("PIN", str(result.json()))

    def test_duplicate_preserves_receipt(self):
        self.submit()
        original = dict(self.store.rows["UNREGISTERED"])
        self.store.now += timedelta(seconds=1)
        self.assertEqual(self.submit(team=" unregistered ", code="different").status_code, 409)
        self.assertEqual(self.store.rows["UNREGISTERED"], original)

    def test_invalid_inputs(self):
        for payload in [
            {},
            {"team_id": "A"},
            {"team_id": "   ", "code": "x"},
            {"team_id": "A", "code": ""},
            {"team_id": "A", "code": " \n "},
            {"team_id": "A", "code": "x\ny"},
            {"team_id": "A", "code": "x" * 257},
            {"team_id": 123, "code": "x"},
            {"team_id": "A", "code": "x", "rank": 1},
        ]:
            with self.subTest(payload=payload):
                result = self.client.post("/api/submissions", json=payload)
                self.assertEqual(result.status_code, 422)
                self.assertNotIn("input", result.json())

    def test_no_deadline_or_registration_checks(self):
        self.assertEqual(self.submit(" team with spaces ").status_code, 201)
        self.store.now += timedelta(days=365)
        self.assertEqual(self.submit("LATER").status_code, 201)

    def test_timestamp_order_and_team_tie(self):
        self.sign_in()
        self.submit("Z")
        self.submit("A")
        self.store.now += timedelta(seconds=1)
        self.submit("EARLIER-ALPHABET")
        self.assertEqual([r["team_id"] for r in self.client.get("/api/admin/leaderboard").json()],
                         ["A", "Z", "EARLIER-ALPHABET"])

    def test_organizer_projection(self):
        self.sign_in()
        self.submit("FIRST")
        result = self.client.get("/api/admin/leaderboard")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), [{"rank": 1, "team_id": "FIRST", "accepted_at": self.store.now.isoformat()}])

    def test_private_routes_and_absent_sheet_routes(self):
        for route in ["overview", "teams", "leaderboard"]:
            self.assertEqual(self.client.get("/api/admin/" + route).status_code, 401)
        self.assertEqual(self.client.post("/api/admin/end-round", json={}).status_code, 404)
        self.assertEqual(
            self.client.post("/api/admin/deadline", json={"cutoff": "2026-01-02T00:00:00Z"}).status_code,
            404,
        )
        self.assertEqual(self.client.get("/api/admin/sheet-report").status_code, 404)
        self.assertEqual(self.client.post("/api/admin/sync-sheet", json={}).status_code, 404)

    def test_origin_csrf_and_logout(self):
        self.assertEqual(
            self.client.post("/api/admin/login", json={"password": CONFIG.admin_password}).status_code,
            403,
        )
        headers = self.sign_in()
        self.assertEqual(self.client.get("/api/admin/overview").status_code, 200)
        self.assertEqual(
            self.client.post("/api/admin/logout", json={}, headers=ORIGIN).status_code,
            403,
        )
        self.assertEqual(
            self.client.post("/api/admin/logout", json={}, headers=headers).status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/admin/overview").status_code, 401)
        self.assertEqual(self.client.get("/api/leaderboard").status_code, 401)

    def test_removed_workflow_even_for_admin(self):
        headers = self.sign_in()
        for route in ["deadline", "end-round", "sync-sheet"]:
            self.assertEqual(self.client.post("/api/admin/" + route, json={}, headers=headers).status_code, 404)

    def test_database_error_never_confirms_or_leaks_pin(self):
        async def unavailable(team, code):
            raise Problem(503, "database_unavailable", "Database unavailable.")
        self.store.submit = unavailable
        result = self.submit(code="private-test-pin")
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("private-test-pin", result.text)
        self.assertNotIn("accepted", result.json())

    def test_limits_and_public_status(self):
        self.assertEqual(self.client.post("/api/submissions", content="x" * 16385).status_code, 413)
        for path in ["/docs", "/openapi.json"]:
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(
            set(self.client.get("/api/competition/status").json()),
            {"submissions_enabled"},
        )
        for _ in range(15):
            self.submit("X")
        self.assertEqual(self.submit("Y").status_code, 429)

    def test_public_leaderboard_and_reset_rejected(self):
        self.submit("PRIVATE")
        for route in ["/api/leaderboard", "/api/admin/leaderboard", "/api/admin/teams"]:
            result = self.client.get(route)
            self.assertEqual(result.status_code, 401)
            self.assertNotIn("PRIVATE", result.text)
        self.assertEqual(self.client.post("/api/admin/reset", json={"confirmation":"DELETE ALL SIMPLIFIED SUBMISSIONS"}).status_code, 401)
        self.assertEqual(len(self.store.rows), 1)

    def test_reset_requires_origin_csrf_and_explicit_body(self):
        self.submit()
        headers = self.sign_in()
        body = {"confirmation":"DELETE ALL SIMPLIFIED SUBMISSIONS"}
        self.assertEqual(self.client.post("/api/admin/reset", json=body, headers=ORIGIN).status_code, 403)
        self.assertEqual(self.client.post("/api/admin/reset", json=body, headers={**headers,"Origin":"https://attacker.invalid"}).status_code, 403)
        for invalid in [{}, {"confirmation":True}, {"confirmation":"yes"}, {**body,"extra":True}]:
            self.assertEqual(self.client.post("/api/admin/reset", json=invalid, headers=headers).status_code, 422)
        self.assertEqual(len(self.store.rows), 1)

    def test_reset_then_same_normalized_id_can_submit(self):
        self.submit(" team ")
        headers = self.sign_in()
        result = self.client.post("/api/admin/reset", json={"confirmation":"DELETE ALL SIMPLIFIED SUBMISSIONS"}, headers=headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["deleted"], 1)
        self.assertEqual(self.client.get("/api/admin/leaderboard").json(), [])
        self.assertEqual(self.submit("TEAM").status_code, 201)
        self.assertEqual(self.client.get("/api/admin/overview").json()["accepted"], 1)

    def test_reset_database_failure_keeps_entries(self):
        self.submit()
        headers = self.sign_in()
        async def failed():
            raise Problem(503,"database_unavailable","Reset unavailable.")
        self.store.reset = failed
        result = self.client.post("/api/admin/reset", json={"confirmation":"DELETE ALL SIMPLIFIED SUBMISSIONS"}, headers=headers)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(len(self.store.rows), 1)


class StoreTests(unittest.TestCase):
    def test_only_simple_rpc_namespace(self):
        calls = []

        def handler(request):
            name = request.url.path.split("/")[-1]
            calls.append(name)
            return httpx.Response(
                200,
                json={"simple_competition": 3} if name == "ch_simple_policy" else {"accepted": True},
            )

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                store = SimpleStore(CONFIG, client)
                await store.submit("NEW", "PIN")
                await store.leaderboard()

        asyncio.run(run())
        self.assertEqual(
            calls,
            [
                "ch_simple_policy",
                "ch_simple_submit",
                "ch_simple_leaderboard",
            ],
        )

    def test_advanced_policy_does_not_enable_simple_writes(self):
        async def run():
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(200, json={"registration_integrity": 3})
                )
            ) as client:
                with self.assertRaises(Problem):
                    await SimpleStore(CONFIG, client).submit("NEW", "PIN")

        asyncio.run(run())

    def test_no_google_config_needed(self):
        env = {
            "SUPABASE_URL": CONFIG.supabase_url,
            "SUPABASE_SECRET_KEY": CONFIG.supabase_key,
            "ADMIN_PASSWORD": CONFIG.admin_password,
            "SESSION_SECRET": CONFIG.session_secret,
            "CORS_ORIGINS": "http://localhost:5175",
        }
        with patch.dict(os.environ, env, clear=True), patch("app.config.load_dotenv"):
            config = Config.load()
            self.assertEqual(config.sheet_url, "")
            self.assertEqual(config.sync_interval, 0)

    def test_old_deadline_policy_cannot_fake_readiness(self):
        calls = []

        def handler(request):
            calls.append(request.url.path.split("/")[-1])
            return httpx.Response(200, json={"simple_competition": 1})

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(Problem):
                    await SimpleStore(CONFIG, client).submit("NEW", "private-test-pin")

        asyncio.run(run())
        self.assertEqual(calls, ["ch_simple_policy"])

