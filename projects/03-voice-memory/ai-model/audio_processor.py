"""
VoiceMemory 오디오 전처리

노이즈 제거, VAD(Voice Activity Detection), 오디오 포맷 변환
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AudioProcessor:
    """오디오 전처리"""

    SUPPORTED_FORMATS = [".wav", ".mp3", ".m4a", ".ogg", ".webm"]
    TARGET_SAMPLE_RATE = 44100
    TARGET_CHANNELS = 1

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), "..", "audio_data")
        os.makedirs(self.output_dir, exist_ok=True)

    def validate_audio(self, file_path: str) -> dict:
        """오디오 파일 유효성 검증"""
        if not os.path.exists(file_path):
            return {"valid": False, "error": "파일이 존재하지 않습니다"}

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.SUPPORTED_FORMATS:
            return {"valid": False, "error": f"지원하지 않는 형식: {ext}"}

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > 100:
            return {"valid": False, "error": f"파일 크기 초과: {size_mb:.1f}MB (최대 100MB)"}

        return {"valid": True, "format": ext, "size_mb": round(size_mb, 2)}

    def get_audio_info(self, file_path: str) -> dict:
        """오디오 파일 정보 조회"""
        try:
            import wave
            with wave.open(file_path, 'rb') as f:
                return {
                    "channels": f.getnchannels(),
                    "sample_rate": f.getframerate(),
                    "duration_seconds": f.getnframes() / f.getframerate(),
                    "bit_depth": f.getsampwidth() * 8,
                }
        except Exception:
            # WAV가 아니면 기본 정보 반환
            return {
                "channels": 0,
                "sample_rate": 0,
                "duration_seconds": 0,
                "format": os.path.splitext(file_path)[1],
            }

    def estimate_recording_quality(self, duration_seconds: float, session_count: int) -> dict:
        """
        녹음 품질 추정

        음성 클론에 필요한 최소 데이터:
        - 최소: 30초 (저품질)
        - 권장: 3~5분 (중품질)
        - 최적: 30분 이상 (고품질)
        """
        total_minutes = (duration_seconds * session_count) / 60

        if total_minutes >= 30:
            quality = "excellent"
            message = "충분한 음성 데이터가 수집되었습니다. 최상의 품질 기대!"
        elif total_minutes >= 10:
            quality = "good"
            message = "좋은 품질의 음성 복원이 가능합니다."
        elif total_minutes >= 3:
            quality = "acceptable"
            message = "기본적인 음성 복원이 가능합니다. 추가 녹음을 권장합니다."
        elif total_minutes >= 0.5:
            quality = "minimal"
            message = "최소 품질입니다. 더 많은 녹음이 필요합니다."
        else:
            quality = "insufficient"
            message = "음성 데이터가 부족합니다. 녹음을 시작해주세요."

        return {
            "quality": quality,
            "total_minutes": round(total_minutes, 1),
            "sessions": session_count,
            "message": message,
            "recommended_more_minutes": max(0, 10 - total_minutes),
        }
