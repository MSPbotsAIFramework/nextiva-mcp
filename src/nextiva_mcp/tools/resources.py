from collections.abc import Callable
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .._json import dump_json_capped
from ..api_client import NextivaClient, NextivaError
from ._common import NO_TOKEN

_START_FIELD = Field(
    description=(
        "Pagination offset cursor. Omit for the first page; pass the value "
        "from the previous response's next/previous cursor field to continue."
    )
)
_RANGE_TYPE_FIELD = Field(
    description='Time range, e.g. "today", "lastweek" (default), "thismonth".'
)


def register(mcp: FastMCP, client_factory: Callable[[], NextivaClient | None]) -> None:

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def nextiva_get_users(
        start: Annotated[int | None, _START_FIELD] = None,
    ) -> str:
        """List all Thrio/Nextiva users (agents/technicians) in the account."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call("/data/api/types/user", params={"start": start})
            return dump_json_capped(result)
        except NextivaError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def nextiva_get_campaigns(
        range_type: Annotated[str, _RANGE_TYPE_FIELD] = "lastweek",
        start: Annotated[int | None, _START_FIELD] = None,
    ) -> str:
        """List outbound/inbound calling campaigns."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call(
                "/data/api/types/campaign", params={"rangeType": range_type, "start": start}
            )
            return dump_json_capped(result)
        except NextivaError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def nextiva_get_contacts(
        start: Annotated[int | None, _START_FIELD] = None,
    ) -> str:
        """List contacts (customers/leads) in the account."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call("/data/api/types/contact", params={"start": start})
            return dump_json_capped(result)
        except NextivaError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def nextiva_get_queues(
        start: Annotated[int | None, _START_FIELD] = None,
    ) -> str:
        """List call/chat/email queues in the account."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call("/data/api/types/queue", params={"start": start})
            return dump_json_capped(result)
        except NextivaError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def nextiva_get_workitems_history(
        range_type: Annotated[str, _RANGE_TYPE_FIELD] = "lastweek",
    ) -> str:
        """Get historical work item (call/chat/SMS/email) activity and summary totals for the account."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call(
                "/analytics/api/v1/types/workitems/history", params={"rangeType": range_type}
            )
            return dump_json_capped(result)
        except NextivaError as e:
            return e.to_envelope()
