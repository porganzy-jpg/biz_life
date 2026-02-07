"""
PromoMap 지오펜싱 로직

GPS 좌표 기반 반경 계산 및 진입 감지
"""
import math
from typing import List, Tuple


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    두 GPS 좌표 사이의 거리 계산 (미터)
    Haversine 공식 사용
    """
    R = 6371000  # 지구 반경 (미터)

    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def find_nearby_stores(user_lat: float, user_lon: float,
                       stores: list, radius_m: float = 100.0) -> list:
    """
    주어진 반경 내 매장 찾기

    Args:
        user_lat, user_lon: 사용자 GPS 좌표
        stores: 매장 목록 (latitude, longitude 속성 필요)
        radius_m: 검색 반경 (미터)

    Returns:
        list: (store, distance_m) 튜플 리스트 (거리순 정렬)
    """
    nearby = []
    for store in stores:
        dist = haversine_distance(user_lat, user_lon, store.latitude, store.longitude)
        if dist <= radius_m:
            nearby.append((store, round(dist, 1)))

    return sorted(nearby, key=lambda x: x[1])


def check_geofence_entry(user_lat: float, user_lon: float,
                         store_lat: float, store_lon: float,
                         radius_m: float = 100.0) -> Tuple[bool, float]:
    """
    지오펜스 진입 여부 확인

    Returns:
        (bool, float): (진입 여부, 거리)
    """
    dist = haversine_distance(user_lat, user_lon, store_lat, store_lon)
    return dist <= radius_m, round(dist, 1)


def get_bounding_box(lat: float, lon: float, radius_m: float) -> dict:
    """
    GPS 좌표 주변 바운딩 박스 계산 (DB 쿼리 최적화용)

    Returns:
        dict: {min_lat, max_lat, min_lon, max_lon}
    """
    lat_delta = radius_m / 111320  # 위도 1도 ≈ 111.32km
    lon_delta = radius_m / (111320 * math.cos(math.radians(lat)))

    return {
        "min_lat": lat - lat_delta,
        "max_lat": lat + lat_delta,
        "min_lon": lon - lon_delta,
        "max_lon": lon + lon_delta,
    }
