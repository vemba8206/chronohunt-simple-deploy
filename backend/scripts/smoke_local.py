"""Local real HTTP smoke check; no submission, sync, cutoff or DB writes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx

from app.config import Config


def main():
    config = Config.load()
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=40) as client:
        for path in (
            "/api/leaderboard",
            "/api/admin/leaderboard",
            "/api/admin/teams",
            "/api/admin/sheet-report",
        ):
            response = client.get(path)
            assert response.status_code == 401, f"Unauthenticated route was exposed: {path}"
            print(path, "unauthenticated: 401")
        response = client.post(
            "/api/admin/login",
            headers={"Origin": config.origins[0]},
            json={"password": config.admin_password},
        )
        response.raise_for_status()
        csrf = response.json()["csrf_token"]
        response = client.get("/api/admin/overview")
        response.raise_for_status()
        overview = response.json()
        print(
            "Authenticated overview:",
            {
                key: overview[key]
                for key in ("status", "qualification_slots", "teams", "accepted", "submission_policy_ready")
            },
        )
        response = client.get("/api/admin/leaderboard")
        response.raise_for_status()
        print("Authenticated leaderboard: 200; entries:", len(response.json()))
        response = client.get("/api/admin/sheet-report")
        response.raise_for_status()
        report = response.json()
        print(
            "Read-only Sheet audit: 200; returned rows:",
            report["returned_rows"],
            "; coverage:",
            report["coverage_verified"],
        )
        response = client.post(
            "/api/admin/logout", headers={"Origin": config.origins[0], "X-CSRF-Token": csrf}, json={}
        )
        response.raise_for_status()
        assert client.get("/api/admin/leaderboard").status_code == 401
        print("Logout: 200; protected data inaccessible afterward.")


if __name__ == "__main__":
    main()
