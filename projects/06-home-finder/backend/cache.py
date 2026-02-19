"""
In-memory TTL cache utility for HomeFinder.

Provides a simple, thread-safe caching layer for expensive database queries.
Each cache namespace has its own TTL and max-size settings.

Usage:
    from cache import response_cache

    # Get or set a cached value
    result = response_cache.get("dashboard", "summary")
    if result is None:
        result = expensive_query()
        response_cache.set("dashboard", "summary", result, ttl=300)

    # Invalidate specific keys or entire namespaces
    response_cache.invalidate("dashboard", "summary")
    response_cache.invalidate_namespace("dashboard")
    response_cache.invalidate_all()
"""
import hashlib
import json
import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger("homefinder.cache")


class TTLCacheEntry:
    """Single cache entry with expiration tracking."""

    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float):
        self.value = value
        self.expires_at = time.monotonic() + ttl

    def is_expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class CacheNamespace:
    """A namespace within the cache, with its own max-size limit."""

    def __init__(self, maxsize: int = 256):
        self.maxsize = maxsize
        self._store: dict[str, TTLCacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._store[key]
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl: float) -> None:
        with self._lock:
            # Evict expired entries if at capacity
            if len(self._store) >= self.maxsize:
                self._evict_expired()
            # If still at capacity after eviction, remove oldest entry
            if len(self._store) >= self.maxsize:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]
            self._store[key] = TTLCacheEntry(value, ttl)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> int:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def _evict_expired(self) -> None:
        """Remove all expired entries. Must be called under lock."""
        now = time.monotonic()
        expired_keys = [k for k, v in self._store.items() if now >= v.expires_at]
        for k in expired_keys:
            del self._store[k]

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)


class ResponseCache:
    """
    Multi-namespace in-memory TTL cache.

    Namespaces are created lazily on first access. Each namespace is
    independently lockable for better concurrency.
    """

    # Default TTL values (seconds) for known namespaces
    DEFAULT_TTLS = {
        "dashboard_summary": 300,     # 5 minutes
        "top_properties": 600,        # 10 minutes
        "area_stats": 1800,           # 30 minutes
        "search_results": 120,        # 2 minutes
        "map_markers": 300,           # 5 minutes
    }

    # Default max sizes per namespace
    DEFAULT_MAXSIZES = {
        "dashboard_summary": 16,
        "top_properties": 32,
        "area_stats": 64,
        "search_results": 256,
        "map_markers": 16,
    }

    def __init__(self):
        self._namespaces: dict[str, CacheNamespace] = {}
        self._ns_lock = threading.Lock()

    def _get_namespace(self, namespace: str) -> CacheNamespace:
        """Get or create a namespace."""
        if namespace not in self._namespaces:
            with self._ns_lock:
                if namespace not in self._namespaces:
                    maxsize = self.DEFAULT_MAXSIZES.get(namespace, 128)
                    self._namespaces[namespace] = CacheNamespace(maxsize=maxsize)
        return self._namespaces[namespace]

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """Retrieve a cached value, or None if missing/expired."""
        ns = self._get_namespace(namespace)
        value = ns.get(key)
        if value is not None:
            logger.debug("Cache HIT: %s:%s", namespace, key)
        else:
            logger.debug("Cache MISS: %s:%s", namespace, key)
        return value

    def set(
        self, namespace: str, key: str, value: Any, ttl: Optional[float] = None
    ) -> None:
        """Store a value in the cache with a TTL (seconds)."""
        if ttl is None:
            ttl = self.DEFAULT_TTLS.get(namespace, 300)
        ns = self._get_namespace(namespace)
        ns.set(key, value, ttl)
        logger.debug("Cache SET: %s:%s (ttl=%ss)", namespace, key, ttl)

    def invalidate(self, namespace: str, key: str) -> bool:
        """Remove a specific key from a namespace."""
        ns = self._get_namespace(namespace)
        removed = ns.delete(key)
        if removed:
            logger.debug("Cache INVALIDATE: %s:%s", namespace, key)
        return removed

    def invalidate_namespace(self, namespace: str) -> int:
        """Clear all entries in a namespace. Returns count of removed entries."""
        ns = self._get_namespace(namespace)
        count = ns.clear()
        if count > 0:
            logger.info(
                "Cache INVALIDATE namespace '%s': %d entries removed",
                namespace, count,
            )
        return count

    def invalidate_all(self) -> int:
        """Clear all namespaces. Returns total count of removed entries."""
        total = 0
        with self._ns_lock:
            for ns in self._namespaces.values():
                total += ns.clear()
        if total > 0:
            logger.info("Cache INVALIDATE ALL: %d entries removed", total)
        return total

    def invalidate_on_property_change(self) -> None:
        """
        Invalidate all caches that depend on property data.
        Call this when properties are created, updated, or deactivated.
        """
        self.invalidate_namespace("dashboard_summary")
        self.invalidate_namespace("top_properties")
        self.invalidate_namespace("search_results")
        self.invalidate_namespace("map_markers")

    def invalidate_on_candidate_change(self) -> None:
        """
        Invalidate caches that depend on candidate data.
        Call this when candidates are created or their status changes.
        """
        self.invalidate_namespace("dashboard_summary")
        self.invalidate_namespace("map_markers")

    def stats(self) -> dict:
        """Return current cache statistics (for debugging)."""
        result = {}
        with self._ns_lock:
            for name, ns in self._namespaces.items():
                result[name] = {
                    "size": ns.size,
                    "maxsize": ns.maxsize,
                }
        return result


def make_cache_key(*args, **kwargs) -> str:
    """
    Create a stable cache key from positional and keyword arguments.
    Handles common types: str, int, float, None, list, dict, Pydantic models.
    """
    parts = []
    for arg in args:
        parts.append(_serialize_value(arg))
    for k in sorted(kwargs.keys()):
        parts.append(f"{k}={_serialize_value(kwargs[k])}")
    raw = "|".join(parts)
    # Use hash for long keys to keep memory usage reasonable
    if len(raw) > 200:
        return hashlib.md5(raw.encode()).hexdigest()
    return raw


def _serialize_value(v: Any) -> str:
    """Convert a value to a stable string representation for cache key use."""
    if v is None:
        return "None"
    if isinstance(v, (str, int, float, bool)):
        return str(v)
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(_serialize_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return (
            "{"
            + ",".join(
                f"{k}:{_serialize_value(val)}" for k, val in sorted(v.items())
            )
            + "}"
        )
    # Pydantic model support
    if hasattr(v, "model_dump"):
        return _serialize_value(v.model_dump())
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)


# Singleton instance - import this in your modules
response_cache = ResponseCache()
