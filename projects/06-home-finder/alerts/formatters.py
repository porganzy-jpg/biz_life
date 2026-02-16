"""
HomeFinder - 한국어 가격/매물 포맷터
텔레그램 알림 및 리포트용 메시지 생성
"""
from datetime import date, datetime
from typing import Optional


def format_price_kr(price_krw: int) -> str:
    """가격을 한국어로 포맷 (예: 850000000 -> "8억 5,000만")"""
    if not price_krw:
        return "가격미정"
    eok = price_krw // 100000000  # 억
    man = (price_krw % 100000000) // 10000  # 만
    if eok > 0 and man > 0:
        return f"{eok}억 {man:,}만"
    elif eok > 0:
        return f"{eok}억"
    elif man > 0:
        return f"{man:,}만"
    return str(price_krw)


def format_price_change(old_price: int, new_price: int) -> str:
    """가격 변동 포맷 (예: "12억 -> 11억 5,000만 (-4.2%)")"""
    if not old_price or not new_price:
        return ""
    diff = new_price - old_price
    pct = (diff / old_price) * 100 if old_price > 0 else 0
    arrow = "\u2b06" if diff > 0 else "\u2b07" if diff < 0 else "\u27a1"
    sign = "+" if diff > 0 else ""
    return (
        f"{format_price_kr(old_price)} {arrow} {format_price_kr(new_price)} "
        f"({sign}{pct:.1f}%)"
    )


def format_area(area_m2: Optional[float]) -> str:
    """면적 포맷 (예: 84.5 -> "84.5㎡(25.6평)")"""
    if not area_m2:
        return ""
    pyeong = area_m2 * 0.3025
    return f"{area_m2:.1f}\u33a1({pyeong:.1f}평)"


def format_discount_rate(rate: Optional[float]) -> str:
    """할인율 포맷 (예: 30.5 -> "30.5%")"""
    if rate is None:
        return ""
    return f"{rate:.1f}%"


def format_date_kr(d: Optional[date]) -> str:
    """날짜를 한국어 포맷 (예: 2026-03-15 -> "2026-03-15")"""
    if d is None:
        return "미정"
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%Y-%m-%d")


def format_property_card(prop) -> str:
    """
    매물 카드 (텔레그램용)

    Args:
        prop: Property ORM object or dict-like object with attributes:
              property_type, complex_name, district, dong, price_krw,
              area_m2, score_composite, nearest_subway_name,
              nearest_subway_distance, nearest_subway_lines,
              nearest_park_name, nearest_park_distance
    """
    def _get(key, default=""):
        if hasattr(prop, key):
            val = getattr(prop, key)
            return val if val is not None else default
        elif isinstance(prop, dict):
            return prop.get(key, default)
        return default

    prop_type = _get("property_type", "아파트")
    complex_name = _get("complex_name", "")
    address_line = _get("address", "")
    district = _get("district", "")
    dong = _get("dong", "")
    price_krw = _get("price_krw", 0)
    area_m2 = _get("area_m2", 0)
    score = _get("score_composite")
    subway_name = _get("nearest_subway_name", "")
    subway_dist = _get("nearest_subway_distance")
    subway_lines = _get("nearest_subway_lines", "")
    park_name = _get("nearest_park_name", "")
    park_dist = _get("nearest_park_distance")
    floor = _get("floor")
    direction = _get("direction", "")
    prop_id = _get("id", "")

    # Title line
    title = complex_name or address_line or f"{district} {dong}"
    lines = [f"\U0001f3e0 [{prop_type}] {title}"]

    # Location
    location_parts = [p for p in [district, dong] if p]
    if location_parts:
        lines.append(f"\U0001f4cd {' '.join(location_parts)}")

    # Price + area
    price_str = format_price_kr(price_krw)
    area_str = format_area(area_m2) if area_m2 else ""
    price_line = f"\U0001f4b0 {price_str}"
    if area_str:
        price_line += f" ({area_str})"
    lines.append(price_line)

    # Floor / direction
    detail_parts = []
    if floor:
        detail_parts.append(f"{floor}층")
    if direction:
        detail_parts.append(direction)
    if detail_parts:
        lines.append(f"\U0001f3e2 {' / '.join(detail_parts)}")

    # Score
    if score is not None and score > 0:
        lines.append(f"\U0001f4ca 종합점수: {score:.1f}")

    # Nearest subway
    if subway_name:
        dist_str = f"{int(subway_dist)}m" if subway_dist else ""
        line_str = f" ({subway_lines})" if subway_lines else ""
        lines.append(f"\U0001f687 {subway_name}역 {dist_str}{line_str}")

    # Nearest park
    if park_name:
        dist_str = f"{int(park_dist)}m" if park_dist else ""
        lines.append(f"\U0001f333 {park_name} {dist_str}")

    # Property ID
    if prop_id:
        lines.append(f"\U0001f4ce ID: {prop_id}")

    return "\n".join(lines)


