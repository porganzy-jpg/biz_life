"""
VoiceMemory 음성 클론 서비스

ElevenLabs API를 사용하여 음성 클론 및 TTS 생성
API 키가 없으면 edge-tts (무료 한국어 TTS) 폴백 사용
"""
import os
import hashlib
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# Base directory for synthesized audio responses
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESPONSES_AUDIO_DIR = os.path.join(_BASE_DIR, "..", "data", "audio", "responses")
os.makedirs(RESPONSES_AUDIO_DIR, exist_ok=True)

# Default Korean voice for edge-tts
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "ko-KR-SunHiNeural")


class VoiceCloneService:
    """음성 클론 서비스"""

    def __init__(self):
        self.api_key = ELEVENLABS_API_KEY
        self.has_api = bool(self.api_key)
        self._edge_tts_available = None  # lazy check
        if not self.has_api:
            logger.info("ElevenLabs API 키 미설정 - edge-tts 폴백 모드")

    def _check_edge_tts(self) -> bool:
        """edge-tts 사용 가능 여부 확인 (lazy)"""
        if self._edge_tts_available is None:
            try:
                import edge_tts  # noqa: F401
                self._edge_tts_available = True
                logger.info("edge-tts 사용 가능")
            except ImportError:
                self._edge_tts_available = False
                logger.warning("edge-tts 미설치 (pip install edge-tts)")
        return self._edge_tts_available

    def clone_voice(self, name: str, audio_files: list) -> str:
        """
        음성 클론 생성

        Args:
            name: 음성 이름
            audio_files: 학습용 오디오 파일 경로 리스트

        Returns:
            str: 생성된 voice_id
        """
        if not self.has_api:
            voice_id = f"sim_voice_{name.replace(' ', '_').lower()}"
            logger.info(f"[SIM] 음성 클론 생성: {voice_id}")
            return voice_id

        try:
            import requests
            url = "https://api.elevenlabs.io/v1/voices/add"
            headers = {"xi-api-key": self.api_key}

            files_data = []
            for path in audio_files:
                if os.path.exists(path):
                    files_data.append(("files", open(path, "rb")))

            data = {"name": name, "description": f"Voice clone for {name}"}
            resp = requests.post(url, headers=headers, data=data, files=files_data, timeout=60)
            result = resp.json()
            return result.get("voice_id", "")
        except Exception as e:
            logger.error(f"음성 클론 실패: {e}")
            return ""

    def generate_speech(self, voice_id: str, text: str) -> Optional[bytes]:
        """
        TTS 음성 생성

        Args:
            voice_id: 클론된 음성 ID
            text: 변환할 텍스트

        Returns:
            bytes: 오디오 데이터 (MP3)
        """
        if not self.has_api:
            # ElevenLabs 없으면 edge-tts 폴백
            return self._generate_speech_edge_tts(text)

        try:
            import requests
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
            }
            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.8,
                },
            }
            resp = requests.post(url, headers=headers, json=data, timeout=30)
            if resp.ok:
                return resp.content
            logger.error(f"TTS 생성 실패: {resp.status_code}")
            # ElevenLabs 실패 시 edge-tts 폴백 시도
            return self._generate_speech_edge_tts(text)
        except Exception as e:
            logger.error(f"TTS 생성 오류: {e}")
            return self._generate_speech_edge_tts(text)

    def _generate_speech_edge_tts(self, text: str, voice: str = "") -> Optional[bytes]:
        """
        edge-tts를 사용한 무료 TTS 생성 (한국어 지원)

        Args:
            text: 변환할 텍스트
            voice: edge-tts 음성 이름 (기본: ko-KR-SunHiNeural)

        Returns:
            bytes: MP3 오디오 데이터
        """
        if not self._check_edge_tts():
            logger.warning("edge-tts 미설치 - TTS 생성 불가")
            return None

        voice = voice or EDGE_TTS_VOICE

        try:
            import edge_tts
            import tempfile

            async def _synthesize():
                communicate = edge_tts.Communicate(text, voice)
                # Write to temp file then read bytes
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    tmp_path = tmp.name

                await communicate.save(tmp_path)

                with open(tmp_path, "rb") as f:
                    audio_data = f.read()

                # Cleanup temp file
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

                return audio_data

            # Run async edge-tts in sync context
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # We're already in an async context - use a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(lambda: asyncio.run(_synthesize()))
                    audio_data = future.result(timeout=30)
            else:
                audio_data = asyncio.run(_synthesize())

            if audio_data and len(audio_data) > 0:
                logger.info(f"edge-tts 합성 완료: {len(audio_data)} bytes, voice={voice}")
                return audio_data
            else:
                logger.warning("edge-tts가 빈 오디오를 반환함")
                return None

        except Exception as e:
            logger.error(f"edge-tts 합성 오류: {e}")
            return None

    def list_voices(self) -> list:
        """사용 가능한 음성 목록"""
        if not self.has_api:
            voices = [{"voice_id": "edge_default", "name": "한국어 여성 (SunHi)", "engine": "edge-tts"}]
            if self._check_edge_tts():
                voices.append({"voice_id": "edge_male", "name": "한국어 남성 (InJoon)", "engine": "edge-tts"})
            return voices

        try:
            import requests
            url = "https://api.elevenlabs.io/v1/voices"
            headers = {"xi-api-key": self.api_key}
            resp = requests.get(url, headers=headers, timeout=10)
            return resp.json().get("voices", [])
        except Exception:
            return []

    async def synthesize_response(self, text: str, person_id: int, voice: str = "") -> Optional[str]:
        """
        AI 응답 텍스트를 음성으로 합성하고 파일로 저장

        Args:
            text: 합성할 텍스트
            person_id: 인물 ID (캐시 키에 사용)
            voice: edge-tts 음성 이름 (선택)

        Returns:
            str: 생성된 오디오 파일 경로 (없으면 None)
        """
        if not text or not text.strip():
            return None

        # 텍스트 해시로 캐시 키 생성 (동일 텍스트는 재합성하지 않음)
        text_hash = hashlib.md5(
            f"{person_id}:{voice or EDGE_TTS_VOICE}:{text.strip()}".encode("utf-8")
        ).hexdigest()[:16]
        filename = f"resp_{person_id}_{text_hash}.mp3"
        file_path = os.path.join(RESPONSES_AUDIO_DIR, filename)

        # 캐시된 파일이 있으면 바로 반환
        if os.path.exists(file_path) and os.path.getsize(file_path) > 100:
            logger.info(f"캐시된 합성 음성 사용: {filename}")
            return file_path

        # ElevenLabs API가 있고 person의 voice_id가 있으면 ElevenLabs 사용
        audio_data = None
        if self.has_api:
            audio_data = self.generate_speech(voice or "default", text)

        # ElevenLabs 실패 또는 미설정 시 edge-tts 사용
        if not audio_data:
            audio_data = self._generate_speech_edge_tts(text, voice)

        if not audio_data:
            logger.warning(f"음성 합성 실패: person_id={person_id}")
            return None

        # 파일 저장
        try:
            with open(file_path, "wb") as f:
                f.write(audio_data)
            logger.info(f"합성 음성 저장: {filename} ({len(audio_data)} bytes)")
            return file_path
        except Exception as e:
            logger.error(f"합성 음성 파일 저장 실패: {e}")
            return None
