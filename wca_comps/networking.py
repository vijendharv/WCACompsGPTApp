"""Networking module: a thin, reusable HTTP client for the WCA API.

This is the single place that knows how to talk to the network. Everything
else in the package depends on this abstraction rather than on ``requests``
directly, which keeps the rest of the code easy to test and to repoint at a
different transport if needed.
"""

from __future__ import annotations

import time
from threading import Lock, local
from typing import Any
from urllib.parse import urlencode, urljoin

import requests

from .config import DEFAULT_TIMEOUT, DEFAULT_USER_AGENT, WCA_API_BASE

# On machines behind a TLS-intercepting proxy (common in corporate networks)
# the WCA certificate is re-signed by a CA that lives in the OS trust store but
# not in certifi's bundle. ``truststore`` makes Python's ``ssl`` use the OS
# trust store, which fixes verification transparently. It is optional: if it is
# not installed we silently fall back to the default certifi behaviour.
try:  # pragma: no cover - environment dependent
    import truststore

    truststore.inject_into_ssl()
except Exception:  # pragma: no cover - truststore missing or unsupported
    pass


class WCAApiError(RuntimeError):
    """Raised when the WCA API returns an error or is unreachable."""


class WCAClient:
    """Minimal HTTP client around the WCA REST API.

    Responsibilities are deliberately narrow: build URLs, perform GET requests
    with retries/back-off, and hand back decoded JSON. It has no knowledge of
    competitions or registrations.
    """

    def __init__(
        self,
        base_url: str = WCA_API_BASE,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        backoff_seconds: float = 1.5,
        cache_ttl_seconds: float = 60,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self._headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}
        self._provided_session = session
        self._thread_local = local()
        if session is not None:
            session.headers.update(self._headers)
        self.session = session or self._new_session()
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_lock = Lock()

    def get_json(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Any:
        """GET ``path`` (relative to the base URL) and return decoded JSON.

        Retries on transient network/server errors with linear back-off.
        Raises :class:`WCAApiError` on persistent failure.
        """
        url = urljoin(self.base_url, path.lstrip("/"))
        cache_key = self._cache_key(url, params)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._get_session().get(
                    url, params=params, timeout=self.timeout
                )
            except requests.RequestException as exc:  # network-level failure
                last_error = exc
            else:
                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except ValueError as exc:
                        raise WCAApiError(
                            f"Invalid JSON from {url}: {exc}"
                        ) from exc
                    self._set_cached(cache_key, payload)
                    return payload
                # 429/5xx are worth retrying; 4xx (other) are not.
                if response.status_code not in (429, 500, 502, 503, 504):
                    raise WCAApiError(
                        f"GET {url} failed with HTTP {response.status_code}"
                    )
                last_error = WCAApiError(
                    f"GET {url} returned HTTP {response.status_code}"
                )

            if attempt < self.max_retries:
                time.sleep(self.backoff_seconds * attempt)

        raise WCAApiError(
            f"GET {url} failed after {self.max_retries} attempts: {last_error}"
        )

    def _cache_key(self, url: str, params: dict[str, Any] | None) -> str:
        if not params:
            return url
        pairs = sorted((str(key), str(value)) for key, value in params.items())
        return f"{url}?{urlencode(pairs)}"

    def _get_cached(self, key: str) -> Any | None:
        if self.cache_ttl_seconds <= 0:
            return None
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            expires_at, payload = entry
            if expires_at <= time.monotonic():
                del self._cache[key]
                return None
            return payload

    def _set_cached(self, key: str, payload: Any) -> None:
        if self.cache_ttl_seconds <= 0:
            return
        with self._cache_lock:
            self._cache[key] = (time.monotonic() + self.cache_ttl_seconds, payload)

    def _new_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(self._headers)
        return session

    def _get_session(self) -> requests.Session:
        if self._provided_session is not None:
            return self._provided_session
        thread_session = getattr(self._thread_local, "session", None)
        if thread_session is None:
            thread_session = self._new_session()
            self._thread_local.session = thread_session
        return thread_session

    def get_paginated(
        self, path: str, params: dict[str, Any] | None = None, per_page: int = 100
    ) -> list[Any]:
        """Fetch all pages of a list endpoint and return a flat list.

        The WCA API paginates list endpoints and signals more data simply by
        returning a full page, so we keep requesting until a short page arrives.
        """
        params = dict(params or {})
        params["per_page"] = per_page
        page = 1
        items: list[Any] = []

        while True:
            params["page"] = page
            batch = self.get_json(path, params=params)
            if not isinstance(batch, list):
                raise WCAApiError(
                    f"Expected a list from {path}, got {type(batch).__name__}"
                )
            items.extend(batch)
            if len(batch) < per_page:
                break
            page += 1

        return items
