from __future__ import annotations

import threading
import time
import unittest
from datetime import date, datetime, timezone

from wca_comps.cli import parse_args
from wca_comps.config import CANADA_REGIONS, DEFAULT_REGIONS, REGIONS, US_REGIONS
from wca_comps.errors import InputValidationError
from wca_comps.models import Competition, RegistrationStatus
from wca_comps.networking import WCAClient
from wca_comps.report import build_assessments
from wca_comps.serializers import serialize_search_result
from wca_comps.validation import parse_from_date, select_regions, validate_wca_id


class ValidationTests(unittest.TestCase):
    def test_wca_id_is_normalized_and_validated(self) -> None:
        self.assertEqual(validate_wca_id(" 2023vont01 "), "2023VONT01")

        with self.assertRaises(InputValidationError):
            validate_wca_id("2023BAD1")

    def test_from_date_defaults_at_call_time(self) -> None:
        self.assertEqual(
            parse_from_date(None, today=date(2026, 8, 1)),
            date(2026, 8, 1),
        )
        self.assertEqual(parse_from_date("2026-08-02"), date(2026, 8, 2))

        with self.assertRaises(InputValidationError):
            parse_from_date("08/02/2026")

    def test_regions_are_selected_and_deduped(self) -> None:
        selected = select_regions(
            ["washington", "WA", "OR", "Washington", "bc"]
        )
        self.assertEqual(
            [region.name for region in selected],
            ["Washington", "Oregon", "British Columbia"],
        )

        with self.assertRaises(InputValidationError):
            select_regions(["Mexico City"])

    def test_default_regions_remain_pacific_northwest(self) -> None:
        self.assertEqual(
            [region.name for region in select_regions(None)],
            ["Washington", "Oregon", "British Columbia"],
        )

    def test_all_us_and_canadian_subdivisions_are_supported(self) -> None:
        self.assertEqual(len(US_REGIONS), 51)
        self.assertEqual(len(CANADA_REGIONS), 13)
        self.assertEqual(len(REGIONS), 64)
        self.assertIn("California", {region.name for region in US_REGIONS})
        self.assertIn("Ontario", {region.name for region in CANADA_REGIONS})
        self.assertIn("Nunavut", {region.name for region in CANADA_REGIONS})

        selected = select_regions(["United States", "Canada"])
        self.assertEqual(len(selected), 64)

    def test_city_matching_uses_exact_subdivision_component(self) -> None:
        regions = {region.name: region for region in REGIONS}

        self.assertTrue(regions["Virginia"].matches_city("Richmond, Virginia"))
        self.assertFalse(
            regions["Virginia"].matches_city("Charleston, West Virginia")
        )
        self.assertFalse(
            regions["Washington"].matches_city("Washington, D.C.")
        )
        self.assertTrue(
            regions["District of Columbia"].matches_city("Washington, D.C.")
        )
        self.assertTrue(regions["Quebec"].matches_city("Montréal, Québec"))

    def test_cli_accepts_repeated_regions(self) -> None:
        args = parse_args(["--region", "California", "--region", "ON"])
        self.assertEqual(args.regions, ["California", "ON"])


class AssessmentTests(unittest.TestCase):
    def test_registration_lookups_run_concurrently(self) -> None:
        service = FakeCompetitionService(comp_count=4)
        registrations = SlowRegistrationService()

        assessments = build_assessments(
            service,
            registrations,
            DEFAULT_REGIONS[:1],
            "2023VONT01",
            date(2026, 1, 1),
            max_registration_workers=4,
        )

        self.assertEqual(len(assessments), 4)
        self.assertGreater(registrations.max_active, 1)

    def test_serializer_groups_deleted_registration_as_available(self) -> None:
        service = FakeCompetitionService(comp_count=1)
        registrations = DeletedRegistrationService()

        assessments = build_assessments(
            service,
            registrations,
            DEFAULT_REGIONS[:1],
            "2023VONT01",
            date(2026, 1, 1),
            now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        payload = serialize_search_result(
            assessments=assessments,
            wca_id="2023VONT01",
            person_name="Saharsh Sai Vontela",
            regions=("Washington",),
            from_date=date(2026, 1, 1),
        )

        self.assertEqual(payload["summary"]["registered"], 0)
        self.assertEqual(payload["summary"]["available"], 1)
        self.assertEqual(
            payload["groups"]["available"][0]["registration"]["status"], "deleted"
        )


class CacheTests(unittest.TestCase):
    def test_wca_client_reuses_short_lived_get_json_cache(self) -> None:
        session = FakeSession()
        client = WCAClient(session=session, cache_ttl_seconds=60)

        first = client.get_json("competitions", {"country_iso2": "US"})
        second = client.get_json("competitions", {"country_iso2": "US"})

        self.assertEqual(first, second)
        self.assertEqual(session.calls, 1)


class FakeCompetitionService:
    def __init__(self, comp_count: int) -> None:
        self.comp_count = comp_count

    def upcoming_in_regions(self, regions, start_from):
        return [
            (
                regions[0],
                Competition(
                    id=f"FakeComp{i}",
                    name=f"Fake Comp {i}",
                    city="Seattle, Washington",
                    country_iso2="US",
                    start_date=f"2026-01-{i + 1:02d}",
                    end_date=f"2026-01-{i + 1:02d}",
                    venue="Fake Venue",
                    url=f"https://example.test/FakeComp{i}",
                    event_ids=["333"],
                    competitor_limit=100,
                    registration_open=datetime(2025, 12, 1, tzinfo=timezone.utc),
                    registration_close=datetime(2026, 1, 15, tzinfo=timezone.utc),
                ),
            )
            for i in range(self.comp_count)
        ]


class SlowRegistrationService:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def check(self, competition_id: str, wca_id: str) -> RegistrationStatus:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.05)
        with self.lock:
            self.active -= 1
        return RegistrationStatus(is_registered=False, competitor_count=10)


class DeletedRegistrationService:
    def check(self, competition_id: str, wca_id: str) -> RegistrationStatus:
        return RegistrationStatus(
            is_registered=True,
            status="deleted",
            event_ids=["333"],
            competitor_count=10,
        )


class FakeSession:
    def __init__(self) -> None:
        self.headers = {}
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return FakeResponse({"url": url, "params": params})


class FakeResponse:
    status_code = 200

    def __init__(self, payload) -> None:
        self.payload = payload

    def json(self):
        return self.payload


if __name__ == "__main__":
    unittest.main()
