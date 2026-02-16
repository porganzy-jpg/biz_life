"""
데이터 수집기 기반 클래스
레이트리밋, 재시도, 로깅 포함
"""
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import sys
import os

# Add backend to path for model imports
_backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend")
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

from database import SessionLocal
from models.data_collection_log import DataCollectionLog

logger = logging.getLogger("homefinder.collector")


class BaseCollector(ABC):
    """데이터 수집기 추상 기반 클래스"""

    name: str = "base"
    rate_limit_seconds: float = 1.0
    max_retries: int = 3

    def __init__(self):
        self._last_request_time = 0.0

    @abstractmethod
    def collect(self, **kwargs) -> dict:
        """
        데이터 수집 실행

        Returns:
            {"fetched": int, "new": int, "updated": int}
        """
        pass

    def run(self, **kwargs) -> dict:
        """수집 실행 + 로깅"""
        db = SessionLocal()
        log = DataCollectionLog(
            collector_name=self.name,
            started_at=datetime.utcnow(),
            status="running",
        )
        db.add(log)
        db.commit()

        try:
            result = self.collect(**kwargs)
            log.status = "success"
            log.records_fetched = result.get("fetched", 0)
            log.records_new = result.get("new", 0)
            log.records_updated = result.get("updated", 0)
            log.finished_at = datetime.utcnow()
            db.commit()
            logger.info(
                f"[{self.name}] Success: fetched={result.get('fetched', 0)}, "
                f"new={result.get('new', 0)}, updated={result.get('updated', 0)}"
            )
            return result
        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)[:500]
            log.finished_at = datetime.utcnow()
            db.commit()
            logger.error(f"[{self.name}] Failed: {e}")
            raise
        finally:
            db.close()

    def _rate_limit(self):
        """레이트리밋 적용"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_time = time.time()

    def _retry(self, func, *args, **kwargs):
        """재시도 래퍼"""
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self._rate_limit()
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                wait = attempt * 2
                logger.warning(f"[{self.name}] Retry {attempt}/{self.max_retries} in {wait}s: {e}")
                time.sleep(wait)
        raise last_error
