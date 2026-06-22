"""Core HTTP client: auth, retry, rate limiting, pagination, logging."""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator
from typing import Any

import requests

from .auth import OAuthTokenProvider
from .errors import ApiError

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class BenchlingClient:
    """
    Thin HTTP client for the Benchling REST API.

    Responsibilities:
      - OAuth2 Bearer token management (via OAuthTokenProvider)
      - Retry with exponential backoff on transient errors
      - Optional inter-request rate limiting
      - nextToken pagination (iterator and eager list)
      - Structured ApiError on failures
      - Structured debug/warning logging per request

    Not responsible for business logic, entity-specific methods, or idempotency.
    Those belong in helpers.py or the calling app.

    Usage::

        provider = OAuthTokenProvider(domain, client_id, client_secret)
        client = BenchlingClient(domain, provider, rate_limit_delay=0.1)

        # Or using the convenience constructor:
        client = BenchlingClient.from_credentials(domain, client_id, client_secret)
    """

    def __init__(
        self,
        domain: str,
        token_provider: OAuthTokenProvider,
        *,
        max_retries: int = 4,
        retry_backoff: float = 1.0,
        request_timeout: int = 20,
        rate_limit_delay: float = 0.0,
    ) -> None:
        self._domain = domain
        self._token_provider = token_provider
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._request_timeout = request_timeout
        self._rate_limit_delay = rate_limit_delay
        self._last_request_at: float = 0.0
        self._rate_limit_lock = threading.Lock()

    @classmethod
    def from_credentials(
        cls,
        domain: str,
        client_id: str,
        client_secret: str,
        **kwargs: Any,
    ) -> "BenchlingClient":
        """Convenience constructor — creates an OAuthTokenProvider internally."""
        provider = OAuthTokenProvider(domain, client_id, client_secret)
        return cls(domain, provider, **kwargs)

    # ------------------------------------------------------------------
    # Core request
    # ------------------------------------------------------------------

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict | None = None,
        json: Any = None,
        version: str = "v2",
    ) -> Any:
        """
        Execute a single HTTP request with retry logic.

        Returns the parsed JSON body, or {} for empty 2xx responses.
        Raises ApiError on non-retryable failures or exhausted retries.
        """
        url = f"https://{self._domain}/api/{version}/{endpoint.lstrip('/')}"
        last_exc: ApiError | None = None

        for attempt in range(1, self._max_retries + 1):
            self._enforce_rate_limit()

            token = self._token_provider.get_token()
            headers: dict[str, str] = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }
            if json is not None:
                headers["Content-Type"] = "application/json"

            logger.debug("%s %s attempt=%d/%d", method, endpoint, attempt, self._max_retries)

            try:
                resp = requests.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                    timeout=self._request_timeout,
                )
            except requests.RequestException as exc:
                logger.warning("Network error %s %s attempt=%d: %s", method, endpoint, attempt, exc)
                last_exc = ApiError(str(exc), endpoint=endpoint)
                self._sleep(attempt)
                continue

            if resp.status_code == 401:
                if attempt < self._max_retries:
                    logger.warning("401 on %s %s — invalidating token (attempt %d)", method, endpoint, attempt)
                    self._token_provider.invalidate()
                    continue
                raise ApiError(
                    f"Unauthorized: {method} {endpoint}",
                    status_code=401,
                    response_text=resp.text[:2000],
                    endpoint=endpoint,
                )

            if resp.status_code in RETRYABLE_STATUS_CODES:
                if attempt < self._max_retries:
                    logger.warning(
                        "Retryable HTTP %d on %s %s (attempt %d/%d)",
                        resp.status_code, method, endpoint, attempt, self._max_retries,
                    )
                    self._sleep(attempt, resp)
                    continue
                # fall through to raise on last attempt
                raise ApiError(
                    f"Exhausted {self._max_retries} retries: {method} {endpoint} → {resp.status_code}",
                    status_code=resp.status_code,
                    response_text=resp.text[:2000],
                    endpoint=endpoint,
                )

            if resp.status_code >= 400:
                raise ApiError(
                    f"{method} {endpoint} → {resp.status_code}",
                    status_code=resp.status_code,
                    response_text=resp.text[:2000],
                    endpoint=endpoint,
                )

            logger.debug("%s %s → %d", method, endpoint, resp.status_code)
            return resp.json() if resp.content else {}

        raise last_exc or ApiError(
            f"Exhausted {self._max_retries} retries: {method} {endpoint}",
            endpoint=endpoint,
        )

    # ------------------------------------------------------------------
    # HTTP verb shortcuts
    # ------------------------------------------------------------------

    def get(self, endpoint: str, *, params: dict | None = None, version: str = "v2") -> Any:
        return self.request("GET", endpoint, params=params, version=version)

    def post(self, endpoint: str, *, json: Any = None, params: dict | None = None, version: str = "v2") -> Any:
        return self.request("POST", endpoint, json=json, params=params, version=version)

    def patch(self, endpoint: str, *, json: Any = None, params: dict | None = None, version: str = "v2") -> Any:
        return self.request("PATCH", endpoint, json=json, params=params, version=version)

    def delete(self, endpoint: str, *, params: dict | None = None, version: str = "v2") -> Any:
        return self.request("DELETE", endpoint, params=params, version=version)

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def iter_pages(
        self,
        endpoint: str,
        result_key: str,
        *,
        params: dict | None = None,
        page_size: int | None = None,
        version: str = "v2",
    ) -> Iterator[list[Any]]:
        """
        Yield one page of results at a time.

        Prefer this over paginate() when working with large result sets — it avoids
        loading all pages into memory before the caller can start processing.
        """
        p = dict(params or {})
        if page_size is not None:
            p["pageSize"] = page_size

        while True:
            data = self.get(endpoint, params=p, version=version)
            items = data.get(result_key, [])
            if items:
                yield items
            next_token = data.get("nextToken")
            if not next_token:
                break
            p["nextToken"] = next_token

    def paginate(
        self,
        endpoint: str,
        result_key: str,
        *,
        params: dict | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
        version: str = "v2",
    ) -> list[Any]:
        """
        Fetch all pages and return a flat list.

        Use max_results to cap how many items are returned (fetches stop early once
        the limit is reached — no wasted requests).
        """
        results: list[Any] = []
        for page in self.iter_pages(
            endpoint, result_key, params=params, page_size=page_size, version=version
        ):
            results.extend(page)
            if max_results is not None and len(results) >= max_results:
                return results[:max_results]
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _enforce_rate_limit(self) -> None:
        if not self._rate_limit_delay:
            return
        with self._rate_limit_lock:
            elapsed = time.monotonic() - self._last_request_at
            wait = self._rate_limit_delay - elapsed
            if wait > 0:
                time.sleep(wait)
            self._last_request_at = time.monotonic()

    def _sleep(self, attempt: int, response: requests.Response | None = None) -> None:
        """Exponential backoff, respecting Retry-After if present."""
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    time.sleep(float(retry_after))
                    return
                except ValueError:
                    pass
        time.sleep(self._retry_backoff * (2 ** (attempt - 1)))
