import httpx

from .domain import Problem, inspect_sheet, parse_sheet


class SheetClient:
    def __init__(self, config, client):
        self.config, self.client = config, client

    async def payload(self):
        try:
            if self.config.sheet_token:
                response = await self.client.post(
                    self.config.sheet_url,
                    json={"token": self.config.sheet_token},
                    follow_redirects=True,
                )
            else:
                response = await self.client.get(self.config.sheet_url, follow_redirects=True)
            if response.status_code != 200 or "json" not in response.headers.get("content-type", ""):
                raise Problem(
                    502,
                    "sheet_access",
                    "Backend cannot access Sheet JSON. Check the Apps Script deployment access; Only myself requires Google login.",
                )
            return response.json()
        except httpx.HTTPError, ValueError:
            raise Problem(
                502,
                "sheet_unavailable",
                "Sheet request failed or returned non-JSON data. Check deployment access and connectivity.",
            ) from None

    async def fetch(self):
        return parse_sheet(await self.payload())

    async def inspect(self):
        return inspect_sheet(await self.payload())


class SupabaseStore:
    """PostgREST RPC uses the existing project; every mutation is a DB transaction."""

    def __init__(self, config, client):
        self.url, self.client = config.supabase_url + "/rest/v1", client
        self.headers = {
            "apikey": config.supabase_key,
            "Content-Type": "application/json",
        }
        # Legacy JWT service-role keys require Authorization; new sb_secret keys use apikey.
        if not config.supabase_key.startswith("sb_secret_"):
            self.headers["Authorization"] = "Bearer " + config.supabase_key

    async def rpc(self, name, args=None):
        try:
            response = await self.client.post(
                self.url + "/rpc/" + name, headers=self.headers, json=args or {}
            )
            if response.is_error:
                raise Problem(
                    503,
                    "database_unavailable",
                    "Database operation failed. Administrator: verify credentials, schema and SQL migration.",
                )
            return response.json()
        except httpx.HTTPError, ValueError:
            raise Problem(
                503,
                "database_unavailable",
                "Competition database is temporarily unavailable.",
            ) from None

    async def status(self):
        return await self.rpc("ch_status")

    async def require_integrity(self):
        try:
            result = await self.rpc("ch_integrity_status")
        except Problem:
            raise Problem(
                503,
                "integrity_update_required",
                "Administrator: the registration-integrity SQL update is unavailable. Review the focused update and database access before competition writes.",
            ) from None
        if not isinstance(result, dict) or result.get("registration_integrity") != 3:
            raise Problem(
                503,
                "integrity_update_required",
                "Administrator: review and apply the focused registration-integrity SQL update before competition writes.",
            )

    async def policy_ready(self):
        try:
            await self.require_integrity()
            return True
        except Problem:
            return False

    async def leaderboard(self):
        return await self.rpc("ch_leaderboard")

    async def team(self, team_id):
        return await self.rpc("ch_team", {"p_team_id": team_id})

    async def submit(self, team_id, code):
        await self.require_integrity()
        return await self.rpc("ch_submit", {"p_team_id": team_id, "p_code": code})

    async def sync(self, rows):
        await self.require_integrity()
        return await self.rpc("ch_sync", {"p_rows": rows})

    async def cutoff(self):
        await self.require_integrity()
        return await self.rpc("ch_cutoff")

    async def finalize(self, rows):
        await self.require_integrity()
        return await self.rpc("ch_finalize", {"p_rows": rows})

    async def overview(self):
        return await self.rpc("ch_overview")

    async def teams(self, offset=0):
        rows = await self.rpc("ch_teams", {"p_offset": offset})
        return [
            {
                ("website_submission_timestamp" if key == "tinkercad_timestamp" else key): value
                for key, value in row.items()
            }
            for row in rows
        ]


def check_result(result):
    if isinstance(result, dict) and result.get("error"):
        errors = {
            "invalid_team": (
                422,
                "Enter a nonempty Team ID of at most 32 characters.",
            ),
            "deadline_required": (
                503,
                "The organizer must configure the submission deadline first.",
            ),
            "invalid_deadline": (
                422,
                "Choose a future deadline with an explicit timezone.",
            ),
            "round_closed": (409, "The round has ended. New submissions are closed."),
            "unknown_team": (
                404,
                "Team ID is not registered. Complete the Google Form first, then wait for registration synchronization.",
            ),
            "duplicate_submission": (
                409,
                "A successful submission has already been recorded for this team.",
            ),
            "round_active": (409, "End the round before finalizing."),
            "registration_timestamp_conflict": (
                409,
                "A Sheet registration timestamp differs from its stored original value. Review the source before synchronizing; no records were changed.",
            ),
            "invalid_code": (422, "Enter a nonempty PIN of at most 256 characters."),
        }
        code = result["error"]
        status, message = errors.get(code, (503, "Competition operation could not be completed."))
        raise Problem(status, code, message)
    return result
