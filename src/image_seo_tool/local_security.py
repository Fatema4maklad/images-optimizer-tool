"""Browser request boundary for the loopback-only local application."""

from fastapi.responses import JSONResponse


class LocalRequestGate:
    """Reject DNS rebinding hosts and cross-site writes to the local app."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {name.lower(): value for name, value in scope.get("headers", [])}
        host = headers.get(b"host", b"").decode("ascii", errors="ignore").lower()
        if host.split(":", 1)[0] not in {"127.0.0.1", "localhost"}:
            await JSONResponse({"detail": "Local host required."}, status_code=403)(scope, receive, send)
            return

        if scope.get("method") not in {"GET", "HEAD", "OPTIONS"}:
            origin = headers.get(b"origin", b"").decode("ascii", errors="ignore").lower()
            fetch_site = headers.get(b"sec-fetch-site", b"").decode("ascii", errors="ignore").lower()
            if (origin and origin != f"http://{host}") or fetch_site == "cross-site":
                await JSONResponse({"detail": "Cross-site request blocked."}, status_code=403)(scope, receive, send)
                return

        await self.app(scope, receive, send)
