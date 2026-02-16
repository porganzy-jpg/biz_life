"""
HomeFinder DB 설정 (SQLite)
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    DB_DIR = os.path.dirname(__file__)
    DATABASE_URL = f"sqlite:///{os.path.join(DB_DIR, 'homefinder.db')}"

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


def init_db():
    from models import (  # noqa
        property, complex, area, transaction, auction,
        subscription, candidate, subway_station, park,
        price_index, data_collection_log, saved_search, note
    )
    Base.metadata.create_all(bind=engine)
