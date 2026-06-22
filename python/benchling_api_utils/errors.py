"""Structured exceptions for Benchling API errors."""
from __future__ import annotations


class ApiError(Exception):
    """Raised when a Benchling API call fails after all retries."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_text: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
        self.endpoint = endpoint

    @property
    def is_not_found(self) -> bool:
        return self.status_code == 404

    @property
    def is_forbidden(self) -> bool:
        return self.status_code == 403

    @property
    def is_bad_request(self) -> bool:
        return self.status_code == 400

    @property
    def is_rate_limited(self) -> bool:
        return self.status_code == 429

    @property
    def is_non_retryable_lookup(self) -> bool:
        """True for errors where retrying will not help (entity gone, no access, bad ID)."""
        return self.status_code in {400, 403, 404}

    def __repr__(self) -> str:
        return (
            f"ApiError(status_code={self.status_code!r}, "
            f"endpoint={self.endpoint!r}, message={str(self)!r})"
        )
