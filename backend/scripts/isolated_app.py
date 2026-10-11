"""Loopback disposable development API. Never loads .env or remote credentials.

Run with uvicorn scripts.isolated_app:app --host 127.0.0.1 --port 8001 --workers 1.
Only use the separate PGlite SQL bridge on 127.0.0.1:8091; never deploy this module.
"""

from contextlib import asynccontextmanager

import httpx

from app.config import Config
from app.main import create_app
from app.simple_store import SimpleStore

config = Config(
    supabase_url="https://isolated.invalid",
    supabase_key="isolated-fixture-only",
    sheet_url="",
    admin_password="isolated-organizer-only",
    session_secret="isolated-fixture-signing-secret-not-for-production",
    origins=("http://localhost:5175",),
)
client = httpx.AsyncClient(timeout=30)
store = SimpleStore(config, client)
store.url = "http://127.0.0.1:8091/rest/v1"
app = create_app(config=config, store=store)


@app.get("/api/isolated")
async def isolated_marker():
    return {"isolated": True, "database": "disposable-pglite"}


original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def isolated_lifespan(application):
    async with original_lifespan(application):
        try:
            yield
        finally:
            await client.aclose()


app.router.lifespan_context = isolated_lifespan
