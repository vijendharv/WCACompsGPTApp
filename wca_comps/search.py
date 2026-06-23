"""Validated structured search workflow for app and MCP entrypoints."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from .competitions import CompetitionService
from .config import DEFAULT_PERSON_NAME
from .errors import NoResultsError, UpstreamServiceError
from .networking import WCAApiError, WCAClient
from .registrations import RegistrationService
from .report import build_assessments
from .serializers import serialize_search_result
from .validation import parse_from_date, select_regions, validate_wca_id


def search_competitions(
    *,
    wca_id: str,
    person_name: str | None = None,
    regions: Iterable[str] | None = None,
    from_date: str | None = None,
    today: date | None = None,
    client: WCAClient | None = None,
) -> dict[str, Any]:
    """Validate inputs, assess competitions, and return structured output."""
    normalized_wca_id = validate_wca_id(wca_id)
    selected_regions = select_regions(regions)
    start_from = parse_from_date(from_date, today=today)
    display_name = _normalize_person_name(person_name)

    wca_client = client or WCAClient()
    competition_service = CompetitionService(wca_client)
    registration_service = RegistrationService(wca_client)

    try:
        assessments = build_assessments(
            competition_service,
            registration_service,
            selected_regions,
            normalized_wca_id,
            start_from,
        )
    except WCAApiError as exc:
        raise UpstreamServiceError(f"WCA API request failed: {exc}") from exc

    if not assessments:
        region_names = ", ".join(region.name for region in selected_regions)
        raise NoResultsError(
            f"No competitions found in {region_names} from {start_from.isoformat()}"
        )

    return serialize_search_result(
        assessments=assessments,
        wca_id=normalized_wca_id,
        person_name=display_name,
        regions=tuple(region.name for region in selected_regions),
        from_date=start_from,
    )


def _normalize_person_name(value: str | None) -> str | None:
    if value is None:
        return DEFAULT_PERSON_NAME
    stripped = value.strip()
    return stripped or None
