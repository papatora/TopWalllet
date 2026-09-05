"""Shared async rate limiters for all HTTP clients."""
from __future__ import annotations

from aiolimiter import AsyncLimiter


class RateLimiter:
    """Token-bucket limiter: `rate` requests per `period` seconds."""

    def __init__(self, rate: float, period: float = 60.0):
        self._limiter = AsyncLimiter(max(rate, 0.01), period)

    async def acquire(self) -> None:
        await self._limiter.acquire()