def format_comparison_table(prop1, prop2) -> str:
    """
    두 매물 비교표 (텔레그램용)

    Args:
        prop1, prop2: Property ORM objects or dict-like objects
    """
    def _get(obj, key, default=""):
        if hasattr(obj, key):
            val = getattr(obj, key)
            return val if val is not None else default
        elif isinstance(obj, dict):
            return obj.get(key, default)
        return default

    name1 = _get(prop1, "complex_name") or _get(prop1, "address", "매물1")
    name2 = _get(prop2, "complex_name") or _get(prop2, "address", "매물2")

    separator = "\u2501" * 26
    lines = [
        f"\u2696 매물 비교",
        separator,
        f"{'항목':^8} | {name1[:8]:^8} | {name2[:8]:^8}",
        "\u2500" * 26,
    ]

    # Price
    p1 = format_price_kr(_get(prop1, "price_krw", 0))
    p2 = format_price_kr(_get(prop2, "price_krw", 0))
    lines.append(f"{'가격':^8} | {p1:^8} | {p2:^8}")

    # Area
    a1 = _get(prop1, "area_m2", 0)
    a2 = _get(prop2, "area_m2", 0)
    a1_str = f"{a1:.0f}\u33a1" if a1 else "-"
    a2_str = f"{a2:.0f}\u33a1" if a2 else "-"
    lines.append(f"{'면적':^8} | {a1_str:^8} | {a2_str:^8}")

    # Floor
    f1 = str(_get(prop1, "floor", "-"))
    f2 = str(_get(prop2, "floor", "-"))
    lines.append(f"{'층수':^8} | {f1 + '층':^8} | {f2 + '층':^8}")

    # Built year
    b1 = str(_get(prop1, "built_year", "-"))
    b2 = str(_get(prop2, "built_year", "-"))
    lines.append(f"{'건축년도':^8} | {b1:^8} | {b2:^8}")

    # Direction
    d1 = _get(prop1, "direction", "-") or "-"
    d2 = _get(prop2, "direction", "-") or "-"
    lines.append(f"{'향':^8} | {d1:^8} | {d2:^8}")

    # Score
    s1 = _get(prop1, "score_composite")
    s2 = _get(prop2, "score_composite")
    s1_str = f"{s1:.1f}" if s1 else "-"
    s2_str = f"{s2:.1f}" if s2 else "-"
    lines.append(f"{'점수':^8} | {s1_str:^8} | {s2_str:^8}")

    # Subway
    sw1 = _get(prop1, "nearest_subway_name", "-") or "-"
    sw2 = _get(prop2, "nearest_subway_name", "-") or "-"
    sd1 = _get(prop1, "nearest_subway_distance")
    sd2 = _get(prop2, "nearest_subway_distance")
    sw1_str = f"{sw1}({int(sd1)}m)" if sd1 else sw1
    sw2_str = f"{sw2}({int(sd2)}m)" if sd2 else sw2
    lines.append(f"{'지하철':^8} | {sw1_str:^8} | {sw2_str:^8}")

    lines.append(separator)

    # Verdict
    if s1 and s2:
        if s1 > s2:
            lines.append(f"\u2b50 {name1} 점수 우위 (+{s1 - s2:.1f})")
        elif s2 > s1:
            lines.append(f"\u2b50 {name2} 점수 우위 (+{s2 - s1:.1f})")
        else:
            lines.append("\u2b50 두 매물 점수 동일")

    return "\n".join(lines)


