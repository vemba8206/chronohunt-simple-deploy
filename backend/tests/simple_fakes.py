"""Clock-controlled isolated fixtures; never imported by deployed ASGI app."""

import threading
from datetime import datetime, timezone


class SimpleFixture:
    def __init__(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.lock = threading.Lock()
        self.rows = {}
        self.ready = True

    async def policy_ready(self):
        return self.ready

    async def status(self):
        return {"submissions_enabled": self.ready}

    async def submit(self, team_id, code):
        with self.lock:
            if not self.ready:
                return {"error": "simple_update_required"}
            if team_id in self.rows:
                return {"error": "duplicate_submission"}
            self.rows[team_id] = {
                "team_id": team_id,
                "accepted_at": self.now,
                "pin": code,
            }
            return {"accepted": True}

    async def leaderboard(self):
        return [
            {
                "rank": i + 1,
                "team_id": row["team_id"],
                "pin": row["pin"],
                "accepted_at": row["accepted_at"],
                "form_timestamp": "PRIVATE",
            }
            for i, row in enumerate(
                sorted(self.rows.values(), key=lambda x: (x["accepted_at"], x["team_id"]))
            )
        ]

    async def overview(self):
        return {
            **await self.status(),
            "teams": len(self.rows),
            "accepted": len(self.rows),
        }

    async def teams(self, offset=0):
        return [{k: v for k, v in row.items() if k != "pin"} for row in self.rows.values()][
            offset : offset + 100
        ]


    async def reset(self):
        with self.lock:
            count = len(self.rows)
            self.rows.clear()
            return {"reset": True, "deleted": count}
