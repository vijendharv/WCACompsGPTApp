"""MCP server adapter for the WCA Competition Finder."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from .errors import InputValidationError, NoResultsError, UpstreamServiceError
from .people import search_people
from .search import search_competitions

SERVER_NAME = "WCA Competition Finder"
WIDGET_RESOURCE_URI = "ui://widget/competition-results-v1.html"
WIDGET_MIME_TYPE = "text/html;profile=mcp-app"
WIDGET_HTML_PATH = Path(__file__).resolve().parent.parent / "public" / "competition-results-widget.html"
SERVER_INSTRUCTIONS = (
    "Use this server to find upcoming World Cube Association competitions, "
    "check public registration status for a WCA ID, and explain registration "
    "eligibility. If the user gives a name without a WCA ID, first call "
    "search_wca_people, show its candidates, and ask the user to choose the "
    "correct WCA ID. Never select an identity on the user's behalf. The search "
    "tools are read-only and use public WCA data. "
    "After render_competition_results returns, treat its widget as the complete "
    "user-facing result. Do not repeat its competition rows, summary, or table "
    "unless the user explicitly asks for a text version."
)


class WCAPersonCandidate(BaseModel):
    """A public WCA identity candidate returned by a name search."""

    name: str
    wca_id: str
    country: str | None = None
    profile_url: str


class SearchWCAPeopleResult(BaseModel):
    """Structured output for the search_wca_people MCP tool."""

    model_config = ConfigDict(extra="forbid")

    query: str
    count: int
    selection_required: bool
    candidates: list[WCAPersonCandidate]


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


def search_wca_people_handler(
    name: Annotated[
        str,
        Field(
            description=(
                "Person name to search in the public WCA directory. Returns at "
                "most 20 candidates with WCA IDs for the user to choose from."
            )
        ),
    ],
) -> SearchWCAPeopleResult:
    """Find public WCA identity candidates without choosing one."""
    try:
        payload = search_people(name)
    except InputValidationError as exc:
        raise _tool_error(exc.code, str(exc), field=exc.field) from exc
    except UpstreamServiceError as exc:
        raise _tool_error(exc.code, str(exc)) from exc

    return SearchWCAPeopleResult.model_validate(payload)


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
                "Optional U.S. states or Canadian provinces/territories to "
                "search by full name or postal abbreviation. Defaults to "
                "Washington, Oregon, and British Columbia. Use United States "
                "or Canada to search every supported subdivision in a country."
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


def render_competition_results_handler(
    prepared_result: Annotated[
        SearchWCACompetitionsResult,
        Field(
            description=(
                "A structured search_wca_competitions result to render. "
                "This tool does not refetch WCA data."
            )
        ),
    ],
) -> SearchWCACompetitionsResult:
    """Render prepared competition results as a ChatGPT widget."""
    return prepared_result


def _widget_resource_meta() -> dict[str, Any]:
    """Build widget metadata from portable defaults and deployment settings."""
    ui: dict[str, Any] = {
        "prefersBorder": True,
        "csp": {
            "connectDomains": [],
            "resourceDomains": [],
        },
    }
    widget_domain = os.environ.get("WIDGET_DOMAIN", "").strip()
    if widget_domain:
        ui["domain"] = widget_domain

    return {
        "ui": ui,
        "openai/widgetDescription": (
            "Complete interactive WCA competition results, including grouped "
            "registration status, capacity, region filtering, and official WCA "
            "links. The widget already presents the full result, so no duplicate "
            "assistant table or summary is needed."
        ),
        "openai/widgetPrefersBorder": True,
        "openai/widgetCSP": {
            "connect_domains": [],
            "resource_domains": [],
            "redirect_domains": ["https://www.worldcubeassociation.org"],
        },
    }


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
    server.custom_route(
        "/health",
        methods=["GET"],
        name="health",
        include_in_schema=False,
    )(health_check_handler)
    server.resource(
        WIDGET_RESOURCE_URI,
        name="competition_results_widget",
        title="Competition results widget",
        description="Responsive grouped WCA competition cards.",
        mime_type=WIDGET_MIME_TYPE,
        meta=_widget_resource_meta(),
    )(_competition_results_widget_html)
    server.tool(
        name="search_wca_people",
        title="Search WCA people",
        description=(
            "Search the public WCA directory by person name and return at most "
            "20 candidates. Present the candidates and ask the user to choose "
            "the correct WCA ID before searching competitions; never choose "
            "an identity automatically."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        structured_output=True,
    )(search_wca_people_handler)
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
    server.tool(
        name="render_competition_results",
        title="Render competition results",
        description=(
            "Render a prepared search_wca_competitions result as responsive "
            "grouped competition cards. This tool does not refetch data. Treat "
            "the widget as the complete response unless the user asks for text."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
        meta={
            "ui": {"resourceUri": WIDGET_RESOURCE_URI},
            "openai/outputTemplate": WIDGET_RESOURCE_URI,
        },
        structured_output=True,
    )(render_competition_results_handler)
    return server


async def health_check_handler(_request: Request) -> JSONResponse:
    """Report process health without calling upstream services."""
    return JSONResponse({"status": "ok"})


def _competition_results_widget_html() -> str:
    return WIDGET_HTML_PATH.read_text(encoding="utf-8")


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
