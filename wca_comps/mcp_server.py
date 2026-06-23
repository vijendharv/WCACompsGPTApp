"""MCP server adapter for the WCA Competition Finder."""

from __future__ import annotations

import json
import os
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .errors import InputValidationError, NoResultsError, UpstreamServiceError
from .search import search_competitions

SERVER_NAME = "WCA Competition Finder"
SERVER_INSTRUCTIONS = (
    "Use this server to find upcoming World Cube Association competitions, "
    "check public registration status for a WCA ID, and explain registration "
    "eligibility. The search tool is read-only and uses public WCA API data."
)


class QueryResult(BaseModel):
    """The validated search query used to produce a result."""

    wca_id: str
    person_name: str | None = None
    regions: list[str]
    from_date: str


class SummaryResult(BaseModel):
    """Summary counts for a competition search."""

    total: int
    registered: int
    available: int
    unavailable: int


class CompetitionResult(BaseModel):
    """Public competition details returned by WCA."""

    id: str
    name: str
    start_date: str
    end_date: str
    location: str
    venue: str
    url: str
    region: str
    event_ids: list[str]
    registration_open: str | None = None
    registration_close: str | None = None
    competitor_limit: int | None = None


class RegistrationResult(BaseModel):
    """Public registration status for the requested WCA ID."""

    is_registered: bool
    status: str | None = None
    event_ids: list[str]
    competitor_count: int | None = None


class EligibilityResult(BaseModel):
    """Computed registration eligibility."""

    registration_state: Literal["not_open_yet", "open", "closed"]
    can_register: bool
    reason: str


class CompetitionAssessmentResult(BaseModel):
    """A competition paired with registration and eligibility details."""

    competition: CompetitionResult
    registration: RegistrationResult
    eligibility: EligibilityResult


class GroupedCompetitionResults(BaseModel):
    """Competition assessments grouped for UI consumption."""

    registered: list[CompetitionAssessmentResult]
    available: list[CompetitionAssessmentResult]
    unavailable: list[CompetitionAssessmentResult]


class SearchWCACompetitionsResult(BaseModel):
    """Structured output for the search_wca_competitions MCP tool."""

    model_config = ConfigDict(extra="forbid")

    query: QueryResult
    summary: SummaryResult
    groups: GroupedCompetitionResults
    competitions: list[CompetitionAssessmentResult]


def search_wca_competitions_handler(
    wca_id: Annotated[
        str,
        Field(description="WCA competitor ID to check, for example 2023VONT01."),
    ],
    person_name: Annotated[
        str | None,
        Field(description="Optional display name for the searched competitor."),
    ] = None,
    regions: Annotated[
        list[str] | None,
        Field(
            description=(
                "Optional supported regions to search. Defaults to Washington, "
                "Oregon, and British Columbia."
            )
        ),
    ] = None,
    from_date: Annotated[
        str | None,
        Field(
            description=(
                "Earliest competition start date in YYYY-MM-DD format. Defaults "
                "to the current date at request time when omitted or null."
            )
        ),
    ] = None,
) -> SearchWCACompetitionsResult:
    """Find upcoming WCA competitions and assess registration eligibility."""
    try:
        payload = search_competitions(
            wca_id=wca_id,
            person_name=person_name,
            regions=regions,
            from_date=from_date,
        )
    except InputValidationError as exc:
        raise _tool_error(exc.code, str(exc), field=exc.field) from exc
    except NoResultsError as exc:
        raise _tool_error(exc.code, str(exc)) from exc
    except UpstreamServiceError as exc:
        raise _tool_error(exc.code, str(exc)) from exc

    return SearchWCACompetitionsResult.model_validate(payload)


def create_mcp_server() -> FastMCP:
    """Create and configure the WCA Comps MCP server."""
    server = FastMCP(
        SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        streamable_http_path="/mcp",
        stateless_http=True,
    )
    server.tool(
        name="search_wca_competitions",
        title="Search WCA competitions",
        description=(
            "Find upcoming WCA competitions in supported regions and assess "
            "whether the requested competitor is registered or can register."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        structured_output=True,
    )(search_wca_competitions_handler)
    return server


def _tool_error(code: str, message: str, **extra: Any) -> ToolError:
    payload = {"code": code, "message": message, **extra}
    return ToolError(json.dumps(payload, sort_keys=True))


mcp = create_mcp_server()
app = mcp.streamable_http_app()


def main() -> None:
    """Run the MCP server.

    Defaults to stdio for local MCP Inspector usage. Set
    ``MCP_TRANSPORT=streamable-http`` to serve the `/mcp` HTTP endpoint.
    """
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport not in {"stdio", "streamable-http", "sse"}:
        raise SystemExit(
            "MCP_TRANSPORT must be one of: stdio, streamable-http, sse"
        )
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
