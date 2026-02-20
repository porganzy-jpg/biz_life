"""
Upbit Scalping Bot Configuration - v6.3

v6 changes (from v5):
- ATR 적응형 SL: 코인 변동성에 비례하는 손절 (하드캡 1.2%→3.0%)
- ATR SL=1.5x, TP=4.0x: 변동성 높은 코인에서 자연스러운 R:R
- 트레일링 개선: 0.8% 활성화, 0.3% 추적 (수익 조기 확보)
- Breakeven 지연: 16봉→48봉 (12시간, 조기 탈출 방지)
- 진입 강화: 최소 2전략 합의, 추세 위치 필터 활성화
- 스캐너 변동성 가중: 거래대금 * 변동성 복합 점수로 마켓 선정
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
CANDLE_INTERVAL = "minute15"  # 15분봉: 노이즈 대폭 감소, 안정적 신호
CANDLE_COUNT = 96             # 24시간 데이터 (15분 × 96 = 1440분)
CANDLE_INTERVAL_SEC = 900     # 15분 = 900초 (bars_held 계산용)

# === Trading Loop ===
LOOP_INTERVAL_SEC = 10        # 15분봉에 맞게 조정 (5s → 10s)
WEIGHT_ADJUST_CYCLE = 100     # 가중치 조정 주기 (약 17분)

# === RSI + Bollinger Band Strategy ===
RSI_PERIOD = 14               # 표준 RSI 기간 (7 → 14)
RSI_OVERSOLD = 35             # 약간 완화 (30 → 35)
RSI_OVERBOUGHT = 65           # 약간 완화 (70 → 65)
BB_PERIOD = 20                # 유지
BB_STD_DEV = 2.0              # 유지

# === VWAP + Volume Strategy ===
VWAP_PERIOD = 14              # 유지
VOLUME_SURGE_MULTIPLIER = 1.3 # 약간 완화 (1.5 → 1.3)

# === Stochastic RSI Strategy ===
STOCH_RSI_PERIOD = 14         # 유지
STOCH_K_PERIOD = 5            # 유지
STOCH_D_PERIOD = 3            # 유지
STOCH_OVERSOLD = 30           # 약간 완화 (25 → 30)
STOCH_OVERBOUGHT = 70         # 약간 완화 (75 → 70)

# === EMA Crossover Strategy ===
EMA_FAST = 5                  # 15분봉에 적합 (3 → 5)
EMA_SLOW = 13                 # 15분봉에 적합 (8 → 13)
EMA_TREND = 34                # 15분봉에 적합 (21 → 34)

# === Ensemble Weights ===
DEFAULT_WEIGHTS = {
    "rsi_bb": 0.30,
    "vwap_volume": 0.25,
    "stoch_rsi": 0.25,
    "ema_cross": 0.20,
}
MIN_AGREEMENT = 2             # 최소 2전략 합의 필수 (1 → 2, 진입 품질 향상)
MIN_ENSEMBLE_CONFIDENCE = 0.25  # 2전략 이상 합산 신뢰도 문턱 (0.20 → 0.25)
WEIGHT_EMA_ALPHA = 0.1
ENTRY_COOLDOWN_BARS = 3       # 15분봉 기준 3봉 = 45분 대기 (5 → 3)

# === Signal Exit Filter ===
SIGNAL_EXIT_MIN_BARS = 4      # 15분봉 기준 4봉 = 1시간 후 시그널 매도 허용 (8 → 4)
SIGNAL_EXIT_MIN_PROFIT = 0.003  # 수익 +0.3% 이상일 때만 시그널 매도 (-0.001 → 0.003)

# === Trend Filter (앙상블 레벨) ===
TREND_EMA_PERIOD = 50         # 장기 추세 판단
TREND_LOOKBACK = 10           # 기울기 측정 구간
TREND_POSITION_FILTER = True  # 활성화: 가격이 EMA50 위에서만 매수 (하락세 진입 차단)

# === Volatility Regime Filter ===
VOL_ATR_LOOKBACK = 60         # ATR 분포 계산 기간
VOL_LOW_PERCENTILE = 0.10     # 횡보장 허용 폭 확대 (0.2 → 0.10)
VOL_HIGH_PERCENTILE = 0.95    # 극단적 변동성만 제외 (0.9 → 0.95)

# === Risk Management ===
RISK_PER_TRADE = 0.02         # 잔고 2.0% 리스크
ATR_PERIOD = 14               # 유지
ATR_STOP_MULTIPLIER = 1.5     # ATR 비례 SL: 코인 변동성에 적응 (1.0 → 1.5)
ATR_TP_MULTIPLIER = 4.0       # ATR 비례 TP (4.5 → 4.0)
STOP_LOSS_MIN_PCT = 0.005     # 0.5% 최소 스탑
STOP_LOSS_HARD_CAP = 0.030    # 3.0% 하드캡 (1.2% → 3.0%): ATR 우선, 안전망만
TAKE_PROFIT_PCT = 0.030       # 3.0% 최소 TP 목표
TAKE_PROFIT_MIN = 0.020       # 2.0% 최소 TP
TRAILING_ACTIVATE_PCT = 0.008 # 0.8% 수익 시 트레일링 (1.0% → 0.8%): 빨리 활성화
TRAILING_STOP_PCT = 0.003     # 0.3% 추적 (0.5% → 0.3%): 타이트한 추적

# === Breakeven Stop ===
BREAKEVEN_AFTER_BARS = 48     # 15분봉 48봉 = 12시간 후 BEP (16 → 48): 조기 탈출 방지
BREAKEVEN_BUFFER = 0.002      # 0.2% 버퍼 (0.1% → 0.2%)
COMMISSION_RATE = 0.0005      # 업비트 편도 0.05%
ROUND_TRIP_COMMISSION = 0.001 # 왕복 0.1%

# === Kelly Criterion Adaptive Position Sizing ===
KELLY_ENABLED = True
KELLY_WINDOW = 50                 # 최근 N개 트레이드 기반 계산
KELLY_SAFETY_FACTOR = 0.5         # Half-Kelly (안전계수 50%)
KELLY_MIN_RISK = 0.005            # 최소 리스크 0.5%
KELLY_MAX_RISK = 0.04             # 최대 리스크 4.0%

# === Circuit Breaker ===
DAILY_LOSS_LIMIT = 0.05       # 일일 손실 5% (3% → 5%: 여유 확대)
MAX_CONSECUTIVE_LOSSES = 5    # 연속 5패 시 쿨다운 (4 → 5)
COOLDOWN_MINUTES = 10         # 쿨다운 10분 (15 → 10)
MAX_TRADES_PER_HOUR = 20      # 유지

# === Position Limits ===
MAX_OPEN_POSITIONS = 3        # 최대 동시 포지션 수

# === Dashboard ===
DASHBOARD_PORT = 8081

# === Alert ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === Dynamic Market Scanner ===
DYNAMIC_MARKETS_ENABLED = True
SCANNER_TOP_N = 8              # 상위 8개 마켓 (5 → 8)
SCANNER_INTERVAL_SEC = 3600    # 1시간마다 스캔
SCANNER_MIN_VOLUME_KRW = 10_000_000_000  # 최소 24h 거래대금 100억원 (10억 → 100억)

# === Walk-Forward Optimizer ===
OPTIMIZER_ENABLED = True
OPTIMIZER_INTERVAL_SEC = 7200  # 2시간마다 최적화
OPTIMIZER_LOOKBACK_DAYS = 3    # 과거 3일 데이터
OPTIMIZER_N_PROFILES = 12      # 테스트할 프로필 수
OPTIMIZER_MARKETS = ["KRW-BTC", "KRW-ETH"]  # 최적화 대상 (고정, 속도)

# === Multi-Timeframe Confluence ===
MTF_ENABLED = True
MTF_TIMEFRAMES = ["minute15", "minute60", "minute240"]  # 15m, 1h, 4h
MTF_MIN_CONFLUENCE = 2           # 최소 2개 타임프레임 정렬 필요
MTF_CACHE_SEC = 300              # 상위 TF 캐시 5분 (15m 루프에서 반복 호출 방지)

# === Portfolio Risk Management ===
PORTFOLIO_RISK_ENABLED = True
MAX_PORTFOLIO_VAR_PCT = 0.05        # 5% max portfolio VaR
CORRELATION_WINDOW = 96             # Rolling correlation window (96 x 15min = 24h)
MAX_CORRELATED_POSITIONS = 2        # Max positions in correlated (>threshold) assets
CONCENTRATION_THRESHOLD = 0.8       # Pearson corr above this = "highly correlated"

# === Logging ===
LOG_LEVEL = os.getenv("SCALPER_LOG_LEVEL", "INFO")
