"""
Lightweight response model shared by all HTTP adapters.

Resolvers use HTTPResponse rather than importing httpx/requests
types directly, keeping the transport layer swappable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(slots=True)
class HTTPResponse:
    """Normalised HTTP response returned by every adapter."""

    status_code: int
    url: str
    headers: Mapping[str, str]
    content: bytes
    _text: str | None = field(default=None, repr=False)

    # ------------------------------------------------------------------ #
    # Convenience properties                                               #
    # ------------------------------------------------------------------ #

    @property
    def text(self) -> str:
        if self._text is None:
            self._text = self.content.decode("utf-8", errors="replace")
        return self._text

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def raise_for_status(self) -> None:
        from FZBypass.core.networking.exceptions import NetworkHTTPError, NetworkRateLimited
        if self.status_code == 429:
            raise NetworkRateLimited()
        if not self.ok:
            raise NetworkHTTPError(self.status_code, self.url)
