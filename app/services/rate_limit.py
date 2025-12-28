from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Tuple


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after: float


class RateLimiter:
    def __init__(self, max_calls: int, period_seconds: int) -> None:
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self._calls: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> RateLimitResult:
        now = time.time()
        window = self._calls[key]
        while window and now - window[0] > self.period_seconds:
            window.popleft()
        if len(window) >= self.max_calls:
            retry_after = self.period_seconds - (now - window[0])
            return RateLimitResult(False, max(retry_after, 0))
        window.append(now)
        return RateLimitResult(True, 0)


rate_limiter = RateLimiter(max_calls=5, period_seconds=10)
