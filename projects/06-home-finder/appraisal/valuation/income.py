"""
수익환원법 (Income Capitalization) — 상가 가치평가의 본령

    자산가치 = NOI ÷ Cap Rate

상가는 아파트와 달리 "동일 규격 대체재"가 없다. 같은 건물 1층과 3층이
3배 차이 나는 이유는 면적이 아니라 벌어들이는 순영업소득(NOI)이 다르기 때문이다.
따라서 비교사례가 아니라 수익이 가치를 결정한다.

NOI 산출 흐름:
    잠재총수입(PGI) = 연 임대료 + 보증금 운용수익
    유효총수입(EGI) = PGI × (1 − 공실률)
    순영업소득(NOI) = EGI − 운영비 − 재산세
"""
from appraisal import constants as C
from appraisal.inputs import PropertyInput


# 층별 임대료 계수 — 1층을 1.0으로 둔 상대값.
# 상가 임대시장의 경험칙이며, 지하/고층으로 갈수록 급격히 낮아진다.
FLOOR_RENT_FACTOR = {
    -1: 0.45,
    1: 1.00,
    2: 0.42,
    3: 0.30,
}
FLOOR_RENT_FACTOR_UPPER = 0.25  # 4층 이상


def floor_factor(floor: int | None) -> float:
    if floor is None:
        return FLOOR_RENT_FACTOR[1]
    if floor >= 4:
        return FLOOR_RENT_FACTOR_UPPER
    return FLOOR_RENT_FACTOR.get(floor, FLOOR_RENT_FACTOR_UPPER)


def resolve_cap_rate(prop: PropertyInput) -> tuple[float, str]:
    """
    Cap Rate 결정. 상권 등급이 곧 위험 등급이다.

    등급 미입력 시 기본 C등급을 쓰되, 코너·1층·광폭 접도 같은
    가치 상승 요인이 있으면 한 단계 상향(= Cap Rate 하향)한다.
    """
    grade = prop.cap_grade
    reason = "사용자 입력"

    if not grade:
        grade = C.DEFAULT_CAP_GRADE
        reason = f"미입력 → 기본값 {grade}등급"

        bonus = 0
        if prop.is_first_floor:
            bonus += 1
        if prop.is_corner:
            bonus += 1
        if prop.road_width_m and prop.road_width_m >= 12:
            bonus += 1

        if bonus >= 2:
            grades = ["A", "B", "C", "D"]
            idx = max(0, grades.index(grade) - 1)
            grade = grades[idx]
            reason = f"입지 가점({bonus}) → {grade}등급 상향"

    return C.CAP_RATE_BY_GRADE[grade], f"{grade}등급 ({reason})"


def calculate_noi(prop: PropertyInput, vacancy_rate: float | None = None) -> dict:
    """순영업소득(NOI) 산출"""
    rent = prop.rent

    annual_rent = rent.monthly_rent_krw * 12
    deposit_income = int(rent.deposit_krw * C.DEPOSIT_YIELD)
    pgi = annual_rent + deposit_income

    if vacancy_rate is None:
        grade = prop.cap_grade or C.DEFAULT_CAP_GRADE
        vacancy_rate = C.VACANCY_BY_GRADE[grade]

    egi = int(pgi * (1 - vacancy_rate))

    from appraisal.costs import annual_operating_expenses
    opex = annual_operating_expenses(egi)

    noi = egi - opex["total"]

    return {
        "annual_rent": annual_rent,
        "deposit_income": deposit_income,
        "pgi": pgi,
        "vacancy_rate": vacancy_rate,
        "vacancy_loss": pgi - egi,
        "egi": egi,
        "opex": opex,
        "noi": noi,
    }


def appraise(prop: PropertyInput) -> dict:
    """
    수익환원법 평가.

    공실 물건이거나 임대료 정보가 없으면 평가 불가로 반환한다.
    (추정 임대료로 대체하는 건 시장 데이터 연동 후 Phase 2에서 처리)
    """
    if prop.rent.monthly_rent_krw <= 0:
        return {
            "method": "수익환원법",
            "applicable": False,
            "reason": "임대료 정보 없음 (공실이거나 미입력)",
            "value": None,
        }

    noi_detail = calculate_noi(prop)
    cap_rate, cap_desc = resolve_cap_rate(prop)

    value = int(noi_detail["noi"] / cap_rate)

    # 실제 매수가 기준 수익률 — 호가가 합리적인지 보는 첫 신호
    going_in_cap = (
        round(noi_detail["noi"] / prop.asking_price_krw, 4)
        if prop.asking_price_krw else None
    )

    return {
        "method": "수익환원법",
        "applicable": True,
        "value": value,
        "noi": noi_detail["noi"],
        "noi_detail": noi_detail,
        "cap_rate": cap_rate,
        "cap_rate_desc": cap_desc,
        "going_in_cap_rate": going_in_cap,
        "verdict": _judge(going_in_cap, cap_rate),
    }


def _judge(going_in: float | None, market_cap: float) -> str:
    """
    실효 Cap Rate가 시장 Cap Rate보다 높으면 = 같은 수익을 싸게 사는 것.
    """
    if going_in is None:
        return "판단불가"
    gap = going_in - market_cap
    if gap >= 0.010:
        return "수익률 우수 (시장 대비 저가)"
    if gap >= 0.002:
        return "적정"
    if gap >= -0.005:
        return "다소 비쌈"
    return "고평가 (수익 대비 과한 가격)"
