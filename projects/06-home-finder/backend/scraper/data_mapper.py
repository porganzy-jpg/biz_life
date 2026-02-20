"""
데이터 매퍼 (Data Mapper)

Maps external data formats (Naver, KB) to our internal PropertyCreate schema.
Handles field mapping, unit conversion, data cleaning, and enrichment.
"""
import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger("homefinder.scraper.mapper")

# Naver property type to our PropertyType enum values
NAVER_TYPE_MAP: Dict[str, str] = {
    "아파트": "아파트",
    "오피스텔": "오피스텔",
    "빌라": "빌라",
    "연립다세대": "빌라",
    "단독/다가구": "단독",
    "전원주택": "전원주택",
    "타운하우스": "타운하우스",
    "토지": "토지",
}


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int."""
    if value is None:
        return default
    try:
        cleaned = str(value).replace(",", "").replace(" ", "").strip()
        if not cleaned:
            return default
        return int(float(cleaned))
    except (ValueError, TypeError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    if value is None:
        return default
    try:
        cleaned = str(value).replace(",", "").replace(" ", "").strip()
        if not cleaned:
            return default
        return float(cleaned)
    except (ValueError, TypeError):
        return default


def _parse_floor_info(floor_info: str) -> tuple:
    """
    Parse Naver floor info string like "12/20" into (floor, total_floors).

    Returns:
        (floor, total_floors) or (None, None) if unparseable.
    """
    if not floor_info:
        return None, None

    floor_str = str(floor_info).strip()
    if "/" in floor_str:
        parts = floor_str.split("/")
        try:
            floor = int(parts[0].strip()) if parts[0].strip() else None
            total = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else None
            return floor, total
        except ValueError:
            return None, None
    else:
        try:
            return int(floor_str), None
        except ValueError:
            return None, None


def _parse_naver_price(price_str: str) -> int:
    """
    Parse Naver price string to KRW (원).

    Naver prices are typically in 만원 (10,000 KRW units).
    Examples: "12,000" -> 120,000,000원, "85000" -> 850,000,000원

    Returns:
        Price in KRW (원).
    """
    if not price_str:
        return 0

    cleaned = str(price_str).replace(",", "").replace(" ", "").strip()

    # Handle "X억 Y" format (e.g., "12억 5000")
    if "억" in cleaned:
        parts = cleaned.split("억")
        eok = _safe_int(parts[0])
        man = _safe_int(parts[1]) if len(parts) > 1 else 0
        return (eok * 10000 + man) * 10000  # Convert 만원 to 원

    price_man = _safe_int(cleaned)
    return price_man * 10000  # 만원 -> 원


def _extract_built_year(data: Dict[str, Any]) -> Optional[int]:
    """Extract built year from various Naver data fields."""
    # Direct buildYear field
    built = data.get("buildYear") or data.get("approvalDate") or data.get("useApprovalDate")
    if built:
        year_str = str(built)[:4]
        try:
            year = int(year_str)
            if 1950 <= year <= 2030:
                return year
        except ValueError:
            pass

    # From articleConfirmYmd (registration date, not build year but fallback)
    return None


def map_naver_to_property(naver_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a Naver Real Estate article to a PropertyCreate-compatible dict.

    This maps Naver's field names and value formats to our standardized schema.

    Args:
        naver_data: Raw article dict from Naver API or mock data.

    Returns:
        Dict matching the PropertyCreate schema fields.
    """
    article_no = str(naver_data.get("articleNo", ""))
    if not article_no:
        logger.warning("Naver article has no articleNo, skipping")
        return {}

    # Property type mapping
    re_type_name = naver_data.get("realEstateTypeName", "아파트")
    property_type = NAVER_TYPE_MAP.get(re_type_name, "아파트")

    # Price (만원 -> 원)
    price_krw = _parse_naver_price(naver_data.get("dealOrWarrantPrc", "0"))

    # Areas (m2)
    area_m2 = _safe_float(naver_data.get("area2", 0))  # 전용면적
    area_supply_m2 = _safe_float(naver_data.get("area1", 0))  # 공급면적

    # For land, area2 might not be set separately
    if property_type == "토지" and area_m2 == 0:
        area_m2 = area_supply_m2

    # Price per m2
    price_per_m2 = int(price_krw / area_m2) if area_m2 > 0 and price_krw > 0 else 0

    # Floor info
    floor, total_floors = _parse_floor_info(naver_data.get("floorInfo", ""))

    # Coordinates
    lat = _safe_float(naver_data.get("latitude")) or None
    lng = _safe_float(naver_data.get("longitude")) or None

    # Dong (neighborhood)
    dong = (naver_data.get("dong") or "").strip()

    # Complex name
    complex_name = (naver_data.get("complexName") or "").strip()

    # Complex ID (if available)
    complex_id_raw = naver_data.get("complexNo") or naver_data.get("hscpNo")
    complex_id = _safe_int(complex_id_raw) if complex_id_raw else None

    # Direction
    direction = (naver_data.get("direction") or "").strip()

    # Built year
    built_year = _extract_built_year(naver_data)

    # Rooms / Bathrooms
    rooms = _safe_int(naver_data.get("roomCnt")) or None
    bathrooms = _safe_int(naver_data.get("bathroomCnt")) or None

    # Maintenance fee (in 만원)
    maintenance_raw = naver_data.get("maintenanceFee") or naver_data.get("managementFee")
    maintenance_fee = _safe_int(maintenance_raw) if maintenance_raw else None

    # Source URL
    source_url = f"https://new.land.naver.com/houses?articleNo={article_no}"

    # Description
    description = (naver_data.get("articleFeatureDesc") or "").strip()
    if not description:
        description = (naver_data.get("articleName") or "").strip()

    # Address construction
    address = (naver_data.get("articleName") or "").strip()

    # Build the property dict
    result = {
        "source": "naver",
        "source_id": article_no,
        "property_type": property_type,
        "acquisition_type": "매매",
        "city": "서울특별시",
        "district": naver_data.get("_district", ""),
        "dong": dong,
        "address": address,
        "lat": lat,
        "lng": lng,
        "price_krw": price_krw if price_krw > 0 else None,
        "price_per_m2": price_per_m2 if price_per_m2 > 0 else None,
        "area_m2": area_m2 if area_m2 > 0 else None,
        "area_supply_m2": area_supply_m2 if area_supply_m2 > 0 else None,
        "floor": floor,
        "total_floors": total_floors,
        "rooms": rooms,
        "bathrooms": bathrooms,
        "direction": direction if direction else None,
        "built_year": built_year,
        "maintenance_fee": maintenance_fee,
        "complex_name": complex_name if complex_name else None,
        "complex_id": complex_id,
        "source_url": source_url,
        "description": description if description else None,
    }

    # Land-specific fields
    if property_type == "토지":
        result["land_use"] = (naver_data.get("landUse") or naver_data.get("jimok") or "").strip() or None
        result["zoning_type"] = (naver_data.get("zoningType") or naver_data.get("yongdoJiyeok") or "").strip() or None
        result["building_coverage_ratio"] = _safe_float(naver_data.get("buildingCoverageRatio")) or None
        result["floor_area_ratio"] = _safe_float(naver_data.get("floorAreaRatio")) or None
        result["road_frontage"] = (naver_data.get("roadFrontage") or naver_data.get("jeobdo") or "").strip() or None
        result["topography"] = (naver_data.get("topography") or naver_data.get("jihyeong") or "").strip() or None

    # Remove None values for clean schema creation
    result = {k: v for k, v in result.items() if v is not None}

    # Ensure required fields are present
    if "source" not in result:
        result["source"] = "naver"
    if "property_type" not in result:
        result["property_type"] = "아파트"

    return result


