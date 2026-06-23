"""Stable JSON-ready serializers for structured app results."""

from __future__ import annotations

from datetime import date
from typing import Any

from .models import CompetitionAssessment


def serialize_assessment(assessment: CompetitionAssessment) -> dict[str, Any]:
    """Convert a domain assessment to a stable structured result."""
    comp = assessment.competition
    reg = assessment.registration
    return {
        "competition": {
            "id": comp.id,
            "name": comp.name,
            "start_date": comp.start_date,
            "end_date": comp.end_date,
            "location": comp.city,
            "venue": comp.venue,
            "url": comp.url,
            "region": assessment.region_name,
            "event_ids": comp.event_ids,
            "registration_open": _datetime_to_iso(comp.registration_open),
            "registration_close": _datetime_to_iso(comp.registration_close),
            "competitor_limit": comp.competitor_limit,
        },
        "registration": {
            "is_registered": reg.is_registered,
            "status": reg.status,
            "event_ids": reg.event_ids or [],
            "competitor_count": reg.competitor_count,
        },
        "eligibility": {
            "registration_state": assessment.registration_state,
            "can_register": assessment.can_register,
            "reason": assessment.reason,
        },
    }


def serialize_search_result(
    *,
    assessments: list[CompetitionAssessment],
    wca_id: str,
    person_name: str | None,
    regions: tuple[str, ...],
    from_date: date,
) -> dict[str, Any]:
    """Build the stable result shape expected by MCP and widgets."""
    registered = [
        item
        for item in assessments
        if item.registration.is_registered and item.registration.status != "deleted"
    ]
    available = [item for item in assessments if item not in registered and item.can_register]
    unavailable = [
        item for item in assessments if item not in registered and not item.can_register
    ]

    return {
        "query": {
            "wca_id": wca_id,
            "person_name": person_name,
            "regions": list(regions),
            "from_date": from_date.isoformat(),
        },
        "summary": {
            "total": len(assessments),
            "registered": len(registered),
            "available": len(available),
            "unavailable": len(unavailable),
        },
        "groups": {
            "registered": [serialize_assessment(item) for item in registered],
            "available": [serialize_assessment(item) for item in available],
            "unavailable": [serialize_assessment(item) for item in unavailable],
        },
        "competitions": [serialize_assessment(item) for item in assessments],
    }


def _datetime_to_iso(value: object) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None
