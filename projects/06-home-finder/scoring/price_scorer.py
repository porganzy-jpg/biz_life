"""
가격 점수 (0~100)
- 적정가 비교 (40%): 지역 평균 대비
- 추세 모멘텀 (25%): 최근 상승세
- 예산 적합도 (20%): 9~12억 스윗스팟 보너스
- 가성비 (15%): m2당 가격 대비 위치/시설 품질
"""


def score_vs_average(price_per_m2: int, area_avg_per_m2: int) -> float:
    """지역 평균 대비 가격 (저렴할수록 높은 점수)"""
    if not price_per_m2 or not area_avg_per_m2 or area_avg_per_m2 == 0:
        return 50
    ratio = price_per_m2 / area_avg_per_m2
    if ratio <= 0.8:
        return 100
    elif ratio <= 0.9:
        return 85
    elif ratio <= 1.0:
        return 70
    elif ratio <= 1.1:
        return 55
    elif ratio <= 1.2:
        return 40
    elif ratio <= 1.3:
        return 25
    else:
        return 10


def score_trend(price_change_1y_pct: float) -> float:
    """가격 추세 (상승 = 자산가치 증가)"""
    if price_change_1y_pct is None:
        return 50
    if price_change_1y_pct >= 10:
        return 100
    elif price_change_1y_pct >= 5:
        return 85
    elif price_change_1y_pct >= 2:
        return 70
    elif price_change_1y_pct >= 0:
        return 55
    elif price_change_1y_pct >= -3:
        return 40
    elif price_change_1y_pct >= -5:
        return 25
    else:
        return 10


def score_budget_fit(price_krw: int, budget_min: int, budget_max: int) -> float:
    """예산 적합도 (스윗스팟: 예산 중간대 보너스)"""
    if not price_krw:
        return 0
    if price_krw < budget_min:
        # Under budget - good deal
        ratio = price_krw / budget_min
        if ratio >= 0.9:
            return 90
        elif ratio >= 0.7:
            return 75
        else:
            return 60  # Too cheap might mean issues
    elif price_krw <= budget_max:
        # In budget
        sweet_min = budget_min + (budget_max - budget_min) * 0.1
        sweet_max = budget_min + (budget_max - budget_min) * 0.6
        if sweet_min <= price_krw <= sweet_max:
            return 100  # Sweet spot
        else:
            return 80
    else:
        # Over budget
        over_pct = (price_krw - budget_max) / budget_max * 100
        if over_pct <= 5:
            return 50
        elif over_pct <= 10:
            return 30
        else:
            return 10


def score_value(price_per_m2: int, location_score: float) -> float:
    """가성비 (위치 점수 대비 가격)"""
    if not price_per_m2 or not location_score:
        return 50
    # Higher location score per price = better value
    # Normalize: typical Seoul m2 price range 5M~20M KRW
    price_norm = max(0, min(1, (price_per_m2 - 3000000) / 17000000))
    loc_norm = location_score / 100
    if price_norm == 0:
        return 90
    value_ratio = loc_norm / price_norm
    if value_ratio >= 2.0:
        return 100
    elif value_ratio >= 1.5:
        return 85
    elif value_ratio >= 1.0:
        return 70
    elif value_ratio >= 0.7:
        return 55
    elif value_ratio >= 0.5:
        return 40
    else:
        return 25


class PriceScorer:
    W_AVERAGE = 0.40
    W_TREND = 0.25
    W_BUDGET = 0.20
    W_VALUE = 0.15

    def __init__(self, budget_min: int, budget_max: int):
        self.budget_min = budget_min
        self.budget_max = budget_max

    def score(self, price_krw: int, price_per_m2: int,
              area_avg_per_m2: int = None, price_change_1y: float = None,
              location_score: float = None) -> dict:

        s_avg = score_vs_average(price_per_m2, area_avg_per_m2)
        s_trend = score_trend(price_change_1y)
        s_budget = score_budget_fit(price_krw, self.budget_min, self.budget_max)
        s_value = score_value(price_per_m2, location_score)

        total = (s_avg * self.W_AVERAGE +
                 s_trend * self.W_TREND +
                 s_budget * self.W_BUDGET +
                 s_value * self.W_VALUE)

        return {
            "total": round(total, 1),
            "vs_average": round(s_avg, 1),
            "trend": round(s_trend, 1),
            "budget_fit": round(s_budget, 1),
            "value": round(s_value, 1),
        }
