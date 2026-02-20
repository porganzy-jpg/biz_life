"""PromoMap API v1"""
from fastapi import APIRouter

from api.v1.auth import router as auth_router
from api.v1.stores import router as stores_router
from api.v1.discounts import router as discounts_router
from api.v1.favorites import router as favorites_router
from api.v1.reviews import router as reviews_router
from api.v1.users import router as users_router
from api.v1.notifications import router as notifications_router
from api.v1.redemption import router as redemption_router
from api.v1.trending import router as trending_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(stores_router)
v1_router.include_router(discounts_router)
v1_router.include_router(favorites_router)
v1_router.include_router(reviews_router)
v1_router.include_router(users_router)
v1_router.include_router(notifications_router)
v1_router.include_router(redemption_router)
v1_router.include_router(trending_router)
