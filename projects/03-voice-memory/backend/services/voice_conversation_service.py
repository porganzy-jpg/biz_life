"""
VoiceMemory - 실시간 음성 대화 파이프라인 서비스

Pipeline: Voice Input -> Transcription -> AI Response -> Voice Synthesis -> Audio Output

음성 입력을 받아 전사하고, AI 페르소나 응답을 생성한 후,
응답을 음성으로 합성하여 반환하는 전체 파이프라인을 담당합니다.
"""
import os
import logging
import time
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session as DBSession

from models import Person, Conversation
from memory_engine import MemoryEngine
from persona_chat import PersonaChat
from voice_clone_service import VoiceCloneService
from transcription_service import TranscriptionService

logger = logging.getLogger(__name__)

# Temp directory for incoming voice chat audio
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_CHAT_TEMP_DIR = os.path.join(_BASE_DIR, "..", "..", "data", "audio", "voice_chat_temp")
os.makedirs(VOICE_CHAT_TEMP_DIR, exist_ok=True)


class VoiceConversationService:
    """
    실시간 음성 대화 파이프라인 서비스

    전체 흐름:
    1. 음성 입력 (audio blob) 저장
    2. Whisper/로컬 모델로 전사 (Speech-to-Text)
    3. 메모리 엔진으로 관련 기억 검색 + AI 페르소나 응답 생성
    4. edge-tts로 응답 음성 합성 (Text-to-Speech)
    5. 결과 반환: {transcribed_text, ai_response_text, audio_url, memory_attribution}
    """

    def __init__(
        self,
        persona_chat: PersonaChat,
        voice_service: VoiceCloneService,
    ):
        self.persona_chat = persona_chat
        self.voice_service = voice_service

    async def process_voice_message(
        self,
        person_id: int,
        audio_data: bytes,
        audio_format: str,
        db: DBSession,
    ) -> Dict[str, Any]:
        """
        음성 메시지를 처리하는 전체 파이프라인

        Args:
            person_id: 대화 대상 인물 ID
            audio_data: 업로드된 오디오 바이너리 데이터
            audio_format: 오디오 형식 (예: "webm", "wav", "ogg")
            db: SQLAlchemy DB 세션

        Returns:
            dict: {
                transcribed_text: str,       # 전사된 사용자 음성 텍스트
                ai_response_text: str,       # AI 페르소나 응답 텍스트
                audio_url: str | None,       # 합성된 응답 음성 URL (실패 시 None)
                emotion: str,                # 감지된 감정
                memory_attribution: list,    # 참조된 기억 목록
                error: str | None,           # 에러 메시지 (있을 경우)
            }
        """
        result = {
            "transcribed_text": "",
            "ai_response_text": "",
            "audio_url": None,
            "emotion": "neutral",
            "memory_attribution": [],
            "error": None,
        }

        # --- Step 0: Validate person exists ---
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            result["error"] = "인물을 찾을 수 없습니다."
            return result

        # --- Step 1: Save audio to temp file ---
        temp_path = None
        try:
            ext = self._normalize_extension(audio_format)
            temp_path = self._save_temp_audio(audio_data, ext)
            logger.info(
                f"Voice chat audio saved: {temp_path} "
                f"({len(audio_data)} bytes, format={audio_format})"
            )
        except Exception as e:
            logger.error(f"Failed to save voice chat audio: {e}")
            result["error"] = "음성 파일 저장에 실패했습니다."
            return result

        # --- Step 2: Transcribe audio ---
        try:
            transcribed_text = TranscriptionService.transcribe_audio(
                temp_path, language="ko"
            )
            if not transcribed_text or not transcribed_text.strip():
                result["error"] = "음성을 인식하지 못했습니다. 다시 말씀해 주세요."
                self._cleanup_temp(temp_path)
                return result

            result["transcribed_text"] = transcribed_text.strip()
            logger.info(
                f"Voice chat transcription: "
                f"'{transcribed_text[:80]}...' (person_id={person_id})"
            )
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            result["error"] = "음성 인식에 실패했습니다. 다시 시도해 주세요."
            self._cleanup_temp(temp_path)
            return result

        # --- Step 3: Generate AI persona response with memory context ---
        try:
            person_dict = {
                "id": person.id,
                "name": person.name,
                "personality_traits": person.personality_traits,
                "speaking_style": person.speaking_style,
                "relationship_type": person.relationship_type,
            }

            # Memory context retrieval
            memory_ctx = {}
            source_sessions = []
            try:
                memory_ctx = MemoryEngine.generate_context(
                    person_id, result["transcribed_text"], db
                )
                if memory_ctx.get("memory_context"):
                    person_dict["memory_context"] = memory_ctx["memory_context"]
                source_sessions = memory_ctx.get("source_sessions", [])
            except Exception as mem_err:
                logger.warning(f"Memory context generation failed: {mem_err}")

            # Generate AI response
            chat_result = self.persona_chat.chat(
                person_dict, result["transcribed_text"]
            )
            result["ai_response_text"] = chat_result.get("response", "")
            result["emotion"] = chat_result.get("emotion", "neutral")

            # Build memory attribution
            relevant_memories = memory_ctx.get("relevant_memories", [])
            for mem in relevant_memories:
                if mem.get("score", 0) >= 0.05:
                    result["memory_attribution"].append({
                        "session_id": mem.get("session_id"),
                        "session_number": mem.get("session_number", 0),
                        "topic": mem.get("topic", ""),
                        "score": mem.get("score", 0),
                        "keywords": mem.get("keywords", []),
                        "emotional_tone": mem.get("emotional_tone", ""),
                        "text_preview": (
                            (mem.get("text", "")[:120] + "...")
                            if len(mem.get("text", "")) > 120
                            else mem.get("text", "")
                        ),
                    })

            # Save conversation to DB
            try:
                conv = Conversation(
                    person_id=person_id,
                    user_id=1,
                    user_message=result["transcribed_text"],
                    ai_response=result["ai_response_text"],
                    emotion=result["emotion"],
                )
                db.add(conv)
                db.commit()
            except Exception as db_err:
                logger.warning(f"Failed to save voice conversation: {db_err}")
                try:
                    db.rollback()
                except Exception:
                    pass

            logger.info(
                f"Voice chat AI response: "
                f"'{result['ai_response_text'][:80]}...' "
                f"(emotion={result['emotion']})"
            )

        except Exception as e:
            logger.error(f"AI response generation failed: {e}")
            result["ai_response_text"] = "죄송합니다, 지금은 대답하기 어렵습니다. 다시 말씀해 주세요."
            result["emotion"] = "neutral"

        # --- Step 4: Synthesize AI response to audio ---
        try:
            if result["ai_response_text"]:
                # Limit text length for TTS
                tts_text = result["ai_response_text"][:2000]
                file_path = await self.voice_service.synthesize_response(
                    tts_text, person_id
                )
                if file_path and os.path.exists(file_path):
                    filename = os.path.basename(file_path)
                    result["audio_url"] = f"/api/audio/responses/{filename}"
                    logger.info(
                        f"Voice chat TTS complete: {filename}"
                    )
                else:
                    logger.warning(
                        "TTS synthesis returned no file - "
                        "text-only response will be sent"
                    )
        except Exception as e:
            logger.warning(
                f"TTS synthesis failed (returning text only): {e}"
            )
            # TTS failure is non-fatal - we still return the text response

        # --- Cleanup temp audio ---
        self._cleanup_temp(temp_path)

        return result

    @staticmethod
    def _normalize_extension(audio_format: str) -> str:
        """오디오 형식 문자열을 파일 확장자로 정규화"""
        fmt = audio_format.lower().strip()
        # Handle MIME types
        if "/" in fmt:
            fmt = fmt.split("/")[-1]
        # Handle codec suffixes
        if ";" in fmt:
            fmt = fmt.split(";")[0].strip()

        mapping = {
            "webm": ".webm",
            "wav": ".wav",
            "wave": ".wav",
            "ogg": ".ogg",
            "mp3": ".mp3",
            "mpeg": ".mp3",
            "mp4": ".m4a",
            "m4a": ".m4a",
            "flac": ".flac",
        }
        return mapping.get(fmt, ".webm")

    @staticmethod
    def _save_temp_audio(audio_data: bytes, ext: str) -> str:
        """오디오 데이터를 임시 파일로 저장"""
        timestamp = int(time.time() * 1000)
        filename = f"vc_{timestamp}{ext}"
        file_path = os.path.join(VOICE_CHAT_TEMP_DIR, filename)

        with open(file_path, "wb") as f:
            f.write(audio_data)

        return file_path

    @staticmethod
    def _cleanup_temp(file_path: Optional[str]):
        """임시 파일 정리"""
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except OSError as e:
                logger.debug(f"Failed to cleanup temp file {file_path}: {e}")
