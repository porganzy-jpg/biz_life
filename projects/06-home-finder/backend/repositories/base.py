"""Base repository with common CRUD operations."""
from sqlalchemy.orm import Session


class BaseRepository:
    def __init__(self, model, db: Session):
        self.model = model
        self.db = db

    def get_by_id(self, id: int):
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, offset: int = 0, limit: int = 20):
        return self.db.query(self.model).offset(offset).limit(limit).all()

    def count(self):
        return self.db.query(self.model).count()

    def create(self, **kwargs):
        obj = self.model(**kwargs)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj, **kwargs):
        for key, value in kwargs.items():
            if value is not None:
                setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, obj):
        self.db.delete(obj)
        self.db.commit()
