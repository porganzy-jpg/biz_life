"""UsageLog 리포지토리"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import UsageLog
from repositories.base import BaseRepository


class UsageLogRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(UsageLog, db)

    def get_by_user(self, user_id: int, offset: int = 0, limit: int = 20):
        return (
            self.db.query(UsageLog)
            .filter(UsageLog.user_id == user_id)
            .order_by(UsageLog.used_at.desc())
            .offset(offset).limit(limit).all()
        )

    def count_by_user(self, user_id: int) -> int:
        return self.db.query(UsageLog).filter(UsageLog.user_id == user_id).count()

    def get_daily_counts(self, days: int = 30):
        """최근 N일간 일별 사용 건수"""
        from datetime import datetime, timedelta
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(
                func.date(UsageLog.used_at).label("date"),
                func.count().label("count"),
            )
            .filter(UsageLog.used_at >= since)
            .group_by(func.date(UsageLog.used_at))
            .order_by(func.date(UsageLog.used_at))
            .all()
        )

    def get_popular_stores(self, limit: int = 10):
        """인기 매장 (사용 횟수 기준)"""
        return (
            self.db.query(
                UsageLog.store_id,
                func.count().label("usage_count"),
            )
            .group_by(UsageLog.store_id)
            .order_by(func.count().desc())
            .limit(limit)
            .all()
        )
