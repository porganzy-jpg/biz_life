"""
VoiceMemory 녹음 세션 관리

가이드 대화 주제를 제공하고, 녹음 세션을 관리합니다.
50가지 대화 주제로 자연스러운 음성 데이터를 수집합니다.
"""
import os
import uuid
import wave
import logging
from datetime import datetime
from sqlalchemy.orm import Session as DBSession
from models import RecordingSession, Person

logger = logging.getLogger(__name__)

# Recordings base directory (project_root/recordings/)
RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "..", "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)


# 50가지 가이드 대화 주제
GUIDED_TOPICS = [
    # 어린 시절
    {"topic": "어린 시절 추억", "questions": [
        "어린 시절 가장 좋아했던 놀이는 무엇이었나요?",
        "학교 다닐 때 가장 기억에 남는 선생님은 누구였나요?",
        "어릴 때 살던 동네는 어떤 곳이었나요?",
    ]},
    {"topic": "가족 이야기", "questions": [
        "부모님은 어떤 분이셨나요?",
        "형제자매와의 특별한 추억이 있다면?",
        "가족끼리 자주 갔던 곳이 있었나요?",
    ]},
    {"topic": "학창 시절", "questions": [
        "가장 좋아했던 과목은 무엇이었나요?",
        "학교 친구들과의 재미있는 에피소드를 들려주세요.",
        "졸업식 날 기억이 나시나요?",
    ]},
    # 인생의 전환점
    {"topic": "첫 직장", "questions": [
        "첫 직장은 어디였나요?",
        "직장 생활에서 가장 보람 있었던 순간은?",
        "직업을 선택하게 된 계기는?",
    ]},
    {"topic": "결혼과 사랑", "questions": [
        "배우자를 처음 만났을 때 이야기를 들려주세요.",
        "결혼식은 어땠나요?",
        "신혼 시절의 추억이 있다면?",
    ]},
    {"topic": "자녀 이야기", "questions": [
        "아이가 처음 태어났을 때 기분은 어떠셨나요?",
        "자녀를 키우면서 가장 힘들었던 순간은?",
        "자녀에게 해주고 싶은 말이 있다면?",
    ]},
    # 일상과 취미
    {"topic": "좋아하는 음식", "questions": [
        "가장 좋아하는 음식은 무엇인가요?",
        "어머니/아버지의 손맛이 그리운 음식이 있나요?",
        "특별한 요리 비법이 있다면?",
    ]},
    {"topic": "취미와 여가", "questions": [
        "평소 여가 시간에 무엇을 하시나요?",
        "여행 다녀온 곳 중 가장 좋았던 곳은?",
        "배워보고 싶은 것이 있다면?",
    ]},
    {"topic": "좋아하는 노래", "questions": [
        "가장 좋아하는 노래는 무엇인가요?",
        "그 노래가 특별한 이유가 있나요?",
        "노래방에서 자주 부르는 노래는?",
    ]},
    {"topic": "계절과 날씨", "questions": [
        "가장 좋아하는 계절은 언제인가요?",
        "비 오는 날이면 생각나는 추억이 있나요?",
        "눈 내리는 날 가장 기억에 남는 순간은?",
    ]},
    # 인생 철학
    {"topic": "인생 조언", "questions": [
        "살면서 가장 중요하다고 생각하는 가치는?",
        "젊은 사람들에게 해주고 싶은 조언이 있다면?",
        "후회하는 일이 있다면 무엇인가요?",
    ]},
    {"topic": "감사한 것들", "questions": [
        "인생에서 가장 감사한 사람은 누구인가요?",
        "가장 행복했던 순간을 떠올려 주세요.",
        "앞으로 이루고 싶은 소원이 있다면?",
    ]},
]


