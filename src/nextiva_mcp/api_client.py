import httpx


class NextivaError(Exception):
    def __init__(self, message: str):
        super().__init__(f"Nextiva (Thrio) API error: {message}")


class NextivaClient:
    """Async httpx client wrapping the Nextiva/Thrio contact center API.

    Auth is a single call that returns both a token and the actual
    per-tenant API host ("location") to use — Thrio clusters are
    multi-region, so the data host is never a fixed constant:

      GET https://login.thrio.com/provider/token-with-authorities
      with HTTP Basic Auth (username:password)
      -> {"location": "https://<tenant>.thrio.io", "token": "..."}

    The token is then sent as-is (no "Bearer " prefix) in an
    "Authorization" header on every real data/analytics call. Since there
    is no session state to preserve, this client re-authenticates fresh on
    every single call rather than caching the token across MCP requests.
    """

    def __init__(self, username: str, password: str, auth_url: str):
        self._username = username
        self._password = password
        self._auth_url = auth_url

    async def _login(self, client: httpx.AsyncClient) -> tuple[str, str]:
        try:
            resp = await client.get(
                self._auth_url,
                headers={"Content-Type": "application/json"},
                auth=(self._username, self._password),
            )
        except httpx.RequestError as e:
            raise NextivaError(f"{e or type(e).__name__} (token-with-authorities)") from e
        if resp.status_code >= 400:
            raise NextivaError(f"HTTP {resp.status_code} during login: {resp.text}")
        data = resp.json()
        location = data.get("location")
        token = data.get("token")
        if not location or not token:
            raise NextivaError(f"login did not return location/token: {resp.text}")
        return location, token

    def _clean(self, params: dict | None) -> dict:
        if not params:
            return {}
        return {k: v for k, v in params.items() if v is not None}

    async def call(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            location, token = await self._login(client)
            try:
                resp = await client.get(
                    f"{location}{path}",
                    headers={"Authorization": token},
                    params=self._clean(params),
                )
            except httpx.RequestError as e:
                raise NextivaError(f"{e or type(e).__name__} (path={path})") from e
            if resp.status_code >= 400:
                raise NextivaError(f"HTTP {resp.status_code} calling {path}: {resp.text}")
            return resp.json()
