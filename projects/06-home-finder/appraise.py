"""
매물 투자 심사 CLI

사용 예:
    python appraise.py --addr "서울시 강남구 역삼동 123-4" --price 12억 \
        --rent 450 --deposit 1억 --area 66 --floor 1 --grade B

    python appraise.py --demo        # 샘플 물건으로 동작 확인
"""
import sys
import argparse
from pathlib import Path

# Windows 콘솔(cp949)에서도 한글/특수문자 출력되도록 UTF-8 강제
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from appraisal import constants as C
from appraisal.inputs import PropertyInput, RentRoll
from appraisal.decision import summarize


# ─────────────────────────────────────────────────────────
# 입력 파싱 — "12억", "3500만" 같은 한국식 금액 표기 지원
# ─────────────────────────────────────────────────────────
def parse_krw(text: str) -> int:
    """'12억', '1억2000만', '4500만', '450' (만원 단위 가정) → 원"""
    if text is None:
        return 0
    s = str(text).replace(",", "").replace(" ", "").strip()
    if not s:
        return 0

    total = 0
    if "억" in s:
        head, s = s.split("억", 1)
        total += int(float(head) * 100_000_000)
    if "만" in s:
        head, s = s.split("만", 1)
        if head:
            total += int(float(head) * 10_000)
    if s and s.replace(".", "").isdigit():
        # 접미사 없는 잔여 숫자는 만원 단위로 해석
        total += int(float(s) * 10_000) if total == 0 else int(float(s))
    return total


def fmt(krw: int | None) -> str:
    """원 단위 정수를 억/만원 표기로"""
    if krw is None:
        return "-"
    sign = "-" if krw < 0 else ""
    v = abs(int(krw))
    eok, rest = divmod(v, 100_000_000)
    man = rest // 10_000
    if eok and man:
        return f"{sign}{eok}억 {man:,}만원"
    if eok:
        return f"{sign}{eok}억원"
    return f"{sign}{man:,}만원"


def pct(x: float | None, digits: int = 2) -> str:
    return "-" if x is None else f"{x * 100:.{digits}f}%"


# ─────────────────────────────────────────────────────────
# 리포트 출력
# ─────────────────────────────────────────────────────────
def print_report(r: dict):
    prop = r["input"]
    iv = r["income_valuation"]
    an = r["analysis"]
    base = an["scenarios"]["base"]
    cf = base["cashflow"]

    line = "─" * 62
    print(f"\n{line}")
    print(f"  매물 투자 심사 리포트")
    print(f"{line}")
    print(f"  주소      : {prop.address}")
    print(f"  유형      : {prop.asset_type}")
    print(f"  희망 매수가: {fmt(prop.asking_price_krw)}", end="")
    if prop.area_m2:
        print(f"  ({prop.area_m2:.1f}㎡ / 평당 {fmt(int(prop.asking_price_krw / (prop.area_m2 / 3.3058)))})")
    else:
        print()
    print(f"  투자 성향  : {r['profile']['name']}  "
          f"(요구수익률 {pct(an['required_return'], 1)}, 보유 {cf['holding_years']}년)")

    # ── 1. 수익환원법 ──
    print(f"\n{line}\n  [1] 현재가치 — 수익환원법\n{line}")
    if not iv["applicable"]:
        print(f"  평가 불가: {iv['reason']}")
    else:
        n = iv["noi_detail"]
        print(f"  연 임대료        : {fmt(n['annual_rent'])}")
        print(f"  보증금 운용수익  : {fmt(n['deposit_income'])}  (보증금 {fmt(prop.rent.deposit_krw)} × {pct(C.DEPOSIT_YIELD,1)})")
        print(f"  잠재총수입 PGI   : {fmt(n['pgi'])}")
        print(f"  공실손실         : -{fmt(n['vacancy_loss'])}  (공실률 {pct(n['vacancy_rate'],1)})")
        print(f"  운영비           : -{fmt(n['opex']['total'])}")
        print(f"  ── 순영업소득 NOI : {fmt(n['noi'])}")
        print()
        print(f"  적용 Cap Rate    : {pct(iv['cap_rate'])}  [{iv['cap_rate_desc']}]")
        print(f"  수익환원 평가액  : {fmt(iv['value'])}")
        print(f"  호가 기준 실효 Cap: {pct(iv['going_in_cap_rate'])}")
        gap = iv["value"] - prop.asking_price_krw
        print(f"  평가액 − 호가    : {fmt(gap)}  →  {iv['verdict']}")

    # ── 2. 자금 구조 ──
    acq = cf["acquisition"]
    print(f"\n{line}\n  [2] 자금 구조 · 취득비용\n{line}")
    print(f"  매수가           : {fmt(prop.asking_price_krw)}")
    print(f"  대출 (LTV {pct(cf['ltv'],0)})   : {fmt(cf['loan'])}  @ 금리 {pct(cf['loan_rate'],2)}")
    print(f"  취득세 (4.6%)    : {fmt(acq['acquisition_tax'])}")
    print(f"  중개보수         : {fmt(acq['broker_fee'])}")
    print(f"  법무·등기        : {fmt(acq['legal_fee'])}")
    if not acq["vat_refundable"]:
        print(f"  건물분 부가세    : {fmt(acq['vat_burden'])}")
    print(f"  ── 실제 투입 자기자본: {fmt(cf['equity'])}")

    # ── 3. 연간 현금흐름 ──
    print(f"\n{line}\n  [3] 연간 현금흐름 (기준 시나리오)\n{line}")
    print(f"  {'연차':<5}{'NOI':>14}{'원리금':>14}{'보유세':>12}{'세전현금흐름':>16}")
    for y in cf["yearly"]:
        print(f"  {y['year']:<5}{fmt(y['noi']):>14}{fmt(-y['debt_service']):>14}"
              f"{fmt(-y['property_tax']):>12}{fmt(y['btcf']):>16}")

    ex = cf["exit"]
    print(f"\n  [매각 시점 — {cf['holding_years']}년 후, 연 {pct(cf['growth'],1)} 성장 가정]")
    print(f"  예상 매각가      : {fmt(ex['sale_price'])}")
    print(f"  중개보수         : -{fmt(ex['selling_cost'])}")
    print(f"  양도세           : -{fmt(ex['capital_gains_tax']['total'])} "
          f"(장특공제 {pct(ex['capital_gains_tax']['ltd_rate'],0)}, 실효 {pct(ex['capital_gains_tax']['effective_rate'])})")
    print(f"  대출 잔액 상환   : -{fmt(ex['remaining_loan'])}")
    print(f"  ── 매각 순수취액  : {fmt(ex['net_proceeds'])}")

    # ── 4. 수익률 ──
    print(f"\n{line}\n  [4] 투자 성과 · 시나리오\n{line}")
    print(f"  {'시나리오':<10}{'성장률':>8}{'IRR':>10}{'NPV':>18}{'1년차 현금수익률':>18}")
    labels = {"optimistic": "낙관", "base": "기준", "pessimistic": "비관"}
    for key in ("optimistic", "base", "pessimistic"):
        s = an["scenarios"][key]
        print(f"  {labels[key]:<10}{pct(s['growth'],1):>8}{pct(s['irr']):>10}"
              f"{fmt(s['npv']):>18}{pct(s['cash_on_cash']):>18}")

    print(f"\n  요구수익률(기회비용) : {pct(an['required_return'],1)}")
    print(f"  같은 자기자본을 대안투자 시 {cf['holding_years']}년 후: {fmt(r['opportunity_cost'])}")

    # ── 5. 판정 ──
    print(f"\n{line}\n  [5] 최종 판정\n{line}")
    j = r["judgment"]
    print(f"  ▶ {j['verdict']}   (종합점수 {j['score']}/100)")
    if j.get("reasons"):
        print()
        for reason in j["reasons"]:
            print(f"  · {reason}")
    if j.get("risks"):
        print("\n  [리스크]")
        for risk in j["risks"]:
            print(f"  ! {risk}")

    # ── 6. 협상 목표가 ──
    tp = r["target_price"]
    print(f"\n{line}\n  [6] 협상 목표가\n{line}")
    if not tp["achievable"]:
        print(f"  {tp['reason']}")
    else:
        print(f"  요구수익률 {pct(tp['required_return'],0)} 충족 매수가 : {fmt(tp['target_price'])}")
        print(f"  현재 호가                    : {fmt(tp['asking_price'])}")
        if tp["required_discount"] > 0:
            print(f"  → 필요 조정폭                : {fmt(tp['required_discount'])} ({tp['discount_pct']}% 인하)")
        else:
            print(f"  → 호가가 이미 목표가 이하 (여유 {fmt(-tp['required_discount'])})")
    print(f"{line}\n")


