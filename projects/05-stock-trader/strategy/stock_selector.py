"""
종목 선정 앙상블 v3.8 (7전략: 5 기술적 + ML예측 + 펀더멘털)

v3.8: 펀더멘털 가치 분석 7번째 전략 추가
      PER/PBR/ROE/부채비율/배당 섹터 상대평가
      가치 위험 종목 필터링 (경고 3+ → 매수 차단)
v3.7: ML예측 서브스코어 추가 (기존 5전략 비율 축소, 합계 1.0 유지)
      기관/외국인 수급 하이브리드 거래량 분석
v3.2: Z-score 기반 스코어링, tanh MACD, 폭락 가드, 적응형 임계값
"""
import sys
import os
import logging
from collections import deque

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

logger = logging.getLogger(__name__)


def _compute_rsi_wilder(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder EMA 기반 정확한 RSI (C5: 0나누기 방어 포함)"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    # C5 Fix: avg_loss=0 방어 (연속 상승 시)
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)  # NaN → 중립값


class StockSelectorEnsemble:
    """
    종목 선정 앙상블 v3.8

    7전략 통합 (5 기술적 + ML예측 + 펀더멘털) + Z-score 스코어링 + 국면적응형 가중치
    ML/펀더멘털 없을 시 나머지 전략 가중치 재정규화
    """

    # v3.8: 백테스트 최적화 결과 — 펀더멘털은 "필터"로만 사용 (가중치 0%)
    # 2025년 검증: 기술적 앙상블 가중치를 유지하되, F-Score<4 종목만 차단
    # (펀더멘털 가중치 혼합 시 수익률 하락 확인: +75% → +45%)
    REGIME_WEIGHTS = {
        "BULL": {
            "추세추종": 0.25, "한국형모멘텀": 0.17, "거래량": 0.17,
            "평균회귀": 0.13, "변동성": 0.13, "ML예측": 0.15,
        },
        "BEAR": {
            "평균회귀": 0.25, "변동성": 0.22, "거래량": 0.17,
            "추세추종": 0.13, "한국형모멘텀": 0.08, "ML예측": 0.15,
        },
        "SIDEWAYS": {
            "평균회귀": 0.22, "거래량": 0.22, "추세추종": 0.17,
            "변동성": 0.12, "한국형모멘텀": 0.12, "ML예측": 0.15,
        },
    }

    def __init__(self):
        self._regime = "SIDEWAYS"
        # 적응형 임계값용 점수 히스토리
        self._score_history = deque(maxlen=200)
        # ML 예측기 (v3.7)
        self._ml_predictor = None
        self._ml_available = False
        try:
            ml_path = os.path.join(os.path.dirname(__file__), "..", "trading-bot")
            if ml_path not in sys.path:
                sys.path.insert(0, ml_path)
            from ml_model import MLStockPredictor
            self._ml_predictor = MLStockPredictor()
            self._ml_available = self._ml_predictor.is_available()
            if self._ml_available:
                logger.info("ML 예측 모델 활성화")
        except Exception as e:
            logger.debug(f"ML 모델 로드 건너뜀: {e}")

        # 펀더멘털 분석기 (v3.8)
        self._fundamental_analyzer = None
        try:
            from fundamental_analyzer import FundamentalAnalyzer
            self._fundamental_analyzer = FundamentalAnalyzer()
            logger.info("펀더멘털 분석기 활성화")
        except Exception as e:
            logger.debug(f"펀더멘털 분석기 로드 건너뜀: {e}")

    def apply_regime_weights(self, regime_weights: dict) -> None:
        """기존 인터페이스 호환"""
        pass

    def set_regime(self, regime: str) -> None:
        if regime in self.REGIME_WEIGHTS:
            self._regime = regime

    def _z_score(self, series: pd.Series, value: float, lookback: int = 60) -> float:
        """Z-score 계산: (value - rolling_mean) / rolling_std"""
        if len(series) < lookback:
            return 0.0
        window = series.tail(lookback)
        mean = float(window.mean())
        std = float(window.std())
        if std < 1e-10:
            return 0.0
        return (value - mean) / std

    def _get_thresholds(self) -> tuple:
        """적응형 임계값: 최근 점수 분포의 75/25 백분위 사용"""
        if len(self._score_history) >= 50:
            scores = list(self._score_history)
            buy_th = max(55, min(68, float(np.percentile(scores, 75))))
            sell_th = min(45, max(32, float(np.percentile(scores, 25))))
            return buy_th, sell_th
        return 58, 42  # 초기 폴백

    def evaluate(self, df: pd.DataFrame, symbol: str, name: str,
                 regime: str = None, sector: str = "기타") -> dict:
        if regime:
            self._regime = regime

        if df is None or len(df) < 130:
            return {
                "symbol": symbol, "name": name, "action": "HOLD",
                "score": 50, "confidence": 0, "current_price": 0,
                "reasons": ["데이터 부족"], "signals": [], "sub_scores": {},
            }

        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        volume = df["volume"].astype(float)
        current_price = float(close.iloc[-1])

        scores = {}
        reasons = []

        # ── 1. 평균회귀 (RSI Z-score + Bollinger Z-score) ──
        rsi = _compute_rsi_wilder(close, 14)
        rsi_val = float(rsi.iloc[-1])
        rsi_z = self._z_score(rsi, rsi_val, 60)
        # 음의 Z-score = 과매도 = 높은 점수 (역전)
        rsi_score = 50 - rsi_z * 15
        rsi_score = max(10, min(90, rsi_score))

        ma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        upper = ma20 + 2 * std20
        lower = ma20 - 2 * std20
        # %B 계산 (최소 밴드폭 체크)
        min_bandwidth = current_price * 0.001
        band_width = float(upper.iloc[-1]) - float(lower.iloc[-1])
        if band_width > min_bandwidth:
            pband = (close.iloc[-1] - float(lower.iloc[-1])) / band_width
        else:
            pband = 0.5

        # %B Z-score
        pband_series = (close - lower) / (upper - lower)
        pband_series = pband_series.replace([np.inf, -np.inf], 0.5).fillna(0.5)
        bb_z = self._z_score(pband_series, pband, 60)
        bb_score = 50 - bb_z * 15
        bb_score = max(10, min(90, bb_score))

        mean_rev_score = rsi_score * 0.5 + bb_score * 0.5
        scores["평균회귀"] = mean_rev_score
        if mean_rev_score >= 65:
            reasons.append(f"평균회귀↑ RSI={rsi_val:.0f} %B={pband:.2f}")
        elif mean_rev_score <= 35:
            reasons.append(f"평균회귀↓ RSI={rsi_val:.0f} %B={pband:.2f}")

        # ── 2. 추세추종 (MACD tanh + MA) ──
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        histogram = macd_line - signal_line

        hist_val = float(histogram.iloc[-1])
        hist_prev = float(histogram.iloc[-2]) if len(histogram) > 1 else 0

        # tanh 정규화 (변동성 높은 종목 포화 방지)
        hist_norm = hist_val / (current_price * 0.01) if current_price > 0 else 0
        macd_score = 50 + float(np.tanh(hist_norm)) * 30
        if hist_prev <= 0 < hist_val:
            macd_score += 15
            reasons.append("MACD 골든크로스")
        elif hist_prev >= 0 > hist_val:
            macd_score -= 15
            reasons.append("MACD 데드크로스")
        if hist_val > 0 and hist_val > hist_prev:
            macd_score += 5
        elif hist_val < 0 and hist_val < hist_prev:
            macd_score -= 5
        macd_score = max(10, min(90, macd_score))

        ma5 = float(close.rolling(5).mean().iloc[-1])
        ma20_val = float(ma20.iloc[-1])
        ma60 = float(close.rolling(60).mean().iloc[-1])
        ma120 = float(close.rolling(120).mean().iloc[-1])

        ma_score = 50
        if ma5 > ma20_val > ma60 > ma120:
            ma_score = 75
            reasons.append("MA 정배열")
        elif ma5 < ma20_val < ma60 < ma120:
            ma_score = 25
            reasons.append("MA 역배열")
        elif ma5 > ma20_val > ma60:
            ma_score = 65
        elif ma5 > ma20_val:
            ma_score = 58
        elif ma5 < ma20_val < ma60:
            ma_score = 35
        elif ma5 < ma20_val:
            ma_score = 42

        trend_score = macd_score * 0.5 + ma_score * 0.5
        scores["추세추종"] = trend_score

        # ── 3. 한국형 모멘텀 (역전 효과 + 폭락 가드) ──
        ret_20 = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 21 else 0
        ret_60 = float((close.iloc[-1] / close.iloc[-61] - 1) * 100) if len(close) > 61 else 0

        # 극단값 클램핑
        ret_20_c = np.clip(ret_20, -30, 30)
        ret_60_c = np.clip(ret_60, -50, 50)

        reversal_score = 50 - ret_20_c * 0.8
        momentum_score = 50 + ret_60_c * 0.3

        korea_mom_score = reversal_score * 0.6 + momentum_score * 0.4
        korea_mom_score = max(10, min(90, korea_mom_score))

        # 폭락 가드: 20일 -25% 이상 하락 시 역전매수 점수 제한
        if ret_20 < -25:
            korea_mom_score = min(korea_mom_score, 55)
            reasons.append(f"폭락가드 20d={ret_20:+.1f}%")
        elif korea_mom_score >= 65:
            reasons.append(f"역전매수 20d={ret_20:+.1f}%")
        elif korea_mom_score <= 35:
            reasons.append(f"과열경고 20d={ret_20:+.1f}%")

        scores["한국형모멘텀"] = korea_mom_score

        # ── 4. 거래량 분석 (v3.7: 기관/외국인 수급 하이브리드) ──
        vol_ma5 = float(volume.rolling(5).mean().iloc[-1])
        vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
        vol_ratio = vol_ma5 / vol_ma20 if vol_ma20 > 0 else 1

        # C1 Fix: close.diff()의 첫 값 NaN → fillna(0)
        obv = (volume * np.sign(close.diff().fillna(0))).cumsum()
        obv_ma5 = float(obv.rolling(5).mean().iloc[-1])
        obv_current = float(obv.iloc[-1])

        vol_score = 50

        # 기관/외국인 실제 수급 데이터 시도
        inst_used = False
        try:
            from institutional_crawler import InstitutionalCrawler
            _inst_crawler = getattr(self, '_inst_crawler', None)
            if _inst_crawler is None:
                _inst_crawler = InstitutionalCrawler()
                self._inst_crawler = _inst_crawler
            flow = _inst_crawler.get_flow_score(symbol)
            if flow is not None:
                vol_score = flow["score"]
                inst_used = True
                if flow["frgn_trend"] == "매수" and flow["inst_trend"] == "매수":
                    reasons.append(f"외국인+기관 매수 (5d외:{flow['frgn_5d']:+,})")
                elif flow["frgn_trend"] == "매수":
                    reasons.append(f"외국인 매수 (5d:{flow['frgn_5d']:+,})")
                elif flow["inst_trend"] == "매수":
                    reasons.append(f"기관 매수 (5d:{flow['inst_5d']:+,})")
                elif flow["frgn_trend"] == "매도" and flow["inst_trend"] == "매도":
                    reasons.append(f"외국인+기관 매도 (5d외:{flow['frgn_5d']:+,})")
        except Exception as e:
            logger.debug(f"수급 데이터 폴백 [{symbol}]: {e}")

        # 폴백: 기존 OBV 기반 로직
        if not inst_used:
            if vol_ratio > 1.5 and close.iloc[-1] > close.iloc[-2]:
                vol_score += 20
                reasons.append(f"거래량급증↑ {vol_ratio:.1f}배")
            elif vol_ratio > 1.2 and close.iloc[-1] > close.iloc[-2]:
                vol_score += 10
            elif vol_ratio > 1.5 and close.iloc[-1] < close.iloc[-2]:
                vol_score -= 15
                reasons.append(f"거래량급증↓ {vol_ratio:.1f}배")
            elif vol_ratio < 0.7:
                vol_score -= 5

            # OBV NaN 체크 후 적용
            if not (np.isnan(obv_current) or np.isnan(obv_ma5)):
                if obv_current > obv_ma5:
                    vol_score += 10
                elif obv_current < obv_ma5:
                    vol_score -= 10

        # 거래량 비율/연속 증가 (수급 사용 여부 상관없이 적용)
        recent_vols = volume.tail(5).values
        if len(recent_vols) >= 4 and all(
            recent_vols[i] > recent_vols[i - 1] for i in range(1, min(4, len(recent_vols)))
        ):
            vol_score += 8
            reasons.append("연속거래량증가")

        vol_score = max(10, min(90, vol_score))
        scores["거래량"] = vol_score

        # ── 5. 변동성 분석 ──
        returns = close.pct_change().dropna()
        vol_20 = float(returns.tail(20).std() * np.sqrt(252) * 100) if len(returns) >= 20 else 0
        vol_60 = float(returns.tail(60).std() * np.sqrt(252) * 100) if len(returns) >= 60 else vol_20

        vol_trend_score = 50
        if vol_60 > 0:
            if vol_20 < vol_60 * 0.7:
                vol_trend_score = 72
                reasons.append(f"변동성감소↑ {vol_20:.0f}%→{vol_60:.0f}%")
            elif vol_20 < vol_60 * 0.85:
                vol_trend_score = 62
                reasons.append(f"변동성감소 {vol_20:.0f}%→{vol_60:.0f}%")
            elif vol_20 > vol_60 * 1.5:
                vol_trend_score = 28
                reasons.append(f"변동성급등↑ {vol_20:.0f}%→{vol_60:.0f}%")
            elif vol_20 > vol_60 * 1.2:
                vol_trend_score = 38
                reasons.append(f"변동성증가 {vol_20:.0f}%→{vol_60:.0f}%")

        scores["변동성"] = vol_trend_score

        # ── 6. ML 예측 (v3.7) ──
        if self._ml_available and self._ml_predictor:
            try:
                ml_score = self._ml_predictor.predict_score(df, self._regime, scores)
                scores["ML예측"] = ml_score
                if ml_score >= 65:
                    reasons.append(f"ML매수신호 {ml_score:.0f}점")
                elif ml_score <= 35:
                    reasons.append(f"ML매도신호 {ml_score:.0f}점")
            except Exception as e:
                logger.debug(f"ML 예측 실패 [{name}]: {e}")

        # ── 7. 펀더멘털 가치 분석 (v3.8: 필터 전용, 가중치 0%) ──
        # 백테스트 검증 결과: 가중치 혼합 시 수익률 하락, 필터로만 사용이 최적
        fundamental_warnings = []
        f_score_val = 9  # 기본값: 통과
        if self._fundamental_analyzer:
            try:
                fund_result = self._fundamental_analyzer.evaluate(symbol, name, sector=sector)
                fundamental_warnings = fund_result.get("warnings", [])
                f_score_val = fund_result.get("raw", {}).get("f_score", 9)

                # F-Score 기반 필터 정보 (점수에는 반영 안 함)
                if fund_result["grade"] in ("A", "B"):
                    reasons.append(f"펀더멘털 {fund_result['grade']}등급")
                elif fund_result["grade"] in ("D", "F"):
                    reasons.append(f"펀더멘털 {fund_result['grade']}등급 (주의)")
            except Exception as e:
                logger.debug(f"펀더멘털 분석 실패 [{name}]: {e}")

        # ── NaN 가드: 모든 서브스코어 ──
        for k, v in scores.items():
            if np.isnan(v):
                scores[k] = 50
                logger.warning(f"NaN 감지 [{name}] {k} → 50으로 대체")

        # ── 앙상블 집계 ──
        weights = dict(self.REGIME_WEIGHTS.get(self._regime, self.REGIME_WEIGHTS["SIDEWAYS"]))

        # 없는 전략 가중치 제거 후 재정규화
        missing_strategies = [k for k in list(weights.keys()) if k not in scores]
        for ms in missing_strategies:
            del weights[ms]
        if missing_strategies:
            total_w = sum(weights.values())
            if total_w > 0:
                weights = {k: v / total_w for k, v in weights.items()}

        final_score = sum(scores.get(k, 50) * weights.get(k, 0) for k in weights)
        final_score = round(max(10, min(90, final_score)), 1)

        # 히스토리 기록 (적응형 임계값용)
        self._score_history.append(final_score)

        # 적응형 임계값 판단
        buy_th, sell_th = self._get_thresholds()
        if final_score >= buy_th:
            action = "BUY"
        elif final_score <= sell_th:
            action = "SELL"
        else:
            action = "HOLD"

        confidence = round(abs(final_score - 50) / 50, 2)

        signals = [
            {"strategy": k, "score": round(v, 1), "weight": weights.get(k, 0),
             "action": "BUY" if v >= 58 else "SELL" if v <= 42 else "HOLD",
             "reason": ""}
            for k, v in scores.items()
        ]

        return {
            "symbol": symbol, "name": name,
            "action": action,
            "score": final_score,
            "confidence": confidence,
            "current_price": int(current_price),
            "reasons": reasons,
            "signals": signals,
            "sub_scores": scores,
            "fundamental_warnings": fundamental_warnings,
            "f_score": f_score_val,
            "thresholds": {"buy": round(buy_th, 1), "sell": round(sell_th, 1)},
        }
