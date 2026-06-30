"""Runtime input validation for CLI, MCP, and future API entrypoints."""

from __future__ import annotations

import re
from datetime import date
from typing import Iterable

from .config import (
    CANADA_REGIONS,
    DEFAULT_REGIONS,
    REGIONS,
    US_REGIONS,
    Region,
    normalize_region_name,
)
from .errors import InputValidationError

WCA_ID_RE = re.compile(r"^\d{4}[A-Z]{4}\d{2}$")
REGION_GROUPS = {
    "us": US_REGIONS,
    "usa": US_REGIONS,
    "unitedstates": US_REGIONS,
    "allusstates": US_REGIONS,
    "canada": CANADA_REGIONS,
    "allcanadianprovinces": CANADA_REGIONS,
    "allcanadianprovincesandterritories": CANADA_REGIONS,
}


def validate_wca_id(value: str) -> str:
    """Validate and normalize a WCA ID."""
    wca_id = value.strip().upper() if isinstance(value, str) else ""
    if not WCA_ID_RE.fullmatch(wca_id):
        raise InputValidationError(
            "wca_id",
            "must match the WCA ID format, for example 2023VONT01",
        )
    return wca_id


def parse_from_date(value: str | None, today: date | None = None) -> date:
    """Parse an optional YYYY-MM-DD date, defaulting at call time."""
    if value is None:
        return today or date.today()
    if not isinstance(value, str) or not value.strip():
        raise InputValidationError("from_date", "must be a YYYY-MM-DD date")
    raw = value.strip()
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise InputValidationError(
            "from_date", "must be a valid YYYY-MM-DD date"
        ) from exc
    if parsed.isoformat() != raw:
        raise InputValidationError("from_date", "must be in YYYY-MM-DD format")
    return parsed


def select_regions(
    names: Iterable[str] | None,
    supported_regions: tuple[Region, ...] = REGIONS,
) -> tuple[Region, ...]:
    """Return supported regions selected by name.

    Region names and postal abbreviations are matched case-insensitively.
    """
    if names is None:
        supported_names = {region.name for region in supported_regions}
        defaults = tuple(
            region for region in DEFAULT_REGIONS if region.name in supported_names
        )
        return defaults or supported_regions

    region_by_name = {
        normalize_region_name(alias): region
        for region in supported_regions
        for alias in (region.name, *region.state_keywords)
    }
    selected: list[Region] = []
    seen: set[str] = set()

    for index, name in enumerate(names):
        if not isinstance(name, str) or not name.strip():
            raise InputValidationError(
                "regions", f"entry {index + 1} must be a supported region name"
            )
        key = normalize_region_name(name.strip())
        group = REGION_GROUPS.get(key)
        if group is not None:
            for region in group:
                region_key = normalize_region_name(region.name)
                if region_key not in seen:
                    selected.append(region)
                    seen.add(region_key)
            continue

        region = region_by_name.get(key)
        if region is None:
            raise InputValidationError(
                "regions",
                f"unsupported region {name!r}; use a U.S. state, District of "
                "Columbia, or Canadian province/territory name or postal abbreviation",
            )
        region_key = normalize_region_name(region.name)
        if region_key not in seen:
            selected.append(region)
            seen.add(region_key)

    if not selected:
        raise InputValidationError("regions", "must include at least one region")
    return tuple(selected)
