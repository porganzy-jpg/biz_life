from fastapi import APIRouter
from api.v1.properties import router as properties_router
from api.v1.complexes import router as complexes_router
from api.v1.areas import router as areas_router
from api.v1.transactions import router as transactions_router
from api.v1.auctions import router as auctions_router
from api.v1.subscriptions import router as subscriptions_router
from api.v1.candidates import router as candidates_router
from api.v1.search import router as search_router
from api.v1.scoring import router as scoring_router
from api.v1.dashboard import router as dashboard_router
from api.v1.scraper import router as scraper_router
from api.v1.predictions import router as predictions_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(properties_router, prefix="/properties", tags=["Properties"])
v1_router.include_router(complexes_router, prefix="/complexes", tags=["Complexes"])
v1_router.include_router(areas_router, prefix="/areas", tags=["Areas"])
v1_router.include_router(transactions_router, prefix="/transactions", tags=["Transactions"])
v1_router.include_router(auctions_router, prefix="/auctions", tags=["Auctions"])
v1_router.include_router(subscriptions_router, prefix="/subscriptions", tags=["Subscriptions"])
v1_router.include_router(candidates_router, prefix="/candidates", tags=["Candidates"])
v1_router.include_router(search_router, prefix="/search", tags=["Search"])
v1_router.include_router(scoring_router, prefix="/scoring", tags=["Scoring"])
v1_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
v1_router.include_router(scraper_router, prefix="/scraper", tags=["Scraper"])
v1_router.include_router(predictions_router, prefix="/predictions", tags=["Predictions"])
