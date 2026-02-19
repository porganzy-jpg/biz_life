"""리뷰 서비스"""
import logging
from sqlalchemy.orm import Session
from models import User
from repositories.review_repo import ReviewRepository
from repositories.store_repo import StoreRepository
from exceptions import NotFoundException, BadRequestException
from cache import store_reviews_cache, invalidate_review

logger = logging.getLogger("promomap.cache")


def get_store_reviews(db: Session, store_id: int, page: int = 1, size: int = 20) -> dict:
    # --- Cache lookup ---
    cache_key = (store_id, page, size)
    cached = store_reviews_cache.get(cache_key)
    if cached is not None:
        logger.debug("store_reviews cache HIT: %s", cache_key)
        return cached

    store_repo = StoreRepository(db)
    review_repo = ReviewRepository(db)

    store = store_repo.get_by_id(store_id)
    if not store:
        raise NotFoundException("Store not found")

    offset = (page - 1) * size
    reviews = review_repo.get_by_store(store_id, offset=offset, limit=size)
    total = review_repo.count_by_store(store_id)
    avg_rating = review_repo.avg_rating_by_store(store_id)

    result = {
        "items": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "user_name": r.user.name if r.user else "Anonymous",
                "store_id": r.store_id,
                "rating": r.rating,
                "content": r.content,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in reviews
        ],
        "total": total,
        "avg_rating": avg_rating,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size if total > 0 else 1,
    }

    store_reviews_cache[cache_key] = result
    logger.debug("store_reviews cache MISS -> stored: %s", cache_key)
    return result


def create_review(db: Session, user: User, store_id: int,
                   rating: int, content: str = "") -> dict:
    store_repo = StoreRepository(db)
    review_repo = ReviewRepository(db)

    store = store_repo.get_by_id(store_id)
    if not store or store.deleted_at:
        raise NotFoundException("Store not found")

    if rating < 1 or rating > 5:
        raise BadRequestException("Rating must be between 1 and 5")

    review = review_repo.create(
        user_id=user.id,
        store_id=store_id,
        rating=rating,
        content=content,
    )

    # Invalidate caches that depend on reviews (reviews list + store detail avg_rating)
    invalidate_review(store_id)

    return {
        "id": review.id,
        "user_id": review.user_id,
        "user_name": user.name,
        "store_id": review.store_id,
        "rating": review.rating,
        "content": review.content,
        "created_at": review.created_at.isoformat() if review.created_at else "",
    }