class RecordingService:
    """녹음 세션 관리"""

    @staticmethod
    def get_guided_topics() -> list:
        """가이드 대화 주제 목록"""
        return GUIDED_TOPICS

    @staticmethod
    def create_session(db: DBSession, person_id: int, topic_index: int = 0) -> RecordingSession:
        """녹음 세션 생성"""
        # 세션 번호 산정
        count = db.query(RecordingSession).filter(
            RecordingSession.person_id == person_id
        ).count()

        topic_data = GUIDED_TOPICS[topic_index % len(GUIDED_TOPICS)]

        session = RecordingSession(
            person_id=person_id,
            session_number=count + 1,
            topic=topic_data["topic"],
            guide_questions=topic_data["questions"],
            status="pending",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def get_sessions(db: DBSession, person_id: int) -> list:
        """특정 인물의 녹음 세션 목록"""
        return db.query(RecordingSession).filter(
            RecordingSession.person_id == person_id
        ).order_by(RecordingSession.session_number).all()

    @staticmethod
    def complete_session(db: DBSession, session_id: int, duration_seconds: int = 0,
                         audio_file_path: str = "", transcript: str = "",
                         status: str = "completed") -> RecordingSession | None:
        """녹음 세션 완료/업데이트"""
        session = db.query(RecordingSession).filter(
            RecordingSession.id == session_id
        ).first()
        if not session:
            return None

        if status:
            session.status = status
        if duration_seconds:
            session.duration_seconds = duration_seconds
        if audio_file_path:
            session.audio_file_path = audio_file_path
        if transcript:
            session.transcript = transcript
        if status == "completed":
            from datetime import datetime
            session.recorded_at = datetime.utcnow()

        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def delete_person_sessions(db: DBSession, person_id: int) -> int:
        """인물의 모든 녹음 세션 삭제 (동의 철회 시)"""
        count = db.query(RecordingSession).filter(
            RecordingSession.person_id == person_id
        ).delete()
        db.commit()
        return count

    @staticmethod
    def get_next_topic(db: DBSession, person_id: int) -> dict:
        """다음 추천 주제"""
        completed = db.query(RecordingSession).filter(
            RecordingSession.person_id == person_id,
            RecordingSession.status == "completed",
        ).count()

        next_idx = completed % len(GUIDED_TOPICS)
        return {
            "topic_index": next_idx,
            "topic": GUIDED_TOPICS[next_idx],
            "completed_sessions": completed,
            "total_topics": len(GUIDED_TOPICS),
        }

    @staticmethod
    def save_audio_file(session_id: int, person_id: int, file_bytes: bytes,
                        original_filename: str) -> dict:
        """
        Save uploaded audio file to disk.

        Returns dict with file_path, filename, size_bytes, format.
        """
        # Determine extension from original filename
        ext = os.path.splitext(original_filename)[1].lower() if original_filename else ".webm"
        if ext not in (".wav", ".webm", ".ogg", ".mp3", ".m4a"):
            ext = ".webm"

        # Create person subdirectory
        person_dir = os.path.join(RECORDINGS_DIR, f"person_{person_id}")
        os.makedirs(person_dir, exist_ok=True)

        # Generate unique filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"session_{session_id}_{timestamp}_{unique_id}{ext}"
        file_path = os.path.join(person_dir, filename)

        # Write file
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        size_bytes = len(file_bytes)
        logger.info(f"Saved audio: {file_path} ({size_bytes} bytes)")

        # Try to get duration for WAV files
        duration_seconds = 0
        if ext == ".wav":
            try:
                with wave.open(file_path, "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    if rate > 0:
                        duration_seconds = frames / rate
            except Exception:
                pass

        return {
            "file_path": file_path,
            "filename": filename,
            "size_bytes": size_bytes,
            "format": ext.lstrip("."),
            "duration_seconds": round(duration_seconds, 2),
        }

    @staticmethod
    def get_audio_file_path(db: DBSession, session_id: int) -> str | None:
        """Get the audio file path for a session, if it exists on disk."""
        session = db.query(RecordingSession).filter(
            RecordingSession.id == session_id
        ).first()
        if not session or not session.audio_file_path:
            return None
        if os.path.exists(session.audio_file_path):
            return session.audio_file_path
        return None

    @staticmethod
    def get_audio_content_type(file_path: str) -> str:
        """Return the MIME content type based on file extension."""
        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {
            ".wav": "audio/wav",
            ".webm": "audio/webm",
            ".ogg": "audio/ogg",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
        }
        return mime_map.get(ext, "application/octet-stream")
