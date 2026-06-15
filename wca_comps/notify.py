"""Email delivery via the Resend HTTP API.

This is the single place that knows how to send mail. Like ``networking``, it
depends on ``requests`` directly and nothing else in the package, so the rest of
the code can stay transport-agnostic.
"""

from __future__ import annotations

import requests

from .config import DEFAULT_TIMEOUT, RESEND_API_URL, RESEND_DEFAULT_FROM

# Mirror networking.py: behind a TLS-intercepting corporate proxy the Resend
# certificate may be re-signed by a CA in the OS trust store but not in
# certifi's bundle. ``truststore`` makes Python's ``ssl`` use the OS trust
# store. It is optional and we fall back silently if it is unavailable.
try:  # pragma: no cover - environment dependent
    import truststore

    truststore.inject_into_ssl()
except Exception:  # pragma: no cover - truststore missing or unsupported
    pass


class EmailError(RuntimeError):
    """Raised when the email fails to send."""


def send_email(
    subject: str,
    body: str,
    to: str,
    api_key: str,
    sender: str = RESEND_DEFAULT_FROM,
    timeout: int = DEFAULT_TIMEOUT,
    html: str | None = None,
) -> str:
    """Send an email through Resend and return the message id.

    ``body`` is the plain-text version; pass ``html`` to also include a rich
    HTML version (email clients that support it will prefer it, the rest fall
    back to the text). Raises :class:`EmailError` if the API key is missing or
    Resend responds with a non-2xx status (the response body is included to aid
    debugging).
    """
    if not api_key:
        raise EmailError("No Resend API key provided.")

    payload = {
        "from": sender,
        "to": [to],
        "subject": subject,
        "text": body,
    }
    if html:
        payload["html"] = html

    try:
        response = requests.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:  # network-level failure
        raise EmailError(f"Could not reach Resend: {exc}") from exc

    if not response.ok:
        raise EmailError(
            f"Resend returned HTTP {response.status_code}: {response.text}"
        )

    try:
        return response.json().get("id", "")
    except ValueError:
        return ""
