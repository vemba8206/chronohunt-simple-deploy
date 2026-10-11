import hashlib
import hmac
import logging
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import httpx
import jwt
from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Config
from .domain import Login, Problem, Reset, Submission
from .services import check_result
from .simple_store import SimpleStore

log = logging.getLogger("chronohunt")


def create_app(config=None, store=None):
    config = config or Config.load()
    config.validate()
    client = httpx.AsyncClient(timeout=30, limits=httpx.Limits(max_connections=30))
    store = store or SimpleStore(config, client)
    sessions, attempts = {}, defaultdict(deque)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await client.aclose()

    app = FastAPI(
        title="ChronoHunt Round 2",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def headers_and_limits(request, call_next):
        if request.method == "POST":
            try:
                size = int(request.headers.get("content-length", "0"))
            except ValueError:
                size = 16385
            if size > 16384 or len(await request.body()) > 16384:
                return JSONResponse(
                    {
                        "error": {
                            "code": "too_large",
                            "message": "Request is too large.",
                        }
                    },
                    status_code=413,
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(Problem)
    async def problem(request, exc):
        if exc.status >= 500:
            log.warning("Competition operation failed: %s", exc.code)
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message}},
            status_code=exc.status,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse(
            {
                "error": {
                    "code": "invalid_request",
                    "message": "Check your inputs. Team ID and PIN are required; additional fields are not accepted.",
                }
            },
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        log.error("Unhandled competition request failure (%s).", type(exc).__name__)
        return JSONResponse(
            {
                "error": {
                    "code": "internal_error",
                    "message": "Request could not be completed. Please try again.",
                }
            },
            status_code=500,
        )

    def origin(request):
        if request.headers.get("origin") not in config.origins:
            raise Problem(403, "origin_denied", "This origin is not permitted.")

    def throttle(request, bucket, maximum):
        now = time.monotonic()
        if len(attempts) > 10000:
            for key in list(attempts):
                if not attempts[key] or now - attempts[key][-1] > 60:
                    del attempts[key]
        key = (bucket, request.client.host if request.client else "unknown")
        queue = attempts[key]
        while queue and queue[0] < now - 60:
            queue.popleft()
        if len(queue) >= maximum or len(attempts) > 20000:
            raise Problem(429, "rate_limited", "Too many attempts. Please wait a minute.")
        queue.append(now)

    def admin(request: Request):
        try:
            claims = jwt.decode(
                request.cookies.get("ch_simple_session", ""),
                config.session_secret,
                algorithms=["HS256"],
                options={"require": ["exp", "sid", "csrf"]},
            )
            if sessions.get(claims["sid"], 0) < time.time():
                raise ValueError()
        except jwt.PyJWTError, ValueError, KeyError:
            raise Problem(401, "unauthorized", "Administrator login is required.") from None
        if request.method != "GET":
            origin(request)
            if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), claims["csrf"]):
                raise Problem(403, "csrf_denied", "Session verification failed. Sign in again.")
        return claims

    @app.get("/api/health")
    async def health():
        return {"ok": True, "service": "chronohunt-round2"}

    @app.get("/api/competition/status")
    async def status():
        result = await store.status()
        return {
            "submissions_enabled": result.get("submissions_enabled", False) and await store.policy_ready(),
        }

    @app.get("/api/leaderboard")
    async def leaderboard(claims=Depends(admin)):
        rows = await store.leaderboard()
        return [{"rank": row["rank"], "team_id": row["team_id"], "accepted_at": row["accepted_at"]} for row in rows]

    @app.get("/api/admin/leaderboard")
    async def admin_leaderboard(claims=Depends(admin)):
        return await leaderboard(claims)

    @app.post("/api/submissions", status_code=201)
    async def submit(body: Submission, request: Request):
        throttle(request, "submit", 15)
        result = check_result(await store.submit(body.team_id, body.code))
        if not isinstance(result, dict) or result.get("accepted") is not True:
            raise Problem(
                503,
                "acceptance_unconfirmed",
                "The server did not confirm recording. Contact the organizer before retrying.",
            )
        return {
            "accepted": True,
            "team_id": body.team_id,
            "message": "Your submission has been recorded successfully.",
        }

    @app.post("/api/admin/login")
    async def login(body: Login, request: Request, response: Response):
        origin(request)
        throttle(request, "login", 5)

        def digest(value):
            return hashlib.sha256(value.encode()).digest()

        if not hmac.compare_digest(digest(body.password), digest(config.admin_password)):
            raise Problem(401, "invalid_credentials", "Incorrect administrator password.")
        now = time.time()
        for sid in list(sessions):
            if sessions[sid] < now:
                del sessions[sid]
        if len(sessions) >= 1000:
            raise Problem(429, "session_limit", "Administrator session limit reached.")
        sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        sessions[sid] = now + config.session_ttl
        token = jwt.encode(
            {"sid": sid, "csrf": csrf, "exp": sessions[sid]},
            config.session_secret,
            algorithm="HS256",
        )
        response.set_cookie(
            "ch_simple_session",
            token,
            httponly=True,
            secure=config.cookie_secure,
            samesite=config.cookie_samesite,
            max_age=config.session_ttl,
            path="/api",
        )
        return {"authenticated": True, "csrf_token": csrf}

    @app.post("/api/admin/logout")
    async def logout(response: Response, claims=Depends(admin)):
        sessions.pop(claims["sid"], None)
        response.delete_cookie(
            "ch_simple_session",
            path="/api",
            secure=config.cookie_secure,
            samesite=config.cookie_samesite,
        )
        # Remove any old cookie from the former path after upgrading this app.
        response.delete_cookie(
            "ch_simple_session",
            path="/api/admin",
            secure=config.cookie_secure,
            samesite=config.cookie_samesite,
        )
        return {"authenticated": False}

    @app.get("/api/admin/overview")
    async def overview(claims=Depends(admin)):
        return {
            **await store.overview(),
            "csrf_token": claims["csrf"],
            "submission_policy_ready": await store.policy_ready(),
        }

    @app.get("/api/admin/teams")
    async def teams(offset: int = Query(0, ge=0), claims=Depends(admin)):
        rows = await store.teams(offset)
        return [{k: row[k] for k in ("team_id", "accepted_at", "rank") if k in row} for row in rows]

    @app.post("/api/admin/reset")
    async def reset(body: Reset, request: Request, claims=Depends(admin)):
        throttle(request, "reset", 3)
        result = check_result(await store.reset())
        if (not isinstance(result, dict) or result.get("reset") is not True
                or type(result.get("deleted")) is not int or result["deleted"] < 0):
            raise Problem(503, "reset_unconfirmed", "The database did not confirm the reset. Refresh before retrying.")
        return {"reset": True, "deleted": result["deleted"], "message": "All simplified submissions were deleted."}

    return app
