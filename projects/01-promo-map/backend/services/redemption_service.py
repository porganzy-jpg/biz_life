"""
QR 기반 할인 코드 발급/사용 서비스
- 8자리 코드, 5분 만료, 인메모리 저장
- 거래 로그는 JSON 파일에 기록
"""
import os
import json
import string
import random
import threading
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from models import User, Store, Discount
from repositories.store_repo import StoreRepository
from repositories.discount_repo import DiscountRepository
from repositories.usage_log_repo import UsageLogRepository
from exceptions import NotFoundException, BadRequestException

logger = logging.getLogger("promomap.redemption")

# === 인메모리 코드 저장소 ===
_redemption_codes: dict = {}
_codes_lock = threading.Lock()

# === JSON 거래 로그 파일 ===
_TRANSACTION_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "redemption_transactions.json"
)


def _load_transactions() -> list:
    """JSON 파일에서 거래 내역 로드"""
    if not os.path.exists(_TRANSACTION_LOG_PATH):
        return []
    try:
        with open(_TRANSACTION_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_transactions(transactions: list):
    """거래 내역을 JSON 파일에 저장"""
    try:
        with open(_TRANSACTION_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(transactions, f, ensure_ascii=False, indent=2, default=str)
    except IOError as e:
        logger.error(f"Failed to save transactions: {e}")


def _generate_code_string() -> str:
    """8자리 영숫자 코드 생성 (대문자 + 숫자)"""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=8))


# === 공개 API ===

def generate_redemption_code(
    db: Session, user_id: int, store_id: int, discount_id: int
) -> dict:
    """
    할인 사용 코드 발급 (8자리, 5분 만료)
    Returns: {code, expires_at, store_name, discount_description, discount_value}
    """
    # 매장/할인 존재 확인
    store_repo = StoreRepository(db)
    discount_repo = DiscountRepository(db)

    store = store_repo.get_by_id(store_id)
    if not store:
        raise NotFoundException("매장을 찾을 수 없습니다")

    discount = discount_repo.get_by_id(discount_id)
    if not discount:
        raise NotFoundException("할인 정보를 찾을 수 없습니다")

    if not discount.is_active:
        raise BadRequestException("비활성 할인입니다")

    # 고유 코드 생성
    with _codes_lock:
        for _ in range(100):  # 충돌 방지 재시도
            code = _generate_code_string()
            if code not in _redemption_codes:
                break
        else:
            raise BadRequestException("코드 생성에 실패했습니다. 잠시 후 다시 시도해주세요.")

        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=5)

        _redemption_codes[code] = {
            "code": code,
            "user_id": user_id,
            "store_id": store_id,
            "discount_id": discount_id,
            "store_name": store.name,
            "store_category": store.category,
            "discount_description": discount.description,
            "discount_value": discount.discount_value,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "is_used": False,
            "used_at": None,
        }

    # 만료된 코드 정리 (비동기적으로)
    _cleanup_expired_codes()

    logger.info(f"Redemption code generated: {code} for user={user_id}, store={store_id}")

    return {
        "code": code,
        "expires_at": expires_at.isoformat(),
        "store_name": store.name,
        "discount_description": discount.description,
        "discount_value": discount.discount_value,
    }


def validate_redemption(code: str) -> dict:
    """
    코드 유효성 검증
    Returns: {valid, code_info or error message}
    """
    code = code.strip().upper()

    with _codes_lock:
        code_data = _redemption_codes.get(code)

    if not code_data:
        raise NotFoundException("유효하지 않은 코드입니다")

    if code_data["is_used"]:
        raise BadRequestException("이미 사용된 코드입니다")

    expires_at = datetime.fromisoformat(code_data["expires_at"])
    if datetime.utcnow() > expires_at:
        raise BadRequestException("만료된 코드입니다")

    return {
        "valid": True,
        "code": code_data["code"],
        "store_name": code_data["store_name"],
        "discount_description": code_data["discount_description"],
        "discount_value": code_data["discount_value"],
        "expires_at": code_data["expires_at"],
    }


