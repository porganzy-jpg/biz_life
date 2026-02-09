"""
Upbit Scalping Bot Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === Upbit API ===
UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY", "")
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY", "")

# === Trading Mode ===
PAPER_TRADING = os.getenv("SCALPER_PAPER_TRADING", "true").lower() == "true"
PAPER_INITIAL_KRW = float(os.getenv("SCALPER_PAPER_KRW", "1000000"))

# === Target Markets ===
MARKETS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE"]

# === Timeframe ===
CANDLE_INTERVAL = "minute1"
CANDLE_COUNT = 200  # 장기 EMA + 지표 안정화

# === Trading Loop ===
LOOP_INTERVAL_SEC = 3
WEIGHT_ADJUST_CYCLE = 500  # 500사이클마다 가중치 조정

# === RSI + Bollinger Band Strategy ===
RSI_PERIOD = 7               # 노이즈 감소
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
BB_PERIOD = 20               # 밴드 안정화
BB_STD_DEV = 2.0

# === VWAP + Volume Strategy ===
VWAP_PERIOD = 14
VOLUME_SURGE_MULTIPLIER = 1.5

# === Stochastic RSI Strategy ===
STOCH_RSI_PERIOD = 14
STOCH_K_PERIOD = 5
STOCH_D_PERIOD = 3
STOCH_OVERSOLD = 25
STOCH_OVERBOUGHT = 75

# === EMA Crossover Strategy ===
EMA_FAST = 3
EMA_SLOW = 8
EMA_TREND = 21

# === Ensemble Weights ===
DEFAULT_WEIGHTS = {
    "rsi_bb": 0.30,
    "vwap_volume": 0.25,
    "stoch_rsi": 0.25,
    "ema_cross": 0.20,
}
MIN_AGREEMENT = 2            # 최소 2개 전략 동의
MIN_ENSEMBLE_CONFIDENCE = 0.30
WEIGHT_EMA_ALPHA = 0.1
ENTRY_COOLDOWN_BARS = 8      # 거래 후 최소 8분 대기

# === Signal Exit Filter ===
SIGNAL_EXIT_MIN_BARS = 15    # 진입 후 최소 15분 보유 후 시그널 매도 허용
SIGNAL_EXIT_MIN_PROFIT = -0.001  # 시그널 매도는 -0.1% 이상일 때만

# === Trend Filter (앙상블 레벨) ===
TREND_EMA_PERIOD = 50        # 장기 추세 판단
TREND_LOOKBACK = 10          # 기울기 측정 구간
TREND_POSITION_FILTER = True # 가격이 장기 EMA 아래면 BUY 차단

# === Volatility Regime Filter ===
VOL_ATR_LOOKBACK = 60        # ATR 분포 계산 기간 (60분)
VOL_LOW_PERCENTILE = 0.2     # 변동성 너무 낮으면 HOLD (횡보장)
VOL_HIGH_PERCENTILE = 0.9    # 변동성 너무 높으면 HOLD (급변장)

# === Risk Management ===
RISK_PER_TRADE = 0.015       # 잔고 1.5% 리스크
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 4.0    # ATR 0.13% × 4 = 0.52%
ATR_TP_MULTIPLIER = 6.0      # ATR × 6 = 0.78% (min 1.0% 보장)
STOP_LOSS_MIN_PCT = 0.004    # 0.4% 최소 스탑
STOP_LOSS_HARD_CAP = 0.012   # 1.2% 하드캡
TAKE_PROFIT_PCT = 0.010      # 1.0% 익절
TAKE_PROFIT_MIN = 0.010      # 1.0% 고정
TRAILING_ACTIVATE_PCT = 0.005  # 0.5% 수익 시 트레일링
TRAILING_STOP_PCT = 0.003    # 0.3% 추적

# === Breakeven Stop (비활성: 999분) ===
BREAKEVEN_AFTER_BARS = 999   # 사실상 비활성
BREAKEVEN_BUFFER = 0.0015
COMMISSION_RATE = 0.0005     # 업비트 편도 0.05%
ROUND_TRIP_COMMISSION = 0.001  # 왕복 0.1%

# === Circuit Breaker ===
DAILY_LOSS_LIMIT = 0.03      # 일일 손실 3%
MAX_CONSECUTIVE_LOSSES = 4   # 연속 4패 시 쿨다운
COOLDOWN_MINUTES = 15
MAX_TRADES_PER_HOUR = 20

# === Dashboard ===
DASHBOARD_PORT = 8081

# === Alert ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === Logging ===
LOG_LEVEL = os.getenv("SCALPER_LOG_LEVEL", "INFO")
