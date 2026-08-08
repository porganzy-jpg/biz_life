"""
투자 심사 엔진 — 의사결정 레이어

여기가 이 엔진의 존재 이유다.
"시세보다 8% 싸다"는 상대평가일 뿐이고, 그 자체로는 사야 할 이유가 못 된다.
같은 돈을 국고채·예금·지수에 넣었을 때보다 나은가를 따져야
비로소 "경제적으로 합리적인 매수"라고 말할 수 있다.

그래서 판정의 기준선은 시세가 아니라 **요구수익률(기회비용)** 이다.
"""
from appraisal import constants as C
from appraisal.cashflow import build_cashflows, npv, irr, cash_on_cash
from appraisal.inputs import PropertyInput


def run_scenarios(prop: PropertyInput, profile: dict = None) -> dict:
    """
    낙관·기준·비관 3개 시나리오로 현금흐름을 각각 돌린다.

    부동산 분석에서 단일 숫자를 내놓는 건 위험하다. 성장률 가정 1%p 차이가
    5년 뒤 매각가를 수천만원 흔들기 때문에, 범위로 보여주는 편이 정직하다.
    """
    profile = profile or C.DEFAULT_PROFILE
    required = prop.required_return if prop.required_return is not None else profile["required_return"]

    results = {}
    for name, adjust in C.SCENARIO_ADJUST.items():
        g = C.BASE_GROWTH_RATE + adjust
        cf = build_cashflows(prop, profile, growth=g)
        results[name] = {
            "growth": g,
            "cashflow": cf,
            "npv": npv(cf["flows"], required),
            "irr": irr(cf["flows"]),
            "cash_on_cash": cash_on_cash(cf),
        }
    return {"required_return": required, "scenarios": results}


def opportunity_cost(equity_krw: int, years: int, alt_rate: float) -> int:
    """같은 자기자본을 대안 자산에 넣었을 때의 기말 가치"""
    return int(equity_krw * (1 + alt_rate) ** years)


# ─────────────────────────────────────────────────────────
# 판정 기준선
#
# 설계 원칙:
#   · 1차 기준은 IRR — 투자자가 체감하는 건 "연 몇 %"이고, 요구수익률과
#     직접 비교되는 유일한 지표다. 다만 IRR은 규모를 무시하므로
#     NPV를 보조 축으로 두어 "수익률은 높은데 금액이 미미한" 경우를 걸러낸다.
#   · 하방(비관 시나리오)은 점수가 아니라 **관문**으로 쓴다. 비관에서 원금이
#     깨지는 물건은 기준 시나리오가 아무리 좋아도 상단 등급을 주지 않는다.
#     레버리지를 쓰는 수익형 투자에서 파산 리스크는 평균수익률로 상쇄되지 않는다.
#   · 무위험수익률(RF)에 미달하면 "나쁜 투자", RF는 넘지만 요구수익률에
#     못 미치면 "내 기준 미달"로 문구를 구분한다.
# ─────────────────────────────────────────────────────────
RISK_FREE_RATE = 0.032          # 국고채 3년 근사 — 이보다 낮으면 존재 이유가 없다
CASH_DRAIN_WARN = -0.02         # 1년차 현금수익률이 이보다 낮으면 유동성 경고

VERDICT_STRONG = "매수 권장"
VERDICT_CONDITIONAL = "조건부 매수"
VERDICT_HOLD = "보류"
VERDICT_REJECT = "매수 부적합"


