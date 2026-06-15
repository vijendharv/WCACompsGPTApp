"""Competition discovery: fetch upcoming competitions and filter by region."""

from __future__ import annotations

from datetime import date

from .config import Region
from .models import Competition
from .networking import WCAClient


class CompetitionService:
    """Fetches upcoming competitions from the WCA API and filters by region."""

    def __init__(self, client: WCAClient) -> None:
        self._client = client

    def upcoming_in_country(
        self, country_iso2: str, start_from: date
    ) -> list[Competition]:
        """Return all competitions in a country starting on/after ``start_from``."""
        raw = self._client.get_paginated(
            "competitions",
            params={
                "country_iso2": country_iso2,
                "start": start_from.isoformat(),
                "sort": "start_date",
            },
        )
        return [Competition.from_api(item) for item in raw]

    def upcoming_in_region(
        self, region: Region, start_from: date
    ) -> list[Competition]:
        """Return competitions in a region (country + state/province match)."""
        comps = self.upcoming_in_country(region.country_iso2, start_from)
        return [c for c in comps if region.matches_city(c.city)]

    def upcoming_in_regions(
        self, regions: tuple[Region, ...], start_from: date
    ) -> list[tuple[Region, Competition]]:
        """Return (region, competition) pairs across several regions.

        Results are de-duplicated per competition id (a comp can only belong to
        one region in practice) and country queries are cached so we hit the API
        once per distinct country rather than once per region.
        """
        country_cache: dict[str, list[Competition]] = {}
        pairs: list[tuple[Region, Competition]] = []
        seen: set[str] = set()

        for region in regions:
            if region.country_iso2 not in country_cache:
                country_cache[region.country_iso2] = self.upcoming_in_country(
                    region.country_iso2, start_from
                )
            for comp in country_cache[region.country_iso2]:
                if comp.id in seen:
                    continue
                if region.matches_city(comp.city):
                    pairs.append((region, comp))
                    seen.add(comp.id)

        pairs.sort(key=lambda pair: pair[1].start_date)
        return pairs
