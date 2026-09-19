"""
Async adapter for the synchronous `cfscrape` library.

`cfscrape` is synchronous.  Running it directly inside an async function
blocks the event loop.  This module wraps every call in
`asyncio.to_thread()` and enforces a semaphore to prevent unbounded
thread creation under concurrent load.

Usage
-----
    from FZBypass.core.networking import cf

    resp = await cf.get("https://cloudflare-protected-site.com/path")
    resp.raise_for_status()
    print(resp.text)

The singleton `cf` is created at module import time with a shared
`cfscrape` session.  A new underlying session is created for operations
that need cookie isolation (pass `fresh=True`).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

import cfscrape

from FZBypass.core.networking.exceptions import (
    NetworkCloudflareBlock,
    NetworkConnectionError,
    NetworkHTTPError,
    NetworkRateLimited,
    NetworkTimeout,
)
from FZBypass.core.networking.models import HTTPResponse

LOGGER = logging.getLogger(__name__)

# Maximum simultaneous cfscrape threads.  cfscrape executes JS
# (via Node.js or a built-in interpreter) which is CPU-bound;
# too many at once starves the event loop's thread pool.
_CF_SEMAPHORE = asyncio.Semaphore(8)

# Per-request timeout passed to cfscrape (seconds).
CF_TIMEOUT = 30


def _to_response(r: Any) -> HTTPResponse:
    """Convert a requests.Response to HTTPResponse."""
    return HTTPResponse(
        status_code=r.status_code,
        url=r.url,
        headers=dict(r.headers),
        content=r.content,
        _text=r.text,
    )


def _check_cloudflare(resp: HTTPResponse) -> None:
    """Raise NetworkCloudflareBlock if CF challenge page detected."""
    if resp.status_code in (403, 503) and "Just a moment" in resp.text:
        raise NetworkCloudflareBlock(
            f"Cloudflare challenge page at {resp.url}"
        )


def _make_scraper() -> Any:
    return cfscrape.create_scraper()


async def _run_cf(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Execute a synchronous cfscrape call in a thread with semaphore guard."""
    async with _CF_SEMAPHORE:
        return await asyncio.to_thread(func, *args, **kwargs)


class CloudflareClient:
    """
    Async wrapper around cfscrape.

    Uses a single shared scraper by default.  Call with fresh=True to
    get an isolated session (e.g. when cookies must not bleed between
    unrelated domains).
    """

    def __init__(self) -> None:
        self._scraper = _make_scraper()
        self._lock = asyncio.Lock()

    def _fresh_scraper(self) -> Any:
        return _make_scraper()

    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        allow_redirects: bool = True,
        timeout: int = CF_TIMEOUT,
        fresh: bool = False,
    ) -> HTTPResponse:
        scraper = self._fresh_scraper() if fresh else self._scraper
        kwargs: dict[str, Any] = {
            "allow_redirects": allow_redirects,
            "timeout": timeout,
        }
        if headers:
            kwargs["headers"] = headers
        if cookies:
            kwargs["cookies"] = cookies
        try:
            r = await _run_cf(scraper.get, url, **kwargs)
            resp = _to_response(r)
            _check_cloudflare(resp)
            return resp
        except NetworkCloudflareBlock:
            raise
        except Exception as exc:
            _raise_from_requests_exc(exc, url)

    async def post(
        self,
        url: str,
        *,
        data: Any = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        timeout: int = CF_TIMEOUT,
        fresh: bool = False,
    ) -> HTTPResponse:
        scraper = self._fresh_scraper() if fresh else self._scraper
        kwargs: dict[str, Any] = {"timeout": timeout}
        if data is not None:
            kwargs["data"] = data
        if json is not None:
            kwargs["json"] = json
        if headers:
            kwargs["headers"] = headers
        if cookies:
            kwargs["cookies"] = cookies
        try:
            r = await _run_cf(scraper.post, url, **kwargs)
            resp = _to_response(r)
            _check_cloudflare(resp)
            return resp
        except NetworkCloudflareBlock:
            raise
        except Exception as exc:
            _raise_from_requests_exc(exc, url)

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        data: Any = None,
        allow_redirects: bool = True,
        timeout: int = CF_TIMEOUT,
        fresh: bool = False,
    ) -> HTTPResponse:
        scraper = self._fresh_scraper() if fresh else self._scraper
        kwargs: dict[str, Any] = {
            "allow_redirects": allow_redirects,
            "timeout": timeout,
        }
        if data is not None:
            kwargs["data"] = data
        if headers:
            kwargs["headers"] = headers
        if cookies:
            kwargs["cookies"] = cookies
        try:
            r = await _run_cf(scraper.request, method, url, **kwargs)
            resp = _to_response(r)
            _check_cloudflare(resp)
            return resp
        except NetworkCloudflareBlock:
            raise
        except Exception as exc:
            _raise_from_requests_exc(exc, url)


def _raise_from_requests_exc(exc: Exception, url: str) -> None:
    """Convert requests-style exceptions to NetworkError hierarchy."""
    import requests.exceptions as req_exc
    name = type(exc).__name__
    if isinstance(exc, req_exc.Timeout):
        raise NetworkTimeout(f"{name}: {exc}") from exc
    if isinstance(exc, (req_exc.ConnectionError, req_exc.SSLError)):
        raise NetworkConnectionError(f"{name}: {exc}") from exc
    if isinstance(exc, req_exc.HTTPError):
        code = getattr(getattr(exc, "response", None), "status_code", 0)
        if code == 429:
            raise NetworkRateLimited() from exc
        raise NetworkHTTPError(code, url) from exc
    # Unknown / unexpected — re-raise as NetworkConnectionError for visibility
    raise NetworkConnectionError(f"{name}: {exc}") from exc


# ── Module-level singleton ────────────────────────────────────────────────────
cf = CloudflareClient()
