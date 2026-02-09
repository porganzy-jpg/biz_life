"""
VoiceMemory DB 모델
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database import Base


class Person(Base):
    """보존 대상 인물"""
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    relationship_type = Column(String(50), default="family")  # family, friend, mentor
    birth_year = Column(Integer, nullable=True)
    personality_traits = Column(JSON, default=list)  # ["따뜻한", "유머러스"]
    speaking_style = Column(Text, default="")  # 말투 특징
    voice_id = Column(String(100), default="")  # 음성 클론 ID (ElevenLabs)
    profile_image_url = Column(String(500), default="")
    created_by_user_id = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("RecordingSession", back_populates="person")
    conversations = relationship("Conversation", back_populates="person")
    consents = relationship("Consent", back_populates="person")


class RecordingSession(Base):
    """녹음 세션"""
    __tablename__ = "recording_sessions"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    session_number = Column(Integer, default=1)
    topic = Column(String(200), default="")
    guide_questions = Column(JSON, default=list)
    duration_seconds = Column(Integer, default=0)
    audio_file_path = Column(String(500), default="")
    transcript = Column(Text, default="")
    status = Column(String(20), default="pending")  # pending, recording, completed
    recorded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person", back_populates="sessions")


class Conversation(Base):
    """AI 대화 기록"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    user_id = Column(Integer, nullable=False)
    user_message = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    audio_url = Column(String(500), default="")
    emotion = Column(String(20), default="neutral")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person", back_populates="conversations")


class Consent(Base):
    """동의 기록"""
    __tablename__ = "consents"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    consent_type = Column(String(50), nullable=False)  # voice_recording, ai_clone, data_storage
    is_granted = Column(Boolean, default=False)
    granted_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    ip_address = Column(String(50), default="")
    notes = Column(Text, default="")

    person = relationship("Person", back_populates="consents")
