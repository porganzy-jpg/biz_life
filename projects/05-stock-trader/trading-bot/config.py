"""
StockBot 설정 파일
한국투자증권 API 및 매매 설정
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === 한국투자증권 API ===
KIS_APP_KEY = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")
KIS_ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO", "")  # 계좌번호 (8자리-2자리)
KIS_IS_PAPER = os.getenv("KIS_IS_PAPER", "true").lower() == "true"

# === 매매 설정 ===
STOCK_TRADING_CONFIG = {
    "max_positions": 20,              # 최대 동시 보유 종목
    "max_single_pct": 10.0,          # 단일 종목 최대 비율
    "max_sector_pct": 30.0,          # 단일 섹터 최대 비율
    "min_cash_reserve_pct": 20.0,    # 최소 현금 보유 비율
    "stop_loss_pct": -5.0,           # 손절 라인
    "take_profit_pct": 15.0,         # 익절 라인
    "trade_interval_minutes": 5,     # 매매 체크 간격 (분)
}

# === 분석 설정 ===
ANALYSIS_CONFIG = {
    # 퀀트 점수 가중치
    "weight_technical": 0.30,
    "weight_sentiment": 0.25,
    "weight_flow": 0.25,
    "weight_fundamental": 0.20,

    # 기술적 분석 파라미터
    "bb_period": 20,
    "bb_std": 2.0,
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "ma_periods": [5, 20, 60, 120],
}

# === 관심 종목 (기본) ===
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
]

# === 대시보드 ===
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 8081

# === 로깅 ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
