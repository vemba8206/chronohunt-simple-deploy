import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    supabase_url: str
    supabase_key: str = field(repr=False)
    sheet_url: str
    admin_password: str = field(repr=False)
    session_secret: str = field(repr=False)
    origins: tuple[str, ...] = ("http://localhost:5175",)
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    session_ttl: int = 3600
    sync_interval: int = 0
    sheet_token: str = field(default="", repr=False)

    @classmethod
    def load(cls):
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        required = (
            "SUPABASE_URL",
            "SUPABASE_SECRET_KEY",
            "ADMIN_PASSWORD",
            "SESSION_SECRET",
            "CORS_ORIGINS",
        )
        missing = [key for key in required if not os.getenv(key, "").strip()]
        if missing:
            raise RuntimeError("Missing configuration: " + ", ".join(missing))
        config = cls(
            supabase_url=os.environ["SUPABASE_URL"].rstrip("/"),
            supabase_key=os.environ["SUPABASE_SECRET_KEY"],
            sheet_url="",
            admin_password=os.environ["ADMIN_PASSWORD"],
            session_secret=os.environ["SESSION_SECRET"],
            origins=tuple(x.strip().rstrip("/") for x in os.environ["CORS_ORIGINS"].split(",")),
            cookie_secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
            cookie_samesite=os.getenv("COOKIE_SAMESITE", "lax"),
            session_ttl=int(os.getenv("SESSION_TTL_SECONDS", "3600")),
            sync_interval=0,
            sheet_token="",
        )
        config.validate()
        return config

    def validate(self):
        if len(self.admin_password) < 12 or len(self.session_secret) < 32:
            raise RuntimeError(
                "ADMIN_PASSWORD needs 12+ characters; SESSION_SECRET needs 32+ random characters."
            )
        if urlparse(self.supabase_url).scheme != "https":
            raise RuntimeError("SUPABASE_URL must use HTTPS.")
        sheet = urlparse(self.sheet_url)
        if self.sheet_url and (
            sheet.scheme != "https"
            or sheet.hostname != "script.google.com"
            or not sheet.path.endswith("/exec")
        ):
            raise RuntimeError("GOOGLE_SHEET_API_URL must be an HTTPS script.google.com /exec deployment.")
        if not self.origins or any(
            urlparse(x).scheme not in ("http", "https") or not urlparse(x).netloc or x == "*"
            for x in self.origins
        ):
            raise RuntimeError("CORS_ORIGINS must contain explicit HTTP(S) origins.")
        if self.cookie_samesite not in ("lax", "strict", "none") or (
            self.cookie_samesite == "none" and not self.cookie_secure
        ):
            raise RuntimeError("Cross-site cookies require SameSite=none and COOKIE_SECURE=true.")
        if not self.cookie_secure and any(
            urlparse(origin).hostname not in ("localhost", "127.0.0.1", "::1") for origin in self.origins
        ):
            raise RuntimeError(
                "Non-local frontend origins require COOKIE_SECURE=true and HTTPS in production."
            )
        if any(
            urlparse(origin).hostname not in ("localhost", "127.0.0.1", "::1")
            and urlparse(origin).scheme != "https"
            for origin in self.origins
        ):
            raise RuntimeError("Non-local frontend origins must use HTTPS.")
        if not 60 <= self.session_ttl <= 86400 or self.sync_interval < 0:
            raise RuntimeError("Invalid session TTL or sync interval.")
