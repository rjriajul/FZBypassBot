"""
FZBypass networking abstraction layer.

Public API
----------
    from FZBypass.core.networking import http, cf
    from FZBypass.core.networking.exceptions import (
        NetworkError, NetworkTimeout, NetworkConnectionError,
        NetworkHTTPError, NetworkRateLimited, NetworkCloudflareBlock,
        NetworkParseError, NetworkRedirectLoop,
    )
    from FZBypass.core.networking.models import HTTPResponse

    # Async HTTP (httpx) — use for all normal requests
    resp = await http.get(url)

    # Cloudflare-compatible (cfscrape) — use only when needed
    resp = await cf.get(url)
"""
from FZBypass.core.networking.client import http, AsyncHTTPClient
from FZBypass.core.networking.cfscrape_adapter import cf, CloudflareClient
from FZBypass.core.networking.exceptions import (
    NetworkError,
    NetworkTimeout,
    NetworkConnectionError,
    NetworkHTTPError,
    NetworkRateLimited,
    NetworkCloudflareBlock,
    NetworkParseError,
    NetworkRedirectLoop,
)
from FZBypass.core.networking.models import HTTPResponse

__all__ = [
    # singletons
    "http",
    "cf",
    # classes
    "AsyncHTTPClient",
    "CloudflareClient",
    "HTTPResponse",
    # exceptions
    "NetworkError",
    "NetworkTimeout",
    "NetworkConnectionError",
    "NetworkHTTPError",
    "NetworkRateLimited",
    "NetworkCloudflareBlock",
    "NetworkParseError",
    "NetworkRedirectLoop",
]
