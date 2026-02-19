"""
StockBot 설정 파일 v2.0
한국투자증권 API + 매매 + 리스크 + 알림 설정
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === 한국투자증권 API ===
KIS_APP_KEY = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")
KIS_ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO", "")
KIS_IS_PAPER = os.getenv("KIS_IS_PAPER", "true").lower() == "true"

# === 매매 설정 ===
STOCK_TRADING_CONFIG = {
    "max_positions": 15,              # 최대 동시 보유 종목
    "max_single_pct": 10.0,          # 단일 종목 최대 비율 (%)
    "max_sector_pct": 30.0,          # 단일 섹터 최대 비율 (%)
    "min_cash_reserve_pct": 20.0,    # 최소 현금 보유 비율 (%)
    "stop_loss_pct": -5.0,           # 손절 라인 (%)
    "take_profit_pct": 15.0,         # 익절 라인 (%)
    "trailing_stop_pct": -5.0,       # 트레일링 스탑 (고점 대비 %)
    "trade_interval_minutes": 5,      # 매매 체크 간격 (분)
    "min_buy_score": 65,             # 최소 매수 점수
    "min_confidence": 0.3,           # 최소 신뢰도
}

# === 서킷브레이커 설정 ===
CIRCUIT_BREAKER_CONFIG = {
    "max_daily_loss_pct": -3.0,      # 일일 최대 손실
    "max_consecutive_losses": 5,      # 최대 연속 손실
    "max_daily_trades": 20,          # 일일 최대 거래 횟수
    "cooldown_minutes": 30,          # 발동 후 쿨다운 (분)
}

# === 분석 설정 ===
ANALYSIS_CONFIG = {
    # 퀀트 점수 가중치 (8전략)
    "weight_technical": 0.25,
    "weight_sentiment": 0.20,
    "weight_flow": 0.20,
    "weight_momentum": 0.20,
    "weight_fundamental": 0.15,

    # 시장 국면(Regime) 감지
    "regime_ma_short": 20,
    "regime_ma_long": 60,
    "regime_adx_period": 14,
    "regime_adx_trending": 25.0,
    "regime_adx_sideways": 20.0,

    # 기술적 분석 파라미터
    "bb_period": 20,
    "bb_std": 2.0,
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "ma_periods": [5, 20, 60, 120],
}

# === 관심 종목 ===
WATCHLIST = [
    {"code": "005930", "name": "삼성전자", "sector": "반도체"},
    {"code": "000660", "name": "SK하이닉스", "sector": "반도체"},
    {"code": "035420", "name": "NAVER", "sector": "인터넷"},
    {"code": "035720", "name": "카카오", "sector": "인터넷"},
    {"code": "051910", "name": "LG화학", "sector": "화학"},
    {"code": "006400", "name": "삼성SDI", "sector": "2차전지"},
    {"code": "003670", "name": "포스코퓨처엠", "sector": "2차전지"},
    {"code": "028260", "name": "삼성물산", "sector": "건설"},
    {"code": "105560", "name": "KB금융", "sector": "금융"},
    {"code": "055550", "name": "신한지주", "sector": "금융"},
    {"code": "005380", "name": "현대자동차", "sector": "자동차"},
    {"code": "000270", "name": "기아", "sector": "자동차"},
    {"code": "207940", "name": "삼성바이오로직스", "sector": "바이오"},
    {"code": "068270", "name": "셀트리온", "sector": "바이오"},
    {"code": "373220", "name": "LG에너지솔루션", "sector": "2차전지"},
]

# === 대시보드 ===
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 8082

# === 텔레그램 ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === 로깅 ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
