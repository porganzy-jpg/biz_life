"""
지역 점수 (0~100)
- 개발 잠재력 (30%): 재개발/GTX 등 호재
- 주거 환경 (25%): 안전, 소음, 보행편의
- 상승 이력 (25%): 과거 1년 가격 상승률
- 인프라 (20%): 학교/병원/편의시설 수
"""


def score_development(development_score: float) -> float:
    """개발 잠재력 (이미 계산된 점수 사용 or 기본값)"""
    if development_score is not None:
        return max(0, min(100, development_score))
    return 50


def score_living(living_score: float) -> float:
    """주거 환경"""
    if living_score is not None:
        return max(0, min(100, living_score))
    return 50


def score_price_history(price_change_1y: float) -> float:
    """과거 1년 가격 상승률"""
    if price_change_1y is None:
        return 50
    if price_change_1y >= 15:
        return 100
    elif price_change_1y >= 10:
        return 90
    elif price_change_1y >= 5:
        return 75
    elif price_change_1y >= 2:
        return 60
    elif price_change_1y >= 0:
        return 50
    elif price_change_1y >= -3:
        return 35
    elif price_change_1y >= -5:
        return 25
    else:
        return 10


def score_infra(subway_count: int = 0, school_count: int = 0,
                hospital_count: int = 0, park_count: int = 0) -> float:
    """인프라 점수"""
    score = 30  # base

    # Subway stations in district
    if subway_count >= 10:
        score += 20
    elif subway_count >= 5:
        score += 15
    elif subway_count >= 2:
        score += 10

    # Schools
    if school_count >= 10:
        score += 15
    elif school_count >= 5:
        score += 10

    # Hospitals
    if hospital_count >= 5:
        score += 15
    elif hospital_count >= 2:
        score += 10

    # Parks
    if park_count >= 5:
        score += 20
    elif park_count >= 2:
        score += 10

    return min(100, score)


class AreaScorer:
    W_DEVELOPMENT = 0.30
    W_LIVING = 0.25
    W_HISTORY = 0.25
    W_INFRA = 0.20

    def score(self, development_score: float = None, living_score: float = None,
              price_change_1y: float = None, subway_count: int = 0,
              school_count: int = 0, hospital_count: int = 0,
              park_count: int = 0) -> dict:

        s_dev = score_development(development_score)
        s_living = score_living(living_score)
        s_history = score_price_history(price_change_1y)
        s_infra = score_infra(subway_count, school_count, hospital_count, park_count)

        total = (s_dev * self.W_DEVELOPMENT +
                 s_living * self.W_LIVING +
                 s_history * self.W_HISTORY +
                 s_infra * self.W_INFRA)

        return {
            "total": round(total, 1),
            "development": round(s_dev, 1),
            "living": round(s_living, 1),
            "price_history": round(s_history, 1),
            "infra": round(s_infra, 1),
        }
