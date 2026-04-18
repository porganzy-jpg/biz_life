"""
StockBot 설정 파일 v3.7
한국투자증권 API + 매매 + 리스크 + 알림 설정
200만원 소규모 자본 최적화
v3.7: 멀티채널 알림 + 리밸런싱 + 기관수급 + WebSocket + ML 종목선정
v3.6: RSI(2) 급락 매수 추가 (RSI2<10 & MA200위, 시간기반 청산)
v3.5: ATR 기반 포지션 사이징 (거래당 자본 2% 리스크)
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === 한국투자증권 API ===
KIS_APP_KEY = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")
KIS_ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO", "")
KIS_IS_PAPER = os.getenv("KIS_IS_PAPER", "true").lower() == "true"

# === 트레이딩 모드 (이중 안전장치) ===
# paper: 페이퍼 트레이딩 (기본값), live: 실전 매매
TRADING_MODE = os.getenv("TRADING_MODE", "paper")
# 라이브 전환 시 이중 확인 (TRADING_MODE=live + 이 값도 true여야 실전 매매)
LIVE_TRADING_CONFIRMED = os.getenv("LIVE_TRADING_CONFIRMED", "false").lower() == "true"

# === 초기 자본 ===
# 환경변수로 설정 가능, 기본값 200만원
INITIAL_CAPITAL = int(os.getenv("INITIAL_CAPITAL", "2000000"))

# === 자본 규모별 자동 조정 ===
def _auto_adjust_config(capital: int) -> dict:
    """자본 규모에 따라 매매 설정 자동 조정"""
    if capital <= 3_000_000:  # 300만원 이하 소규모
        return {
            "max_positions": 4,
            "max_single_pct": 30.0,
            "max_sector_pct": 50.0,
            "min_cash_reserve_pct": 15.0,
            "take_profit_pct": 15.0,  # v3.2: 10→15 (1년 백테스트 최적)
            "min_buy_score": 58,  # v3.1: 62→58 (서브스코어 범위 확대 반영)
        }
    elif capital <= 10_000_000:  # 1000만원 이하 중규모
        return {
            "max_positions": 8,
            "max_single_pct": 20.0,
            "max_sector_pct": 40.0,
            "min_cash_reserve_pct": 18.0,
            "take_profit_pct": 12.0,
            "min_buy_score": 59,  # v3.1: 63→59
        }
    else:  # 대규모
        return {
            "max_positions": 15,
            "max_single_pct": 10.0,
            "max_sector_pct": 30.0,
            "min_cash_reserve_pct": 20.0,
            "take_profit_pct": 15.0,
            "min_buy_score": 60,  # v3.1: 65→60
        }

_auto = _auto_adjust_config(INITIAL_CAPITAL)

# === 매매 설정 ===
STOCK_TRADING_CONFIG = {
    "max_positions": _auto["max_positions"],
    "max_single_pct": _auto["max_single_pct"],
    "max_sector_pct": _auto["max_sector_pct"],
    "min_cash_reserve_pct": _auto["min_cash_reserve_pct"],
    "stop_loss_pct": -5.0,
    "take_profit_pct": _auto["take_profit_pct"],
    "atr_period": 14,            # ATR 계산 기간
    "atr_multiplier": 2.0,       # Chandelier Exit 배수 (최고가 - N*ATR)
    "atr_risk_pct": 2.0,         # ATR 사이징: 거래당 리스크 비율 (자본의 2%)
    "trade_interval_minutes": 3,
    "min_buy_score": _auto["min_buy_score"],
    "min_confidence": 0.15,  # v3.1: 0.3→0.15 (서브스코어 범위 확대 반영)
}

# === 서킷브레이커 설정 ===
CIRCUIT_BREAKER_CONFIG = {
    "max_daily_loss_pct": -3.0,
    "max_consecutive_losses": 5,
    "max_daily_trades": 20,
    "cooldown_minutes": 30,
    "initial_capital": INITIAL_CAPITAL,
    "max_daily_order_amount": INITIAL_CAPITAL * 2,  # 일일 주문 한도: 자본의 200%
}

# === 손실 한도 (KRW 절대값) ===
MAX_DAILY_LOSS_KRW = int(os.getenv("MAX_DAILY_LOSS_KRW", str(int(INITIAL_CAPITAL * 0.03))))
MAX_WEEKLY_LOSS_KRW = int(os.getenv("MAX_WEEKLY_LOSS_KRW", str(int(INITIAL_CAPITAL * 0.07))))

# === 분석 설정 ===
ANALYSIS_CONFIG = {
    # 퀀트 점수 가중치 (v3.1: 5전략 통합, 국면별 자동 조정)
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
# 200만원 기준: 1주당 30만원 이하 종목만 (삼성바이오, LG에너지 제외)
# 대체 종목: 하나금융, SK, 삼성생명, SK텔레콤
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
    {"code": "086790", "name": "하나금융지주", "sector": "금융"},
    {"code": "005380", "name": "현대자동차", "sector": "자동차"},
    {"code": "000270", "name": "기아", "sector": "자동차"},
    {"code": "068270", "name": "셀트리온", "sector": "바이오"},
    {"code": "034730", "name": "SK", "sector": "지주"},
    {"code": "032830", "name": "삼성생명", "sector": "보험"},
    {"code": "017670", "name": "SK텔레콤", "sector": "통신"},
]

# === 대시보드 ===
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 8082

# === 텔레그램 ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === Discord ===
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# === Email (SMTP) ===
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")

# === 로깅 ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
