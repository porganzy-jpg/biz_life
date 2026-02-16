"""
매물 점수 (0~100)
- 연식 (30%): 5~15년 최적
- 층수 (25%): 중고층 선호
- 향 (20%): 남향/남동향 보너스
- 관리비 (15%): 낮을수록 유리
- 구조 (10%): 방수, 욕실수, 전용률
"""
from datetime import datetime


def score_building_age(built_year: int) -> float:
    """연식 점수 (5~15년 최적)"""
    if not built_year:
        return 50
    age = datetime.now().year - built_year
    if age < 0:
        return 90  # Pre-construction
    elif age <= 3:
        return 95  # New
    elif age <= 5:
        return 100  # Sweet spot start
    elif age <= 10:
        return 100  # Optimal
    elif age <= 15:
        return 90  # Still good
    elif age <= 20:
        return 70
    elif age <= 25:
        return 55
    elif age <= 30:
        return 40
    else:
        return 25


def score_floor(floor: int, total_floors: int) -> float:
    """층수 점수 (중고층 선호)"""
    if not floor:
        return 50
    if floor <= 0:
        return 10  # 지하/반지하
    if not total_floors or total_floors == 0:
        # Absolute floor scoring
        if floor <= 2:
            return 40
        elif floor <= 5:
            return 60
        elif floor <= 10:
            return 80
        elif floor <= 20:
            return 90
        else:
            return 85
    # Relative floor scoring
    ratio = floor / total_floors
    if ratio < 0.15:
        return 40  # Too low
    elif ratio < 0.3:
        return 60
    elif ratio < 0.5:
        return 80
    elif ratio < 0.75:
        return 95  # High floors - best views
    elif ratio < 0.9:
        return 90
    else:
        return 85  # Top floor - potential leaks


def score_direction(direction: str) -> float:
    """향 점수"""
    if not direction:
        return 50
    d = direction.strip()
    direction_scores = {
        "남향": 100, "남": 100,
        "남동향": 90, "남동": 90,
        "남서향": 85, "남서": 85,
        "동향": 70, "동": 70,
        "서향": 60, "서": 60,
        "동남향": 90, "서남향": 85,
        "북동향": 45, "북동": 45,
        "북서향": 40, "북서": 40,
        "북향": 30, "북": 30,
    }
    return direction_scores.get(d, 50)


def score_maintenance(maintenance_fee: int) -> float:
    """관리비 점수 (만원 단위, 낮을수록 유리)"""
    if maintenance_fee is None:
        return 50
    if maintenance_fee <= 10:
        return 100
    elif maintenance_fee <= 20:
        return 85
    elif maintenance_fee <= 30:
        return 70
    elif maintenance_fee <= 40:
        return 55
    elif maintenance_fee <= 50:
        return 40
    else:
        return 25


def score_layout(rooms: int, bathrooms: int, area_m2: float, area_supply_m2: float) -> float:
    """구조 점수"""
    score = 50  # base

    # Rooms
    if rooms and rooms >= 3:
        score += 15
    elif rooms and rooms >= 2:
        score += 10

    # Bathrooms
    if bathrooms and bathrooms >= 2:
        score += 10
    elif bathrooms and bathrooms >= 1:
        score += 5

    # 전용률 (area_m2 / area_supply_m2)
    if area_m2 and area_supply_m2 and area_supply_m2 > 0:
        ratio = area_m2 / area_supply_m2
        if ratio >= 0.80:
            score += 15
        elif ratio >= 0.75:
            score += 10
        elif ratio >= 0.70:
            score += 5

    # Area size bonus
    if area_m2:
        if area_m2 >= 85:
            score += 10  # 30평대 이상
        elif area_m2 >= 60:
            score += 5

    return min(100, score)


class PropertyScorer:
    W_AGE = 0.30
    W_FLOOR = 0.25
    W_DIRECTION = 0.20
    W_MAINTENANCE = 0.15
    W_LAYOUT = 0.10

    def score(self, built_year: int = None, floor: int = None,
              total_floors: int = None, direction: str = None,
              maintenance_fee: int = None, rooms: int = None,
              bathrooms: int = None, area_m2: float = None,
              area_supply_m2: float = None) -> dict:

        s_age = score_building_age(built_year)
        s_floor = score_floor(floor, total_floors)
        s_dir = score_direction(direction)
        s_maint = score_maintenance(maintenance_fee)
        s_layout = score_layout(rooms, bathrooms, area_m2, area_supply_m2)

        total = (s_age * self.W_AGE +
                 s_floor * self.W_FLOOR +
                 s_dir * self.W_DIRECTION +
                 s_maint * self.W_MAINTENANCE +
                 s_layout * self.W_LAYOUT)

        return {
            "total": round(total, 1),
            "age": round(s_age, 1),
            "floor": round(s_floor, 1),
            "direction": round(s_dir, 1),
            "maintenance": round(s_maint, 1),
            "layout": round(s_layout, 1),
        }
