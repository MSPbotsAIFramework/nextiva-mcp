# nextiva-mcp

MCP server for **Nextiva** (contact center platform, built on the acquired
**Thrio** product — API host is `login.thrio.com` / `*.thrio.io`). Exposes
the Thrio data and analytics API's users, campaigns, contacts, queues, and
work item history as MCP tools.

> Naming note: MSPbots' own integration is registered as "Nextiva"
> (`subjectCode=NEXTIVA`); the underlying API and all documentation
> reference "Thrio", the contact-center product Nextiva acquired. This MCP
> covers exactly the 5 methods MSPbots itself has configured.

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

### HEADER 授权参数说明

| Header | 类型 | 是否必填 | 默认值 | 枚举值 | 字段描述 | Example |
|---|---|---|---|---|---|---|
| `X-Nextiva-Username` | string | 是 | 无 | 无 | Thrio/Nextiva 账号用户名 | `admin@example.com` |
| `X-Nextiva-Password` | string | 是 | 无 | 无 | 对应密码 | `••••••••` |

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

| Variable | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `MCP_HTTP_PORT` | int | 否 | `8080` | HTTP 监听端口 |
| `MCP_HTTP_HOST` | string | 否 | `0.0.0.0` | HTTP 监听地址 |
| `NEXTIVA_AUTH_URL` | string | 否 | `https://login.thrio.com/provider/token-with-authorities` | 登录换 token/location 的固定入口地址 |

## MCP Endpoint

- `POST /mcp` — MCP protocol (streamable HTTP transport)
- `GET /health` — health check, returns `{"status": "ok", "service": "nextiva-mcp", "transport": "http"}`

## Tool List

| Tool | 功能 | 参数 |
|---|---|---|
| `nextiva_get_users` | 列出账号下所有用户（坐席/技术员） | `start`（可选，分页偏移量） |
| `nextiva_get_campaigns` | 列出呼叫营销活动（campaign） | `range_type`（可选，默认 `lastweek`），`start`（可选） |
| `nextiva_get_contacts` | 列出联系人（客户/线索） | `start`（可选） |
| `nextiva_get_queues` | 列出呼叫/聊天/邮件队列 | `start`（可选） |
| `nextiva_get_workitems_history` | 获取通话/聊天/短信/邮件工作项的历史活动及汇总统计 | `range_type`（可选，默认 `lastweek`） |

Responses are the vendor's JSON, pretty-printed, returned as-is.

## 测试示例

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
