"""Static configuration for the WCA competition finder.

Keeping configuration isolated from logic makes it trivial to point the tool at
a different region, person, or API host without touching the rest of the code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

WCA_API_BASE = "https://www.worldcubeassociation.org/api/v0"

DEFAULT_TIMEOUT = 20  # seconds
DEFAULT_USER_AGENT = "wca-comps-finder/1.0 (+https://github.com)"


@dataclass(frozen=True)
class Region:
    """A geographic region we want to search competitions in.

    ``country_iso2`` narrows the (paginated) WCA query server-side, while
    ``state_keywords`` are matched against a competition's ``city`` string
    (e.g. ``"Seattle, Washington"``) client-side, because the WCA API has no
    state/province filter.
    """

    name: str
    country_iso2: str
    state_keywords: tuple[str, ...]

    def matches_city(self, city: str) -> bool:
        city_lower = city.lower()
        return any(kw.lower() in city_lower for kw in self.state_keywords)


# The three regions the user cares about.
REGIONS: tuple[Region, ...] = (
    Region(name="Washington", country_iso2="US", state_keywords=("Washington",)),
    Region(name="Oregon", country_iso2="US", state_keywords=("Oregon",)),
    Region(
        name="British Columbia",
        country_iso2="CA",
        state_keywords=("British Columbia",),
    ),
)

# The competitor we want to check registrations for.
DEFAULT_WCA_ID = "2023VONT01"
DEFAULT_PERSON_NAME = "Saharsh Sai Vontela"

# Email delivery via Resend (https://resend.com).
RESEND_API_URL = "https://api.resend.com/emails"
# Without a verified custom domain, Resend only accepts its shared sender
# address and only delivers to the account owner's own email.
RESEND_DEFAULT_FROM = "WCA Comps <onboarding@resend.dev>"
# Environment variable that holds the Resend API key.
RESEND_API_KEY_ENV = "RESEND_API_KEY"
# TEMPORARY: hardcoded fallback key for quick local testing. Prefer the
# RESEND_API_KEY environment variable, which takes precedence over this value.
# SECURITY: do not commit a real key to a shared/public repo; rotate it before
# the project is pushed to GitHub.
RESEND_API_KEY_FALLBACK = "re_6R1snG3X_GpB1t64BAKtMjiGABaBYgcS6"
