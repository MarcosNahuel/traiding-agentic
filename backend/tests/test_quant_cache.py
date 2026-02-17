"""Unit tests for quant_cache.py TTLCache."""

import time
from app.services.quant_cache import TTLCache, get_kline_cache, get_indicator_cache, get_analysis_cache


def test_set_and_get():
    cache = TTLCache(max_size=10, default_ttl=60)
    cache.set("k1", "v1")
    assert cache.get("k1") == "v1"


def test_miss_returns_none():
    cache = TTLCache(max_size=10, default_ttl=60)
    assert cache.get("missing") is None


def test_expiry():
    cache = TTLCache(max_size=10, default_ttl=1)
    cache.set("k1", "v1")
    assert cache.get("k1") == "v1"
    time.sleep(1.1)
    assert cache.get("k1") is None


def test_lru_eviction():
    cache = TTLCache(max_size=3, default_ttl=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.get("a")          # mark 'a' as recently used
    cache.set("d", 4)       # should evict 'b' (LRU)
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert cache.get("d") == 4
    assert cache.get("b") is None


def test_overwrite():
    cache = TTLCache(max_size=10, default_ttl=60)
    cache.set("k1", "v1")
    cache.set("k1", "v2")
    assert cache.get("k1") == "v2"


def test_custom_ttl():
    cache = TTLCache(max_size=10, default_ttl=60)
    cache.set("k1", "v1", ttl=1)
    assert cache.get("k1") == "v1"
    time.sleep(1.1)
    assert cache.get("k1") is None


def test_singleton_caches_are_distinct_instances():
    k = get_kline_cache()
    i = get_indicator_cache()
    a = get_analysis_cache()
    assert k is not i
    assert i is not a
    assert k is not a


def test_singleton_returns_same_instance():
    k1 = get_kline_cache()
    k2 = get_kline_cache()
    assert k1 is k2
