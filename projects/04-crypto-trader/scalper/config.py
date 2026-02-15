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
MARKETS = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]

# === Timeframe ===
CANDLE_INTERVAL = "minute3"   # 3분봉: 1분봉 대비 노이즈 대폭 감소
CANDLE_COUNT = 120            # 6시간 데이터 (3분 × 120 = 360분)

# === Trading Loop ===
LOOP_INTERVAL_SEC = 5         # 3분봉에 맞게 조정
WEIGHT_ADJUST_CYCLE = 300     # 300사이클마다 가중치 조정

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
MIN_ENSEMBLE_CONFIDENCE = 0.35  # 신뢰도 문턱 약간 상향
WEIGHT_EMA_ALPHA = 0.1
ENTRY_COOLDOWN_BARS = 5      # 3분봉 기준 5봉 = 15분 대기

# === Signal Exit Filter ===
SIGNAL_EXIT_MIN_BARS = 8     # 3분봉 기준 8봉 = 24분 보유 후 시그널 매도 허용
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
RISK_PER_TRADE = 0.01        # 잔고 1.0% 리스크 (보수적)
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 2.0    # 3분봉 ATR 더 크므로 축소 (was 4.0)
ATR_TP_MULTIPLIER = 3.5      # 3분봉 ATR 비례 조정 (was 6.0)
STOP_LOSS_MIN_PCT = 0.003    # 0.3% 최소 스탑 (was 0.4%)
STOP_LOSS_HARD_CAP = 0.007   # 0.7% 하드캡 (was 1.2%) ← 핵심 개선
TAKE_PROFIT_PCT = 0.008      # 0.8% 익절 (was 1.0%)
TAKE_PROFIT_MIN = 0.006      # 0.6% 최소 TP (was 1.0%)
TRAILING_ACTIVATE_PCT = 0.004  # 0.4% 수익 시 트레일링 (was 0.5%)
TRAILING_STOP_PCT = 0.002    # 0.2% 추적 (was 0.3%) ← 수익 더 잡기

# === Breakeven Stop ===
BREAKEVEN_AFTER_BARS = 20    # 3분봉 20봉 = 60분 후 BEP (was 999/비활성)
BREAKEVEN_BUFFER = 0.001     # 0.1% 버퍼 (was 0.15%)
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

# === Dynamic Market Scanner ===
DYNAMIC_MARKETS_ENABLED = True
SCANNER_TOP_N = 5               # 상위 5개 마켓
SCANNER_INTERVAL_SEC = 3600     # 1시간마다 스캔
SCANNER_MIN_VOLUME_KRW = 1_000_000_000  # 최소 24h 거래대금 10억원

# === Walk-Forward Optimizer ===
OPTIMIZER_ENABLED = True
OPTIMIZER_INTERVAL_SEC = 7200   # 2시간마다 최적화
OPTIMIZER_LOOKBACK_DAYS = 3     # 과거 3일 데이터
OPTIMIZER_N_PROFILES = 12       # 테스트할 프로필 수
OPTIMIZER_MARKETS = ["KRW-BTC", "KRW-ETH"]  # 최적화 대상 (고정, 속도)

# === Logging ===
LOG_LEVEL = os.getenv("SCALPER_LOG_LEVEL", "INFO")
