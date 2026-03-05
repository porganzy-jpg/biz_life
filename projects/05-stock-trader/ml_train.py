"""
StockBot ML 학습 스크립트 v3.7

yfinance 2년 데이터로 XGBoost 종목 선정 모델 학습.
Walk-forward validation (train 9개월, test 1개월 반복).

사용법:
    python ml_train.py

출력:
    trading-bot/models/stock_selector_xgb.pkl
"""
import os
import sys
import logging
import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

# 프로젝트 경로 설정
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "trading-bot"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "strategy"))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 학습 대상 종목 (15개)
TRAIN_SYMBOLS = [
    ("005930", "삼성전자"), ("000660", "SK하이닉스"), ("035420", "NAVER"),
    ("035720", "카카오"), ("051910", "LG화학"), ("006400", "삼성SDI"),
    ("003670", "포스코퓨처엠"), ("028260", "삼성물산"), ("105560", "KB금융"),
    ("055550", "신한지주"), ("005380", "현대자동차"), ("000270", "기아"),
    ("068270", "셀트리온"), ("034730", "SK"), ("017670", "SK텔레콤"),
]

MODEL_OUTPUT = os.path.join(PROJECT_ROOT, "trading-bot", "models", "stock_selector_xgb.pkl")

# ML 피처 이름 (ml_model.py의 FEATURE_NAMES와 동일)
FEATURE_NAMES = [
    "ret_5d", "ret_20d", "ret_60d",
    "vol_20d", "vol_60d",
    "rsi_14", "rsi_2",
    "macd_hist_norm",
    "bb_pband",
    "ma5_above_ma20", "ma20_above_ma60", "ma60_above_ma120",
    "obv_ratio", "vol_ratio_5_20",
    "regime_bull", "regime_bear", "regime_sideways",
    "sub_mean_rev", "sub_trend", "sub_korea_mom", "sub_volume", "sub_volatility",
]


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI 계산"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return (100 - (100 / (1 + rs))).fillna(50)


def detect_regime(close: pd.Series, idx: int) -> str:
    """간이 국면 감지"""
    if idx < 60:
        return "SIDEWAYS"
    ma20 = close.iloc[max(0, idx - 20):idx + 1].mean()
    ma60 = close.iloc[max(0, idx - 60):idx + 1].mean()
    ret20 = (close.iloc[idx] / close.iloc[max(0, idx - 20)] - 1) * 100

    if ma20 > ma60 and ret20 > 3:
        return "BULL"
    elif ma20 < ma60 and ret20 < -3:
        return "BEAR"
    return "SIDEWAYS"


