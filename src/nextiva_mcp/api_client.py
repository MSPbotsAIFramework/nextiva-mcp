import asyncio

import httpx

from ._json import error_envelope

_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_MAX_BACKOFF_SECONDS = 20.0

# status_code -> (error code, retryable). status_code 0 means a network/
# connection-level failure (no response at all). 502 is also used
# synthetically below when the login call returns HTTP 200 but an
# unparseable/incomplete body (missing location/token).
_STATUS_TO_CODE: dict[int, tuple[str, bool]] = {
    0: ("upstream_error", True),
    400: ("invalid_argument", False),
    401: ("unauthorized", False),
    403: ("unauthorized", False),
    404: ("not_found", False),
    422: ("invalid_argument", False),
    429: ("rate_limited", True),
}


def _classify(status_code: int) -> tuple[str, bool]:
    if status_code in _STATUS_TO_CODE:
        return _STATUS_TO_CODE[status_code]
    if status_code >= 500:
        return "upstream_error", True
    return "invalid_argument", False


class NextivaError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Nextiva (Thrio) API error {status_code}: {message}")

    def to_envelope(self) -> str:
        code, retryable = _classify(self.status_code)
        return error_envelope(code, self.message, retryable)


class NextivaClient:
    """Async httpx client wrapping the Nextiva/Thrio contact center API.

    Auth is a single call that returns both a token and the actual
    per-tenant API host ("location") to use — Thrio clusters are
    multi-region, so the data host is never a fixed constant:

      GET https://login.thrio.com/provider/token-with-authorities
      with HTTP Basic Auth (username:password)
      -> {"location": "https://<tenant>.thrio.io", "token": "..."}

    The token is then sent as-is (no "Bearer " prefix) in an
    "Authorization" header on every real data/analytics call.

    Deliberately does NOT use a shared module-level httpx.AsyncClient like
    the Addigy/Cove reference clients do. Auth here is HTTP Basic
    (username/password) exchanged fresh for a token+location pair, and the
    login result is per-tenant; reusing one client/connection pool across
    concurrent requests from different tenants would risk connection-level
    state leaking across tenants. Instead, every top-level call (`call`)
    opens a fresh httpx.AsyncClient, logs in fresh, makes the one real
    call, and discards the client — nothing is cached or persisted across
    requests (see server.py's contextvar-based per-request credential
    isolation, and SOP §3.4's ban on cross-request caching of
    tenant-derived tokens). This is the same "fresh client per top-level
    call" pattern used by logmein-mcp for its session-cookie-based auth.
    """

    def __init__(self, username: str, password: str, auth_url: str):
        self._username = username
        self._password = password
        self._auth_url = auth_url

    def _clean(self, params: dict | None) -> dict:
        if not params:
            return {}
        return {k: v for k, v in params.items() if v is not None}

    def _retry_delay(self, resp: httpx.Response, attempt: int) -> float:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), _MAX_BACKOFF_SECONDS)
            except ValueError:
                pass
        return min(2**attempt, _MAX_BACKOFF_SECONDS)

    async def _get(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        headers: dict | None = None,
        auth: tuple[str, str] | None = None,
        params: dict | None = None,
        context: str,
    ) -> httpx.Response:
        """GET with retry + backoff on network errors and 429/5xx, respecting
        Retry-After (capped at _MAX_BACKOFF_SECONDS, up to _MAX_RETRIES
        attempts). Returns the final response for the caller to inspect;
        raises NextivaError only for network-level failures that exhaust
        all retries.
        """
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await client.get(url, headers=headers, auth=auth, params=params)
            except httpx.RequestError as e:
                last_exc = e
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(min(2**attempt, _MAX_BACKOFF_SECONDS))
                    continue
                raise NextivaError(0, f"{e or type(e).__name__} ({context})") from e

            if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                await asyncio.sleep(self._retry_delay(resp, attempt))
                continue
            return resp

        if last_exc:
            raise NextivaError(0, f"{last_exc}") from last_exc
        raise NextivaError(0, "request failed with no response")

    async def _login(self, client: httpx.AsyncClient) -> tuple[str, str]:
        resp = await self._get(
            client,
            self._auth_url,
            headers={"Content-Type": "application/json"},
            auth=(self._username, self._password),
            context="token-with-authorities",
        )
        if resp.status_code >= 400:
            raise NextivaError(resp.status_code, f"login failed: {resp.text.strip()}")
        data = resp.json()
        location = data.get("location")
        token = data.get("token")
        if not location or not token:
            raise NextivaError(
                502, f"login did not return location/token: {resp.text.strip()}"
            )
        return location, token

    async def call(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            location, token = await self._login(client)
            resp = await self._get(
                client,
                f"{location}{path}",
                headers={"Authorization": token},
                params=self._clean(params),
                context=f"path={path}",
            )
            if resp.status_code >= 400:
                raise NextivaError(resp.status_code, f"{path}: {resp.text.strip()}")
            return resp.json()
