"""Static configuration for the WCA competition finder.

Keeping configuration isolated from logic makes it trivial to point the tool at
a different region, person, or API host without touching the rest of the code.
"""

from __future__ import annotations

from dataclasses import dataclass

WCA_API_BASE = "https://www.worldcubeassociation.org/api/v0"

DEFAULT_TIMEOUT = 20  # seconds
DEFAULT_USER_AGENT = "wca-comps-finder/1.0 (+https://github.com)"


@dataclass(frozen=True)
class Region:
    """A geographic region we want to search competitions in.

    ``country_iso2`` narrows the (paginated) WCA query server-side, while
    ``state_keywords`` provide postal and spelling aliases for the final
    subdivision component of a competition's ``city`` string (for example,
    ``"Seattle, Washington"``). Matching happens client-side because the WCA
    API has no state/province filter.
    """

    name: str
    country_iso2: str
    state_keywords: tuple[str, ...]

    def matches_city(self, city: str) -> bool:
        subdivision = city.rsplit(",", 1)[-1]
        normalized = normalize_region_name(subdivision)
        return any(
            normalize_region_name(keyword) == normalized
            for keyword in (self.name, *self.state_keywords)
        )


def normalize_region_name(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _build_regions(
    country_iso2: str,
    definitions: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[Region, ...]:
    return tuple(
        Region(name=name, country_iso2=country_iso2, state_keywords=aliases)
        for name, aliases in definitions
    )


US_REGIONS = _build_regions(
    "US",
    (
        ("Alabama", ("AL",)),
        ("Alaska", ("AK",)),
        ("Arizona", ("AZ",)),
        ("Arkansas", ("AR",)),
        ("California", ("CA",)),
        ("Colorado", ("CO",)),
        ("Connecticut", ("CT",)),
        ("Delaware", ("DE",)),
        ("District of Columbia", ("DC", "D.C.")),
        ("Florida", ("FL",)),
        ("Georgia", ("GA",)),
        ("Hawaii", ("HI",)),
        ("Idaho", ("ID",)),
        ("Illinois", ("IL",)),
        ("Indiana", ("IN",)),
        ("Iowa", ("IA",)),
        ("Kansas", ("KS",)),
        ("Kentucky", ("KY",)),
        ("Louisiana", ("LA",)),
        ("Maine", ("ME",)),
        ("Maryland", ("MD",)),
        ("Massachusetts", ("MA",)),
        ("Michigan", ("MI",)),
        ("Minnesota", ("MN",)),
        ("Mississippi", ("MS",)),
        ("Missouri", ("MO",)),
        ("Montana", ("MT",)),
        ("Nebraska", ("NE",)),
        ("Nevada", ("NV",)),
        ("New Hampshire", ("NH",)),
        ("New Jersey", ("NJ",)),
        ("New Mexico", ("NM",)),
        ("New York", ("NY",)),
        ("North Carolina", ("NC",)),
        ("North Dakota", ("ND",)),
        ("Ohio", ("OH",)),
        ("Oklahoma", ("OK",)),
        ("Oregon", ("OR",)),
        ("Pennsylvania", ("PA",)),
        ("Rhode Island", ("RI",)),
        ("South Carolina", ("SC",)),
        ("South Dakota", ("SD",)),
        ("Tennessee", ("TN",)),
        ("Texas", ("TX",)),
        ("Utah", ("UT",)),
        ("Vermont", ("VT",)),
        ("Virginia", ("VA",)),
        ("Washington", ("WA",)),
        ("West Virginia", ("WV",)),
        ("Wisconsin", ("WI",)),
        ("Wyoming", ("WY",)),
    ),
)

CANADA_REGIONS = _build_regions(
    "CA",
    (
        ("Alberta", ("AB",)),
        ("British Columbia", ("BC",)),
        ("Manitoba", ("MB",)),
        ("New Brunswick", ("NB",)),
        ("Newfoundland and Labrador", ("NL", "Newfoundland & Labrador")),
        ("Nova Scotia", ("NS",)),
        ("Ontario", ("ON",)),
        ("Prince Edward Island", ("PE", "PEI")),
        ("Quebec", ("QC", "Québec")),
        ("Saskatchewan", ("SK",)),
        ("Northwest Territories", ("NT", "NWT")),
        ("Nunavut", ("NU",)),
        ("Yukon", ("YT", "Yukon Territory")),
    ),
)

REGIONS: tuple[Region, ...] = (*US_REGIONS, *CANADA_REGIONS)

DEFAULT_REGION_NAMES = ("Washington", "Oregon", "British Columbia")
DEFAULT_REGIONS = tuple(
    next(region for region in REGIONS if region.name == name)
    for name in DEFAULT_REGION_NAMES
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
RESEND_API_KEY_FALLBACK = ""