def extract_features_at(df: pd.DataFrame, idx: int) -> np.ndarray:
    """특정 시점에서 22개 피처 추출"""
    if idx < 130:
        return None

    sub = df.iloc[:idx + 1]
    close = sub["close"].astype(float)
    volume = sub["volume"].astype(float)
    current = float(close.iloc[-1])

    # returns
    ret_5d = float(close.iloc[-1] / close.iloc[-6] - 1) if len(close) > 6 else 0
    ret_20d = float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) > 21 else 0
    ret_60d = float(close.iloc[-1] / close.iloc[-61] - 1) if len(close) > 61 else 0

    # volatility
    returns = close.pct_change().dropna()
    vol_20d = float(returns.tail(20).std() * np.sqrt(252)) if len(returns) >= 20 else 0
    vol_60d = float(returns.tail(60).std() * np.sqrt(252)) if len(returns) >= 60 else vol_20d

    # RSI
    rsi_14 = float(compute_rsi(close, 14).iloc[-1])
    rsi_2 = float(compute_rsi(close, 2).iloc[-1])

    # MACD
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9).mean()
    hist = float((macd_line - signal_line).iloc[-1])
    macd_hist_norm = hist / (current * 0.01) if current > 0 else 0

    # Bollinger %B
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = ma20 + 2 * std20
    lower = ma20 - 2 * std20
    band = float(upper.iloc[-1]) - float(lower.iloc[-1])
    bb_pband = (current - float(lower.iloc[-1])) / band if band > current * 0.001 else 0.5

    # MA alignment
    ma5 = float(close.rolling(5).mean().iloc[-1])
    ma20_val = float(ma20.iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1])
    ma120 = float(close.rolling(120).mean().iloc[-1])

    # OBV
    obv = (volume * np.sign(close.diff().fillna(0))).cumsum()
    obv_ma5 = float(obv.rolling(5).mean().iloc[-1])
    obv_current = float(obv.iloc[-1])
    obv_ratio = obv_current / obv_ma5 if obv_ma5 != 0 else 1.0

    vol_ma5 = float(volume.rolling(5).mean().iloc[-1])
    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    vol_ratio = vol_ma5 / vol_ma20 if vol_ma20 > 0 else 1.0

    # regime
    regime = detect_regime(close, len(close) - 1)

    # 간이 서브스코어 (정규화 0~1)
    sub_mean_rev = max(0, min(1, (100 - rsi_14) / 100))
    sub_trend = max(0, min(1, 0.5 + float(np.tanh(macd_hist_norm)) * 0.3))
    sub_korea_mom = max(0, min(1, 0.5 - ret_20d * 0.8 / 100))
    sub_volume = max(0, min(1, 0.3 + vol_ratio * 0.2))
    sub_volatility = max(0, min(1, 0.7 - vol_20d)) if vol_60d > 0 else 0.5

    return np.array([
        ret_5d, ret_20d, ret_60d,
        vol_20d, vol_60d,
        rsi_14, rsi_2,
        macd_hist_norm,
        bb_pband,
        1.0 if ma5 > ma20_val else 0.0,
        1.0 if ma20_val > ma60 else 0.0,
        1.0 if ma60 > ma120 else 0.0,
        obv_ratio, vol_ratio,
        1.0 if regime == "BULL" else 0.0,
        1.0 if regime == "BEAR" else 0.0,
        1.0 if regime == "SIDEWAYS" else 0.0,
        sub_mean_rev, sub_trend, sub_korea_mom, sub_volume, sub_volatility,
    ])


def download_data(symbol: str, days: int = 500) -> pd.DataFrame:
    """yfinance로 데이터 다운로드"""
    import yfinance as yf

    ticker = f"{symbol}.KS"
    end = datetime.now()
    start = end - timedelta(days=int(days * 1.6))

    df = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                     end=end.strftime("%Y-%m-%d"),
                     progress=False, auto_adjust=True)
    if df is None or len(df) == 0:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })
    df = df[["open", "high", "low", "close", "volume"]].dropna().reset_index(drop=True)
    return df


def create_labels(close: pd.Series, idx: int, horizon: int = 5,
                  up_th: float = 0.02, down_th: float = -0.02) -> int:
    """
    라벨 생성: 5일 후 수익률 기반
    >2% → 1 (BUY), <-2% → -1 (SELL), else → 0 (HOLD)
    """
    if idx + horizon >= len(close):
        return None
    future_ret = close.iloc[idx + horizon] / close.iloc[idx] - 1
    if future_ret > up_th:
        return 1
    elif future_ret < down_th:
        return -1
    return 0


def build_dataset():
    """전체 학습 데이터셋 구축"""
    all_X = []
    all_y = []
    all_dates = []  # walk-forward용 날짜 인덱스

    for symbol, name in TRAIN_SYMBOLS:
        logger.info(f"데이터 다운로드: {name} ({symbol})")
        df = download_data(symbol, days=500)
        if len(df) < 200:
            logger.warning(f"  데이터 부족: {len(df)}일 → 건너뜀")
            continue

        close = df["close"].astype(float)
        count = 0
        for i in range(130, len(df) - 5):
            features = extract_features_at(df, i)
            if features is None:
                continue
            label = create_labels(close, i)
            if label is None:
                continue

            # NaN/Inf 가드
            if np.any(np.isnan(features)) or np.any(np.isinf(features)):
                features = np.nan_to_num(features, nan=0.0, posinf=1.0, neginf=-1.0)

            all_X.append(features)
            all_y.append(label)
            all_dates.append(i)
            count += 1

        logger.info(f"  {name}: {count}개 샘플 생성")

    X = np.array(all_X)
    y = np.array(all_y)
    logger.info(f"전체 데이터셋: {len(X)}개 샘플, "
                f"BUY={sum(y == 1)}, HOLD={sum(y == 0)}, SELL={sum(y == -1)}")
    return X, y


