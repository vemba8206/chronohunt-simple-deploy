"""Simplified RPC namespace. Never calls advanced ch_* or Google Sheets."""

from .domain import Problem
from .services import SupabaseStore


class SimpleStore(SupabaseStore):
    async def require_integrity(self):
        try:
            result = await self.rpc("ch_simple_policy")
        except Problem:
            result = None
        if not isinstance(result, dict) or result.get("simple_competition") != 3:
            raise Problem(
                503,
                "simple_update_required",
                "The organizer SQL upgrade (007) is required. No submission was recorded.",
            )

    async def status(self):
        return await self.rpc("ch_simple_status")

    async def leaderboard(self):
        return await self.rpc("ch_simple_leaderboard")

    async def team(self, team_id):
        return await self.rpc("ch_simple_team", {"p_team_id": team_id})

    async def submit(self, team_id, code):
        await self.require_integrity()
        return await self.rpc("ch_simple_submit", {"p_team_id": team_id, "p_code": code})

    async def overview(self):
        return await self.rpc("ch_simple_overview")

    async def teams(self, offset=0):
        return await self.rpc("ch_simple_teams", {"p_offset": offset})

    async def reset(self):
        await self.require_integrity()
        return await self.rpc("ch_simple_reset")
