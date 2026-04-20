"""
HomeFinder DB 설정 (SQLite)
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    _db_path = Path(__file__).resolve().parent / "homefinder.db"
    DATABASE_URL = f"sqlite:///{_db_path}"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_add_columns(engine_):
    """Add columns that were added after initial schema creation.
    SQLite CREATE_ALL won't add columns to existing tables, so we do it here."""
    import logging
    logger = logging.getLogger("homefinder.migrate")

    migrations = [
        ("properties", "transaction_type", "VARCHAR(20) DEFAULT '매매'"),
        ("properties", "deposit_krw", "INTEGER"),
        ("properties", "monthly_rent_krw", "INTEGER"),
        ("transaction_history", "trade_type", "VARCHAR(20) DEFAULT '매매'"),
        ("transaction_history", "deposit_krw", "INTEGER"),
        ("transaction_history", "monthly_rent_krw", "INTEGER"),
    ]

    with engine_.connect() as conn:
        for table, col, col_type in migrations:
            # Check if table exists
            result = conn.execute(
                __import__("sqlalchemy").text(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
                )
            )
            if not result.fetchone():
                continue
            # Check if column exists
            result = conn.execute(__import__("sqlalchemy").text(f"PRAGMA table_info({table})"))
            existing_cols = {row[1] for row in result.fetchall()}
            if col not in existing_cols:
                conn.execute(
                    __import__("sqlalchemy").text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                )
                conn.commit()
                logger.info(f"Migration: added {table}.{col}")


def init_db():
    from models import (  # noqa
        property, complex, area, transaction, auction,
        subscription, candidate, subway_station, park,
        price_index, data_collection_log, saved_search, note,
        matching
    )
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns(engine)
