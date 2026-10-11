"""HTTPS privacy checks; no submissions, credentials or destructive confirmation."""

import argparse
import ipaddress
from urllib.parse import urlparse

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Actual deployed participant HTTPS origin")
    args = parser.parse_args()
    url = urlparse(args.url)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in ("", "/")
    ):
        parser.error("Use the actual HTTPS participant origin only, without credentials/path/query.")
    if url.hostname == "localhost" or url.hostname.endswith((".localhost", ".local")):
        parser.error("Local network addresses are not public deployment URLs.")
    try:
        if not ipaddress.ip_address(url.hostname).is_global:
            parser.error("Private network addresses are not public deployment URLs.")
    except ValueError:
        pass
    passed = True
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=45, follow_redirects=False) as client:
        expected = {
            "/": 200,
            "/admin": 200,
            "/leaderboard": 200,
            "/chronohunt-logo.png": 200,
            "/api/health": 200,
            "/api/competition/status": 200,
            "/api/leaderboard": 401,
            "/api/admin/leaderboard": 401,
            "/api/admin/teams": 401,
            "/api/admin/overview": 401,
        }
        for path, code in expected.items():
            try:
                response = client.get(path)
                ok = response.status_code == code
                if path.startswith("/api/"):
                    ok = ok and "json" in response.headers.get("content-type", "")
                    data = response.json() if ok else None
                    if path == "/api/competition/status" and ok:
                        ok = set(data) == {"submissions_enabled"}
                        print("Submissions enabled:", data.get("submissions_enabled"))
                    if code == 401 and ok:
                        ok = set(data) == {"error"} and data["error"].get("code") == "unauthorized"
                    if path == "/api/health" and ok:
                        ok = data.get("service") == "chronohunt-round2" and data.get("ok") is True
                elif path == "/chronohunt-logo.png":
                    ok = ok and "image/png" in response.headers.get("content-type", "")
                else:
                    ok = ok and "text/html" in response.headers.get("content-type", "")
                print(path, "PASS" if ok else "FAIL", response.status_code)
                passed = passed and ok
            except httpx.HTTPError, ValueError, TypeError, AttributeError:
                print(path, "FAIL: unavailable or invalid response")
                passed = False
        # An invalid confirmation cannot invoke the reviewed reset RPC, even if auth regresses.
        if passed:
            try:
                response = client.post("/api/admin/reset", json={"confirmation": "INVALID-NONDESTRUCTIVE-CHECK"})
                ok = response.status_code == 401 and response.json().get("error", {}).get("code") == "unauthorized"
                print("/api/admin/reset (invalid confirmation, no login)", "PASS" if ok else "FAIL", response.status_code)
                passed = passed and ok
            except httpx.HTTPError, ValueError, TypeError, AttributeError:
                print("/api/admin/reset FAIL: unavailable or invalid response")
                passed = False
    print(
        "No data writes or destructive confirmation sent. Browser flow and authenticated organizer checks remain."
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
