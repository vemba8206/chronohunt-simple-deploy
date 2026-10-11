"""Read-only live checks; never print credentials, endpoint URLs or Sheet rows."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx

from app.config import Config
from app.domain import Problem
from app.services import SheetClient, SupabaseStore


async def main():
    try:
        config = Config.load()
    except (RuntimeError, ValueError) as exc:
        print("CONFIGURATION BLOCKED: " + str(exc))
        return 1
    failed = False
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            status = await SupabaseStore(config, client).status()
            if not isinstance(status, dict) or status.get("status") not in ("ACTIVE", "ENDED"):
                raise Problem(503, "schema", "Unexpected status. Inspect the existing schema and migration.")
            print("Supabase backend RPC: OK; round " + status["status"])
        except Problem as exc:
            print("SUPABASE BLOCKED: " + exc.message)
            failed = True
        try:
            snapshot = await SheetClient(config, client).inspect()
            print("Google Sheet backend request: OK (read-only; no records imported).")
            print(
                "Total relevant Sheet rows reported:",
                snapshot.total_rows_read
                if snapshot.total_rows_read is not None
                else "UNKNOWN — legacy endpoint supplies no full-Sheet coverage metadata",
            )
            print("Returned rows:", snapshot.returned_rows)
            print("Eligible records:", snapshot.eligible_records)
            print("Invalid rows:", len(snapshot.invalid_rows))
            print(
                "Invalid registration timestamps:",
                sum(row["reason"] == "invalid_registration_timestamp" for row in snapshot.invalid_rows),
            )
            print("Duplicate normalized IDs:", len(snapshot.duplicate_ids))
            print("Export coverage verified:", snapshot.coverage_verified)
            if not snapshot.coverage_verified or snapshot.duplicate_ids:
                print(
                    "REGISTRATION READINESS NOT VERIFIED: compare with the actual response Sheet before importing."
                )
                failed = True
            stored = []
            for offset in range(0, 100000, 100):
                batch = await SupabaseStore(config, client).teams(offset)
                stored.extend(batch)
                if len(batch) < 100:
                    break
            by_id = {row["team_id"]: row for row in stored}
            from datetime import datetime

            matched, mismatched = 0, 0
            for row in snapshot.records:
                current = by_id.get(row["team_id"])
                if current is None:
                    continue
                original = current.get("form_timestamp")
                if original and datetime.fromisoformat(
                    original.replace("Z", "+00:00")
                ) == datetime.fromisoformat(row["form_timestamp"].replace("Z", "+00:00")):
                    matched += 1
                else:
                    mismatched += 1
            print("Eligible records already stored with matching original timestamp:", matched)
            print(
                "Eligible records missing from database:",
                sum(row["team_id"] not in by_id for row in snapshot.records),
            )
            print("Stored/source original timestamp conflicts:", mismatched)
            if mismatched:
                failed = True
        except Problem as exc:
            print("GOOGLE SHEET BLOCKED: " + exc.message)
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
