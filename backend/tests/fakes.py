"""TEST ONLY — no runtime app imports this module and no external DB writes."""

import threading
from datetime import datetime, timezone

from app.domain import Problem, inspect_sheet


class FixtureSheet:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.fail = False

    async def fetch(self):
        if self.fail:
            raise Problem(502, "sheet_access", "Sheet JSON is not accessible.")
        return self.rows

    async def inspect(self):
        rows = await self.fetch()
        return inspect_sheet(
            {"success": True, "count": len(rows), "total_rows_read": len(rows), "data": rows}
        )


class FixtureStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.closed, self.finalized, self.cutoff_time = False, False, None
        self.data = {"CH01": {"tinkercad_valid": False, "source_present": True}}
        self.submission_calls = 0
        self.finalize_calls = 0

    async def policy_ready(self):
        return True

    async def status(self):
        return {"status": "ENDED" if self.closed else "ACTIVE", "finalized": self.finalized}

    async def team(self, team_id):
        row = self.data.get(team_id)
        return row if row and row.get("source_present") else None

    async def submit(self, team_id, code):
        with self.lock:
            self.submission_calls += 1
            if self.closed:
                return {"error": "round_closed"}
            if team_id not in self.data:
                return {"error": "unknown_team"}
            if self.data[team_id]["tinkercad_valid"]:
                return {"error": "duplicate_submission"}
            self.data[team_id].update(
                tinkercad_valid=True, tinkercad_code=code, tinkercad_timestamp=datetime.now(timezone.utc)
            )
            return {"accepted": True}

    async def leaderboard(self):
        return [
            {
                "rank": 1,
                "team_id": "CH01",
                "tinkercad_code": "PRIVATE",
                "email": "private@example.test",
                "form_timestamp": "PRIVATE",
            }
        ]

    async def sync(self, rows):
        if self.finalized:
            return {"count": 0, "skipped": True}
        for row in self.data.values():
            row["source_present"] = False
        for row in rows:
            existing = self.data.setdefault(row["team_id"], {"tinkercad_valid": False})
            existing.update(form_timestamp=row["form_timestamp"], source_present=True)
        return {"count": len(rows)}

    async def cutoff(self):
        with self.lock:
            if not self.closed:
                self.cutoff_time = datetime.now(timezone.utc)
            self.closed = True
            return {"status": "ENDED", "finalized": self.finalized}

    async def finalize(self, rows):
        if not self.finalized:
            self.finalize_calls += 1
            await self.sync(rows)
            self.finalized = True
        return {"status": "ENDED", "finalized": True}

    async def overview(self):
        return {
            **await self.status(),
            "teams": len(self.data),
            "accepted": 0,
            "qualification_slots": 15,
            "cutoff": None,
            "last_synced_at": None,
        }

    async def teams(self, offset=0):
        return [
            {"team_id": key, "tinkercad_valid": value["tinkercad_valid"]} for key, value in self.data.items()
        ][offset : offset + 100]
