"""
PromoMap - In-memory TTL Cache

Lightweight caching layer for expensive database queries.
Uses cachetools TTLCache with per-domain cache instances and
helper functions for cache invalidation on mutations.
"""
import logging
import math
from cachetools import TTLCache

logger = logging.getLogger("promomap.cache")

# ---------------------------------------------------------------------------
# Cache instances  (maxsize, ttl in seconds)
# ---------------------------------------------------------------------------

# Nearby stores: keyed by (grid_lat, grid_lon, radius, category)
# 5-minute TTL, up to 512 distinct queries
nearby_stores_cache = TTLCache(maxsize=512, ttl=300)

# Store detail: keyed by store_id (user-specific favorite flag is NOT cached)
# 10-minute TTL, up to 1024 entries
store_detail_cache = TTLCache(maxsize=1024, ttl=600)

# Active discounts per store: keyed by store_id
# 15-minute TTL, up to 1024 entries
store_discounts_cache = TTLCache(maxsize=1024, ttl=900)

# Active discounts per company: keyed by company_id
# 15-minute TTL, up to 256 entries
company_discounts_cache = TTLCache(maxsize=256, ttl=900)

# Reviews aggregation: keyed by (store_id, page, size)
# 5-minute TTL, up to 1024 entries
store_reviews_cache = TTLCache(maxsize=1024, ttl=300)


# ---------------------------------------------------------------------------
# Grid helpers for nearby-stores cache key
# ---------------------------------------------------------------------------

def _lat_lon_grid_key(lat: float, lon: float, radius: float,
                      category: str = None, grid_size_m: float = 50.0) -> tuple:
    """
    Snap lat/lon to a grid so that nearby requests within the same cell
    share a cache entry.  grid_size_m controls the cell size in meters.
    """
    # Approximate degrees per grid cell
    lat_step = grid_size_m / 111_320
    lon_step = grid_size_m / (111_320 * max(math.cos(math.radians(lat)), 0.01))

    grid_lat = round(lat / lat_step) * lat_step
    grid_lon = round(lon / lon_step) * lon_step

    # Round to 6 decimal places to avoid float-key drift
    grid_lat = round(grid_lat, 6)
    grid_lon = round(grid_lon, 6)

    return (grid_lat, grid_lon, radius, category)


# ---------------------------------------------------------------------------
# Invalidation helpers
# ---------------------------------------------------------------------------

def invalidate_store(store_id: int):
    """
    Call after a store is created / updated / deleted.
    Clears store detail and the entire nearby-stores cache
    (because any grid cell could contain this store).
    """
    store_detail_cache.pop(store_id, None)
    nearby_stores_cache.clear()
    logger.debug("Cache invalidated: store %s + nearby_stores", store_id)


def invalidate_discount(store_id: int = None, company_id: int = None):
    """
    Call after a discount is created / updated / deleted.
    Clears related caches that include discount information.
    """
    if store_id is not None:
        store_detail_cache.pop(store_id, None)
        store_discounts_cache.pop(store_id, None)
    if company_id is not None:
        company_discounts_cache.pop(company_id, None)
    # Nearby stores include discount snippets, so clear that cache too
    nearby_stores_cache.clear()
    logger.debug(
        "Cache invalidated: discount (store=%s, company=%s) + nearby_stores",
        store_id, company_id,
    )


def invalidate_review(store_id: int):
    """
    Call after a review is created.
    Clears store reviews and store detail (which includes avg_rating).
    """
    store_detail_cache.pop(store_id, None)
    # Clear all review pages for this store
    keys_to_remove = [k for k in store_reviews_cache if k[0] == store_id]
    for k in keys_to_remove:
        store_reviews_cache.pop(k, None)
    logger.debug("Cache invalidated: reviews for store %s", store_id)


def clear_all():
    """Clear every cache (useful for tests or admin flush)."""
    nearby_stores_cache.clear()
    store_detail_cache.clear()
    store_discounts_cache.clear()
    company_discounts_cache.clear()
    store_reviews_cache.clear()
    logger.info("All caches cleared")
