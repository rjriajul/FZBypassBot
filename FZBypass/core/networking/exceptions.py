"""
Structured networking exceptions for the bypass engine.

Resolvers catch these to distinguish failure modes without
needing to import httpx/requests/cfscrape directly.
"""


class NetworkError(Exception):
    """Base class for all networking failures."""


class NetworkTimeout(NetworkError):
    """Request exceeded its configured time limit."""


class NetworkConnectionError(NetworkError):
    """TCP/DNS-level connection failure."""


class NetworkHTTPError(NetworkError):
    """Server returned a non-success HTTP status."""

    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class NetworkRateLimited(NetworkHTTPError):
    """Server returned 429 Too Many Requests."""

    def __init__(self, message: str = "Rate limited"):
        super().__init__(429, message)


class NetworkCloudflareBlock(NetworkError):
    """Request was blocked by a Cloudflare challenge (403/503 + CF page)."""


class NetworkParseError(NetworkError):
    """Response was received but could not be parsed as expected."""


class NetworkRedirectLoop(NetworkError):
    """Redirect chain exceeded maximum depth or visited a URL twice."""