# ─────────────────────────────────────────────────────────
def build_demo() -> PropertyInput:
    """샘플: 강남 역세권 1층 구분상가"""
    return PropertyInput(
        address="서울시 강남구 역삼동 123-4 (샘플)",
        asking_price_krw=parse_krw("12억"),
        asset_type=C.ASSET_COMMERCIAL_UNIT,
        area_m2=66.0,
        floor=1,
        built_year=2010,
        building_name="샘플프라자",
        cap_grade="B",
        is_first_floor=True,
        is_corner=True,
        rent=RentRoll(
            monthly_rent_krw=parse_krw("450"),
            deposit_krw=parse_krw("1억"),
            tenant_business="프랜차이즈 카페",
        ),
        notes="역 도보 3분, 코너 전면",
    )


def main():
    p = argparse.ArgumentParser(description="매물 투자 심사 엔진")
    p.add_argument("--demo", action="store_true", help="샘플 물건으로 실행")
    p.add_argument("--addr", help="주소")
    p.add_argument("--price", help="희망 매수가 (예: 12억)")
    p.add_argument("--rent", help="월 임대료 (예: 450 = 450만원)")
    p.add_argument("--deposit", help="보증금 (예: 1억)")
    p.add_argument("--area", type=float, help="전용면적 ㎡")
    p.add_argument("--floor", type=int, help="층")
    p.add_argument("--built", type=int, help="준공연도")
    p.add_argument("--grade", choices=list(C.CAP_RATE_BY_GRADE), help="상권 등급 A~D")
    p.add_argument("--ltv", type=float, help="대출비율 (예: 0.6)")
    p.add_argument("--years", type=int, help="보유기간")
    p.add_argument("--required", type=float, help="요구수익률 (예: 0.10)")
    args = p.parse_args()

    if args.demo:
        prop = build_demo()
    else:
        if not args.addr or not args.price:
            p.error("--addr 와 --price 는 필수입니다 (또는 --demo 사용)")
        prop = PropertyInput(
            address=args.addr,
            asking_price_krw=parse_krw(args.price),
            asset_type=C.ASSET_COMMERCIAL_UNIT,
            area_m2=args.area,
            floor=args.floor,
            built_year=args.built,
            cap_grade=args.grade,
            is_first_floor=(args.floor == 1) if args.floor else None,
            rent=RentRoll(
                monthly_rent_krw=parse_krw(args.rent),
                deposit_krw=parse_krw(args.deposit),
            ),
            ltv=args.ltv,
            holding_years=args.years,
            required_return=args.required,
        )

    print_report(summarize(prop))


if __name__ == "__main__":
    main()
