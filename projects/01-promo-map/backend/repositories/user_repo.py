"""User 리포지토리"""
from sqlalchemy.orm import Session
from models import User
from repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_active_users(self, offset: int = 0, limit: int = 20):
        return self.db.query(User).filter(User.is_active == True).offset(offset).limit(limit).all()

    def count_active(self) -> int:
        return self.db.query(User).filter(User.is_active == True).count()

    def update_refresh_token(self, user: User, token: str | None):
        user.refresh_token = token
        self.db.commit()

    def update_last_login(self, user: User):
        from datetime import datetime
        user.last_login_at = datetime.utcnow()
        self.db.commit()
