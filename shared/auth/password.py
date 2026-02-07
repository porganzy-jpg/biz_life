"""
BIZ LIFE - 비밀번호 해싱 유틸리티
bcrypt 기반 안전한 비밀번호 관리
"""
import bcrypt


def hash_password(password: str) -> str:
    """비밀번호를 bcrypt 해시로 변환"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
