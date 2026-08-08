"""
투자 심사 엔진 — 보유기간 현금흐름 모델 (DCF)

"싸게 샀는가"가 아니라 "내 돈이 얼마를 벌어오는가"를 본다.
그래서 자산 전체 수익률이 아니라 **실제 투입한 자기자본(Equity) 기준**으로
연도별 현금흐름을 만들고, 마지막 해에 매각대금을 얹는다.

    Year 0 : −(자기자본 + 취득부대비용)
    Year 1..N−1 : NOI − 원리금 − 보유세
    Year N : 위 + (매각가 − 매도비용 − 양도세 − 대출잔액)
"""
from appraisal import constants as C
from appraisal.costs import (
    acquisition_costs, annual_property_tax, capital_gains_tax, selling_costs,
)
from appraisal.inputs import PropertyInput
from appraisal.valuation.income import calculate_noi

# 공시가격은 통상 시세의 60% 수준 — 보유세 과세표준 근사에 사용
ASSESSED_TO_MARKET = 0.60


def annual_debt_service(principal: int, rate: float, years: int) -> int:
    """원리금균등상환 연 납입액"""
    if principal <= 0 or years <= 0:
        return 0
    if rate == 0:
        return int(principal / years)
    factor = (rate * (1 + rate) ** years) / ((1 + rate) ** years - 1)
    return int(principal * factor)


def loan_balance(principal: int, rate: float, years: int, elapsed: int) -> int:
    """경과 `elapsed`년 시점의 대출 잔액"""
    if principal <= 0 or elapsed >= years:
        return 0
    payment = annual_debt_service(principal, rate, years)
    balance = float(principal)
    for _ in range(elapsed):
        interest = balance * rate
        balance -= (payment - interest)
    return max(0, int(balance))


def build_cashflows(prop: PropertyInput, profile: dict = None, growth: float = None) -> dict:
    """
    보유기간 전체 현금흐름을 구성한다.

    Args:
        growth: 자산가치 연평균 성장률. 미지정 시 기본 시나리오 사용.
    """
    profile = profile or C.DEFAULT_PROFILE
    growth = C.BASE_GROWTH_RATE if growth is None else growth

    price = prop.asking_price_krw
    ltv = prop.ltv if prop.ltv is not None else profile["ltv"]
    loan_rate = prop.loan_rate if prop.loan_rate is not None else profile["loan_rate"]
    years = prop.holding_years or profile["holding_years"]
    loan_term = profile["loan_term_years"]

    # ── 초기 투입 ──
    acq = acquisition_costs(price, prop.asset_type)
    loan = int(price * ltv)
    equity = price - loan + acq["total"]

    # ── 연간 운영 ──
    noi_detail = calculate_noi(prop)
    noi = noi_detail["noi"]

    assessed_total = int(price * ASSESSED_TO_MARKET)
    building_assessed = int(assessed_total * 0.5)
    land_assessed = assessed_total - building_assessed
    ptax = annual_property_tax(building_assessed, land_assessed)

    debt_service = annual_debt_service(loan, loan_rate, loan_term)

    flows = [-equity]
    yearly = []
    for y in range(1, years + 1):
        # 임대료도 물가 수준으로 함께 상승한다고 본다
        grown_noi = int(noi * (1 + growth) ** (y - 1))
        btcf = grown_noi - debt_service - ptax["total"]
        yearly.append({
            "year": y,
            "noi": grown_noi,
            "debt_service": debt_service,
            "property_tax": ptax["total"],
            "btcf": btcf,
        })
        flows.append(btcf)

    # ── 매각 (마지막 해에 합산) ──
    sale_price = int(price * (1 + growth) ** years)
    sell_cost = selling_costs(sale_price)
    cgt = capital_gains_tax(
        sale_price_krw=sale_price,
        acquisition_price_krw=price,
        acquisition_cost_krw=acq["total"],
        holding_years=years,
        selling_cost_krw=sell_cost,
    )
    remaining_loan = loan_balance(loan, loan_rate, loan_term, years)
    net_sale = sale_price - sell_cost - cgt["total"] - remaining_loan

    flows[-1] += net_sale
    yearly[-1]["net_sale_proceeds"] = net_sale

    return {
        "equity": equity,
        "loan": loan,
        "ltv": ltv,
        "loan_rate": loan_rate,
        "holding_years": years,
        "growth": growth,
        "acquisition": acq,
        "noi_detail": noi_detail,
        "property_tax": ptax,
        "debt_service": debt_service,
        "yearly": yearly,
        "exit": {
            "sale_price": sale_price,
            "selling_cost": sell_cost,
            "capital_gains_tax": cgt,
            "remaining_loan": remaining_loan,
            "net_proceeds": net_sale,
        },
        "flows": flows,
    }


# ─────────────────────────────────────────────────────────
# 수익률 지표
# ─────────────────────────────────────────────────────────
def npv(flows: list[int], discount_rate: float) -> int:
    """순현재가치 — 요구수익률로 할인했을 때 남는 초과가치"""
    return int(sum(cf / (1 + discount_rate) ** i for i, cf in enumerate(flows)))


def irr(flows: list[int], lo: float = -0.99, hi: float = 2.0, tol: float = 1e-7) -> float | None:
    """내부수익률 — 이분법. 부호 변화가 없으면 계산 불가."""
    def f(r):
        return sum(cf / (1 + r) ** i for i, cf in enumerate(flows))

    if f(lo) * f(hi) > 0:
        return None

    for _ in range(200):
        mid = (lo + hi) / 2
        v = f(mid)
        if abs(v) < tol:
            return round(mid, 6)
        if f(lo) * v < 0:
            hi = mid
        else:
            lo = mid
    return round((lo + hi) / 2, 6)


def cash_on_cash(cf: dict) -> float | None:
    """자기자본 대비 1년차 현금수익률 — 체감 수익의 직관적 지표"""
    if not cf["equity"]:
        return None
    return round(cf["yearly"][0]["btcf"] / cf["equity"], 4)
