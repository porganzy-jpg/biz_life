"""HomeFinder Pydantic 스키마 패키지"""

# Enums
from .common import (
    PropertyType,
    AcquisitionType,
    CandidateStatus,
    DataSource,
    SortOrder,
)

# Pagination
from .pagination import PaginatedResponse

# Property
from .property import PropertyCreate, PropertyUpdate, PropertyResponse, PropertyBrief

# Complex
from .complex import ComplexCreate, ComplexResponse

# Area
from .area import AreaResponse, AreaComparison

# Transaction
from .transaction import TransactionResponse, PriceTrendPoint, PriceTrend

# Auction
from .auction import AuctionResponse, AuctionDeal

# Subscription
from .subscription import SubscriptionResponse

# Candidate
from .candidate import (
    CandidateCreate,
    CandidateUpdate,
    CandidateResponse,
    CandidateStatusCount,
    CandidatePipeline,
)

# Search
from .search import SearchCriteria, SavedSearchCreate, SavedSearchResponse

# Scoring
from .scoring import ScoreWeights, ScoreDetail, ScoreResponse

# Dashboard
from .dashboard import DashboardSummary, MapMarker, PriceStats, TopCandidate

__all__ = [
    # Enums
    "PropertyType",
    "AcquisitionType",
    "CandidateStatus",
    "DataSource",
    "SortOrder",
    # Pagination
    "PaginatedResponse",
    # Property
    "PropertyCreate",
    "PropertyUpdate",
    "PropertyResponse",
    "PropertyBrief",
    # Complex
    "ComplexCreate",
    "ComplexResponse",
    # Area
    "AreaResponse",
    "AreaComparison",
    # Transaction
    "TransactionResponse",
    "PriceTrendPoint",
    "PriceTrend",
    # Auction
    "AuctionResponse",
    "AuctionDeal",
    # Subscription
    "SubscriptionResponse",
    # Candidate
    "CandidateCreate",
    "CandidateUpdate",
    "CandidateResponse",
    "CandidateStatusCount",
    "CandidatePipeline",
    # Search
    "SearchCriteria",
    "SavedSearchCreate",
    "SavedSearchResponse",
    # Scoring
    "ScoreWeights",
    "ScoreDetail",
    "ScoreResponse",
    # Dashboard
    "DashboardSummary",
    "MapMarker",
    "PriceStats",
    "TopCandidate",
]
