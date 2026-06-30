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
    """Return up to 20 WCA-ID-bearing people matching ``name``."""
    query = _normalize_name(name)
    wca_client = client or WCAClient()

    try:
        payload = wca_client.get_json("search/users", params={"q": query})
    except WCAApiError as exc:
        raise UpstreamServiceError(f"WCA person search failed: {exc}") from exc

    raw_results = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(raw_results, list):
        raise UpstreamServiceError("WCA person search returned an unexpected response")

    candidates: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for item in raw_results:
        candidate = _candidate_from_result(item)
        if candidate is None or candidate["wca_id"] in seen_ids:
            continue
        seen_ids.add(candidate["wca_id"])
        candidates.append(candidate)
        if len(candidates) == MAX_PERSON_RESULTS:
            break

    return {
        "query": query,
        "count": len(candidates),
        "selection_required": bool(candidates),
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