def map_kb_to_property(kb_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert KB Real Estate price data to a PropertyCreate-compatible dict.

    KB data is primarily price/index data, not individual listings.
    This mapper is used when KB provides specific property/complex data
    that we want to import as a property record.

    Args:
        kb_data: Raw data dict from KB API.

    Returns:
        Dict matching the PropertyCreate schema fields.
    """
    complex_name = (kb_data.get("complexName") or kb_data.get("단지명") or "").strip()
    district = (kb_data.get("district") or kb_data.get("구") or "").strip()
    dong = (kb_data.get("dong") or kb_data.get("동") or "").strip()

    # Price handling: KB provides prices in 만원
    price_man = _safe_int(
        kb_data.get("price") or kb_data.get("매매가") or kb_data.get("dealPrice")
    )
    price_krw = price_man * 10000 if price_man > 0 else 0

    # Area
    area_m2 = _safe_float(
        kb_data.get("area") or kb_data.get("전용면적") or kb_data.get("exclusiveArea")
    )
    area_supply_m2 = _safe_float(
        kb_data.get("supplyArea") or kb_data.get("공급면적")
    )

    price_per_m2 = int(price_krw / area_m2) if area_m2 > 0 and price_krw > 0 else 0

    # Source ID from KB
    source_id = str(
        kb_data.get("complexCode")
        or kb_data.get("단지코드")
        or kb_data.get("kbComplexId")
        or ""
    ).strip()

    # Built year
    built_year_raw = kb_data.get("builtYear") or kb_data.get("건축년도") or kb_data.get("useApprovalYear")
    built_year = _safe_int(built_year_raw)
    if built_year and not (1950 <= built_year <= 2030):
        built_year = None

    # Coordinates
    lat = _safe_float(kb_data.get("lat") or kb_data.get("latitude")) or None
    lng = _safe_float(kb_data.get("lng") or kb_data.get("longitude")) or None

    result = {
        "source": "kb",
        "source_id": source_id if source_id else None,
        "property_type": NAVER_TYPE_MAP.get(
            kb_data.get("propertyType", kb_data.get("매물유형", "아파트")),
            "아파트",
        ),
        "acquisition_type": "매매",
        "city": "서울특별시",
        "district": district if district else None,
        "dong": dong if dong else None,
        "address": complex_name,
        "complex_name": complex_name if complex_name else None,
        "lat": lat,
        "lng": lng,
        "price_krw": price_krw if price_krw > 0 else None,
        "price_per_m2": price_per_m2 if price_per_m2 > 0 else None,
        "area_m2": area_m2 if area_m2 > 0 else None,
        "area_supply_m2": area_supply_m2 if area_supply_m2 > 0 else None,
        "built_year": built_year,
        "source_url": f"https://kbland.kr/complex/{source_id}" if source_id else None,
        "description": kb_data.get("description") or kb_data.get("비고"),
    }

    # Remove None values
    result = {k: v for k, v in result.items() if v is not None}

    # Ensure required fields
    if "source" not in result:
        result["source"] = "kb"
    if "property_type" not in result:
        result["property_type"] = "아파트"

    return result
