"""
Haversine 거리 계산 + 도보시간 추정
"""
import math
from typing import Tuple

# 평균 도보 속도 (km/h)
WALKING_SPEED_KMH = 4.5


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    두 좌표 간 거리 (미터)

    Args:
        lat1, lng1: 좌표 1
        lat2, lng2: 좌표 2

    Returns:
        거리 (meters)
    """
    R = 6371000  # 지구 반경 (m)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def walking_minutes(distance_m: float) -> float:
    """도보 시간 (분)"""
    return (distance_m / 1000) / WALKING_SPEED_KMH * 60


def bounding_box(lat: float, lng: float, radius_km: float) -> Tuple[float, float, float, float]:
    """
    주어진 좌표 주변 바운딩 박스

    Returns:
        (lat_min, lat_max, lng_min, lng_max)
    """
    lat_range = radius_km / 111.0
    lng_range = radius_km / (111.0 * math.cos(math.radians(lat)))
    return (
        lat - lat_range,
        lat + lat_range,
        lng - lng_range,
        lng + lng_range,
    )


def find_nearest(target_lat: float, target_lng: float,
                 points: list, lat_key: str = "lat", lng_key: str = "lng",
                 top_n: int = 1) -> list:
    """
    가장 가까운 포인트 N개 찾기

    Args:
        target_lat, target_lng: 기준 좌표
        points: dict/object 리스트
        lat_key, lng_key: 좌표 키 이름
        top_n: 반환 개수

    Returns:
        [(point, distance_m), ...] 거리순 정렬
    """
    results = []
    for p in points:
        if hasattr(p, lat_key):
            plat = getattr(p, lat_key)
            plng = getattr(p, lng_key)
        else:
            plat = p[lat_key]
            plng = p[lng_key]

        if plat is None or plng is None:
            continue

        dist = haversine(target_lat, target_lng, plat, plng)
        results.append((p, dist))

    results.sort(key=lambda x: x[1])
    return results[:top_n]


def count_within_radius(target_lat: float, target_lng: float,
                        points: list, radius_m: float,
                        lat_key: str = "lat", lng_key: str = "lng") -> int:
    """반경 내 포인트 개수"""
    count = 0
    for p in points:
        if hasattr(p, lat_key):
            plat = getattr(p, lat_key)
            plng = getattr(p, lng_key)
        else:
            plat = p[lat_key]
            plng = p[lng_key]

        if plat is None or plng is None:
            continue

        if haversine(target_lat, target_lng, plat, plng) <= radius_m:
            count += 1
    return count
