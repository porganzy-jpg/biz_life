"""
토지 매물 점수 (0~100)
- 용도지역 적합성 (30%): 주거개발 가능 여부
- 건축 가능성 (25%): 건폐율+용적률 합산 평가
- 접도 상태 (20%): 도로 접근성
- 지형 (15%): 개발 용이성
- 면적 적정성 (10%): 단독주택 적정 면적 (200~500㎡)
"""


def score_zoning(zoning_type: str) -> float:
    """용도지역 적합성 점수"""
    if not zoning_type:
        return 50
    zoning_scores = {
        "제2종일반주거": 100,
        "제1종일반주거": 90,
        "제3종일반주거": 85,
        "준주거": 90,
        "제1종전용주거": 80,
        "제2종전용주거": 80,
        "준공업": 40,
        "일반상업": 50,
        "근린상업": 55,
        "자연녹지": 30,
        "생산녹지": 20,
        "보전녹지": 10,
    }
    return zoning_scores.get(zoning_type, 50)


def score_buildability(bcr: float, far: float) -> float:
    """건축 가능성 점수 (건폐율 + 용적률 합산)"""
    if bcr is None and far is None:
        return 50

    score = 0
    # 건폐율 평가 (0~50)
    if bcr is not None:
        if bcr >= 60:
            score += 50
        elif bcr >= 50:
            score += 45
        elif bcr >= 40:
            score += 35
        elif bcr >= 30:
            score += 25
        else:
            score += 15
    else:
        score += 25

    # 용적률 평가 (0~50)
    if far is not None:
        if far >= 250:
            score += 50
        elif far >= 200:
            score += 45
        elif far >= 150:
            score += 35
        elif far >= 100:
            score += 25
        else:
            score += 15
    else:
        score += 25

    return score


def score_road_frontage(road: str) -> float:
    """접도 상태 점수"""
    if not road:
        return 50
    road_scores = {
        "8m이상": 100,
        "6~8m": 85,
        "4~6m": 70,
        "4m미만": 40,
        "맹지": 10,
    }
    return road_scores.get(road, 50)


def score_topography(topo: str) -> float:
    """지형 점수"""
    if not topo:
        return 50
    topo_scores = {
        "평지": 100,
        "완경사": 75,
        "경사": 45,
    }
    return topo_scores.get(topo, 50)


def score_land_area(area_m2: float) -> float:
    """면적 적정성 점수 (단독주택 적정: 200~500㎡)"""
    if not area_m2:
        return 50
    if 200 <= area_m2 <= 500:
        return 100
    elif 150 <= area_m2 < 200:
        return 80
    elif 500 < area_m2 <= 700:
        return 80
    elif 100 <= area_m2 < 150:
        return 60
    elif 700 < area_m2 <= 1000:
        return 60
    elif area_m2 < 100:
        return 30
    else:
        return 40


class LandPropertyScorer:
    W_ZONING = 0.30
    W_BUILDABILITY = 0.25
    W_ROAD = 0.20
    W_TOPOGRAPHY = 0.15
    W_AREA = 0.10

    def score(self, zoning_type: str = None,
              building_coverage_ratio: float = None,
              floor_area_ratio: float = None,
              road_frontage: str = None,
              topography: str = None,
              area_m2: float = None, **kwargs) -> dict:

        s_zoning = score_zoning(zoning_type)
        s_build = score_buildability(building_coverage_ratio, floor_area_ratio)
        s_road = score_road_frontage(road_frontage)
        s_topo = score_topography(topography)
        s_area = score_land_area(area_m2)

        total = (s_zoning * self.W_ZONING +
                 s_build * self.W_BUILDABILITY +
                 s_road * self.W_ROAD +
                 s_topo * self.W_TOPOGRAPHY +
                 s_area * self.W_AREA)

        return {
            "total": round(total, 1),
            "zoning": round(s_zoning, 1),
            "buildability": round(s_build, 1),
            "road_frontage": round(s_road, 1),
            "topography": round(s_topo, 1),
            "land_area": round(s_area, 1),
        }
