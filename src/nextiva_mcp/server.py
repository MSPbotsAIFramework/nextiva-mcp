import contextvars
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .api_client import NextivaClient
from .config import Settings

# Per-request credential isolation via contextvars.
# GatewayTokenMiddleware sets this before the MCP handler runs.
# Python asyncio copies context per task, so concurrent SSE connections are isolated.
_gateway_creds_var: contextvars.ContextVar[tuple[str, str] | None] = contextvars.ContextVar(
    "nextiva_gateway_creds", default=None
)


def get_client_from_context(settings: Settings) -> NextivaClient | None:
    """Resolve the active NextivaClient for the current request context."""
    creds = _gateway_creds_var.get()
    if not creds:
        return None
    username, password = creds
    return NextivaClient(username, password, settings.nextiva_auth_url)


class GatewayTokenMiddleware:
    """ASGI middleware.

    Reads X-Nextiva-Username and X-Nextiva-Password (both required) from
    request headers and stores them in the contextvar. Returns 401 if
    either is missing on /mcp requests.
    """

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        username = request.headers.get("x-nextiva-username")
        password = request.headers.get("x-nextiva-password")
        if not username or not password:
            response = JSONResponse(
                {
                    "error": "Missing credentials",
                    "message": (
                        "This server requires the X-Nextiva-Username and "
                        "X-Nextiva-Password headers"
                    ),
                    "required_headers": ["X-Nextiva-Username", "X-Nextiva-Password"],
                    "optional_headers": [],
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        ctx_token = _gateway_creds_var.set((username, password))
        try:
            await self.app(scope, receive, send)
        finally:
            _gateway_creds_var.reset(ctx_token)


def create_mcp_server(settings: Settings) -> FastMCP:
    """Build the FastMCP server instance and register all Nextiva tools."""
    # DNS-rebinding protection is a browser-oriented safeguard that rejects
    # non-localhost Host headers with 421. Disable it so the server works
    # correctly behind a reverse proxy or docker network.
    mcp = FastMCP(
        name="nextiva-mcp",
        instructions=(
            "Nextiva is a cloud contact-center platform (built on the acquired "
            "Thrio product) that routes and tracks calls, chats, SMS, and email "
            "through queues to agents, runs outbound/inbound calling campaigns, "
            "and stores contacts (customers/leads). This server exposes 5 "
            "read-only tools mirroring the Thrio data/analytics API: "
            "nextiva_get_users (agents/technicians), nextiva_get_queues "
            "(call/chat/email routing queues), nextiva_get_contacts "
            "(customers/leads), nextiva_get_campaigns (calling campaigns), and "
            "nextiva_get_workitems_history (aggregated call/chat/SMS/email "
            "activity totals over a time range). Typical flow: list queues or "
            "users to understand account structure, then pull "
            "workitems_history or campaign activity for reporting over a given "
            "range (e.g. today/lastweek/thismonth). All tools are read-only; "
            "there are no write/delete tools. Pagination uses a `start` offset "
            "cursor rather than a page number — responses include next/"
            "previous cursor values to continue."
        ),
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    client_factory: Callable[[], NextivaClient | None] = lambda: get_client_from_context(settings)

    from .tools import resources

    resources.register(mcp, client_factory)

    return mcp
