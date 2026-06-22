"""OAuth2 client-credentials token provider with caching and thread safety."""
from __future__ import annotations

import logging
import threading
import time

import requests

logger = logging.getLogger(__name__)

_REFRESH_SKEW_SECONDS = 60


class OAuthTokenProvider:
    """
    Fetches and caches an OAuth2 client-credentials token for the Benchling API.

    Thread-safe: concurrent callers block on the first fetch and share the result.
    Proactively refreshes REFRESH_SKEW_SECONDS before the token actually expires
    to avoid mid-request expiry.
    """

    def __init__(
        self,
        domain: str,
        client_id: str,
        client_secret: str,
        *,
        timeout: int = 20,
    ) -> None:
        self._domain = domain
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    def get_token(self) -> str:
        with self._lock:
            if self._token and time.monotonic() < self._expires_at - _REFRESH_SKEW_SECONDS:
                return self._token
            self._fetch()
            return self._token  # type: ignore[return-value]

    def invalidate(self) -> None:
        """Force a fresh fetch on the next call (e.g. after a 401 response)."""
        with self._lock:
            self._token = None
            self._expires_at = 0.0

    def _fetch(self) -> None:
        url = f"https://{self._domain}/api/v2/token"
        logger.debug("Fetching OAuth token from %s", url)
        try:
            resp = requests.post(
                url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to fetch Benchling OAuth token: {exc}") from exc

        payload = resp.json()
        token = payload.get("access_token")
        if not token:
            raise RuntimeError("Benchling token response missing access_token")

        self._token = token
        self._expires_at = time.monotonic() + int(payload.get("expires_in", 3600))
        logger.debug("OAuth token fetched, expires in %ds", payload.get("expires_in", 3600))
