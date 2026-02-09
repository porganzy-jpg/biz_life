"""
VoiceMemory 음성 클론 서비스

ElevenLabs API를 사용하여 음성 클론 및 TTS 생성
API 키가 없으면 시뮬레이션 모드로 동작
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")


class VoiceCloneService:
    """음성 클론 서비스"""

    def __init__(self):
        self.api_key = ELEVENLABS_API_KEY
        self.has_api = bool(self.api_key)
        if not self.has_api:
            logger.info("ElevenLabs API 키 미설정 - 시뮬레이션 모드")

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
            logger.info(f"[SIM] TTS 생성: '{text[:50]}...' (voice: {voice_id})")
            return None

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
            return None
        except Exception as e:
            logger.error(f"TTS 생성 오류: {e}")
            return None

    def list_voices(self) -> list:
        """사용 가능한 음성 목록"""
        if not self.has_api:
            return [{"voice_id": "sim_default", "name": "시뮬레이션 음성"}]

        try:
            import requests
            url = "https://api.elevenlabs.io/v1/voices"
            headers = {"xi-api-key": self.api_key}
            resp = requests.get(url, headers=headers, timeout=10)
            return resp.json().get("voices", [])
        except Exception:
            return []
