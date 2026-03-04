"""
StockBot 데이터베이스 - SQLite 기반 영속성
거래이력, 포지션, 일일 성과, 뉴스 감성 기록
"""
import sqlite3
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "stockbot.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """데이터베이스 초기화"""
    conn = get_connection()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        action TEXT NOT NULL,
        symbol TEXT NOT NULL,
        name TEXT,
        qty INTEGER NOT NULL,
        price REAL NOT NULL,
        amount REAL NOT NULL,
        fee REAL DEFAULT 0,
        tax REAL DEFAULT 0,
        pnl REAL DEFAULT 0,
        pnl_pct REAL DEFAULT 0,
        score REAL DEFAULT 0,
        confidence REAL DEFAULT 0,
        reasons TEXT DEFAULT '[]',
        mode TEXT DEFAULT 'paper'
    );

    CREATE TABLE IF NOT EXISTS positions (
        symbol TEXT PRIMARY KEY,
        name TEXT,
        qty INTEGER NOT NULL,
        avg_price REAL NOT NULL,
        sector TEXT,
        bought_at TEXT,
        highest_price REAL DEFAULT 0,
        score_at_buy REAL DEFAULT 0,
        entry_source TEXT DEFAULT 'ens'
    );

    CREATE TABLE IF NOT EXISTS daily_performance (
        date TEXT PRIMARY KEY,
        total_assets REAL,
        cash REAL,
        invested REAL,
        pnl_day REAL DEFAULT 0,
        pnl_day_pct REAL DEFAULT 0,
        total_pnl REAL DEFAULT 0,
        total_pnl_pct REAL DEFAULT 0,
        trades_count INTEGER DEFAULT 0,
        win_count INTEGER DEFAULT 0,
        positions_count INTEGER DEFAULT 0,
        kospi REAL DEFAULT 0,
        notes TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS news_sentiment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        symbol TEXT NOT NULL,
        name TEXT,
        overall_score REAL,
        positive_count INTEGER DEFAULT 0,
        negative_count INTEGER DEFAULT 0,
        neutral_count INTEGER DEFAULT 0,
        news_count INTEGER DEFAULT 0,
        top_headlines TEXT DEFAULT '[]'
    );

    CREATE TABLE IF NOT EXISTS bot_state (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
    CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
    CREATE INDEX IF NOT EXISTS idx_news_symbol ON news_sentiment(symbol);
    """)

    # 기존 DB 마이그레이션: entry_source 컬럼 추가
    try:
        c.execute("ALTER TABLE positions ADD COLUMN entry_source TEXT DEFAULT 'ens'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # 이미 존재

    conn.commit()
    conn.close()
    logger.info(f"DB 초기화 완료: {DB_PATH}")


class TradeDB:
    """거래 데이터베이스 래퍼"""

    def __init__(self):
        init_db()

    def record_trade(self, action: str, symbol: str, name: str, qty: int,
                     price: float, pnl: float = 0, pnl_pct: float = 0,
                     score: float = 0, confidence: float = 0,
                     reasons: list = None, mode: str = "paper"):
        conn = get_connection()
        conn.execute(
            """INSERT INTO trades (timestamp, action, symbol, name, qty, price,
               amount, fee, tax, pnl, pnl_pct, score, confidence, reasons, mode)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().isoformat(),
                action, symbol, name, qty, price,
                qty * price,
                qty * price * 0.00015,  # 수수료
                qty * price * 0.0018 if action != "BUY" else 0,  # 거래세
                pnl, round(pnl_pct, 2),
                round(score, 1), round(confidence, 2),
                json.dumps(reasons or [], ensure_ascii=False),
                mode,
            )
        )
        conn.commit()
        conn.close()

    def get_trades(self, limit: int = 50, symbol: str = None) -> list:
        conn = get_connection()
        if symbol:
            rows = conn.execute(
                "SELECT * FROM trades WHERE symbol=? ORDER BY timestamp DESC LIMIT ?",
                (symbol, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_trade_stats(self, days: int = 30) -> dict:
        conn = get_connection()
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            "SELECT * FROM trades WHERE timestamp >= ? AND action != 'BUY'",
            (since,)
        ).fetchall()
        conn.close()

        if not rows:
            return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0,
                    "total_pnl": 0, "avg_pnl_pct": 0}

        total = len(rows)
        wins = sum(1 for r in rows if r["pnl"] > 0)
        losses = sum(1 for r in rows if r["pnl"] < 0)
        total_pnl = sum(r["pnl"] for r in rows)
        avg_pnl_pct = sum(r["pnl_pct"] for r in rows) / total if total else 0

        return {
            "total": total, "wins": wins, "losses": losses,
            "win_rate": round(wins / total * 100, 1) if total else 0,
            "total_pnl": round(total_pnl),
            "avg_pnl_pct": round(avg_pnl_pct, 2),
        }

    def save_position(self, symbol: str, name: str, qty: int, avg_price: float,
                      sector: str = "", score: float = 0, entry_source: str = "ens"):
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO positions
               (symbol, name, qty, avg_price, sector, bought_at, highest_price, score_at_buy, entry_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol, name, qty, avg_price, sector,
             datetime.now().isoformat(), avg_price, score, entry_source)
        )
        conn.commit()
        conn.close()

    def remove_position(self, symbol: str):
        conn = get_connection()
        conn.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
        conn.commit()
        conn.close()

    def get_positions(self) -> list:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM positions").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_highest_price(self, symbol: str, price: float):
        conn = get_connection()
        conn.execute(
            "UPDATE positions SET highest_price=MAX(highest_price, ?) WHERE symbol=?",
            (price, symbol)
        )
        conn.commit()
        conn.close()

    def record_daily(self, total_assets: float, cash: float, invested: float,
                     pnl_day: float, pnl_day_pct: float, total_pnl: float,
                     total_pnl_pct: float, trades_count: int, win_count: int,
                     positions_count: int, kospi: float = 0):
        conn = get_connection()
        today = datetime.now().strftime("%Y-%m-%d")
        conn.execute(
            """INSERT OR REPLACE INTO daily_performance
               (date, total_assets, cash, invested, pnl_day, pnl_day_pct,
                total_pnl, total_pnl_pct, trades_count, win_count,
                positions_count, kospi)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (today, total_assets, cash, invested, pnl_day, pnl_day_pct,
             total_pnl, total_pnl_pct, trades_count, win_count,
             positions_count, kospi)
        )
        conn.commit()
        conn.close()

    def get_daily_performance(self, days: int = 30) -> list:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM daily_performance ORDER BY date DESC LIMIT ?",
            (days,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def save_state(self, key: str, value: str):
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO bot_state (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def get_state(self, key: str) -> Optional[str]:
        conn = get_connection()
        row = conn.execute("SELECT value FROM bot_state WHERE key=?", (key,)).fetchone()
        conn.close()
        return row["value"] if row else None

    def record_sentiment(self, symbol: str, name: str, overall: float,
                         pos: int, neg: int, neu: int, count: int,
                         headlines: list = None):
        conn = get_connection()
        conn.execute(
            """INSERT INTO news_sentiment
               (timestamp, symbol, name, overall_score, positive_count,
                negative_count, neutral_count, news_count, top_headlines)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now().isoformat(), symbol, name, overall,
             pos, neg, neu, count,
             json.dumps(headlines or [], ensure_ascii=False))
        )
        conn.commit()
        conn.close()