def format_auction_card(auction) -> str:
    """
    경매 물건 카드 (텔레그램용)

    Args:
        auction: AuctionListing ORM object or dict-like object
    """
    def _get(key, default=""):
        if hasattr(auction, key):
            val = getattr(auction, key)
            return val if val is not None else default
        elif isinstance(auction, dict):
            return auction.get(key, default)
        return default

    district = _get("district", "")
    dong = _get("dong", "")
    address = _get("address", "")
    case_number = _get("case_number", "")
    court = _get("court", "")
    appraisal = _get("appraisal_price", 0)
    minimum_bid = _get("minimum_bid", 0)
    discount = _get("discount_rate")
    auction_date = _get("auction_date")
    status = _get("auction_status", "")
    risk_level = _get("risk_level", "")
    area_m2 = _get("area_m2")
    bid_round = _get("current_bid_round", 1)

    location = f"{district} {dong}".strip() or address
    lines = [f"\U0001f528 [경매] {location}"]

    if case_number:
        lines.append(f"\U0001f4cb 사건번호: {case_number}")
    if court:
        lines.append(f"\U0001f3db 법원: {court}")

    # Prices
    if appraisal:
        lines.append(f"\U0001f4b0 감정가: {format_price_kr(appraisal)}")
    if minimum_bid:
        lines.append(f"\U0001f4b0 최저가: {format_price_kr(minimum_bid)}")

    # Discount rate
    if discount is not None and discount > 0:
        lines.append(f"\U0001f4c9 할인율: {format_discount_rate(discount)}")

    # Area
    if area_m2:
        lines.append(f"\U0001f4d0 면적: {format_area(area_m2)}")

    # Bid round
    if bid_round and bid_round > 1:
        lines.append(f"\U0001f504 {bid_round}회차")

    # Auction date
    if auction_date:
        lines.append(f"\U0001f4c5 경매일: {format_date_kr(auction_date)}")

    # Status
    if status:
        lines.append(f"\U0001f4cc 상태: {status}")

    # Risk
    if risk_level:
        risk_emoji = {
            "낮음": "\U0001f7e2",
            "보통": "\U0001f7e1",
            "높음": "\U0001f534",
        }.get(risk_level, "\u26aa")
        lines.append(f"{risk_emoji} 위험도: {risk_level}")

    return "\n".join(lines)


def format_subscription_card(sub) -> str:
    """
    청약 정보 카드 (텔레그램용)

    Args:
        sub: SubscriptionOpportunity ORM object or dict-like object
    """
    def _get(key, default=""):
        if hasattr(sub, key):
            val = getattr(sub, key)
            return val if val is not None else default
        elif isinstance(sub, dict):
            return sub.get(key, default)
        return default

    name = _get("name", "")
    district = _get("district", "")
    dong = _get("dong", "")
    address = _get("address", "")
    min_price = _get("min_price", 0)
    max_price = _get("max_price", 0)
    sub_start = _get("subscription_start")
    sub_end = _get("subscription_end")
    announcement = _get("announcement_date")
    move_in = _get("move_in_date")
    competition = _get("competition_rate")
    total_units = _get("total_units")
    sub_units = _get("subscription_units")
    status = _get("status", "")
    developer = _get("developer", "")

    lines = [f"\U0001f3d7 [청약] {name}"]

    # Location
    location = f"{district} {dong}".strip() or address
    if location:
        lines.append(f"\U0001f4cd {location}")

    # Developer
    if developer:
        lines.append(f"\U0001f3e2 시행사: {developer}")

    # Price range
    if min_price and max_price:
        lines.append(f"\U0001f4b0 {format_price_kr(min_price)}~{format_price_kr(max_price)}")
    elif min_price:
        lines.append(f"\U0001f4b0 {format_price_kr(min_price)}~")
    elif max_price:
        lines.append(f"\U0001f4b0 ~{format_price_kr(max_price)}")

    # Units
    if total_units:
        unit_str = f"총 {total_units}세대"
        if sub_units:
            unit_str += f" (청약 {sub_units}세대)"
        lines.append(f"\U0001f3e0 {unit_str}")

    # Dates
    if sub_start and sub_end:
        lines.append(
            f"\U0001f4c5 접수: {format_date_kr(sub_start)} ~ {format_date_kr(sub_end)}"
        )
    elif sub_start:
        lines.append(f"\U0001f4c5 접수시작: {format_date_kr(sub_start)}")

    if announcement:
        lines.append(f"\U0001f4e2 당첨발표: {format_date_kr(announcement)}")

    if move_in:
        lines.append(f"\U0001f3e1 입주: {format_date_kr(move_in)}")

    # Competition rate
    if competition:
        lines.append(f"\U0001f3c6 경쟁률: {competition:.1f}:1")

    # Status
    if status:
        status_emoji = {
            "접수중": "\U0001f7e2",
            "마감": "\U0001f534",
            "당첨발표": "\U0001f4e2",
        }.get(status, "\u26aa")
        lines.append(f"{status_emoji} 상태: {status}")

    return "\n".join(lines)


