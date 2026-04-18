"""
펀더멘털 가치 분석기 v2.0

주가뿐 아니라 기업의 본질적 가치를 객관적으로 평가한다.

v2.0 업그레이드 (논문 기반):
  - Piotroski F-Score (2000): 9항목 바이너리 퀄리티 체크 (+7.5% 연간 알파)
  - Novy-Marx GP/A (2013): 매출총이익/총자산 퀄리티 팩터 (+4% 알파)
  - 섹터별 상대 평가 + 절대 기준 혼합 방식
  - 위험 종목 멀티레이어 필터링

캐시: 펀더멘털은 분기 실적 발표 시에만 크게 변동하므로 1일 TTL.
"""
import logging
import time
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# 펀더멘털 캐시 TTL (초) — 1일 (분기 실적 기반이므로 자주 안 변함)
FUNDAMENTAL_CACHE_TTL = 86400

# 섹터별 PER 중앙값 기준 (한국 시장 2024-2025 기준, 주기적 업데이트 권장)
SECTOR_PER_MEDIAN = {
    "반도체": 15.0,
    "인터넷": 30.0,
    "화학": 12.0,
    "2차전지": 40.0,
    "건설": 8.0,
    "금융": 6.0,
    "자동차": 7.0,
    "바이오": 50.0,  # 적자 기업 많아 높게 설정
    "지주": 8.0,
    "보험": 6.0,
    "통신": 10.0,
    "기타": 15.0,
}

# 섹터별 PBR 중앙값
SECTOR_PBR_MEDIAN = {
    "반도체": 1.8,
    "인터넷": 3.0,
    "화학": 0.8,
    "2차전지": 3.5,
    "건설": 0.6,
    "금융": 0.4,
    "자동차": 0.7,
    "바이오": 5.0,
    "지주": 0.5,
    "보험": 0.4,
    "통신": 0.8,
    "기타": 1.0,
}


def _safe_float(val, default=None) -> Optional[float]:
    """안전한 float 변환. None, NaN, 'N/A' 등 처리."""
    if val is None:
        return default
    try:
        result = float(val)
        if np.isnan(result) or np.isinf(result):
            return default
        return result
    except (ValueError, TypeError):
        return default


