"""어드민 서비스"""
from datetime import datetime
from sqlalchemy.orm import Session
from models import User, Store, Discount, Company
from repositories.user_repo import UserRepository
from repositories.store_repo import StoreRepository
from repositories.discount_repo import DiscountRepository
from repositories.company_repo import CompanyRepository
from repositories.usage_log_repo import UsageLogRepository
from repositories.admin_log_repo import AdminLogRepository
from exceptions import NotFoundException


def get_dashboard_stats(db: Session) -> dict:
    user_repo = UserRepository(db)
    store_repo = StoreRepository(db)
    company_repo = CompanyRepository(db)
    usage_repo = UsageLogRepository(db)

    return {
        "total_users": user_repo.count_active(),
        "total_stores": store_repo.count_active(),
        "total_companies": company_repo.count_active(),
        "total_usage": usage_repo.count(),
        "daily_usage": [
            {"date": str(row.date), "count": row.count}
            for row in usage_repo.get_daily_counts(30)
        ],
        "popular_stores": _get_popular_store_names(db, usage_repo),
    }


def _get_popular_store_names(db: Session, usage_repo: UsageLogRepository) -> list:
    popular = usage_repo.get_popular_stores(10)
    store_repo = StoreRepository(db)
    results = []
    for row in popular:
        store = store_repo.get_by_id(row.store_id)
        if store:
            results.append({"store_name": store.name, "usage_count": row.usage_count})
    return results


# --- Store CRUD ---
def admin_list_stores(db: Session, page: int = 1, size: int = 20) -> dict:
    store_repo = StoreRepository(db)
    offset = (page - 1) * size
    stores = store_repo.get_all(offset=offset, limit=size)
    total = store_repo.count()
    return {
        "items": [_store_to_dict(s) for s in stores],
        "total": total, "page": page, "size": size,
        "pages": (total + size - 1) // size if total > 0 else 1,
    }


def admin_create_store(db: Session, admin: User, data: dict) -> dict:
    store_repo = StoreRepository(db)
    log_repo = AdminLogRepository(db)
    store = store_repo.create(**data)
    log_repo.log_action(admin.id, "CREATE", "store", store.id, f"Created store: {store.name}")
    return _store_to_dict(store)


def admin_update_store(db: Session, admin: User, store_id: int, data: dict) -> dict:
    store_repo = StoreRepository(db)
    log_repo = AdminLogRepository(db)
    store = store_repo.get_by_id(store_id)
    if not store:
        raise NotFoundException("Store not found")
    store = store_repo.update(store, **data)
    log_repo.log_action(admin.id, "UPDATE", "store", store.id, f"Updated store: {store.name}")
    return _store_to_dict(store)


def admin_delete_store(db: Session, admin: User, store_id: int):
    store_repo = StoreRepository(db)
    log_repo = AdminLogRepository(db)
    store = store_repo.get_by_id(store_id)
    if not store:
        raise NotFoundException("Store not found")
    store_repo.soft_delete(store)
    log_repo.log_action(admin.id, "DELETE", "store", store.id, f"Deleted store: {store.name}")


# --- Discount CRUD ---
def admin_list_discounts(db: Session, page: int = 1, size: int = 20) -> dict:
    discount_repo = DiscountRepository(db)
    offset = (page - 1) * size
    discounts = discount_repo.get_all_with_relations(offset=offset, limit=size)
    total = discount_repo.count()
    return {
        "items": [_discount_to_dict(d) for d in discounts],
        "total": total, "page": page, "size": size,
        "pages": (total + size - 1) // size if total > 0 else 1,
    }


def admin_create_discount(db: Session, admin: User, data: dict) -> dict:
    discount_repo = DiscountRepository(db)
    log_repo = AdminLogRepository(db)

    # Parse date strings
    for field in ["valid_from", "valid_until"]:
        if data.get(field):
            data[field] = datetime.fromisoformat(data[field])

    discount = discount_repo.create(**data)
    log_repo.log_action(admin.id, "CREATE", "discount", discount.id, f"Created discount: {discount.description}")
    return _discount_to_dict(discount)


def admin_update_discount(db: Session, admin: User, discount_id: int, data: dict) -> dict:
    discount_repo = DiscountRepository(db)
    log_repo = AdminLogRepository(db)
    discount = discount_repo.get_by_id(discount_id)
    if not discount:
        raise NotFoundException("Discount not found")

    for field in ["valid_from", "valid_until"]:
        if data.get(field):
            data[field] = datetime.fromisoformat(data[field])

    discount = discount_repo.update(discount, **data)
    log_repo.log_action(admin.id, "UPDATE", "discount", discount.id, f"Updated discount")
    return _discount_to_dict(discount)


