"""
투자 심사 엔진 — 취득·보유·처분 단계 비용 계산

매수가만 보면 실제 투입 자본을 20% 가까이 과소평가하게 된다.
상가는 취득세만 4.6%이고, 매도 시 양도세까지 합치면 왕복 거래비용이
수익률을 결정적으로 갉아먹는다. 그래서 세 단계를 모두 명시적으로 계산한다.
"""
from appraisal import constants as C


# ─────────────────────────────────────────────────────────
# 1. 취득 단계
# ─────────────────────────────────────────────────────────
def acquisition_costs(
    price_krw: int,
    asset_type: str = C.ASSET_COMMERCIAL_UNIT,
    building_ratio: float = 0.5,
    vat_refundable: bool = C.DEFAULT_VAT_REFUNDABLE,
) -> dict:
    """
    매수 시 발생하는 부대비용 일체.

    Args:
        building_ratio: 매매가 중 건물분 비율 (부가세 과세 대상).
                        토지는 부가세 면세라 안분이 필요하다.
        vat_refundable: 일반과세자 등록으로 매입세액 환급 가능 여부.
                        환급되면 최종 부담은 0이지만 초기 현금은 묶인다.
    """
    acq_tax = int(price_krw * C.ACQ_TAX_TOTAL_NON_HOUSING)

    broker = int(price_krw * C.BROKER_FEE_RATE_NON_HOUSING)
    broker_vat = int(broker * C.BROKER_FEE_VAT)

    legal = max(int(price_krw * C.LEGAL_FEE_RATE), C.LEGAL_FEE_MIN)

    building_value = int(price_krw * building_ratio)
    vat = int(building_value * C.VAT_RATE)
    vat_burden = 0 if vat_refundable else vat

    total = acq_tax + broker + broker_vat + legal + vat_burden

    return {
        "acquisition_tax": acq_tax,
        "broker_fee": broker + broker_vat,
        "legal_fee": legal,
        "vat_on_building": vat,
        "vat_burden": vat_burden,
        "vat_refundable": vat_refundable,
        "total": total,
        "rate_of_price": round(total / price_krw, 4) if price_krw else 0,
    }


# ─────────────────────────────────────────────────────────
# 2. 보유 단계 (연간)
# ─────────────────────────────────────────────────────────
def _progressive_tax(base: int, brackets) -> int:
    """누진공제 방식 세액 계산"""
    for limit, rate, deduction in brackets:
        if base <= limit:
            return max(0, int(base * rate - deduction))
    return 0


def annual_property_tax(
    building_assessed_krw: int,
    land_assessed_krw: int,
) -> dict:
    """
    재산세 + 지방교육세 + 종부세(별도합산토지).

    과세표준은 시가표준액(공시가격)에 공정시장가액비율 70%를 곱해 구한다.
    실거래가가 아니라 공시가격 기준이라는 점이 중요하다 — 통상 시세의 60~70% 수준.
    """
    bldg_base = int(building_assessed_krw * C.PROPERTY_TAX_FAIR_RATIO)
    land_base = int(land_assessed_krw * C.PROPERTY_TAX_FAIR_RATIO)

    bldg_tax = int(bldg_base * C.PROPERTY_TAX_BUILDING_RATE)
    land_tax = _progressive_tax(land_base, C.LAND_TAX_BRACKETS)

    property_tax = bldg_tax + land_tax
    edu_tax = int(property_tax * C.LOCAL_EDU_TAX_ON_PROPERTY_TAX)

    # 종부세: 별도합산토지 공시가 80억 초과분
    ctax = 0
    if land_assessed_krw > C.CTAX_LAND_THRESHOLD:
        ctax = int((land_assessed_krw - C.CTAX_LAND_THRESHOLD) * C.CTAX_LAND_RATE)

    return {
        "building_tax": bldg_tax,
        "land_tax": land_tax,
        "local_edu_tax": edu_tax,
        "comprehensive_tax": ctax,
        "total": property_tax + edu_tax + ctax,
    }


def annual_operating_expenses(gross_rent_krw: int) -> dict:
    """NOI 산출용 운영비 — 임대수입 대비 비율로 근사"""
    mgmt = int(gross_rent_krw * C.OPEX_MGMT_RATE)
    repair = int(gross_rent_krw * C.OPEX_REPAIR_RESERVE)
    insurance = int(gross_rent_krw * C.OPEX_INSURANCE_RATE)
    return {
        "management": mgmt,
        "repair_reserve": repair,
        "insurance": insurance,
        "total": mgmt + repair + insurance,
    }


# ─────────────────────────────────────────────────────────
# 3. 처분 단계 — 양도소득세
# ─────────────────────────────────────────────────────────
def _long_term_deduction_rate(holding_years: int) -> float:
    """장기보유특별공제 표1: 3년 6%, 이후 연 2%p, 최대 30%"""
    if holding_years < C.LTD_MIN_YEARS:
        return 0.0
    rate = C.LTD_BASE_RATE + (holding_years - C.LTD_MIN_YEARS) * C.LTD_ANNUAL_RATE
    return min(rate, C.LTD_MAX_RATE)


def capital_gains_tax(
    sale_price_krw: int,
    acquisition_price_krw: int,
    acquisition_cost_krw: int,
    holding_years: int,
    selling_cost_krw: int = 0,
) -> dict:
    """
    개인의 비주택 양도소득세.

    양도차익 = 양도가 − 취득가 − 필요경비(취득부대비용 + 양도비용)
    과세표준 = 양도차익 − 장기보유특별공제 − 기본공제
    """
    gain = sale_price_krw - acquisition_price_krw - acquisition_cost_krw - selling_cost_krw

    if gain <= 0:
        return {
            "gain": gain, "ltd_rate": 0.0, "ltd_amount": 0,
            "taxable_base": 0, "income_tax": 0, "local_tax": 0, "total": 0,
        }

    ltd_rate = _long_term_deduction_rate(holding_years)
    ltd_amount = int(gain * ltd_rate)

    taxable = max(0, gain - ltd_amount - C.CGT_BASIC_DEDUCTION)

    # 단기 보유는 중과세율이 기본세율보다 유리하지 않은 한 중과 적용
    if holding_years < 1:
        income_tax = int(taxable * C.CGT_SHORT_TERM_UNDER_1Y)
    elif holding_years < 2:
        income_tax = int(taxable * C.CGT_SHORT_TERM_UNDER_2Y)
    else:
        income_tax = _progressive_tax(taxable, C.CAPITAL_GAINS_BRACKETS)

    local_tax = int(income_tax * C.LOCAL_INCOME_TAX_ON_CGT)

    return {
        "gain": gain,
        "ltd_rate": round(ltd_rate, 4),
        "ltd_amount": ltd_amount,
        "taxable_base": taxable,
        "income_tax": income_tax,
        "local_tax": local_tax,
        "total": income_tax + local_tax,
        "effective_rate": round((income_tax + local_tax) / gain, 4) if gain else 0,
    }


def selling_costs(sale_price_krw: int) -> int:
    """매도 시 중개보수 (부가세 포함)"""
    broker = int(sale_price_krw * C.BROKER_FEE_RATE_NON_HOUSING)
    return broker + int(broker * C.BROKER_FEE_VAT)