def format_pipeline_summary(counts: dict) -> str:
    """
    파이프라인 현황 요약

    Args:
        counts: dict mapping status -> count
                e.g. {"발견": 45, "조사": 12, "관심": 8, ...}
    """
    status_order = ["발견", "조사", "관심", "방문예정", "방문완료", "결정"]
    total = sum(counts.values())

    lines = [
        "\U0001f4ca 후보 파이프라인 현황",
        "\u2501" * 24,
    ]
    for status in status_order:
        count = counts.get(status, 0)
        bar = "\u2588" * min(count, 20)
        lines.append(f"  {status:<6} | {count:>3}건 {bar}")

    lines.append("\u2500" * 24)
    lines.append(f"  합계: {total}건")

    return "\n".join(lines)


def format_daily_report(
    new_properties: int,
    price_changes: int,
    new_auctions: int,
    upcoming_subs: int,
    top_properties: list,
) -> str:
    """일일 리포트 포맷"""
    today_str = date.today().strftime("%Y-%m-%d")

    lines = [
        f"\U0001f4c8 HomeFinder 일일 리포트 ({today_str})",
        "\u2501" * 30,
        "",
        f"\U0001f195 신규 매물: {new_properties}건",
        f"\U0001f4b1 가격변동: {price_changes}건",
        f"\U0001f528 신규 경매: {new_auctions}건",
        f"\U0001f3d7 접수중 청약: {upcoming_subs}건",
    ]

    if top_properties:
        lines.append("")
        lines.append("\u2b50 오늘의 TOP 매물:")
        for i, prop in enumerate(top_properties[:5], 1):
            name = ""
            score = 0
            price = 0
            if hasattr(prop, "complex_name"):
                name = prop.complex_name or prop.address or ""
                score = prop.score_composite or 0
                price = prop.price_krw or 0
            elif isinstance(prop, dict):
                name = prop.get("complex_name") or prop.get("address", "")
                score = prop.get("score_composite", 0)
                price = prop.get("price_krw", 0)
            lines.append(
                f"  {i}. {name} - {format_price_kr(price)} (점수: {score:.1f})"
            )

    return "\n".join(lines)


def format_weekly_report(
    total_properties: int,
    new_this_week: int,
    pipeline_counts: dict,
    price_trend: str,
    top_districts: list,
) -> str:
    """주간 리포트 포맷"""
    today_str = date.today().strftime("%Y-%m-%d")

    lines = [
        f"\U0001f4ca HomeFinder 주간 리포트 ({today_str})",
        "\u2501" * 30,
        "",
        f"\U0001f4e6 전체 매물: {total_properties}건",
        f"\U0001f195 금주 신규: {new_this_week}건",
        f"\U0001f4c8 시장동향: {price_trend}",
        "",
    ]

    # Pipeline summary
    if pipeline_counts:
        lines.append(format_pipeline_summary(pipeline_counts))
        lines.append("")

    # Top districts
    if top_districts:
        lines.append("\U0001f3d9 구별 매물 현황:")
        for district_info in top_districts[:5]:
            if isinstance(district_info, dict):
                name = district_info.get("district", "")
                count = district_info.get("count", 0)
                avg_score = district_info.get("avg_score", 0)
                lines.append(f"  {name}: {count}건 (평균점수: {avg_score:.1f})")
            elif isinstance(district_info, (list, tuple)) and len(district_info) >= 2:
                lines.append(f"  {district_info[0]}: {district_info[1]}건")

    return "\n".join(lines)


def format_match_alert(search_name: str, properties: list) -> str:
    """저장검색 매칭 알림 포맷"""
    count = len(properties)
    lines = [
        f"\U0001f50d 저장검색 매칭: [{search_name}]",
        f"\U0001f4e9 {count}건의 새 매물이 조건에 맞습니다.",
        "\u2500" * 24,
    ]

    for i, prop in enumerate(properties[:5], 1):
        name = ""
        price = 0
        district = ""
        if hasattr(prop, "complex_name"):
            name = prop.complex_name or prop.address or ""
            price = prop.price_krw or 0
            district = prop.district or ""
        elif isinstance(prop, dict):
            name = prop.get("complex_name") or prop.get("address", "")
            price = prop.get("price_krw", 0)
            district = prop.get("district", "")

        lines.append(f"  {i}. [{district}] {name} - {format_price_kr(price)}")

    if count > 5:
        lines.append(f"  ... 외 {count - 5}건")

    return "\n".join(lines)