def judge_investment(analysis: dict) -> dict:
    """
    시나리오 분석 결과를 받아 최종 매수 판정을 내린다.

    Args:
        analysis: run_scenarios()의 반환값.

    Returns:
        {"verdict": str, "score": int, "reasons": list[str], "risks": list[str]}
    """
    required = analysis["required_return"]
    base = analysis["scenarios"]["base"]
    pess = analysis["scenarios"]["pessimistic"]
    opt = analysis["scenarios"]["optimistic"]

    base_irr = base["irr"]
    pess_irr = pess["irr"]
    coc = base["cash_on_cash"]

    reasons, risks = [], []
    score = 0

    # ── ① 수익률 (45점) — 요구수익률 대비 상대 위치 ──
    if base_irr is None:
        reasons.append("현금흐름 부호가 바뀌지 않아 IRR 산출 불가 (전 기간 손실 가능성)")
    else:
        gap = base_irr - required
        if gap >= 0.02:
            score += 45
            reasons.append(f"기준 IRR {base_irr*100:.1f}%로 요구수익률을 {gap*100:.1f}%p 상회")
        elif gap >= 0:
            score += 38
            reasons.append(f"기준 IRR {base_irr*100:.1f}%로 요구수익률 {required*100:.0f}% 충족")
        elif gap >= -0.03:
            score += 22
            reasons.append(f"기준 IRR {base_irr*100:.1f}% — 요구수익률에 {-gap*100:.1f}%p 미달 (협상 여지)")
        elif base_irr >= RISK_FREE_RATE:
            score += 10
            reasons.append(
                f"기준 IRR {base_irr*100:.1f}% — 무위험수익률({RISK_FREE_RATE*100:.1f}%)은 넘지만 "
                f"부동산 리스크를 감수할 보상이 못 됨"
            )
        else:
            reasons.append(
                f"기준 IRR {base_irr*100:.1f}% — 무위험수익률({RISK_FREE_RATE*100:.1f}%)에도 미달. "
                f"예금·국고채가 우월"
            )

    # ── ② NPV (25점) — 절대 금액으로 본 초과가치 ──
    npv_base = base["npv"]
    if npv_base > 0:
        score += 25
        reasons.append(f"요구수익률로 할인해도 NPV +{npv_base/100_000_000:.2f}억 (초과가치 존재)")
    elif npv_base > -50_000_000:
        score += 12
        reasons.append(f"NPV {npv_base/100_000_000:.2f}억 — 손익분기 근처")
    else:
        reasons.append(f"NPV {npv_base/100_000_000:.2f}억 — 요구수익률 기준 가치 파괴")

    # ── ③ 하방 방어 (20점) — 관문 역할 ──
    downside_broken = pess_irr is None or pess_irr < 0
    if not downside_broken:
        if pess_irr >= RISK_FREE_RATE:
            score += 20
            reasons.append(f"비관 시나리오에서도 IRR {pess_irr*100:.1f}% 확보 (하방 견고)")
        else:
            score += 12
            reasons.append(f"비관 시나리오 IRR {pess_irr*100:.1f}% — 원금은 보전")
    else:
        risks.append("비관 시나리오(무성장)에서 원금 손실 — 레버리지 상태에서 가장 위험한 구간")

    # ── ④ 보유 중 현금흐름 (10점) ──
    if coc is None:
        pass
    elif coc >= 0:
        score += 10
        reasons.append(f"1년차 자기자본 현금수익률 +{coc*100:.2f}% (보유 중 현금 유입)")
    elif coc >= CASH_DRAIN_WARN:
        score += 4
        risks.append(f"1년차 현금수익률 {coc*100:.2f}% — 소폭이지만 매달 순유출")
    else:
        monthly = abs(coc) / 12
        risks.append(
            f"1년차 현금수익률 {coc*100:.2f}% — 자기자본 대비 월 {monthly*100:.2f}% 순유출. "
            f"보유기간 내내 추가 자금 투입 필요"
        )

    # ── 역레버리지 경고 ──
    cf = base["cashflow"]
    noi = cf["noi_detail"]["noi"]
    price_implied_cap = noi / (cf["equity"] + cf["loan"]) if (cf["equity"] + cf["loan"]) else 0
    if cf["loan"] > 0 and price_implied_cap < cf["loan_rate"]:
        risks.append(
            f"역레버리지: 실효 수익률 {price_implied_cap*100:.2f}% < 대출금리 {cf['loan_rate']*100:.2f}%. "
            f"대출을 늘릴수록 수익률이 낮아지므로 LTV 축소가 유리"
        )

    # ── 낙관 의존도 ──
    if opt["irr"] is not None and base_irr is not None and opt["irr"] >= required > base_irr:
        risks.append("요구수익률 충족이 낙관 시나리오에서만 성립 — 시세 상승에 베팅하는 구조")

    # ── 최종 등급 ──
    if score >= 78 and not downside_broken:
        verdict = VERDICT_STRONG
    elif score >= 55:
        verdict = VERDICT_CONDITIONAL if not downside_broken else VERDICT_HOLD
    elif score >= 32:
        verdict = VERDICT_HOLD
    else:
        verdict = VERDICT_REJECT

    return {"verdict": verdict, "score": min(100, score), "reasons": reasons, "risks": risks}


# ─────────────────────────────────────────────────────────
# 협상 목표가 — "그래서 얼마면 사도 되는가"
# ─────────────────────────────────────────────────────────
def target_price(prop: PropertyInput, profile: dict = None, tol: int = 1_000_000) -> dict:
    """
    요구수익률을 정확히 충족시키는 매수가를 역산한다 (NPV = 0 지점).

    임대수익(NOI)은 가격과 무관하게 고정이므로 NPV는 가격에 대해 단조감소한다.
    따라서 이분법으로 안전하게 수렴한다.
    """
    import dataclasses

    profile = profile or C.DEFAULT_PROFILE
    required = prop.required_return if prop.required_return is not None else profile["required_return"]

    def npv_at(price: int) -> int:
        trial = dataclasses.replace(prop, asking_price_krw=int(price))
        cf = build_cashflows(trial, profile, growth=C.BASE_GROWTH_RATE)
        return npv(cf["flows"], required)

    lo, hi = 10_000_000, max(prop.asking_price_krw * 3, 100_000_000)

    if npv_at(lo) < 0:
        return {"achievable": False, "reason": "임대수익이 낮아 어떤 가격에서도 요구수익률 충족 불가"}

    while hi - lo > tol:
        mid = (lo + hi) // 2
        if npv_at(mid) >= 0:
            lo = mid
        else:
            hi = mid

    discount = prop.asking_price_krw - lo
    return {
        "achievable": True,
        "target_price": lo,
        "asking_price": prop.asking_price_krw,
        "required_discount": discount,
        "discount_pct": round(discount / prop.asking_price_krw * 100, 1) if prop.asking_price_krw else 0,
        "required_return": required,
    }


def summarize(prop: PropertyInput, profile: dict = None) -> dict:
    """심사 전 과정을 실행하고 결과를 묶어 반환한다."""
    from appraisal.valuation.income import appraise as income_appraise

    profile = profile or C.DEFAULT_PROFILE
    analysis = run_scenarios(prop, profile)
    base_cf = analysis["scenarios"]["base"]["cashflow"]

    result = {
        "input": prop,
        "profile": profile,
        "income_valuation": income_appraise(prop),
        "analysis": analysis,
        "opportunity_cost": opportunity_cost(
            base_cf["equity"], base_cf["holding_years"], analysis["required_return"]
        ),
        "judgment": judge_investment(analysis),
        "target_price": target_price(prop, profile),
    }
    return result
