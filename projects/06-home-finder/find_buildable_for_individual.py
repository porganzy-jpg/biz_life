"""
개인이 '현실적으로 구매해서 집 짓고 살 수 있는' 토지를 골라 순위화한다.

판정 축:
  1) 취득 난이도 (지목):
       대/잡종지  → 개인이 바로 취득·건축 가능 (농취증/전용 불필요)
       전/답/과수원 → 농지취득자격증명(농취증) + 농지전용 필요
       임야        → 산지전용 필요 (보전산지면 사실상 불가)
  2) 거주 적합 (용도지역): 주거지역 > 준주거 > 계획관리 > 녹지 > 상업/공업
  3) 규모 적정: 단독주택 실거주 66~660㎡(20~200평), 스위트스팟 130~495㎡(40~150평)
  4) 가격 신뢰성: 지역(구/시) 평당가 중앙값 대비 극단 이탈(지분·특수거래 추정) 제외
  5) 예산 밴드: 실속(≤3억) / 중간(3~7억) / 여유(7~15억)

출력: 지역 × 예산밴드별 상위 매물 + JSON 리포트(data/buildable_shortlist.json)
"""
import sys
import json
import statistics
from pathlib import Path
from collections import defaultdict

# Windows 콘솔(cp949)에서도 한글/특수문자 출력되도록 UTF-8 강제
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from database import SessionLocal
from models.property import Property

PYEONG = 3.3058  # 1평 = 3.3058㎡

# ── 취득 난이도 (지목) ──
JIMOK_EASY = {"대", "대지", "잡종지"}          # 바로 취득·건축
JIMOK_FARM = {"전", "답", "과수원", "목장용지"}  # 농취증+전용 필요
JIMOK_FOREST = {"임야"}                        # 산지전용 필요

# ── 거주 적합 용도지역 점수 ──
def zoning_score(z: str) -> int:
    z = z or ""
    if "전용주거" in z: return 30
    if "일반주거" in z: return 30
    if "준주거" in z:   return 24
    if "계획관리" in z: return 18
    if "상업" in z:     return 10   # 건축 가능하나 거주 부적합
    if "녹지" in z:     return 12   # 자연녹지 등 저밀 단독 가능
    if "공업" in z:     return 6
    return 8

BUDGET_BANDS = [
    ("실속형 (≤3억)", 0, 3_0000_0000),
    ("중간형 (3~7억)", 3_0000_0000, 7_0000_0000),
    ("여유형 (7~15억)", 7_0000_0000, 15_0000_0000),
]

REGIONS = {"서울": "서울특별시", "경기": "경기도", "송도·인천": "인천광역시"}


def acquire_note(jimok):
    if jimok in JIMOK_EASY:
        return "즉시취득", "지목 '대/잡종지' — 개인이 바로 매입·건축 가능"
    if jimok in JIMOK_FARM:
        return "농취증필요", "농지 — 농지취득자격증명 + 농지전용허가 필요"
    if jimok in JIMOK_FOREST:
        return "산지전용", "임야 — 산지전용허가 필요(보전산지면 불가)"
    return "확인필요", f"지목 '{jimok}' — 개별 확인 필요"


def suitability(p, median_ppm2):
    """0~100 거주 적합도. 가격 이상치면 None(제외)."""
    ppm2 = p.price_per_m2 or 0
    # 가격 신뢰성: 지역 중앙값의 25%~400% 벗어나면 이상치(지분/특수거래 추정)
    if ppm2 <= 0 or median_ppm2 <= 0:
        return None, "가격정보 부족"
    if ppm2 < median_ppm2 * 0.25:
        return None, f"평당가 이상치(지역중앙값의 {ppm2/median_ppm2*100:.0f}%) — 지분/특수거래 추정"

    # 건축 최소면적: 66㎡(20평) 미만은 단독주택 실거주 부적합 → 제외
    if (p.area_m2 or 0) < 66:
        return None, "건축 최소면적 미달(<20평)"

    score = 0
    jimok = p.land_use or ""
    # 취득 난이도
    if jimok in JIMOK_EASY: score += 40
    elif jimok in JIMOK_FARM: score += 12
    elif jimok in JIMOK_FOREST: score += 6
    else: score += 15
    # 용도지역
    score += zoning_score(p.zoning_type)
    # 규모
    a = p.area_m2 or 0
    if 130 <= a <= 495: score += 20
    elif 66 <= a < 130 or 495 < a <= 660: score += 12
    elif a > 660: score += 4
    # else 너무 작음 +0
    return min(score, 100), None


def main():
    db = SessionLocal()
    try:
        rows = db.query(Property).filter(
            Property.source == "molit_land", Property.is_active == 1).all()

        # 지역(구/시)별 평당가 중앙값 → 이상치 판정 기준
        by_dist = defaultdict(list)
        for p in rows:
            if p.price_per_m2 and p.price_per_m2 > 0:
                by_dist[p.district].append(p.price_per_m2)
        median = {d: statistics.median(v) for d, v in by_dist.items() if v}

        report = {}
        print("=" * 72)
        print(" 개인이 현실적으로 '사서 집 짓고 살 수 있는' 토지 — 지역 × 예산별 TOP")
        print("=" * 72)

        for region_label, city in REGIONS.items():
            report[region_label] = {}
            region_rows = [p for p in rows if p.city == city]
            for band_label, lo, hi in BUDGET_BANDS:
                cands = []
                for p in region_rows:
                    if not (lo <= (p.price_krw or 0) < hi):
                        continue
                    med = median.get(p.district, 0)
                    sc, reason = suitability(p, med)
                    if sc is None:
                        continue
                    acq, acq_note = acquire_note(p.land_use or "")
                    cands.append({
                        "구": p.district, "동": p.dong,
                        "면적㎡": round(p.area_m2 or 0), "평": round((p.area_m2 or 0)/PYEONG),
                        "가격억": round((p.price_krw or 0)/1e8, 2),
                        "평당만": round((p.price_per_m2 or 0)*PYEONG/1e4),
                        "지목": p.land_use, "용도지역": p.zoning_type,
                        "건폐/용적": f"{p.building_coverage_ratio}/{p.floor_area_ratio}",
                        "취득": acq, "취득설명": acq_note,
                        "적합도": sc,
                        "위도": p.lat, "경도": p.lng,
                    })
                # 적합도 desc, 평당가 asc
                cands.sort(key=lambda x: (-x["적합도"], x["평당만"]))
                top = cands[:6]
                report[region_label][band_label] = {"총후보": len(cands), "top": top}

                print(f"\n▶ {region_label} · {band_label} — 후보 {len(cands)}건")
                if not top:
                    print("   (해당 예산·조건 매물 없음)")
                for t in top:
                    print(f"   [{t['적합도']:>3}점] {t['구']} {t['동']} | {t['평']}평({t['면적㎡']}㎡) | "
                          f"{t['가격억']}억 | 평당 {t['평당만']:,}만 | {t['지목']}/{t['용도지역']} | {t['취득']}")

        out_path = PROJECT_ROOT / "data" / "buildable_shortlist.json"
        out_path.parent.mkdir(exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n리포트 저장: {out_path}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
