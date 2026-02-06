"""
StockBot - 주식 분석 엔진

뉴스 크롤링 + 퀀트 분석을 통한 종목 선정 및 매매 시점 판단
"""
import hashlib
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np


@dataclass
class StockSignal:
    """주식 매매 신호"""
    symbol: str           # 종목코드
    name: str             # 종목명
    action: str           # BUY / SELL / HOLD
    confidence: float     # 신뢰도 0~1
    current_price: int    # 현재가
    target_price: int     # 목표가
    stop_loss_price: int  # 손절가
    reasons: list         # 판단 근거
    quant_score: float    # 퀀트 점수
    news_sentiment: float # 뉴스 감성 점수 (-1 ~ +1)
    timestamp: str


class QuantAnalyzer:
    """퀀트 분석 모듈"""

    def __init__(self):
        self.indicators = {}

    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std: float = 2.0):
        """볼린저밴드 계산"""
        df = df.copy()
        df["bb_ma"] = df["close"].rolling(window=period).mean()
        df["bb_std"] = df["close"].rolling(window=period).std()
        df["bb_upper"] = df["bb_ma"] + (df["bb_std"] * std)
        df["bb_lower"] = df["bb_ma"] - (df["bb_std"] * std)
        df["bb_pband"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
        return df

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14):
        """RSI 계산"""
        df = df.copy()
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        return df

    def calculate_macd(self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
        """MACD 계산"""
        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=fast).mean()
        df["ema_slow"] = df["close"].ewm(span=slow).mean()
        df["macd"] = df["ema_fast"] - df["ema_slow"]
        df["macd_signal"] = df["macd"].ewm(span=signal).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        return df

    def calculate_moving_averages(self, df: pd.DataFrame):
        """이동평균선 계산"""
        df = df.copy()
        for period in [5, 10, 20, 60, 120]:
            df[f"ma_{period}"] = df["close"].rolling(window=period).mean()
        return df

    def calculate_volume_analysis(self, df: pd.DataFrame):
        """거래량 분석"""
        df = df.copy()
        df["vol_ma_20"] = df["volume"].rolling(window=20).mean()
        df["vol_ratio"] = df["volume"] / df["vol_ma_20"]
        # OBV (On-Balance Volume)
        df["obv"] = (np.sign(df["close"].diff()) * df["volume"]).cumsum()
        return df

    def calculate_stochastic(self, df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
        """스토캐스틱 계산"""
        df = df.copy()
        low_min = df["low"].rolling(window=k_period).min()
        high_max = df["high"].rolling(window=k_period).max()
        df["stoch_k"] = ((df["close"] - low_min) / (high_max - low_min)) * 100
        df["stoch_d"] = df["stoch_k"].rolling(window=d_period).mean()
        return df

    def full_analysis(self, df: pd.DataFrame) -> pd.DataFrame:
        """전체 기술적 분석 수행"""
        df = self.calculate_bollinger_bands(df)
        df = self.calculate_rsi(df)
        df = self.calculate_macd(df)
        df = self.calculate_moving_averages(df)
        df = self.calculate_volume_analysis(df)
        df = self.calculate_stochastic(df)
        return df

    def generate_quant_score(self, df: pd.DataFrame) -> dict:
        """
        종합 퀀트 점수 생성 (0~100)

        각 지표별 점수를 가중 합산하여 종합 점수 산출
        - 50 이상: 매수 유리
        - 50 이하: 매도 유리
        """
        latest = df.iloc[-1]
        scores = {}

        # 1. RSI 점수 (30 이하: 매수, 70 이상: 매도)
        rsi = latest.get("rsi", 50)
        if rsi <= 30:
            scores["rsi"] = 80 + (30 - rsi)
        elif rsi >= 70:
            scores["rsi"] = 20 - (rsi - 70)
        else:
            scores["rsi"] = 50

        # 2. 볼린저밴드 위치
        bb_pband = latest.get("bb_pband", 0.5)
        if bb_pband <= 0.1:
            scores["bollinger"] = 85
        elif bb_pband >= 0.9:
            scores["bollinger"] = 15
        else:
            scores["bollinger"] = 50 + (0.5 - bb_pband) * 50

        # 3. MACD 신호
        macd_hist = latest.get("macd_hist", 0)
        prev_hist = df.iloc[-2].get("macd_hist", 0) if len(df) > 1 else 0
        if macd_hist > 0 and prev_hist <= 0:  # 골든크로스
            scores["macd"] = 80
        elif macd_hist < 0 and prev_hist >= 0:  # 데드크로스
            scores["macd"] = 20
        elif macd_hist > 0:
            scores["macd"] = 60
        else:
            scores["macd"] = 40

        # 4. 이동평균 배열
        ma_5 = latest.get("ma_5", 0)
        ma_20 = latest.get("ma_20", 0)
        ma_60 = latest.get("ma_60", 0)
        if ma_5 > ma_20 > ma_60 and all(v > 0 for v in [ma_5, ma_20, ma_60]):
            scores["ma_alignment"] = 75  # 정배열
        elif ma_5 < ma_20 < ma_60 and all(v > 0 for v in [ma_5, ma_20, ma_60]):
            scores["ma_alignment"] = 25  # 역배열
        else:
            scores["ma_alignment"] = 50

        # 5. 거래량
        vol_ratio = latest.get("vol_ratio", 1.0)
        if vol_ratio > 2.0 and latest["close"] > latest.get("ma_5", latest["close"]):
            scores["volume"] = 75  # 상승 + 거래량 폭증
        elif vol_ratio > 2.0 and latest["close"] < latest.get("ma_5", latest["close"]):
            scores["volume"] = 25  # 하락 + 거래량 폭증
        else:
            scores["volume"] = 50

        # 6. 스토캐스틱
        stoch_k = latest.get("stoch_k", 50)
        stoch_d = latest.get("stoch_d", 50)
        if stoch_k < 20 and stoch_k > stoch_d:
            scores["stochastic"] = 80  # 과매도 + 상향 전환
        elif stoch_k > 80 and stoch_k < stoch_d:
            scores["stochastic"] = 20  # 과매수 + 하향 전환
        else:
            scores["stochastic"] = 50

        # 가중 합산
        weights = {
            "rsi": 0.20,
            "bollinger": 0.15,
            "macd": 0.20,
            "ma_alignment": 0.20,
            "volume": 0.15,
            "stochastic": 0.10,
        }

        total_score = sum(scores.get(k, 50) * w for k, w in weights.items())

        return {
            "total_score": round(total_score, 1),
            "detail_scores": scores,
            "recommendation": "BUY" if total_score >= 65 else "SELL" if total_score <= 35 else "HOLD",
        }


class NewsAnalyzer:
    """
    뉴스 감성 분석 모듈

    실제 구현 시에는 네이버 뉴스, 한경, 매경 등을 크롤링하여 분석
    현재는 구조만 설계 (API 키 필요)
    """

    def __init__(self):
        self.cache = {}

    def analyze_sentiment(self, news_list: list) -> float:
        """
        뉴스 리스트의 감성 점수 계산

        Args:
            news_list: [{"title": str, "content": str, "date": str}, ...]

        Returns:
            float: -1.0 (매우 부정) ~ +1.0 (매우 긍정)
        """
        if not news_list:
            return 0.0

        # 긍정/부정 키워드 기반 간이 분석
        # 실전에서는 KoBERT 등 한국어 NLP 모델 사용
        positive_keywords = [
            "상승", "급등", "호재", "실적개선", "매수", "신고가", "돌파",
            "성장", "수주", "흑자전환", "목표가상향", "긍정적", "기대",
        ]
        negative_keywords = [
            "하락", "급락", "악재", "실적부진", "매도", "신저가", "이탈",
            "감소", "적자", "적자전환", "목표가하향", "부정적", "우려",
        ]

        total_score = 0
        for news in news_list:
            text = news.get("title", "") + " " + news.get("content", "")
            pos = sum(1 for k in positive_keywords if k in text)
            neg = sum(1 for k in negative_keywords if k in text)

            if pos + neg > 0:
                score = (pos - neg) / (pos + neg)
            else:
                score = 0
            total_score += score

        return round(total_score / max(len(news_list), 1), 2)

    def fetch_news(self, symbol: str, stock_name: str) -> list:
        """
        종목 관련 뉴스 수집 (구조 설계)

        실제 구현 시:
        - 네이버 뉴스 API
        - 한국경제 크롤링
        - 매일경제 크롤링
        - RSS 피드 수집
        """
        # 프로토타입: 더미 데이터 반환
        return [
            {
                "title": f"{stock_name} 실적 전망 긍정적",
                "content": "분기 실적이 시장 예상치를 상회할 것으로 전망",
                "date": datetime.now().isoformat(),
                "source": "한국경제",
            }
        ]


class StockSelector:
    """종목 선정 모듈"""

    def __init__(self):
        self.quant = QuantAnalyzer()
        self.news = NewsAnalyzer()

    def evaluate_stock(self, df: pd.DataFrame, symbol: str, name: str) -> StockSignal:
        """
        개별 종목 종합 평가

        Args:
            df: OHLCV DataFrame
            symbol: 종목코드 (예: "005930")
            name: 종목명 (예: "삼성전자")

        Returns:
            StockSignal: 매매 신호
        """
        # 기술적 분석
        analyzed_df = self.quant.full_analysis(df)
        quant_result = self.quant.generate_quant_score(analyzed_df)

        # 뉴스 감성 분석
        news_list = self.news.fetch_news(symbol, name)
        news_sentiment = self.news.analyze_sentiment(news_list)

        # 종합 판단
        quant_score = quant_result["total_score"]
        # 뉴스 감성을 퀀트 점수에 가중 반영 (20%)
        combined_score = quant_score * 0.8 + (news_sentiment * 50 + 50) * 0.2

        latest = analyzed_df.iloc[-1]
        current_price = int(latest["close"])

        # 목표가/손절가 설정
        bb_upper = latest.get("bb_upper", current_price * 1.05)
        bb_lower = latest.get("bb_lower", current_price * 0.95)

        if combined_score >= 65:
            action = "BUY"
            target = int(bb_upper)
            stop_loss = int(current_price * 0.97)
        elif combined_score <= 35:
            action = "SELL"
            target = int(bb_lower)
            stop_loss = int(current_price * 1.03)
        else:
            action = "HOLD"
            target = current_price
            stop_loss = int(current_price * 0.95)

        # 판단 근거 수집
        reasons = []
        detail = quant_result["detail_scores"]
        if detail.get("rsi", 50) >= 70:
            reasons.append(f"RSI 과매도 ({detail['rsi']:.0f}점)")
        elif detail.get("rsi", 50) <= 30:
            reasons.append(f"RSI 과매수 ({detail['rsi']:.0f}점)")
        if detail.get("macd", 50) >= 70:
            reasons.append("MACD 골든크로스")
        elif detail.get("macd", 50) <= 30:
            reasons.append("MACD 데드크로스")
        if detail.get("ma_alignment", 50) >= 65:
            reasons.append("이동평균선 정배열")
        elif detail.get("ma_alignment", 50) <= 35:
            reasons.append("이동평균선 역배열")
        if news_sentiment > 0.3:
            reasons.append(f"뉴스 긍정적 (감성:{news_sentiment:+.2f})")
        elif news_sentiment < -0.3:
            reasons.append(f"뉴스 부정적 (감성:{news_sentiment:+.2f})")

        return StockSignal(
            symbol=symbol,
            name=name,
            action=action,
            confidence=abs(combined_score - 50) / 50,
            current_price=current_price,
            target_price=target,
            stop_loss_price=stop_loss,
            reasons=reasons,
            quant_score=round(quant_score, 1),
            news_sentiment=news_sentiment,
            timestamp=datetime.now().isoformat(),
        )


# === 데모 실행 ===
if __name__ == "__main__":
    print("=" * 60)
    print("  StockBot - Stock Analyzer v1.0")
    print("=" * 60)

    # 더미 데이터로 시연
    np.random.seed(42)
    dates = pd.date_range(start="2025-01-01", periods=200, freq="D")
    price = 70000 + np.cumsum(np.random.randn(200) * 500)

    df = pd.DataFrame({
        "open": price + np.random.randn(200) * 200,
        "high": price + abs(np.random.randn(200) * 500),
        "low": price - abs(np.random.randn(200) * 500),
        "close": price,
        "volume": np.random.randint(1000000, 50000000, 200),
    }, index=dates)

    selector = StockSelector()
    signal = selector.evaluate_stock(df, "005930", "Samsung Electronics")

    print(f"\n  Symbol: {signal.symbol} ({signal.name})")
    print(f"  Action: {signal.action}")
    print(f"  Confidence: {signal.confidence:.2f}")
    print(f"  Current Price: {signal.current_price:,} KRW")
    print(f"  Target Price: {signal.target_price:,} KRW")
    print(f"  Stop Loss: {signal.stop_loss_price:,} KRW")
    print(f"  Quant Score: {signal.quant_score}")
    print(f"  News Sentiment: {signal.news_sentiment:+.2f}")
    print(f"  Reasons:")
    for r in signal.reasons:
        print(f"    - {r}")
