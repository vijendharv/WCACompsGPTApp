from __future__ import annotations

import unittest

from wca_comps.errors import InputValidationError, UpstreamServiceError
from wca_comps.people import MAX_PERSON_RESULTS, search_people


class FakeClient:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_json(self, path: str, params: dict[str, object]) -> object:
        self.calls.append((path, params))
        return self.payload


class PeopleSearchTests(unittest.TestCase):
    def test_returns_public_candidates_and_requires_selection(self) -> None:
        client = FakeClient(
            [
                {
                    "person": {
                        "name": "  Jane Cuber  ",
                        "wca_id": "2020CUBE01",
                        "country": {"name": "United States"},
                    }
                }
            ]
        )

        result = search_people("  Jane   Cuber ", client=client)

        self.assertEqual(
            client.calls,
            [("persons", {"q": "Jane Cuber", "per_page": 21, "page": 1})],
        )
        self.assertEqual(result["query"], "Jane Cuber")
        self.assertEqual(result["count"], 1)
        self.assertTrue(result["selection_required"])
        self.assertFalse(result["refinement_required"])
        self.assertIsNone(result["message"])
        self.assertEqual(
            result["candidates"][0],
            {
                "name": "Jane Cuber",
                "wca_id": "2020CUBE01",
                "country": "United States",
                "profile_url": (
                    "https://www.worldcubeassociation.org/persons/2020CUBE01"
                ),
            },
        )

    def test_more_than_twenty_matches_requires_a_refined_search(self) -> None:
        results = [
            {"name": "No ID", "wca_id": None},
            {"name": "Malformed", "wca_id": "not-an-id"},
        ]
        results.extend(
            {
                "name": f"Cuber {index}",
                "wca_id": f"2020TEST{index:02d}",
            }
            for index in range(1, 22)
        )
        results.append({"name": "Duplicate", "wca_id": "2020TEST01"})

        result = search_people("Cuber", client=FakeClient(results))

        self.assertEqual(result["count"], 0)
        self.assertFalse(result["selection_required"])
        self.assertTrue(result["refinement_required"])
        self.assertIn("more complete name", result["message"])
        self.assertEqual(result["candidates"], [])

    def test_exactly_twenty_matches_are_returned_for_selection(self) -> None:
        results = [
            {
                "person": {
                    "name": f"Cuber {index}",
                    "wca_id": f"2020TEST{index:02d}",
                }
            }
            for index in range(1, MAX_PERSON_RESULTS + 1)
        ]

        result = search_people("Cuber", client=FakeClient(results))

        self.assertEqual(result["count"], MAX_PERSON_RESULTS)
        self.assertTrue(result["selection_required"])
        self.assertFalse(result["refinement_required"])
        self.assertEqual(len(result["candidates"]), MAX_PERSON_RESULTS)

    def test_empty_matches_do_not_require_selection(self) -> None:
        result = search_people("Nobody", client=FakeClient([]))

        self.assertEqual(result["candidates"], [])
        self.assertFalse(result["selection_required"])
        self.assertFalse(result["refinement_required"])

    def test_rejects_names_that_are_too_short(self) -> None:
        with self.assertRaises(InputValidationError):
            search_people(" A ", client=FakeClient([]))

    def test_rejects_unexpected_upstream_payload(self) -> None:
        with self.assertRaises(UpstreamServiceError):
            search_people("Jane Cuber", client=FakeClient({}))


if __name__ == "__main__":
    unittest.main()
