"""
위치 점수 (0~100)
- 지하철 거리 (35%): <400m=100, <800m=80, <1200m=50
- 한강 거리 (20%): <500m=100, <1km=80, <2km=50
- 공원 거리 (15%): <300m=100, <800m=70
- 접근 노선 수 (15%): 3+=100, 2=80, 1=60
- 학군 (15%): 1km 이내 학교 수 기반
"""
from scoring.geo_utils import haversine, find_nearest, count_within_radius


def score_subway_distance(distance_m: float) -> float:
    if distance_m is None:
        return 0
    if distance_m < 400:
        return 100
    elif distance_m < 600:
        return 90
    elif distance_m < 800:
        return 80
    elif distance_m < 1000:
        return 65
    elif distance_m < 1200:
        return 50
    elif distance_m < 1500:
        return 35
    elif distance_m < 2000:
        return 20
    else:
        return 10


def score_river_distance(distance_m: float) -> float:
    if distance_m is None:
        return 0
    if distance_m < 500:
        return 100
    elif distance_m < 1000:
        return 80
    elif distance_m < 1500:
        return 65
    elif distance_m < 2000:
        return 50
    elif distance_m < 3000:
        return 35
    elif distance_m < 5000:
        return 20
    else:
        return 10


def score_park_distance(distance_m: float) -> float:
    if distance_m is None:
        return 0
    if distance_m < 300:
        return 100
    elif distance_m < 500:
        return 85
    elif distance_m < 800:
        return 70
    elif distance_m < 1200:
        return 50
    elif distance_m < 2000:
        return 30
    else:
        return 10


def score_line_count(line_count: int) -> float:
    if line_count >= 3:
        return 100
    elif line_count == 2:
        return 80
    elif line_count == 1:
        return 60
    else:
        return 20


def score_school_count(count: int) -> float:
    """1km 이내 학교 수 기반 점수"""
    if count >= 10:
        return 100
    elif count >= 7:
        return 85
    elif count >= 5:
        return 70
    elif count >= 3:
        return 55
    elif count >= 1:
        return 40
    else:
        return 15


class LocationScorer:
    W_SUBWAY = 0.35
    W_RIVER = 0.20
    W_PARK = 0.15
    W_LINES = 0.15
    W_SCHOOL = 0.15

    def __init__(self, subway_stations: list, parks: list, river_points: list, schools: list = None):
        self.subway_stations = subway_stations
        self.parks = parks
        self.river_points = river_points
        self.schools = schools or []

    def score(self, lat: float, lng: float) -> dict:
        if lat is None or lng is None:
            return {"total": 0, "subway": 0, "river": 0, "park": 0, "lines": 0,
                    "school": 0, "nearby_school_count": 0,
                    "nearest_subway": None, "subway_distance": None,
                    "nearest_park": None, "park_distance": None,
                    "river_distance": None, "line_count": 0}

        # Nearest subway
        nearest_subs = find_nearest(lat, lng, self.subway_stations, top_n=5)
        subway_dist = nearest_subs[0][1] if nearest_subs else None
        nearest_subway = nearest_subs[0][0] if nearest_subs else None

        # Count unique subway lines within 1km
        lines_nearby = set()
        for station, dist in nearest_subs:
            if dist <= 1000:
                if hasattr(station, "line"):
                    lines_nearby.add(station.line)
                elif isinstance(station, dict):
                    lines_nearby.add(station.get("line", ""))

        # Nearest river point
        nearest_rivers = find_nearest(lat, lng, self.river_points, top_n=1)
        river_dist = nearest_rivers[0][1] if nearest_rivers else None

        # Nearest park
        nearest_parks = find_nearest(lat, lng, self.parks, top_n=1)
        park_dist = nearest_parks[0][1] if nearest_parks else None
        nearest_park = nearest_parks[0][0] if nearest_parks else None

        # Schools within 1km
        nearby_school_count = 0
        if self.schools:
            nearby_school_count = count_within_radius(lat, lng, self.schools, radius_m=1000)

        s_subway = score_subway_distance(subway_dist)
        s_river = score_river_distance(river_dist)
        s_park = score_park_distance(park_dist)
        s_lines = score_line_count(len(lines_nearby))
        s_school = score_school_count(nearby_school_count)

        total = (s_subway * self.W_SUBWAY +
                 s_river * self.W_RIVER +
                 s_park * self.W_PARK +
                 s_lines * self.W_LINES +
                 s_school * self.W_SCHOOL)

        subway_name = None
        subway_lines_str = None
        if nearest_subway:
            subway_name = getattr(nearest_subway, "name", None) or nearest_subway.get("name")
            subway_lines_str = ",".join(sorted(lines_nearby))

        park_name = None
        if nearest_park:
            park_name = getattr(nearest_park, "name", None) or nearest_park.get("name")

        return {
            "total": round(total, 1),
            "subway": round(s_subway, 1),
            "river": round(s_river, 1),
            "park": round(s_park, 1),
            "lines": round(s_lines, 1),
            "school": round(s_school, 1),
            "nearby_school_count": nearby_school_count,
            "nearest_subway": subway_name,
            "subway_distance": round(subway_dist, 0) if subway_dist else None,
            "subway_lines": subway_lines_str,
            "nearest_park": park_name,
            "park_distance": round(park_dist, 0) if park_dist else None,
            "river_distance": round(river_dist, 0) if river_dist else None,
            "line_count": len(lines_nearby),
        }
