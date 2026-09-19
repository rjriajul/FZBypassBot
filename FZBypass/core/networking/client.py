"""
Primary async HTTP client built on httpx.

Usage
-----
    from FZBypass.core.networking import http

    resp = await http.get("https://example.com")
    resp.raise_for_status()
    print(resp.text)

The singleton `http` is created at module import time with sensible
defaults.  Resolvers that need custom headers or cookies should pass
them per-request rather than mutating the shared client.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

import httpx

from FZBypass.core.networking.exceptions import (
    NetworkConnectionError,
    NetworkHTTPError,
    NetworkRateLimited,
    NetworkTimeout,
)
from FZBypass.core.networking.models import HTTPResponse

LOGGER = logging.getLogger(__name__)

# ── Timeout policy ────────────────────────────────────────────────────────────
# These values cover the vast majority of link-shortener responses.
# Terabox uses its own 60-second total timeout via the API call.
CONNECT_TIMEOUT = 10.0   # seconds — TCP handshake + TLS
READ_TIMEOUT    = 25.0   # seconds — time to receive the first byte … last byte
WRITE_TIMEOUT   = 15.0   # seconds — sending the request body
POOL_TIMEOUT    = 10.0   # seconds — waiting for a free connection slot

DEFAULT_TIMEOUT = httpx.Timeout(
    connect=CONNECT_TIMEOUT,
    read=READ_TIMEOUT,
    write=WRITE_TIMEOUT,
    pool=POOL_TIMEOUT,
)

# ── Connection pool ───────────────────────────────────────────────────────────
DEFAULT_LIMITS = httpx.Limits(
    max_connections=100,
    max_keepalive_connections=30,
    keepalive_expiry=30.0,
)

# ── Retry policy ─────────────────────────────────────────────────────────────
# Only transient HTTP failures are retried.
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
MAX_RETRIES = 2
BASE_BACKOFF = 1.0   # seconds (doubles per attempt, plus jitter)

MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": MOBILE_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _to_response(r: httpx.Response) -> HTTPResponse:
    return HTTPResponse(
        status_code=r.status_code,
        url=str(r.url),
        headers=dict(r.headers),
        content=r.content,
        _text=r.text,
    )


async def _with_retry(
    client: "AsyncHTTPClient",
    method: str,
    url: str,
    **kwargs: Any,
) -> HTTPResponse:
    import random

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = await client._raw_request(method, url, **kwargs)
            if resp.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                delay = BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 0.5)
                LOGGER.debug(
                    "Retryable %s from %s (attempt %d/%d) — backoff %.1fs",
                    resp.status_code, url, attempt + 1, MAX_RETRIES + 1, delay,
                )
                await asyncio.sleep(delay)
                continue
            return resp
        except (NetworkTimeout, NetworkConnectionError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                delay = BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 0.5)
                LOGGER.debug(
                    "%s for %s (attempt %d/%d) — backoff %.1fs",
                    type(exc).__name__, url, attempt + 1, MAX_RETRIES + 1, delay,
                )
                await asyncio.sleep(delay)
            else:
                raise
    raise last_exc  # type: ignore[misc]


# ── Main client ───────────────────────────────────────────────────────────────

class AsyncHTTPClient:
    """
    Shared async HTTP client backed by httpx.

    Designed as a long-lived singleton; do not create instances per request.
    """

    def __init__(
        self,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        limits: httpx.Limits = DEFAULT_LIMITS,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
        max_redirects: int = 10,
    ) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            headers=headers or DEFAULT_HEADERS,
            follow_redirects=follow_redirects,
            max_redirects=max_redirects,
        )

    # ---- raw single-attempt request (no retry) ----

    async def _raw_request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        data: Any = None,
        json: Any = None,
        timeout: httpx.Timeout | float | None = None,
        follow_redirects: bool | None = None,
    ) -> HTTPResponse:
        kwargs: dict[str, Any] = {}
        if headers:
            kwargs["headers"] = headers
        if cookies:
            kwargs["cookies"] = cookies
        if data is not None:
            kwargs["data"] = data
        if json is not None:
            kwargs["json"] = json
        if timeout is not None:
            kwargs["timeout"] = timeout
        if follow_redirects is not None:
            kwargs["follow_redirects"] = follow_redirects

        try:
            r = await self._client.request(method, url, **kwargs)
            return _to_response(r)
        except httpx.TimeoutException as exc:
            raise NetworkTimeout(str(exc)) from exc
        except httpx.ConnectError as exc:
            raise NetworkConnectionError(str(exc)) from exc
        except httpx.TooManyRedirects as exc:
            from FZBypass.core.networking.exceptions import NetworkRedirectLoop
            raise NetworkRedirectLoop(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise NetworkRateLimited() from exc
            raise NetworkHTTPError(exc.response.status_code, url) from exc
        except httpx.RequestError as exc:
            raise NetworkConnectionError(str(exc)) from exc

    # ---- public API with retry ----

    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        timeout: httpx.Timeout | float | None = None,
        follow_redirects: bool | None = None,
        retry: bool = True,
    ) -> HTTPResponse:
        fn = _with_retry if retry else self._raw_request
        if retry:
            return await _with_retry(self, "GET", url,
                headers=headers, cookies=cookies,
                timeout=timeout, follow_redirects=follow_redirects)
        return await self._raw_request("GET", url,
            headers=headers, cookies=cookies,
            timeout=timeout, follow_redirects=follow_redirects)

    async def post(
        self,
        url: str,
        *,
        data: Any = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        timeout: httpx.Timeout | float | None = None,
        retry: bool = True,
    ) -> HTTPResponse:
        if retry:
            return await _with_retry(self, "POST", url,
                data=data, json=json,
                headers=headers, cookies=cookies, timeout=timeout)
        return await self._raw_request("POST", url,
            data=data, json=json,
            headers=headers, cookies=cookies, timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()


# ── Module-level singleton ────────────────────────────────────────────────────
# Resolvers import `http` from this module.
http = AsyncHTTPClient()