def admin_delete_discount(db: Session, admin: User, discount_id: int):
    discount_repo = DiscountRepository(db)
    log_repo = AdminLogRepository(db)
    discount = discount_repo.get_by_id(discount_id)
    if not discount:
        raise NotFoundException("Discount not found")
    discount_repo.delete(discount)
    log_repo.log_action(admin.id, "DELETE", "discount", discount_id, "Deleted discount")


# --- Company CRUD ---
def admin_list_companies(db: Session, page: int = 1, size: int = 20) -> dict:
    company_repo = CompanyRepository(db)
    offset = (page - 1) * size
    companies = company_repo.get_all(offset=offset, limit=size)
    total = company_repo.count()
    return {
        "items": [_company_to_dict(c) for c in companies],
        "total": total, "page": page, "size": size,
        "pages": (total + size - 1) // size if total > 0 else 1,
    }


def admin_create_company(db: Session, admin: User, data: dict) -> dict:
    company_repo = CompanyRepository(db)
    log_repo = AdminLogRepository(db)

    for field in ["contract_start", "contract_end"]:
        if data.get(field):
            from datetime import date as date_cls
            data[field] = date_cls.fromisoformat(data[field])

    company = company_repo.create(**data)
    log_repo.log_action(admin.id, "CREATE", "company", company.id, f"Created company: {company.name}")
    return _company_to_dict(company)


def admin_update_company(db: Session, admin: User, company_id: int, data: dict) -> dict:
    company_repo = CompanyRepository(db)
    log_repo = AdminLogRepository(db)
    company = company_repo.get_by_id(company_id)
    if not company:
        raise NotFoundException("Company not found")

    for field in ["contract_start", "contract_end"]:
        if data.get(field):
            from datetime import date as date_cls
            data[field] = date_cls.fromisoformat(data[field])

    company = company_repo.update(company, **data)
    log_repo.log_action(admin.id, "UPDATE", "company", company.id, f"Updated company: {company.name}")
    return _company_to_dict(company)


# --- User Management ---
def admin_list_users(db: Session, page: int = 1, size: int = 20) -> dict:
    user_repo = UserRepository(db)
    offset = (page - 1) * size
    users = user_repo.get_all(offset=offset, limit=size)
    total = user_repo.count()
    return {
        "items": [_user_to_dict(u) for u in users],
        "total": total, "page": page, "size": size,
        "pages": (total + size - 1) // size if total > 0 else 1,
    }


def admin_update_user(db: Session, admin: User, user_id: int, data: dict) -> dict:
    user_repo = UserRepository(db)
    log_repo = AdminLogRepository(db)
    user = user_repo.get_by_id(user_id)
    if not user:
        raise NotFoundException("User not found")
    user = user_repo.update(user, **data)
    log_repo.log_action(admin.id, "UPDATE", "user", user.id, f"Updated user: {user.email}")
    return _user_to_dict(user)


def get_usage_report(db: Session) -> dict:
    usage_repo = UsageLogRepository(db)
    return {
        "daily_usage": [
            {"date": str(row.date), "count": row.count}
            for row in usage_repo.get_daily_counts(30)
        ],
        "popular_stores": _get_popular_store_names(db, usage_repo),
        "total_usage": usage_repo.count(),
    }


# --- Serialization helpers ---
def _store_to_dict(s) -> dict:
    return {
        "id": s.id, "name": s.name, "brand": s.brand,
        "category": s.category, "address": s.address,
        "latitude": s.latitude, "longitude": s.longitude,
        "phone": s.phone, "icon_color": s.icon_color, "icon_letter": s.icon_letter,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else "",
    }


def _discount_to_dict(d) -> dict:
    return {
        "id": d.id, "store_id": d.store_id, "company_id": d.company_id,
        "discount_type": d.discount_type, "discount_value": d.discount_value,
        "description": d.description, "min_purchase": d.min_purchase,
        "max_discount": d.max_discount, "is_active": d.is_active,
        "valid_from": d.valid_from.isoformat() if d.valid_from else None,
        "valid_until": d.valid_until.isoformat() if d.valid_until else None,
        "store_name": d.store.name if d.store else None,
        "company_name": d.company.name if d.company else None,
    }


def _company_to_dict(c) -> dict:
    return {
        "id": c.id, "name": c.name, "code": c.code,
        "logo_url": c.logo_url, "is_active": c.is_active,
        "employee_count": c.employee_count, "industry": c.industry,
        "contract_start": str(c.contract_start) if c.contract_start else None,
        "contract_end": str(c.contract_end) if c.contract_end else None,
    }


def _user_to_dict(u) -> dict:
    return {
        "id": u.id, "email": u.email, "name": u.name,
        "phone": u.phone, "is_active": u.is_active, "is_admin": u.is_admin,
        "company_name": u.company.name if u.company else None,
        "created_at": u.created_at.isoformat() if u.created_at else "",
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }
