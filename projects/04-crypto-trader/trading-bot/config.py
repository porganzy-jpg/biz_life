"""
CryptoBot 설정 파일
실제 API 키는 .env 파일에 보관 (절대 커밋하지 않음)
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === 거래소 설정 ===
EXCHANGE = os.getenv("EXCHANGE", "upbit")  # upbit 또는 binance

# Upbit API
UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY", "")
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY", "")

# Binance API
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")

# === 매매 설정 ===
TRADING_CONFIG = {
    "max_investment_ratio": 0.10,   # 전체 자산의 최대 10%만 사용
    "per_trade_ratio": 0.02,        # 1회 매매 시 전체 자산의 2%
    "stop_loss_pct": -3.0,          # 손절 라인: -3%
    "take_profit_pct": 5.0,         # 익절 라인: +5%
    "max_open_positions": 3,        # 동시 최대 포지션 수
    "trade_interval_seconds": 60,   # 매매 체크 간격 (초)
}

# === 전략 설정 ===
STRATEGY_CONFIG = {
    # 볼린저 밴드
    "bb_period": 20,
    "bb_std": 2.0,

    # RSI
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,

    # MACD
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,

    # 이동평균선
    "ma_short": 5,
    "ma_long": 20,
}

# === 타겟 마켓 ===
TARGET_MARKETS = [
    "KRW-BTC",
    "KRW-ETH",
    "KRW-XRP",
    "KRW-SOL",
    "KRW-DOGE",
    "KRW-ADA",
]

# === 대시보드 설정 ===
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 8080

# === 로깅 ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
