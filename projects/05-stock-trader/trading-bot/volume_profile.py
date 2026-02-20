"""
장중 거래량 프로파일 (Intraday Volume Profile)

최근 20일 데이터를 기반으로 30분 버킷의 거래량 분포를 구축하여
VWAP 실행 엔진에 기대 거래량 커브를 제공한다.

한국 주식시장 09:00 ~ 15:30 기준.
"""
import logging
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 한국 주식시장 30분 버킷 (09:00 ~ 15:30)
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(15, 30)
BUCKET_MINUTES = 30

# 버킷 라벨: "09:00", "09:30", ..., "15:00"
BUCKET_LABELS: List[str] = []
_t = datetime.combine(datetime.today(), MARKET_OPEN)
_end = datetime.combine(datetime.today(), MARKET_CLOSE)
while _t < _end:
    BUCKET_LABELS.append(_t.strftime("%H:%M"))
    _t += timedelta(minutes=BUCKET_MINUTES)

NUM_BUCKETS = len(BUCKET_LABELS)  # 13 buckets


def _bucket_index_for_time(t: time) -> Optional[int]:
    """시각을 버킷 인덱스로 변환 (범위 밖이면 None)."""
    if t < MARKET_OPEN or t >= MARKET_CLOSE:
        return None
    minutes_from_open = (t.hour - MARKET_OPEN.hour) * 60 + (t.minute - MARKET_OPEN.minute)
    idx = minutes_from_open // BUCKET_MINUTES
    return min(idx, NUM_BUCKETS - 1)


def current_bucket_index() -> Optional[int]:
    """현재 시각의 버킷 인덱스 반환 (장 시간 외 None)."""
    return _bucket_index_for_time(datetime.now().time())


