"""Writes ONLY to verified loopback disposable mode. No environment is read."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import httpx


def main():
    with httpx.Client(base_url="http://127.0.0.1:8001", timeout=30) as client:
        marker = client.get("/api/isolated")
        assert marker.status_code == 200 and marker.json() == {
            "isolated": True,
            "database": "disposable-pglite",
        }, "Refusing writes: server is not the explicit isolated application."
        assert client.get("/api/admin/teams").status_code == 401
        assert client.get("/api/leaderboard").status_code == 401
        assert client.post("/api/admin/reset", json={"confirmation":"DELETE ALL SIMPLIFIED SUBMISSIONS"}).status_code == 401
        origin = {"Origin": "http://localhost:5175"}
        login = client.post("/api/admin/login", json={"password": "isolated-organizer-only"}, headers=origin)
        assert login.status_code == 200
        headers = {**origin, "X-CSRF-Token": login.json()["csrf_token"]}
        assert client.get("/api/competition/status").json()["submissions_enabled"] is True
        started = datetime.now(timezone.utc)
        result = client.post(
            "/api/submissions", json={"team_id": "local_only", "code": "isolated arbitrary PIN"}
        )
        assert result.status_code == 201 and result.json()["accepted"] is True
        before = client.get("/api/admin/teams").json()
        assert (
            client.post("/api/submissions", json={"team_id": " local_only ", "code": "replacement"}).status_code
            == 409
        )
        assert client.get("/api/admin/teams").json() == before
        assert set(before[0]) == {"team_id", "accepted_at", "rank"}
        assert client.post("/api/submissions", json={"team_id": "BLANK", "code": ""}).status_code == 422

        def racing(_):
            return httpx.post(
                "http://127.0.0.1:8001/api/submissions",
                json={"team_id": "LOCAL_RACE", "code": "isolated PIN"},
                timeout=30,
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(racing, range(2))) == [201, 409]
        board = client.get("/api/admin/leaderboard").json()
        assert [row["team_id"] for row in board] == ["LOCAL_ONLY", "LOCAL_RACE"]
        assert all(set(row) == {"rank", "team_id", "accepted_at"} for row in board)
        timestamp = datetime.fromisoformat(board[0]["accepted_at"])
        assert started <= timestamp <= datetime.now(timezone.utc)
        assert client.get("/api/admin/leaderboard").json() == board
        for route in ["deadline", "end-round"]:
            assert client.post("/api/admin/" + route, json={}, headers=headers).status_code == 404
        reset = client.post("/api/admin/reset", json={"confirmation":"DELETE ALL SIMPLIFIED SUBMISSIONS"}, headers=headers)
        assert reset.status_code == 200 and reset.json()["reset"] is True and reset.json()["deleted"] == 2
        assert client.get("/api/admin/leaderboard").json() == []
        assert client.post("/api/submissions", json={"team_id":" local_only ","code":"new test-only PIN"}).status_code == 201
        assert client.get("/api/admin/leaderboard").json()[0]["rank"] == 1
        assert client.post("/api/admin/reset", json={"confirmation":"DELETE ALL SIMPLIFIED SUBMISSIONS"}, headers=headers).json()["deleted"] == 1
        assert client.post("/api/admin/logout", json={}, headers=headers).status_code == 200
        assert client.get("/api/admin/teams").status_code == 401
        assert client.get("/api/leaderboard").status_code == 401
        print(
            "PASS isolated FastAPI + actual migration: acceptance, timestamp/duplicate preservation, concurrent duplicate, private timestamps/privacy, authenticated transactional reset/resubmission and session revocation."
        )


if __name__ == "__main__":
    main()
