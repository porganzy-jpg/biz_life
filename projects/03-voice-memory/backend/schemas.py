"""
VoiceMemory Pydantic 스키마
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PersonCreate(BaseModel):
    name: str
    relationship_type: str = "family"
    birth_year: Optional[int] = None
    personality_traits: List[str] = []
    speaking_style: str = ""


class PersonResponse(BaseModel):
    id: int
    name: str
    relationship_type: str
    personality_traits: list
    speaking_style: str
    voice_id: str
    session_count: int = 0
    conversation_count: int = 0

    class Config:
        from_attributes = True


class ConsentCreate(BaseModel):
    person_id: int
    consent_type: str
    is_granted: bool
    notes: str = ""


class ChatRequest(BaseModel):
    person_id: int
    message: str
    user_id: int = 1


class ChatResponse(BaseModel):
    person_name: str
    user_message: str
    ai_response: str
    audio_url: str = ""
    emotion: str = "neutral"


class RecordingSessionCreate(BaseModel):
    person_id: int
    topic: str = ""


class RecordingSessionUpdate(BaseModel):
    status: Optional[str] = None  # "recording", "completed"
    duration_seconds: Optional[int] = None
    audio_file_path: Optional[str] = None
    transcript: Optional[str] = None