def complete_redemption(db: Session, code: str, amount: float = 0) -> dict:
    """
    코드 사용 완료 처리
    - 인메모리에서 사용 처리
    - DB usage_log에 기록
    - JSON 거래 로그에 기록
    """
    code = code.strip().upper()

    with _codes_lock:
        code_data = _redemption_codes.get(code)

        if not code_data:
            raise NotFoundException("유효하지 않은 코드입니다")

        if code_data["is_used"]:
            raise BadRequestException("이미 사용된 코드입니다")

        expires_at = datetime.fromisoformat(code_data["expires_at"])
        if datetime.utcnow() > expires_at:
            raise BadRequestException("만료된 코드입니다")

        # 사용 처리
        now = datetime.utcnow()
        code_data["is_used"] = True
        code_data["used_at"] = now.isoformat()

    # 절약 금액 계산 (amount가 제공되면 사용, 아니면 할인율 기반 추정)
    saved_amount = amount if amount > 0 else code_data["discount_value"] * 100

    # DB에 사용 기록 저장
    try:
        usage_repo = UsageLogRepository(db)
        usage_repo.create(
            user_id=code_data["user_id"],
            store_id=code_data["store_id"],
            discount_id=code_data["discount_id"],
            saved_amount=saved_amount,
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save usage log to DB: {e}")

    # JSON 거래 로그에 기록
    transaction = {
        "code": code,
        "user_id": code_data["user_id"],
        "store_id": code_data["store_id"],
        "store_name": code_data["store_name"],
        "store_category": code_data["store_category"],
        "discount_id": code_data["discount_id"],
        "discount_description": code_data["discount_description"],
        "discount_value": code_data["discount_value"],
        "amount": amount,
        "saved_amount": saved_amount,
        "created_at": code_data["created_at"],
        "used_at": code_data["used_at"],
    }

    try:
        transactions = _load_transactions()
        transactions.append(transaction)
        _save_transactions(transactions)
    except Exception as e:
        logger.error(f"Failed to save transaction log: {e}")

    logger.info(f"Redemption completed: {code}, saved={saved_amount}")

    return {
        "status": "ok",
        "message": "할인이 적용되었습니다",
        "code": code,
        "store_name": code_data["store_name"],
        "discount_value": code_data["discount_value"],
        "saved_amount": saved_amount,
    }


def get_user_redemptions(user_id: int) -> list:
    """
    유저의 사용 완료된 코드 거래 내역 (JSON 로그에서)
    """
    transactions = _load_transactions()
    user_txns = [t for t in transactions if t.get("user_id") == user_id]
    # 최신순 정렬
    user_txns.sort(key=lambda t: t.get("used_at", ""), reverse=True)
    return user_txns


def get_savings_stats(user_id: int) -> dict:
    """
    유저의 절약 통계
    - total_saved: 총 절약액
    - by_category: 카테고리별 절약
    - monthly: 월별 절약
    - count: 총 사용 횟수
    """
    transactions = _load_transactions()
    user_txns = [t for t in transactions if t.get("user_id") == user_id]

    if not user_txns:
        return {
            "total_saved": 0,
            "count": 0,
            "by_category": {},
            "monthly": {},
            "this_month": 0,
        }

    now = datetime.utcnow()
    current_month = f"{now.year}-{now.month:02d}"

    total_saved = 0
    this_month = 0
    by_category = {}
    monthly = {}

    for txn in user_txns:
        saved = txn.get("saved_amount", 0)
        total_saved += saved

        # 카테고리별
        cat = txn.get("store_category", "general")
        by_category[cat] = by_category.get(cat, 0) + saved

        # 월별
        used_at = txn.get("used_at", "")
        month_key = used_at[:7] if len(used_at) >= 7 else ""
        if month_key:
            monthly[month_key] = monthly.get(month_key, 0) + saved
            if month_key == current_month:
                this_month += saved

    return {
        "total_saved": total_saved,
        "count": len(user_txns),
        "by_category": by_category,
        "monthly": monthly,
        "this_month": this_month,
    }


def _cleanup_expired_codes():
    """만료된 미사용 코드 정리 (10분 이상 경과)"""
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    expired_keys = []

    with _codes_lock:
        for code, data in _redemption_codes.items():
            if data["is_used"]:
                continue
            expires_at = datetime.fromisoformat(data["expires_at"])
            if expires_at < cutoff:
                expired_keys.append(code)

        for key in expired_keys:
            del _redemption_codes[key]

    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired redemption codes")
