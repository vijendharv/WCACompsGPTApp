"""Data models describing the subset of WCA API entities we care about.

These are plain dataclasses with ``from_api`` constructors so the rest of the
code works with typed objects instead of raw dicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp (the WCA API uses a trailing ``Z``)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass
class Competition:
    """An upcoming WCA competition."""

    id: str
    name: str
    city: str
    country_iso2: str
    start_date: str
    end_date: str
    venue: str
    url: str
    event_ids: list[str]
    competitor_limit: int | None
    registration_open: datetime | None
    registration_close: datetime | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Competition":
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            city=data.get("city", ""),
            country_iso2=data.get("country_iso2", ""),
            start_date=data.get("start_date", ""),
            end_date=data.get("end_date", ""),
            venue=data.get("venue", ""),
            url=data.get("url", ""),
            event_ids=list(data.get("event_ids", [])),
            competitor_limit=data.get("competitor_limit"),
            registration_open=_parse_dt(data.get("registration_open")),
            registration_close=_parse_dt(data.get("registration_close")),
        )

    def registration_state(self, now: datetime | None = None) -> str:
        """Return one of ``not_open_yet`` / ``open`` / ``closed``."""
        now = now or datetime.now(timezone.utc)
        if self.registration_open and now < self.registration_open:
            return "not_open_yet"
        if self.registration_close and now > self.registration_close:
            return "closed"
        return "open"


@dataclass
class RegistrationStatus:
    """The result of checking whether a person registered for a competition."""

    is_registered: bool
    status: str | None = None  # "accepted", "pending", "deleted", ...
    event_ids: list[str] | None = None
    competitor_count: int | None = None


@dataclass
class CompetitionAssessment:
    """A competition paired with the target person's registration status and
    a computed eligibility verdict."""

    competition: Competition
    region_name: str
    registration: RegistrationStatus
    registration_state: str
    can_register: bool
    reason: str
