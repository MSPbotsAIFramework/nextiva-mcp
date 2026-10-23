# nextiva-mcp

MCP server for **Nextiva** (contact center platform, built on the acquired
**Thrio** product — API host is `login.thrio.com` / `*.thrio.io`). Exposes
the Thrio data and analytics API's users, campaigns, contacts, queues, and
work item history as MCP tools.

> Naming note: MSPbots' own integration is registered as "Nextiva"
> (`subjectCode=NEXTIVA`); the underlying API and all documentation
> reference "Thrio", the contact-center product Nextiva acquired. This MCP
> covers exactly the 5 methods MSPbots itself has configured.

<div align="center">

## MSPbots Connector

**The MCP Gateway built for MSPs: visible, controlled, and your data stays where it belongs.**

[**Get started at connect.mspbots.ai →**](https://connect.mspbots.ai)

</div>

---

MSPbots Connector gives your AI clients one MCP URL to reach your entire MSP stack (RMM, PSA, documentation, security, finance), and gives you control over who can call which tool and a record of everything that was called.

**Hosted service: [connect.mspbots.ai](https://connect.mspbots.ai)** · Free to use.

### Why Connector

![MSPbots Connector](https://stgoss.mspbots.ai/files/mcp/mspbots-mcp.png)

| | |
|---|---|
| **Visible** | Every tool call is logged: who, which vendor, when. Usage dashboard, CSV export, SIEM streaming. |
| **Controlled** | Role-based, per-tool allowlist. Deny by default. |
| **Protected** | Credentials encrypted per record. AI clients never see your vendor passwords or tokens. |
| **MSP-native** | Built for the MSP stack only: RMM, PSA, documentation, security, finance. |

### Quick start

1. **Sign up** at [connect.mspbots.ai](https://connect.mspbots.ai).
2. **Connect your vendors.** Pick from 150+ connectors and authorize each one on the vendor's own page, or bring your own API keys. No extra vendor accounts needed.
3. **Set access.** Create roles and decide which tools each role may call. Nothing is allowed until you allow it.
4. **Add your MCP URL to your AI client.** Copy the URL from your Connector dashboard into Claude, ChatGPT, Cursor, VS Code, Gemini, Codex, or any MCP-capable client.
5. **Ask your AI to do real work**, and watch every call appear in the audit log.

### Features

**Unified gateway**
- One MCP URL for all your AI clients
- 150+ connectors across the MSP stack
- Custom MCP servers supported, free
- Authorization happens on each vendor's own page; the AI never sees passwords or tokens
- Bring your own credentials: use the vendor API keys you already have
- Multiple accounts per app; connect once, reuse across AI clients
- Tool search: finds the right action for the task
- One sign-in; vendor credentials are injected behind the scenes and OAuth tokens refresh automatically

**Visibility**
- Audit log for every tool call (who, which vendor, when)
- Usage dashboard: call volume, top vendors, error rate, per-user activity
- Export audit logs to CSV, or stream to Loki, Graylog, or LogScale (SIEM)
- Optional recording of tool arguments and result summaries (off by default, enabled per organization)

**Control**
- Per-role, per-tool allowlist, deny by default
- owner / admin / member roles
- SCIM provisioning with Entra ID, Okta, JumpCloud, and Google Workspace

**Security**
- Credentials encrypted one record at a time (AES-256-GCM, per-record key)
- AI clients authenticate with OAuth 2.1 + PKCE
- Vendor responses are scanned for prompt-injection patterns and returned as structured data. This is one layer of defense, not a guarantee against every attack.
- Static egress IP for customer firewall and API allowlisting

### Pricing

**Free.**

Links: [connect.mspbots.ai](https://connect.mspbots.ai) · [mspbots.ai](https://mspbots.ai)

---

## Overview

- Stateless HTTP service. No credentials are ever persisted — each request
  supplies its own username/password via headers, used only for the
  lifetime of that single request.
- Supports concurrent requests; per-request credential isolation is done via
  Python `contextvars`, not a global/shared client instance.
- Entry points: `POST /mcp` (MCP protocol) and `GET /health` (health check).
- Default port: `8080` (configurable via `MCP_HTTP_PORT`).

## Authentication

Thrio's auth call returns **both** a token and the actual per-tenant API
host to use — Thrio is deployed across multiple regional clusters, so
there is no single fixed data-plane hostname:

1. `GET https://login.thrio.com/provider/token-with-authorities` with
   **HTTP Basic Auth** (`username:password`) → `{"location":
   "https://<tenant-cluster>.thrio.io", "token": "..."}`.
2. Every real data/analytics call then goes to `{location}` (not
   `login.thrio.com`) with the token sent as-is in an `Authorization`
   header — **no `Bearer ` prefix**.

Since there is no session to preserve, this server re-authenticates fresh
on every single tool call — nothing is cached or persisted across MCP
requests.

### HEADER authentication parameters

| Header | Type | Required | Default | Allowed values | Description | Example |
|---|---|---|---|---|---|---|
| `X-Nextiva-Username` | string | Yes | None | None | Thrio/Nextiva account username | `admin@example.com` |
| `X-Nextiva-Password` | string | Yes | None | None | The corresponding password | `••••••••` |

Missing either header returns `401`:
```json
{
  "error": "Missing credentials",
  "message": "This server requires the X-Nextiva-Username and X-Nextiva-Password headers",
  "required_headers": ["X-Nextiva-Username", "X-Nextiva-Password"],
  "optional_headers": []
}
```

An invalid username/password surfaces as a tool-level error during the
internal login step, not an HTTP-level error from this server.

## Environment Variables

| Variable | Type | Required | Default | Description |
|---|---|---|---|---|
| `MCP_HTTP_PORT` | int | No | `8080` | HTTP listen port |
| `MCP_HTTP_HOST` | string | No | `0.0.0.0` | HTTP listen address |
| `NEXTIVA_AUTH_URL` | string | No | `https://login.thrio.com/provider/token-with-authorities` | Fixed entry URL for logging in to obtain the token/location |

## MCP Endpoint

- `POST /mcp` — MCP protocol (streamable HTTP transport)
- `GET /health` — health check, returns `{"status": "ok"}` (pure local probe, does not call the Nextiva/Thrio API)

## Tool List

All 5 tools are read-only (`readOnlyHint=True`, `idempotentHint=True`); there are no write/delete tools.

| Tool | Description | Parameters |
|---|---|---|
| `nextiva_get_users` | List all users under the account (agents/technicians) | `start` (optional, pagination offset) |
| `nextiva_get_campaigns` | List call marketing campaigns | `range_type` (optional, default `lastweek`), `start` (optional) |
| `nextiva_get_contacts` | List contacts (customers/leads) | `start`(optional) |
| `nextiva_get_queues` | List call/chat/email queues | `start`(optional) |
| `nextiva_get_workitems_history` | Get historical activity and summary statistics for call/chat/SMS/email work items | `range_type` (optional, default `lastweek`) |

Per-parameter documentation lives on each tool's parameter schema (visible via `tools/list`), not in this table — this table is a quick-reference only and parameter names here are kept in sync with the code.

Successful responses are the vendor's JSON, compactly serialized (no
pretty-printing, `ensure_ascii=False`) and capped at ~20,000 characters —
an oversized list response is truncated with `truncated`/`original_count`
markers rather than returned in full. There is no vendor-documented
`limit`/page-size parameter for these endpoints (pagination is a `start`
offset only, see Known Gaps below), so there is nothing to clamp beyond
this automatic character cap.

Errors are returned as a JSON error envelope (not an exception/HTTP
error), e.g.:
```json
{"error": {"code": "upstream_error", "message": "...", "retryable": true}}
```
`code` is one of `not_configured` / `unauthorized` / `not_found` /
`invalid_argument` / `rate_limited` / `upstream_error`, mapped from the
Thrio API's HTTP status code (see `error_envelope`/`NextivaError.to_envelope`
in `api_client.py`). Outbound calls use a 5s connect / 30s read timeout,
and retry up to 3 times with capped exponential backoff on `429`/5xx
responses (respecting `Retry-After`).

## Test Example

```bash
# Health check
curl -s http://localhost:8080/health

# Call a tool via the MCP protocol (streamable HTTP) — requires an
# initialize handshake first per the MCP spec; abbreviated example below
# shows the tool-call request body only:
curl -s -X POST http://localhost:8080/mcp \
  -H "X-Nextiva-Username: admin@example.com" \
  -H "X-Nextiva-Password: <your-password>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <session-id-from-initialize>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "nextiva_get_users",
      "arguments": {}
    }
  }'
```

**Live-verified** (2026-07-30) against a real Nextiva/Thrio tenant, all 5
tools called end-to-end through this running server: `nextiva_get_users`
returned 101 real users; `nextiva_get_campaigns` returned 9 real campaigns
(e.g. "Nextiva - Transfers"); `nextiva_get_contacts` returned 99 real
contacts; `nextiva_get_queues` returned 18 real queues; and
`nextiva_get_workitems_history` returned real summary totals (e.g.
297 inbound, 195 outbound, 500 contacts in the last 7 days) — all with
the login step resolving the tenant's real cluster host dynamically
(`https://mancity.thrio.io`).

## API Reference

- Public, no login required: https://api.thrio.com/ (Postman-generated
  documentation covering Authentication, Objects/Data API, Analytics, and
  more)

## Known Gaps

- **Scope is exactly MSPbots' 5 configured endpoints, not the vendor's
  full API surface** — Thrio's API also covers Workitem actions, List
  Management, Dashboards, Recordings, Contact Consent, State DID, Chat,
  CRM, Client, Number Verification, WFM, TEAMS, Callbacks, and more (per
  the public docs' own navigation); those are out of scope here.
- **Pagination is a `start` offset**, confirmed empirically (passing
  `start=1` shifted the result window by one and updated the response's
  `previous` field accordingly) — the vendor's public docs describe this
  less explicitly than the request/response shape actually demonstrates,
  so this was verified against the live API rather than assumed from the
  docs alone.
- **The `session/login` step described in the vendor's docs (`POST
  {location}/users/api/login`) is NOT used by this server** — it appeared
  necessary only for creating a full interactive agent session (e.g. for
  telephony/ACD state), not for the read-only data/analytics endpoints
  MSPbots uses, which worked correctly with just the Authentication
  token. Confirmed by successfully calling all 5 endpoints without it.
