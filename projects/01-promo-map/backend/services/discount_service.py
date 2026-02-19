"""할인 서비스"""
import logging
from sqlalchemy.orm import Session
from models import User
from repositories.discount_repo import DiscountRepository
from repositories.usage_log_repo import UsageLogRepository
from cache import company_discounts_cache

logger = logging.getLogger("promomap.cache")


def get_active_discounts(db: Session, user: User) -> list:
    """사용자 회사의 활성 할인 목록"""
    if not user.company_id:
        return []

    # --- Cache lookup by company_id ---
    cache_key = user.company_id
    cached = company_discounts_cache.get(cache_key)
    if cached is not None:
        logger.debug("company_discounts cache HIT: company_id=%s", cache_key)
        return cached

    discount_repo = DiscountRepository(db)
    discounts = discount_repo.get_active_by_company(user.company_id)
    result = [
        {
            "id": d.id,
            "store_id": d.store_id,
            "discount_type": d.discount_type,
            "discount_value": d.discount_value,
            "description": d.description,
            "store_name": d.store.name if d.store else None,
            "store_brand": d.store.brand if d.store else None,
            "company_name": d.company.name if d.company else None,
        }
        for d in discounts
    ]

    company_discounts_cache[cache_key] = result
    logger.debug("company_discounts cache MISS -> stored: company_id=%s", cache_key)
    return result


def get_my_discount_history(db: Session, user: User, page: int = 1, size: int = 20) -> dict:
    """내가 사용한 할인 이력"""
    usage_repo = UsageLogRepository(db)
    offset = (page - 1) * size
    logs = usage_repo.get_by_user(user.id, offset=offset, limit=size)
    total = usage_repo.count_by_user(user.id)

    return {
        "items": [
            {
                "id": log.id,
                "store_name": log.store.name if log.store else "Unknown",
                "store_brand": log.store.brand if log.store else "",
                "discount_description": log.discount.description if log.discount else "",
                "discount_value": log.discount.discount_value if log.discount else 0,
                "saved_amount": log.saved_amount,
                "used_at": log.used_at.isoformat() if log.used_at else "",
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size if total > 0 else 1,
    }