class VolumeProfile:
    """
    장중 거래량 프로파일.

    과거 N일 데이터를 기반으로 30분 버킷별 평균 거래량 비율을 산출한다.
    VWAP 실행 시 각 시간대에 배분할 수량 비율로 사용된다.
    """

    def __init__(self, lookback_days: int = 20):
        self.lookback_days = lookback_days
        # symbol -> {"profile": np.array(NUM_BUCKETS), "avg_daily_volume": float, "updated": str}
        self._cache: Dict[str, dict] = {}
        # 기본 프로파일 (한국 시장 경험적 패턴: U자형)
        self._default_profile = self._build_default_profile()

    @staticmethod
    def _build_default_profile() -> np.ndarray:
        """
        경험적 기본 거래량 프로파일 (U자형 곡선).

        한국 시장 특성:
        - 09:00~09:30: 높은 거래량 (개장 효과)
        - 10:00~14:00: 낮은 거래량 (중간 시간대)
        - 14:30~15:30: 높은 거래량 (마감 효과)
        """
        # 13개 버킷 (09:00 ~ 15:00)
        raw = np.array([
            12.0,  # 09:00-09:30 (높음)
            10.0,  # 09:30-10:00
            8.0,   # 10:00-10:30
            7.0,   # 10:30-11:00
            6.5,   # 11:00-11:30
            6.0,   # 11:30-12:00
            5.5,   # 12:00-12:30 (점심, 최저)
            6.0,   # 12:30-13:00
            7.0,   # 13:00-13:30
            7.5,   # 13:30-14:00
            8.0,   # 14:00-14:30
            8.5,   # 14:30-15:00
            8.0,   # 15:00-15:30
        ])
        return raw / raw.sum()  # 합계 1.0으로 정규화

    def build_profile(self, daily_ohlcv: pd.DataFrame,
                      intraday_volumes: Optional[List[dict]] = None) -> np.ndarray:
        """
        일별 OHLCV + (선택적) 분봉 데이터로 거래량 프로파일 구축.

        Args:
            daily_ohlcv: 일봉 데이터 (columns: open, high, low, close, volume)
            intraday_volumes: 분봉/30분봉 거래량 리스트 (선택)
                [{"timestamp": datetime, "volume": int}, ...]

        Returns:
            np.ndarray: 정규화된 버킷별 거래량 비율 (합계 1.0)
        """
        if intraday_volumes and len(intraday_volumes) > NUM_BUCKETS:
            return self._build_from_intraday(intraday_volumes)

        # 분봉 데이터가 없으면 기본 프로파일에 일별 변동성으로 조정
        return self._adjust_default_with_daily(daily_ohlcv)

    def _build_from_intraday(self, intraday_volumes: List[dict]) -> np.ndarray:
        """분봉 데이터에서 직접 프로파일 구축."""
        buckets = np.zeros(NUM_BUCKETS)
        counts = np.zeros(NUM_BUCKETS)

        for entry in intraday_volumes:
            ts = entry.get("timestamp")
            vol = entry.get("volume", 0)
            if ts is None or vol <= 0:
                continue

            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except (ValueError, TypeError):
                    continue

            idx = _bucket_index_for_time(ts.time())
            if idx is not None:
                buckets[idx] += vol
                counts[idx] += 1

        # 버킷별 평균
        for i in range(NUM_BUCKETS):
            if counts[i] > 0:
                buckets[i] /= counts[i]

        total = buckets.sum()
        if total <= 0:
            return self._default_profile.copy()

        return buckets / total

    def _adjust_default_with_daily(self, daily_ohlcv: pd.DataFrame) -> np.ndarray:
        """
        일봉 데이터의 변동성 패턴으로 기본 프로파일을 미세 조정.

        거래량이 급등한 날은 시초/종가 비중이 더 높아지는 경향을 반영한다.
        """
        profile = self._default_profile.copy()

        if daily_ohlcv is None or daily_ohlcv.empty:
            return profile

        try:
            recent = daily_ohlcv.tail(self.lookback_days)
            if len(recent) < 5:
                return profile

            vol_series = recent["volume"].values
            avg_vol = np.mean(vol_series)
            if avg_vol <= 0:
                return profile

            # 최근 거래량/평균 비율
            vol_ratio = vol_series[-1] / avg_vol if avg_vol > 0 else 1.0

            # 거래량 급등 시 시초/종가 버킷 비중 강화
            if vol_ratio > 1.5:
                boost = min(vol_ratio - 1.0, 1.0) * 0.03
                profile[0] += boost  # 시초
                profile[-1] += boost  # 종가 전
                profile[-2] += boost * 0.5
                # 재정규화
                profile = profile / profile.sum()

        except Exception as e:
            logger.debug(f"프로파일 조정 실패: {e}")

        return profile

    def get_profile(self, symbol: str, daily_ohlcv: pd.DataFrame,
                    intraday_volumes: Optional[List[dict]] = None) -> dict:
        """
        종목의 거래량 프로파일을 반환한다.

        Returns:
            dict: {
                "symbol": str,
                "buckets": [{"label": "09:00", "weight": 0.12}, ...],
                "avg_daily_volume": float,
                "profile_source": "intraday" | "estimated",
                "updated": str
            }
        """
        profile = self.build_profile(daily_ohlcv, intraday_volumes)

        # 평균 일일 거래량
        avg_daily_vol = 0.0
        if daily_ohlcv is not None and not daily_ohlcv.empty:
            recent = daily_ohlcv.tail(self.lookback_days)
            avg_daily_vol = float(recent["volume"].mean())

        result = {
            "symbol": symbol,
            "buckets": [
                {"label": BUCKET_LABELS[i], "weight": round(float(profile[i]), 6)}
                for i in range(NUM_BUCKETS)
            ],
            "avg_daily_volume": avg_daily_vol,
            "profile_source": "intraday" if intraday_volumes else "estimated",
            "updated": datetime.now().isoformat(),
        }

        # 캐시 저장
        self._cache[symbol] = {
            "profile": profile,
            "avg_daily_volume": avg_daily_vol,
            "updated": result["updated"],
        }

        return result

    def get_slice_weights(self, symbol: str, start_bucket: int,
                          num_slices: int) -> np.ndarray:
        """
        특정 시점부터 N개 슬라이스에 대한 가중치를 반환한다.
        VWAP 실행 엔진에서 사용.

        Args:
            symbol: 종목코드
            start_bucket: 시작 버킷 인덱스
            num_slices: 슬라이스 수

        Returns:
            np.ndarray: 슬라이스별 가중치 (합계 1.0)
        """
        cached = self._cache.get(symbol)
        if cached is None:
            profile = self._default_profile.copy()
        else:
            profile = cached["profile"].copy()

        # 현재 버킷부터 남은 구간 추출
        end_bucket = min(start_bucket + num_slices, NUM_BUCKETS)
        remaining = profile[start_bucket:end_bucket]

        if len(remaining) == 0:
            # 장 마감 후이면 균등 배분
            return np.ones(num_slices) / num_slices

        # num_slices가 남은 버킷보다 많으면 버킷 내 세분화
        if num_slices <= len(remaining):
            weights = remaining[:num_slices]
        else:
            # 버킷을 슬라이스 수에 맞게 보간
            weights = np.interp(
                np.linspace(0, len(remaining) - 1, num_slices),
                np.arange(len(remaining)),
                remaining,
            )

        total = weights.sum()
        if total <= 0:
            return np.ones(num_slices) / num_slices

        return weights / total

    def get_avg_daily_volume(self, symbol: str) -> float:
        """종목의 20일 평균 거래량 반환 (캐시 기준)."""
        cached = self._cache.get(symbol)
        if cached:
            return cached["avg_daily_volume"]
        return 0.0

    def detect_volume_anomaly(self, symbol: str,
                              current_volume: float,
                              daily_ohlcv: pd.DataFrame) -> dict:
        """
        거래량 이상 감지.

        현재 거래량이 과거 분포 대비 이상치인지 판별한다.

        Returns:
            dict: {
                "is_anomaly": bool,
                "severity": "normal" | "elevated" | "extreme",
                "z_score": float,
                "ratio": float,  # 현재/평균
                "avg_volume": float,
            }
        """
        if daily_ohlcv is None or daily_ohlcv.empty or current_volume <= 0:
            return {
                "is_anomaly": False,
                "severity": "normal",
                "z_score": 0.0,
                "ratio": 0.0,
                "avg_volume": 0.0,
            }

        recent = daily_ohlcv.tail(self.lookback_days)
        if len(recent) < 5:
            return {
                "is_anomaly": False,
                "severity": "normal",
                "z_score": 0.0,
                "ratio": 0.0,
                "avg_volume": 0.0,
            }

        vol_mean = float(recent["volume"].mean())
        vol_std = float(recent["volume"].std())

        if vol_std <= 0 or vol_mean <= 0:
            return {
                "is_anomaly": False,
                "severity": "normal",
                "z_score": 0.0,
                "ratio": current_volume / max(vol_mean, 1),
                "avg_volume": vol_mean,
            }

        z_score = (current_volume - vol_mean) / vol_std
        ratio = current_volume / vol_mean

        if z_score > 3.0:
            severity = "extreme"
            is_anomaly = True
        elif z_score > 2.0:
            severity = "elevated"
            is_anomaly = True
        else:
            severity = "normal"
            is_anomaly = False

        return {
            "is_anomaly": is_anomaly,
            "severity": severity,
            "z_score": round(z_score, 2),
            "ratio": round(ratio, 2),
            "avg_volume": round(vol_mean),
        }

    def get_expected_volume_at(self, symbol: str, bucket_index: int) -> float:
        """특정 버킷 시점의 기대 거래량 반환."""
        cached = self._cache.get(symbol)
        if not cached:
            profile = self._default_profile
            avg_vol = 0.0
        else:
            profile = cached["profile"]
            avg_vol = cached["avg_daily_volume"]

        if 0 <= bucket_index < NUM_BUCKETS and avg_vol > 0:
            return avg_vol * profile[bucket_index]
        return 0.0
