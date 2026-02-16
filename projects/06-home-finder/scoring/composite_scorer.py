"""
종합 채점기
종합점수 = 위치(35%) + 가격(25%) + 매물(20%) + 지역(20%)
"""
import logging
from scoring.location_scorer import LocationScorer
from scoring.price_scorer import PriceScorer
from scoring.property_scorer import PropertyScorer
from scoring.area_scorer import AreaScorer

logger = logging.getLogger("homefinder.scorer")


class CompositeScorer:
    def __init__(self, config):
        self.w_location = config.SCORE_WEIGHT_LOCATION
        self.w_price = config.SCORE_WEIGHT_PRICE
        self.w_property = config.SCORE_WEIGHT_PROPERTY
        self.w_area = config.SCORE_WEIGHT_AREA

        self.location_scorer = None  # Set via set_reference_data
        self.price_scorer = PriceScorer(config.BUDGET_MIN_KRW, config.BUDGET_MAX_KRW)
        self.property_scorer = PropertyScorer()
        self.area_scorer = AreaScorer()

    def set_reference_data(self, subway_stations: list, parks: list, river_points: list):
        """시드 데이터 로딩 후 호출"""
        self.location_scorer = LocationScorer(subway_stations, parks, river_points)

    def score_property(self, prop, area_info: dict = None) -> dict:
        """
        매물 종합 채점

        Args:
            prop: Property ORM object or dict
            area_info: dict with area avg price, price change, infra counts

        Returns:
            dict with all sub-scores and composite
        """
        # Extract property attributes
        def get(key, default=None):
            if hasattr(prop, key):
                return getattr(prop, key)
            elif isinstance(prop, dict):
                return prop.get(key, default)
            return default

        area_info = area_info or {}

        # Location score
        loc_result = {"total": 0}
        if self.location_scorer:
            loc_result = self.location_scorer.score(get("lat"), get("lng"))

        # Price score
        price_result = self.price_scorer.score(
            price_krw=get("price_krw"),
            price_per_m2=get("price_per_m2"),
            area_avg_per_m2=area_info.get("avg_price_per_m2"),
            price_change_1y=area_info.get("price_change_1y"),
            location_score=loc_result["total"],
        )

        # Property score
        prop_result = self.property_scorer.score(
            built_year=get("built_year"),
            floor=get("floor"),
            total_floors=get("total_floors"),
            direction=get("direction"),
            maintenance_fee=get("maintenance_fee"),
            rooms=get("rooms"),
            bathrooms=get("bathrooms"),
            area_m2=get("area_m2"),
            area_supply_m2=get("area_supply_m2"),
        )

        # Area score
        area_result = self.area_scorer.score(
            development_score=area_info.get("development_score"),
            living_score=area_info.get("living_score"),
            price_change_1y=area_info.get("price_change_1y"),
            subway_count=area_info.get("subway_count", 0),
            school_count=area_info.get("school_count", 0),
            hospital_count=area_info.get("hospital_count", 0),
            park_count=area_info.get("park_count", 0),
        )

        # Composite
        composite = (loc_result["total"] * self.w_location +
                     price_result["total"] * self.w_price +
                     prop_result["total"] * self.w_property +
                     area_result["total"] * self.w_area)

        return {
            "composite": round(composite, 1),
            "location": loc_result,
            "price": price_result,
            "property": prop_result,
            "area": area_result,
        }

    def update_weights(self, location: float = None, price: float = None,
                       property_w: float = None, area: float = None):
        """가중치 동적 조정"""
        if location is not None:
            self.w_location = location
        if price is not None:
            self.w_price = price
        if property_w is not None:
            self.w_property = property_w
        if area is not None:
            self.w_area = area
        logger.info(f"Weights updated: loc={self.w_location}, price={self.w_price}, "
                     f"prop={self.w_property}, area={self.w_area}")

    def get_weights(self) -> dict:
        return {
            "location": self.w_location,
            "price": self.w_price,
            "property": self.w_property,
            "area": self.w_area,
        }
