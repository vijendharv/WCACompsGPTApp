"""WCA upcoming-competition finder & registration checker.

The package is split into focused modules:

- ``config``        : Static configuration (API base URL, regions, defaults).
- ``networking``    : Thin HTTP layer around the WCA REST API.
- ``models``        : Plain data classes describing API entities.
- ``competitions``  : Fetch upcoming competitions and filter them by region.
- ``registrations`` : Look up whether a given person registered for a comp.
- ``report``        : Combine the above into a human-readable report.
- ``cli``           : Command-line entrypoint.
"""

__version__ = "1.0.0"
