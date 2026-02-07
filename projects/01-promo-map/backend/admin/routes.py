"""어드민 CRUD API"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from database import get_db
from admin.auth import get_admin_session
from dependencies import get_pagination
from services import admin_service
from schemas.store import StoreCreateRequest, StoreUpdateRequest
from schemas.discount import DiscountCreateRequest, DiscountUpdateRequest
from schemas.company import CompanyCreateRequest, CompanyUpdateRequest

router = APIRouter(prefix="/admin/api", tags=["admin"])


# --- Dashboard ---
@router.get("/stats")
async def dashboard_stats(
    admin=Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    return admin_service.get_dashboard_stats(db)


@router.get("/usage-report")
async def usage_report(
    admin=Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    return admin_service.get_usage_report(db)


# --- Stores ---
@router.get("/stores")
async def list_stores(
    admin=Depends(get_admin_session),
    pagination: dict = Depends(get_pagination),
    db: Session = Depends(get_db),
):
    return admin_service.admin_list_stores(db, page=pagination["page"], size=pagination["size"])


@router.post("/stores")
async def create_store(
    data: StoreCreateRequest,
    admin=Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    return admin_service.admin_create_store(db, admin, data.model_dump())


@router.put("/stores/{store_id}")
async def update_store(
    store_id: int,
    data: StoreUpdateRequest,
    admin=Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    return admin_service.admin_update_store(db, admin, store_id, data.model_dump(exclude_none=True))


@router.delete("/stores/{store_id}")
async def delete_store(
    store_id: int,
    admin=Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    admin_service.admin_delete_store(db, admin, store_id)
    return {"status": "ok", "message": "Store deleted"}


# --- Discounts ---
@router.get("/discounts")
async def list_discounts(
    admin=Depends(get_admin_session),
    pagination: dict = Depends(get_pagination),
    db: Session = Depends(get_db),
):
    return admin_service.admin_list_discounts(db, page=pagination["page"], size=pagination["size"])


@router.post("/discounts")
async def create_discount(
    data: DiscountCreateRequest,
    admin=Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    return admin_service.admin_create_discount(db, admin, data.model_dump())


@router.put("/discounts/{discount_id}")
async def update_discount(
    discount_id: int,
    data: DiscountUpdateRequest,
    admin=Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    return admin_service.admin_update_discount(db, admin, discount_id, data.model_dump(exclude_none=True))


@router.delete("/discounts/{discount_id}")
async def delete_discount(
    discount_id: int,
    admin=Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    admin_service.admin_delete_discount(db, admin, discount_id)
    return {"status": "ok", "message": "Discount deleted"}


# --- Companies ---
@router.get("/companies")
async def list_companies(
    admin=Depends(get_admin_session),
    pagination: dict = Depends(get_pagination),
    db: Session = Depends(get_db),
):
    return admin_service.admin_list_companies(db, page=pagination["page"], size=pagination["size"])


@router.post("/companies")
async def create_company(
    data: CompanyCreateRequest,
    admin=Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    return admin_service.admin_create_company(db, admin, data.model_dump())


@router.put("/companies/{company_id}")
async def update_company(
    company_id: int,
    data: CompanyUpdateRequest,
    admin=Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    return admin_service.admin_update_company(db, admin, company_id, data.model_dump(exclude_none=True))


# --- Users ---
@router.get("/users")
async def list_users(
    admin=Depends(get_admin_session),
    pagination: dict = Depends(get_pagination),
    db: Session = Depends(get_db),
):
    return admin_service.admin_list_users(db, page=pagination["page"], size=pagination["size"])


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    request: Request,
    admin=Depends(get_admin_session),
    db: Session = Depends(get_db),
):
    data = await request.json()
    return admin_service.admin_update_user(db, admin, user_id, data)
