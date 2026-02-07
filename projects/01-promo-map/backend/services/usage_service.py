"""사용 기록 서비스"""
from sqlalchemy.orm import Session
from models import User
from repositories.usage_log_repo import UsageLogRepository
from repositories.store_repo import StoreRepository
from repositories.discount_repo import DiscountRepository
from exceptions import NotFoundException


def log_discount_usage(db: Session, user: User, store_id: int,
                       discount_id: int, saved_amount: float = 0) -> dict:
    store_repo = StoreRepository(db)
    discount_repo = DiscountRepository(db)
    usage_repo = UsageLogRepository(db)

    store = store_repo.get_by_id(store_id)
    if not store:
        raise NotFoundException("Store not found")

    discount = discount_repo.get_by_id(discount_id)
    if not discount:
        raise NotFoundException("Discount not found")

    log = usage_repo.create(
        user_id=user.id,
        store_id=store_id,
        discount_id=discount_id,
        saved_amount=saved_amount,
    )
    return {"status": "ok", "message": "Usage recorded", "id": log.id}
