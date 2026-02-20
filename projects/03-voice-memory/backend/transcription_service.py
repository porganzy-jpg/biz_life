"""
VoiceMemory AI 음성 전사 파이프라인

OpenAI Whisper API (primary) -> local whisper model (fallback) -> None
음성 파일을 텍스트로 변환하고, 요약 및 키워드를 추출합니다.
"""
import os
import re
import json
import logging
import threading
import queue
from datetime import datetime
from collections import Counter
from typing import Optional, List

from sqlalchemy.orm import Session as DBSession
from database import SessionLocal
from models import RecordingSession, Person

logger = logging.getLogger(__name__)

# === Configuration ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
AUTO_TRANSCRIBE = os.getenv("AUTO_TRANSCRIBE", "false").lower() in ("true", "1", "yes")

# Background processing queue
_transcription_queue = queue.Queue()
_worker_thread: Optional[threading.Thread] = None
_worker_running = False


class TranscriptionService:
    """AI 음성 전사 서비스"""

    # ========================================
    # Transcription
    # ========================================

    @staticmethod
    def transcribe_audio(audio_path: str, language: str = "ko") -> Optional[str]:
        """
        오디오 파일을 텍스트로 전사

        Primary: OpenAI Whisper API (OPENAI_API_KEY 설정 시)
        Fallback: Local whisper model (openai-whisper 패키지)
        Last fallback: None 반환
        """
        if not audio_path or not os.path.exists(audio_path):
            logger.warning(f"Audio file not found: {audio_path}")
            return None

        # Primary: OpenAI Whisper API
        if OPENAI_API_KEY:
            result = TranscriptionService._transcribe_openai_api(audio_path, language)
            if result is not None:
                return result
            logger.warning("OpenAI Whisper API failed, trying local model...")

        # Fallback: Local whisper model
        result = TranscriptionService._transcribe_local_whisper(audio_path, language)
        if result is not None:
            return result

        # Last fallback
        logger.info(
            "Transcription unavailable: no OpenAI API key and local whisper not installed. "
            "Install openai-whisper or set OPENAI_API_KEY to enable transcription."
        )
        return None

    @staticmethod
    def _transcribe_openai_api(audio_path: str, language: str = "ko") -> Optional[str]:
        """OpenAI Whisper API를 사용한 전사"""
        try:
            import requests

            with open(audio_path, "rb") as audio_file:
                response = requests.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    files={"file": (os.path.basename(audio_path), audio_file)},
                    data={"model": "whisper-1", "language": language},
                    timeout=120,
                )

            if response.status_code == 200:
                result = response.json()
                transcript = result.get("text", "").strip()
                if transcript:
                    logger.info(f"OpenAI Whisper transcription complete: {len(transcript)} chars")
                    return transcript
                logger.warning("OpenAI Whisper returned empty transcript")
                return None
            else:
                logger.error(f"OpenAI Whisper API error {response.status_code}: {response.text}")
                return None

        except Exception as e:
            logger.error(f"OpenAI Whisper API exception: {e}")
            return None

    @staticmethod
    def _transcribe_local_whisper(audio_path: str, language: str = "ko") -> Optional[str]:
        """로컬 whisper 모델을 사용한 전사"""
        try:
            import whisper

            logger.info(f"Loading local whisper model: {WHISPER_MODEL}")
            model = whisper.load_model(WHISPER_MODEL)
            result = model.transcribe(audio_path, language=language)
            transcript = result.get("text", "").strip()
            if transcript:
                logger.info(f"Local whisper transcription complete: {len(transcript)} chars")
                return transcript
            logger.warning("Local whisper returned empty transcript")
            return None

        except ImportError:
            logger.info("Local whisper not installed (pip install openai-whisper)")
            return None
        except Exception as e:
            logger.error(f"Local whisper exception: {e}")
            return None

    # ========================================
    # Summarization
    # ========================================

    @staticmethod
    def summarize_transcript(transcript_text: str, person_name: str = "") -> str:
        """
        전사 텍스트 요약 생성

        Primary: OpenAI ChatCompletion API
        Fallback: 첫/마지막 문장 추출
        """
        if not transcript_text or not transcript_text.strip():
            return ""

        # Primary: OpenAI API
        if OPENAI_API_KEY:
            result = TranscriptionService._summarize_openai(transcript_text, person_name)
            if result:
                return result

        # Fallback: simple extraction
        return TranscriptionService._summarize_fallback(transcript_text, person_name)

    @staticmethod
    def _summarize_openai(transcript_text: str, person_name: str = "") -> Optional[str]:
        """OpenAI ChatCompletion으로 요약"""
        try:
            import requests

            person_context = f"화자는 '{person_name}'입니다. " if person_name else ""
            prompt = (
                f"{person_context}다음 녹음 전사 텍스트를 2~3문장으로 요약해주세요. "
                f"주요 주제, 감정적 톤을 포함해주세요.\n\n"
                f"전사 텍스트:\n{transcript_text[:3000]}"
            )

            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "당신은 음성 녹음 전사를 요약하는 도우미입니다. 간결하고 정확하게 요약해주세요."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 300,
                    "temperature": 0.5,
                },
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                summary = result["choices"][0]["message"]["content"].strip()
                logger.info(f"OpenAI summary generated: {len(summary)} chars")
                return summary
            else:
                logger.error(f"OpenAI summary API error {response.status_code}: {response.text}")
                return None

        except Exception as e:
            logger.error(f"OpenAI summary exception: {e}")
            return None

    @staticmethod
    def _summarize_fallback(transcript_text: str, person_name: str = "") -> str:
        """규칙 기반 요약 폴백 (첫/마지막 문장 추출)"""
        text = transcript_text.strip()
        if not text:
            return ""

        # Split into sentences (Korean / general punctuation)
        sentences = re.split(r'[.!?。]\s*', text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]

        if not sentences:
            # Just return first 200 chars
            return text[:200] + ("..." if len(text) > 200 else "")

        parts = []
        if person_name:
            parts.append(f"{person_name}님의 녹음 내용입니다.")

        # First sentence
        parts.append(sentences[0] + ".")

        # Last sentence (if different from first)
        if len(sentences) > 1:
            parts.append(sentences[-1] + ".")

        return " ".join(parts)

    # ========================================
    # Keyword Extraction
    # ========================================

    @staticmethod
    def extract_keywords(transcript_text: str) -> List[str]:
        """
        전사 텍스트에서 키워드 추출

        한국어 NLP: 조사 분리 후 명사 빈도 분석
        상위 10개 키워드 반환
        """
        if not transcript_text or not transcript_text.strip():
            return []

        text = transcript_text.strip()

        # Korean particles / suffixes to strip
        particles = [
            "은", "는", "이", "가", "을", "를", "에", "에서", "으로", "로",
            "와", "과", "의", "도", "만", "부터", "까지", "에게", "한테",
            "께서", "에서는", "으로는", "에게서", "하고", "이랑", "랑",
            "처럼", "같이", "보다", "마저", "조차", "밖에",
        ]

        # Common stop words (Korean)
        stop_words = {
            "그", "이", "저", "것", "거", "수", "등", "때", "중",
            "더", "안", "못", "잘", "좀", "다", "또", "다시",
            "그래서", "그런데", "그리고", "하지만", "그래도", "근데",
            "네", "예", "아", "어", "음", "응", "글쎄",
            "있다", "없다", "하다", "되다", "있는", "없는", "하는", "되는",
            "했다", "됐다", "있었", "없었", "했는데", "됐는데",
            "제가", "저는", "나는", "내가", "우리", "저희",
            "그거", "이거", "저거", "여기", "거기", "저기",
            "정말", "진짜", "매우", "아주", "너무", "많이",
        }

        # Tokenize: split on whitespace, punctuation
        tokens = re.findall(r'[가-힣]+', text)

        # Strip particles from end of tokens
        cleaned_tokens = []
        for token in tokens:
            if len(token) <= 1:
                continue
            # Try stripping particles from longest to shortest
            stripped = token
            for p in sorted(particles, key=len, reverse=True):
                if stripped.endswith(p) and len(stripped) > len(p) + 1:
                    stripped = stripped[:-len(p)]
                    break
            if len(stripped) > 1 and stripped not in stop_words:
                cleaned_tokens.append(stripped)

        # Count frequencies
        counter = Counter(cleaned_tokens)

        # Filter: at least 2 chars, appeared at least once
        keywords = [
            word for word, count in counter.most_common(30)
            if len(word) >= 2 and count >= 1
        ]

        return keywords[:10]

    # ========================================
    # Status Check
    # ========================================

    @staticmethod
    def get_transcription_status(db: DBSession, session_id: int) -> dict:
        """세션의 전사 상태 확인"""
        session = db.query(RecordingSession).filter(
            RecordingSession.id == session_id
        ).first()

        if not session:
            return {"status": "not_found", "session_id": session_id}

        return {
            "session_id": session_id,
            "status": session.transcription_status or "none",
            "has_transcript": bool(session.transcript and session.transcript.strip()),
            "has_summary": bool(session.transcript_summary),
            "has_keywords": bool(session.keywords),
            "has_audio": bool(session.audio_file_path),
        }

    # ========================================
    # Full Pipeline (for a single session)
    # ========================================

    @staticmethod
    def process_session(session_id: int) -> dict:
        """
        전체 전사 파이프라인 실행 (단일 세션)

        1. 오디오 전사
        2. 요약 생성
        3. 키워드 추출
        4. DB 업데이트
        """
        db = SessionLocal()
        try:
            session = db.query(RecordingSession).filter(
                RecordingSession.id == session_id
            ).first()

            if not session:
                return {"error": "Session not found", "session_id": session_id}

            if not session.audio_file_path or not os.path.exists(session.audio_file_path):
                session.transcription_status = "failed"
                db.commit()
                return {"error": "No audio file", "session_id": session_id}

            # Mark as processing
            session.transcription_status = "processing"
            db.commit()

            # Get person name for context
            person = db.query(Person).filter(Person.id == session.person_id).first()
            person_name = person.name if person else ""

            # Step 1: Transcribe
            transcript = TranscriptionService.transcribe_audio(session.audio_file_path)

            if not transcript:
                session.transcription_status = "failed"
                db.commit()
                return {
                    "error": "Transcription failed (no API key or local model)",
                    "session_id": session_id,
                }

            session.transcript = transcript

            # Step 2: Summarize
            summary = TranscriptionService.summarize_transcript(transcript, person_name)
            session.transcript_summary = summary

            # Step 3: Keywords
            keywords = TranscriptionService.extract_keywords(transcript)
            session.keywords = json.dumps(keywords, ensure_ascii=False)

            # Step 4: Mark complete
            session.transcription_status = "completed"
            db.commit()

            logger.info(
                f"Transcription pipeline complete for session {session_id}: "
                f"{len(transcript)} chars, {len(keywords)} keywords"
            )

            return {
                "session_id": session_id,
                "status": "completed",
                "transcript_length": len(transcript),
                "summary_length": len(summary) if summary else 0,
                "keyword_count": len(keywords),
            }

        except Exception as e:
            logger.error(f"Transcription pipeline error for session {session_id}: {e}")
            try:
                session = db.query(RecordingSession).filter(
                    RecordingSession.id == session_id
                ).first()
                if session:
                    session.transcription_status = "failed"
                    db.commit()
            except Exception:
                pass
            return {"error": str(e), "session_id": session_id}
        finally:
            db.close()


