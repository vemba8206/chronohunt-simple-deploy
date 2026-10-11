"""Read-only live state/schema evidence. No credentials, team IDs or codes printed."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx

from app.config import Config
from app.services import SupabaseStore


async def main():
    config = Config.load()
    print("PIN policy: nonempty input; no circuit correctness verification")
    print("Token-authenticated Sheet requests:", bool(config.sheet_token))
    print("Session cookie Secure:", config.cookie_secure)
    print("Configured development origins:", ", ".join(config.origins))
    async with httpx.AsyncClient(timeout=30) as client:
        store = SupabaseStore(config, client)
        overview = await store.overview()
        print(
            "Database overview:",
            {
                key: value
                for key, value in overview.items()
                if key in ("status", "finalized", "qualification_slots", "teams", "accepted")
            },
        )
        response = await client.get(
            store.url + "/", headers={**store.headers, "Accept": "application/openapi+json"}
        )
        if response.is_success:
            definitions = response.json().get("definitions", {})
            for table in ("teams", "competition_settings"):
                print(
                    table + " exposed column names:", sorted(definitions.get(table, {}).get("properties", {}))
                )
        else:
            print("PostgREST schema metadata unavailable; run the read-only SQL inspection.")
        response = await client.get(
            store.url + "/teams",
            headers=store.headers,
            params={"select": "form_timestamp,tinkercad_timestamp,source_present", "limit": "1000"},
        )
        if response.is_success:
            rows = response.json()
            print("Stored rows inspected (maximum 1000):", len(rows))
            print(
                "Missing original registration timestamps:",
                sum(row.get("form_timestamp") is None for row in rows),
            )
            print(
                "Stored website receipt timestamps:",
                sum(row.get("tinkercad_timestamp") is not None for row in rows),
            )
        print(
            "Live SQL catalog grants/RLS require SQL-editor inspection; REST metadata does not certify them."
        )


if __name__ == "__main__":
    asyncio.run(main())
