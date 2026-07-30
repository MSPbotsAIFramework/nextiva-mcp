import json
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from ..api_client import NextivaClient, NextivaError
from ._common import NO_TOKEN


def register(mcp: FastMCP, client_factory: Callable[[], NextivaClient | None]) -> None:

    @mcp.tool()
    async def nextiva_get_users(start: int | None = None) -> str:
        """List all Thrio/Nextiva users (agents/technicians) in the account.

        API: GET {location}/data/api/types/user

        No required parameters.

        Args:
            start: Optional. Pagination offset (the response's "previous"/
                "next" fields are cursor values in the same units).
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call("/data/api/types/user", params={"start": start})
            return json.dumps(result, indent=2)
        except NextivaError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def nextiva_get_campaigns(range_type: str = "lastweek", start: int | None = None) -> str:
        """List outbound/inbound calling campaigns.

        API: GET {location}/data/api/types/campaign

        Args:
            range_type: Optional. Time range for campaign activity, e.g.
                "lastweek" (default, matches MSPbots' own usage), "today",
                "thismonth".
            start: Optional. Pagination offset.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call(
                "/data/api/types/campaign", params={"rangeType": range_type, "start": start}
            )
            return json.dumps(result, indent=2)
        except NextivaError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def nextiva_get_contacts(start: int | None = None) -> str:
        """List contacts (customers/leads) in the account.

        API: GET {location}/data/api/types/contact

        No required parameters.

        Args:
            start: Optional. Pagination offset.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call("/data/api/types/contact", params={"start": start})
            return json.dumps(result, indent=2)
        except NextivaError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def nextiva_get_queues(start: int | None = None) -> str:
        """List call/chat/email queues in the account.

        API: GET {location}/data/api/types/queue

        No required parameters.

        Args:
            start: Optional. Pagination offset.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call("/data/api/types/queue", params={"start": start})
            return json.dumps(result, indent=2)
        except NextivaError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def nextiva_get_workitems_history(range_type: str = "lastweek") -> str:
        """Get historical work item (call/chat/SMS/email) activity and
        summary totals across the account.

        API: GET {location}/analytics/api/v1/types/workitems/history

        Args:
            range_type: Optional. Time range for the history, e.g.
                "lastweek" (default, matches MSPbots' own usage), "today",
                "thismonth".
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call(
                "/analytics/api/v1/types/workitems/history", params={"rangeType": range_type}
            )
            return json.dumps(result, indent=2)
        except NextivaError as e:
            return f"Error: {e}"
