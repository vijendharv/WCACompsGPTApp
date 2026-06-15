"""Registration lookup using the public WCIF endpoint.

The WCA exposes a public "WCIF" (WCA Competition Interchange Format) document
per competition at ``/competitions/{id}/wcif/public``. It includes the list of
registered ``persons`` and each person's registration status, which is the
public way to tell whether someone signed up for an upcoming competition.
"""

from __future__ import annotations

from .models import RegistrationStatus
from .networking import WCAClient, WCAApiError


class RegistrationService:
    """Checks whether a given WCA ID is registered for a competition."""

    def __init__(self, client: WCAClient) -> None:
        self._client = client

    def check(self, competition_id: str, wca_id: str) -> RegistrationStatus:
        """Return the registration status of ``wca_id`` for ``competition_id``.

        If the WCIF document cannot be fetched the person is reported as not
        registered (the competition is still listed, just without reg detail).
        """
        try:
            wcif = self._client.get_json(
                f"competitions/{competition_id}/wcif/public"
            )
        except WCAApiError:
            return RegistrationStatus(is_registered=False)

        persons = wcif.get("persons", []) if isinstance(wcif, dict) else []
        competitor_count = sum(
            1
            for p in persons
            if (p.get("registration") or {}).get("status") == "accepted"
        )

        for person in persons:
            if person.get("wcaId") == wca_id:
                reg = person.get("registration") or {}
                return RegistrationStatus(
                    is_registered=bool(reg),
                    status=reg.get("status"),
                    event_ids=list(reg.get("eventIds", [])),
                    competitor_count=competitor_count,
                )

        return RegistrationStatus(
            is_registered=False, competitor_count=competitor_count
        )
