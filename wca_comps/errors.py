"""Typed application errors for user-facing and MCP-facing boundaries."""

from __future__ import annotations


class WCACompsError(RuntimeError):
    """Base class for errors raised by the application core."""

    code = "wca_comps_error"


class InputValidationError(WCACompsError):
    """Raised when runtime inputs fail validation."""

    code = "invalid_input"

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"{field}: {message}")


class NoResultsError(WCACompsError):
    """Raised when a valid search has no matching competitions."""

    code = "no_results"


class UpstreamServiceError(WCACompsError):
    """Raised when an upstream service fails in a user-facing workflow."""

    code = "upstream_service_error"
