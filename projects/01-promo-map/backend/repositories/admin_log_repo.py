"""AdminLog 리포지토리"""
from sqlalchemy.orm import Session
from models import AdminLog
from repositories.base import BaseRepository


class AdminLogRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(AdminLog, db)

    def log_action(self, admin_id: int, action: str, target_type: str,
                   target_id: int = None, detail: str = ""):
        return self.create(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )

    def get_recent(self, limit: int = 50):
        return (
            self.db.query(AdminLog)
            .order_by(AdminLog.created_at.desc())
            .limit(limit).all()
        )
