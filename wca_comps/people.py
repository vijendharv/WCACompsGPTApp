"""WCA person-name lookup for explicit competitor selection."""

from __future__ import annotations

from typing import Any

from .errors import InputValidationError, UpstreamServiceError
from .networking import WCAApiError, WCAClient
from .validation import validate_wca_id

MAX_PERSON_RESULTS = 20


def search_people(
    name: str,
    *,
    client: WCAClient | None = None,
) -> dict[str, Any]:
    """Return candidates when a person search is narrow enough to select from."""
    query = _normalize_name(name)
    wca_client = client or WCAClient()

    try:
        payload = wca_client.get_json(
            "persons",
            params={
                "q": query,
                "per_page": MAX_PERSON_RESULTS + 1,
                "page": 1,
            },
        )
    except WCAApiError as exc:
        raise UpstreamServiceError(f"WCA person search failed: {exc}") from exc

    if not isinstance(payload, list):
        raise UpstreamServiceError("WCA person search returned an unexpected response")

    candidates: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for item in payload:
        candidate = _candidate_from_result(item)
        if candidate is None or candidate["wca_id"] in seen_ids:
            continue
        seen_ids.add(candidate["wca_id"])
        candidates.append(candidate)
        if len(candidates) > MAX_PERSON_RESULTS:
            break

    refinement_required = len(candidates) > MAX_PERSON_RESULTS
    if refinement_required:
        return {
            "query": query,
            "count": 0,
            "selection_required": False,
            "refinement_required": True,
            "message": (
                "More than 20 people matched. Ask the user for a more complete "
                "name or their WCA ID, then search again."
            ),
            "candidates": [],
        }

    return {
        "query": query,
        "count": len(candidates),
        "selection_required": bool(candidates),
        "refinement_required": False,
        "message": None,
        "candidates": candidates,
    }


def _normalize_name(value: str) -> str:
    if not isinstance(value, str):
        raise InputValidationError("name", "must be text")
    normalized = " ".join(value.split())
    if len(normalized) < 2:
        raise InputValidationError("name", "must contain at least 2 characters")
    if len(normalized) > 100:
        raise InputValidationError("name", "must contain at most 100 characters")
    return normalized


def _candidate_from_result(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None

    person = item.get("person")
    if isinstance(person, dict):
        item = person

    name = item.get("name")
    wca_id = item.get("wca_id")
    if not isinstance(name, str) or not name.strip() or not isinstance(wca_id, str):
        return None
    try:
        normalized_wca_id = validate_wca_id(wca_id)
    except InputValidationError:
        return None

    country = item.get("country")
    country_name = country.get("name") if isinstance(country, dict) else None
    candidate = {
        "name": name.strip(),
        "wca_id": normalized_wca_id,
        "profile_url": (
            f"https://www.worldcubeassociation.org/persons/{normalized_wca_id}"
        ),
    }
    if isinstance(country_name, str) and country_name.strip():
        candidate["country"] = country_name.strip()
    return candidate