def walk_forward_train(X: np.ndarray, y: np.ndarray):
    """
    Walk-forward validation.

    Train 9개월(~190일 * 15종목), test 1개월(~22일 * 15종목) 반복.
    """
    from xgboost import XGBClassifier
    from sklearn.metrics import accuracy_score, classification_report

    # 데이터를 시간순으로 나누기 (종목 수로 나눠서 월별)
    n_stocks = len(TRAIN_SYMBOLS)
    samples_per_stock = len(X) // n_stocks if n_stocks > 0 else len(X)
    train_months = 9
    test_months = 1
    train_days = train_months * 22 * n_stocks
    test_days = test_months * 22 * n_stocks

    all_preds = []
    all_true = []

    fold = 0
    start = 0
    while start + train_days + test_days <= len(X):
        train_end = start + train_days
        test_end = train_end + test_days

        X_train = X[start:train_end]
        y_train = y[start:train_end]
        X_test = X[train_end:test_end]
        y_test = y[train_end:test_end]

        if len(X_train) < 100 or len(X_test) < 10:
            start += test_days
            continue

        model = XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric="mlogloss",
            verbosity=0,
        )

        # 라벨 재매핑: -1 → 0, 0 → 1, 1 → 2
        y_train_mapped = y_train + 1
        y_test_mapped = y_test + 1

        model.fit(X_train, y_train_mapped)
        preds = model.predict(X_test)
        acc = accuracy_score(y_test_mapped, preds)

        all_preds.extend(preds)
        all_true.extend(y_test_mapped)

        fold += 1
        logger.info(f"  Fold {fold}: train={len(X_train)}, test={len(X_test)}, acc={acc:.3f}")

        start += test_days

    if all_preds:
        overall_acc = accuracy_score(all_true, all_preds)
        logger.info(f"\nWalk-forward 전체 정확도: {overall_acc:.3f}")
        logger.info(f"Classification Report:\n{classification_report(all_true, all_preds, target_names=['SELL', 'HOLD', 'BUY'])}")

    return model


def train_final_model(X: np.ndarray, y: np.ndarray):
    """전체 데이터로 최종 모델 학습"""
    from xgboost import XGBClassifier
    import joblib

    logger.info("\n=== 최종 모델 학습 (전체 데이터) ===")

    model = XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="mlogloss",
        verbosity=0,
    )

    # 라벨 재매핑
    y_mapped = y + 1
    model.fit(X, y_mapped)

    # 피처 중요도
    importances = model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    logger.info("\n피처 중요도 (상위 10):")
    for i in sorted_idx[:10]:
        logger.info(f"  {FEATURE_NAMES[i]}: {importances[i]:.4f}")

    # 모델 저장
    os.makedirs(os.path.dirname(MODEL_OUTPUT), exist_ok=True)
    joblib.dump(model, MODEL_OUTPUT)
    logger.info(f"\n모델 저장 완료: {MODEL_OUTPUT}")

    return model


def main():
    print("=" * 60)
    print("  StockBot ML 학습 스크립트 v3.7")
    print("  XGBoost 종목 선정 모델")
    print("=" * 60)

    # 1. 데이터셋 구축
    logger.info("\n=== 1단계: 데이터셋 구축 ===")
    X, y = build_dataset()

    if len(X) < 100:
        logger.error("학습 데이터 부족. 최소 100개 샘플 필요.")
        return

    # 2. Walk-forward validation
    logger.info("\n=== 2단계: Walk-forward Validation ===")
    walk_forward_train(X, y)

    # 3. 최종 모델 학습 + 저장
    model = train_final_model(X, y)

    print(f"\n학습 완료! 모델: {MODEL_OUTPUT}")
    print("사용법: /api/scan 호출 시 ML예측 서브스코어가 자동 표시됩니다.")


if __name__ == "__main__":
    main()