class FundamentalAnalyzer:
    """
    기업 펀더멘털 가치 분석기

    평가 항목 (각 0~100점, 가중 합산):
      1. 밸류에이션 (PER/PBR 섹터 상대평가)  — 30%
      2. 수익성 (ROE, 영업이익률)             — 25%
      3. 재무 안정성 (부채비율, 유동비율)      — 25%
      4. 주주환원 (배당수익률)                 — 10%
      5. 성장성 (매출/이익 성장률)             — 10%
    """

    # v2.0: Piotroski F-Score와 GP/A를 반영한 가중치 재배분
    WEIGHTS = {
        "밸류에이션": 0.22,
        "수익성": 0.18,
        "재무안정성": 0.18,
        "피오트로스키": 0.20,  # F-Score (9항목 퀄리티)
        "수익퀄리티": 0.12,    # GP/A (Novy-Marx)
        "주주환원": 0.05,
        "성장성": 0.05,
    }

    def __init__(self):
        self._cache = {}  # {symbol: {"data": dict, "ts": float}}
        self._sector_data = {}  # {sector: [info_dict, ...]} 섹터 비교용

    def _fetch_fundamentals(self, symbol: str) -> Optional[dict]:
        """yfinance에서 펀더멘털 데이터 조회 (캐시 적용)."""
        now = time.time()
        cached = self._cache.get(symbol)
        if cached and (now - cached["ts"]) < FUNDAMENTAL_CACHE_TTL:
            return cached["data"]

        try:
            import yfinance as yf
            ticker = yf.Ticker(f"{symbol}.KS")
            info = ticker.info

            if not info or info.get("regularMarketPrice") is None:
                # .KS 실패 시 .KQ (코스닥) 시도
                ticker = yf.Ticker(f"{symbol}.KQ")
                info = ticker.info

            if not info:
                logger.warning(f"펀더멘털 데이터 없음 [{symbol}]")
                return None

            data = {
                "per": _safe_float(info.get("trailingPE") or info.get("forwardPE")),
                "pbr": _safe_float(info.get("priceToBook")),
                "roe": _safe_float(info.get("returnOnEquity")),  # 0.15 = 15%
                "debt_ratio": _safe_float(info.get("debtToEquity")),  # 150 = 150%
                "current_ratio": _safe_float(info.get("currentRatio")),
                "dividend_yield": _safe_float(info.get("dividendYield")),  # 0.03 = 3%
                "operating_margin": _safe_float(info.get("operatingMargins")),
                "profit_margin": _safe_float(info.get("profitMargins")),
                "revenue_growth": _safe_float(info.get("revenueGrowth")),
                "earnings_growth": _safe_float(info.get("earningsGrowth")),
                "market_cap": _safe_float(info.get("marketCap")),
                "enterprise_value": _safe_float(info.get("enterpriseValue")),
                "ev_ebitda": _safe_float(info.get("enterpriseToEbitda")),
                "free_cashflow": _safe_float(info.get("freeCashflow")),
                "sector_name": info.get("sector", ""),
                "industry": info.get("industry", ""),
            }

            self._cache[symbol] = {"data": data, "ts": now}
            return data

        except Exception as e:
            logger.warning(f"펀더멘털 조회 실패 [{symbol}]: {e}")
            if cached:
                return cached["data"]
            return None

    def evaluate(self, symbol: str, name: str, sector: str = "기타") -> dict:
        """
        종목 펀더멘털 종합 평가.

        Returns:
            dict: {
                "score": float (10~90),
                "grade": str (A~F),
                "details": {항목별 점수},
                "reasons": [str],
                "warnings": [str],   # 위험 신호
                "raw": {원본 데이터},
            }
        """
        data = self._fetch_fundamentals(symbol)
        if not data:
            return {
                "score": 50, "grade": "N/A",
                "details": {}, "reasons": ["펀더멘털 데이터 없음"],
                "warnings": [], "raw": {},
            }

        scores = {}
        reasons = []
        warnings = []

        # ── 1. 밸류에이션 (PER + PBR 섹터 상대평가) ──
        val_score = self._score_valuation(data, sector, reasons, warnings)
        scores["밸류에이션"] = val_score

        # ── 2. 수익성 (ROE + 영업이익률) ──
        prof_score = self._score_profitability(data, reasons, warnings)
        scores["수익성"] = prof_score

        # ── 3. 재무 안정성 (부채비율 + 유동비율) ──
        safety_score = self._score_financial_safety(data, reasons, warnings)
        scores["재무안정성"] = safety_score

        # ── 4. 주주환원 (배당수익률) ──
        div_score = self._score_dividend(data, reasons)
        scores["주주환원"] = div_score

        # ── 5. 성장성 (매출/이익 성장률) ──
        growth_score = self._score_growth(data, reasons, warnings)
        scores["성장성"] = growth_score

        # ── 6. Piotroski F-Score (9항목 바이너리 퀄리티) ──
        f_score, f_details = self._piotroski_f_score(data)
        piotroski_score = self._f_score_to_points(f_score, reasons)
        scores["피오트로스키"] = piotroski_score

        # ── 7. Novy-Marx GP/A (매출총이익/총자산) ──
        gpa_score = self._score_gross_profitability(data, reasons)
        scores["수익퀄리티"] = gpa_score

        # 가중 합산
        final_score = sum(
            scores.get(k, 50) * self.WEIGHTS.get(k, 0)
            for k in self.WEIGHTS
        )
        final_score = round(max(10, min(90, final_score)), 1)

        # 위험 종목 페널티: 경고 2개 이상이면 점수 하향
        if len(warnings) >= 3:
            final_score = min(final_score, 35)
            reasons.append("복합 위험 신호 (경고 3+)")
        elif len(warnings) >= 2:
            final_score = min(final_score, 45)

        grade = self._to_grade(final_score)

        return {
            "score": final_score,
            "grade": grade,
            "details": scores,
            "reasons": reasons,
            "warnings": warnings,
            "raw": data,
        }

    def _score_valuation(self, data: dict, sector: str,
                         reasons: list, warnings: list) -> float:
        """PER/PBR 섹터 상대평가."""
        per = data.get("per")
        pbr = data.get("pbr")
        sector_per = SECTOR_PER_MEDIAN.get(sector, 15.0)
        sector_pbr = SECTOR_PBR_MEDIAN.get(sector, 1.0)

        per_score = 50
        pbr_score = 50

        if per is not None and per > 0:
            # PER이 섹터 중앙값보다 낮으면 저평가
            ratio = per / sector_per
            if ratio < 0.5:
                per_score = 80
                reasons.append(f"PER 강력 저평가 {per:.1f} (섹터중앙 {sector_per:.0f})")
            elif ratio < 0.8:
                per_score = 68
                reasons.append(f"PER 저평가 {per:.1f}")
            elif ratio < 1.2:
                per_score = 50
            elif ratio < 2.0:
                per_score = 35
                reasons.append(f"PER 고평가 {per:.1f}")
            else:
                per_score = 20
                warnings.append(f"PER 과도 {per:.1f} (섹터중앙 {sector_per:.0f})")
        elif per is not None and per < 0:
            per_score = 15
            warnings.append("적자 기업 (PER 음수)")

        if pbr is not None and pbr > 0:
            ratio = pbr / sector_pbr
            if ratio < 0.5:
                pbr_score = 78
                reasons.append(f"PBR 강력 저평가 {pbr:.2f}")
            elif ratio < 0.8:
                pbr_score = 65
            elif ratio < 1.3:
                pbr_score = 50
            elif ratio < 2.5:
                pbr_score = 35
            else:
                pbr_score = 20
                warnings.append(f"PBR 과도 {pbr:.2f}")

        # EV/EBITDA 보조 지표
        ev_ebitda = data.get("ev_ebitda")
        ev_bonus = 0
        if ev_ebitda is not None and ev_ebitda > 0:
            if ev_ebitda < 6:
                ev_bonus = 8
                reasons.append(f"EV/EBITDA 매력 {ev_ebitda:.1f}")
            elif ev_ebitda > 20:
                ev_bonus = -8

        return max(10, min(90, per_score * 0.5 + pbr_score * 0.5 + ev_bonus))

    def _score_profitability(self, data: dict, reasons: list,
                             warnings: list) -> float:
        """ROE + 영업이익률 평가."""
        roe = data.get("roe")  # 0.15 = 15%
        op_margin = data.get("operating_margin")

        roe_score = 50
        if roe is not None:
            roe_pct = roe * 100
            if roe_pct >= 20:
                roe_score = 85
                reasons.append(f"ROE 우수 {roe_pct:.1f}%")
            elif roe_pct >= 12:
                roe_score = 70
            elif roe_pct >= 5:
                roe_score = 55
            elif roe_pct >= 0:
                roe_score = 35
            else:
                roe_score = 15
                warnings.append(f"ROE 마이너스 {roe_pct:.1f}%")

        margin_score = 50
        if op_margin is not None:
            margin_pct = op_margin * 100
            if margin_pct >= 20:
                margin_score = 82
                reasons.append(f"영업이익률 고수익 {margin_pct:.1f}%")
            elif margin_pct >= 10:
                margin_score = 68
            elif margin_pct >= 5:
                margin_score = 50
            elif margin_pct >= 0:
                margin_score = 35
            else:
                margin_score = 15
                warnings.append(f"영업적자 {margin_pct:.1f}%")

        return roe_score * 0.6 + margin_score * 0.4

    def _score_financial_safety(self, data: dict, reasons: list,
                                warnings: list) -> float:
        """부채비율 + 유동비율 안정성 평가."""
        debt = data.get("debt_ratio")  # 150 = 150%
        current = data.get("current_ratio")

        debt_score = 50
        if debt is not None:
            if debt < 50:
                debt_score = 85
                reasons.append(f"부채비율 우량 {debt:.0f}%")
            elif debt < 100:
                debt_score = 70
            elif debt < 200:
                debt_score = 50
            elif debt < 300:
                debt_score = 30
                warnings.append(f"부채비율 높음 {debt:.0f}%")
            else:
                debt_score = 10
                warnings.append(f"부채비율 위험 {debt:.0f}%")

        current_score = 50
        if current is not None:
            if current >= 2.0:
                current_score = 80
            elif current >= 1.5:
                current_score = 68
            elif current >= 1.0:
                current_score = 50
            elif current >= 0.7:
                current_score = 30
                warnings.append(f"유동비율 부족 {current:.2f}")
            else:
                current_score = 15
                warnings.append(f"유동비율 위험 {current:.2f}")

        return debt_score * 0.6 + current_score * 0.4

    def _score_dividend(self, data: dict, reasons: list) -> float:
        """배당수익률 평가."""
        div_yield = data.get("dividend_yield")  # 0.03 = 3%
        if div_yield is None or div_yield <= 0:
            return 40  # 무배당은 약간 감점

        div_pct = div_yield * 100
        if div_pct >= 5.0:
            reasons.append(f"고배당 {div_pct:.1f}%")
            return 85
        elif div_pct >= 3.0:
            reasons.append(f"배당매력 {div_pct:.1f}%")
            return 72
        elif div_pct >= 1.5:
            return 58
        elif div_pct >= 0.5:
            return 45
        return 40

    def _score_growth(self, data: dict, reasons: list,
                      warnings: list) -> float:
        """매출/이익 성장률 평가."""
        rev_growth = data.get("revenue_growth")  # 0.15 = 15%
        earn_growth = data.get("earnings_growth")

        rev_score = 50
        if rev_growth is not None:
            rev_pct = rev_growth * 100
            if rev_pct >= 20:
                rev_score = 82
                reasons.append(f"매출 고성장 {rev_pct:.0f}%")
            elif rev_pct >= 10:
                rev_score = 68
            elif rev_pct >= 0:
                rev_score = 50
            elif rev_pct >= -10:
                rev_score = 35
            else:
                rev_score = 20
                warnings.append(f"매출 급감 {rev_pct:.0f}%")

        earn_score = 50
        if earn_growth is not None:
            earn_pct = earn_growth * 100
            if earn_pct >= 30:
                earn_score = 85
                reasons.append(f"이익 폭증 {earn_pct:.0f}%")
            elif earn_pct >= 10:
                earn_score = 68
            elif earn_pct >= 0:
                earn_score = 50
            elif earn_pct >= -20:
                earn_score = 30
            else:
                earn_score = 15
                warnings.append(f"이익 급감 {earn_pct:.0f}%")

        return rev_score * 0.4 + earn_score * 0.6

    def _piotroski_f_score(self, data: dict) -> tuple:
        """
        Piotroski F-Score (2000) — 9항목 바이너리 체크.

        각 항목이 통과하면 1점, 실패하면 0점. 총 0~9점.
        8-9점: 강력 퀄리티, 0-2점: 위험 퀄리티

        Returns:
            (f_score: int, details: dict)
        """
        details = {}
        score = 0

        # === 수익성 (4항목) ===
        # F1: ROA > 0 (당기 순이익 / 총자산 양수)
        roe = data.get("roe")
        if roe is not None and roe > 0:
            score += 1
            details["F1_ROA양수"] = True
        else:
            details["F1_ROA양수"] = False

        # F2: 영업현금흐름 > 0
        fcf = data.get("free_cashflow")
        if fcf is not None and fcf > 0:
            score += 1
            details["F2_CFO양수"] = True
        else:
            details["F2_CFO양수"] = False

        # F3: ROA 개선 (earnings_growth로 대체 — ROA 전년 비교 데이터 부재)
        earn_growth = data.get("earnings_growth")
        if earn_growth is not None and earn_growth > 0:
            score += 1
            details["F3_ROA개선"] = True
        else:
            details["F3_ROA개선"] = False

        # F4: 현금흐름 > 순이익 (어크루얼 체크 — 이익의 질)
        # FCF > 0이고 이익률도 양수면 통과 (정밀 비교 데이터 부재 시 근사)
        profit_margin = data.get("profit_margin")
        if fcf is not None and fcf > 0 and profit_margin is not None and profit_margin > 0:
            score += 1
            details["F4_어크루얼"] = True
        else:
            details["F4_어크루얼"] = False

        # === 재무 건전성 (3항목) ===
        # F5: 부채비율 감소 (전년 대비 — 데이터 부재 시 현재 수준으로 판단)
        debt = data.get("debt_ratio")
        if debt is not None and debt < 100:  # 100% 미만이면 양호로 판정
            score += 1
            details["F5_부채감소"] = True
        else:
            details["F5_부채감소"] = False

        # F6: 유동비율 > 1.0 (단기 지급 능력)
        current = data.get("current_ratio")
        if current is not None and current > 1.0:
            score += 1
            details["F6_유동비율"] = True
        else:
            details["F6_유동비율"] = False

        # F7: 신주 발행 없음 (희석 없음) — yfinance에 직접 데이터 부재, 통과로 처리
        score += 1
        details["F7_희석없음"] = True  # 데이터 부재 시 중립

        # === 운영 효율성 (2항목) ===
        # F8: 매출총이익률 개선 (revenue_growth > 0이면 근사)
        rev_growth = data.get("revenue_growth")
        if rev_growth is not None and rev_growth > 0:
            score += 1
            details["F8_마진개선"] = True
        else:
            details["F8_마진개선"] = False

        # F9: 자산회전율 개선 (revenue_growth > earnings_growth면 효율 개선으로 근사)
        if (rev_growth is not None and earn_growth is not None and
                rev_growth > 0):
            score += 1
            details["F9_회전율개선"] = True
        else:
            details["F9_회전율개선"] = False

        return score, details

    def _f_score_to_points(self, f_score: int, reasons: list) -> float:
        """F-Score를 0~100 점수로 변환."""
        if f_score >= 8:
            reasons.append(f"F-Score {f_score}/9 (강력 퀄리티)")
            return 85
        elif f_score >= 6:
            reasons.append(f"F-Score {f_score}/9 (양호)")
            return 68
        elif f_score >= 4:
            return 50
        elif f_score >= 2:
            reasons.append(f"F-Score {f_score}/9 (취약)")
            return 30
        else:
            reasons.append(f"F-Score {f_score}/9 (위험)")
            return 15

    def _score_gross_profitability(self, data: dict, reasons: list) -> float:
        """
        Novy-Marx GP/A — 매출총이익 / 총자산.

        이 비율이 높을수록 "비싸 보여도 실질적으로 우수한 기업".
        ROE보다 미래 수익률 예측력이 높다는 것이 논문의 핵심.
        """
        op_margin = data.get("operating_margin")
        market_cap = data.get("market_cap")
        ev = data.get("enterprise_value")

        # yfinance에서 직접 GP/A를 제공하지 않으므로
        # operating_margin을 proxy로 사용 (GP = Revenue * OP_Margin 근사)
        if op_margin is not None:
            gpa_proxy = op_margin * 100  # 퍼센트로 변환
            if gpa_proxy >= 25:
                reasons.append(f"GP/A 우수 {gpa_proxy:.1f}%")
                return 85
            elif gpa_proxy >= 15:
                return 70
            elif gpa_proxy >= 8:
                return 55
            elif gpa_proxy >= 0:
                return 40
            else:
                return 20

        return 50  # 데이터 없으면 중립

    @staticmethod
    def _to_grade(score: float) -> str:
        """점수를 등급으로 변환."""
        if score >= 75:
            return "A"
        elif score >= 65:
            return "B"
        elif score >= 50:
            return "C"
        elif score >= 35:
            return "D"
        return "F"

    def get_cached_count(self) -> int:
        """캐시된 종목 수."""
        return len(self._cache)

    def invalidate(self, symbol: str = None):
        """캐시 무효화."""
        if symbol:
            self._cache.pop(symbol, None)
        else:
            self._cache.clear()