# ========================================
# Background Transcription Worker
# ========================================

def queue_transcription(session_id: int, audio_path: str) -> dict:
    """전사 작업을 큐에 추가"""
    # Update status to pending in DB
    db = SessionLocal()
    try:
        session = db.query(RecordingSession).filter(
            RecordingSession.id == session_id
        ).first()
        if session:
            session.transcription_status = "pending"
            db.commit()
    finally:
        db.close()

    _transcription_queue.put({
        "session_id": session_id,
        "audio_path": audio_path,
        "queued_at": datetime.utcnow().isoformat(),
    })

    logger.info(f"Queued transcription for session {session_id}")
    return {"status": "queued", "session_id": session_id}


def _worker_loop():
    """백그라운드 전사 워커 루프"""
    global _worker_running
    logger.info("Transcription worker started")

    while _worker_running:
        try:
            # Wait for item with timeout (so we can check _worker_running)
            try:
                item = _transcription_queue.get(timeout=2.0)
            except queue.Empty:
                continue

            session_id = item["session_id"]
            logger.info(f"Processing transcription for session {session_id}")

            # Process one at a time
            result = TranscriptionService.process_session(session_id)

            if result.get("error"):
                logger.warning(f"Transcription failed for session {session_id}: {result['error']}")
            else:
                logger.info(f"Transcription completed for session {session_id}")

            _transcription_queue.task_done()

        except Exception as e:
            logger.error(f"Transcription worker error: {e}")
            # Don't crash - continue processing
            continue

    logger.info("Transcription worker stopped")


def start_transcription_worker():
    """백그라운드 전사 워커 시작"""
    global _worker_thread, _worker_running

    if _worker_thread and _worker_thread.is_alive():
        logger.info("Transcription worker already running")
        return

    _worker_running = True
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="transcription-worker")
    _worker_thread.start()
    logger.info("Transcription worker thread started")


def stop_transcription_worker():
    """백그라운드 전사 워커 중지"""
    global _worker_running
    _worker_running = False
    if _worker_thread:
        _worker_thread.join(timeout=5.0)
    logger.info("Transcription worker stopped")
