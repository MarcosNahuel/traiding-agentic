"""In-memory LRU cache with TTL for quant engine data."""

import time
import logging
from typing import Any, Optional
from collections import OrderedDict

logger = logging.getLogger(__name__)


class TTLCache:
    """Thread-safe LRU cache with per-item TTL expiration."""

    def __init__(self, max_size: int = 256, default_ttl: int = 300):
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None
        value, expires_at = self._cache[key]
        if time.time() > expires_at:
            del self._cache[key]
            return None
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        expires_at = time.time() + ttl
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, expires_at)
        # Evict oldest if over capacity
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed items."""
        now = time.time()
        expired = [k for k, (_, exp) in self._cache.items() if now > exp]
        for k in expired:
            del self._cache[k]
        return len(expired)

    @property
    def size(self) -> int:
        return len(self._cache)


# Singleton caches for different data types
_kline_cache = TTLCache(max_size=100, default_ttl=60)       # 1 min for kline DataFrames
_indicator_cache = TTLCache(max_size=50, default_ttl=120)    # 2 min for indicators
_analysis_cache = TTLCache(max_size=50, default_ttl=60)      # 1 min for full snapshots


def get_kline_cache() -> TTLCache:
    return _kline_cache


def get_indicator_cache() -> TTLCache:
    return _indicator_cache


def get_analysis_cache() -> TTLCache:
    return _analysis_cache
