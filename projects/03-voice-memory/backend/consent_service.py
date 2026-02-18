"""
VoiceMemory 동의 관리 서비스

법적 요구사항:
- 통신비밀보호법 준수 (도청이 아닌 본인 동의 하 녹음)
- 개인정보보호법 준수
- 동의 철회 시 데이터 삭제
"""
from datetime import datetime
from sqlalchemy.orm import Session
from models import Consent, Person, RecordingSession, Conversation


REQUIRED_CONSENTS = [
    {
        "type": "voice_recording",
        "title": "음성 녹음 동의",
        "description": "대화 내용을 녹음하고 저장하는 것에 동의합니다. 녹음된 음성은 AI 학습 및 음성 복원에 사용됩니다.",
    },
    {
        "type": "ai_clone",
        "title": "AI 음성 복원 동의",
        "description": "녹음된 음성을 기반으로 AI 음성 모델을 생성하는 것에 동의합니다.",
    },
    {
        "type": "data_storage",
        "title": "데이터 보관 동의",
        "description": "음성 데이터와 대화 내용을 안전하게 보관하는 것에 동의합니다. 동의 철회 시 모든 데이터가 삭제됩니다.",
    },
]


class ConsentService:
    """동의 관리"""

    @staticmethod
    def get_required_consents() -> list:
        """필요한 동의 항목 목록"""
        return REQUIRED_CONSENTS

    @staticmethod
    def grant_consent(db: Session, person_id: int, consent_type: str,
                      ip_address: str = "", notes: str = "") -> Consent:
        """동의 부여"""
        existing = db.query(Consent).filter(
            Consent.person_id == person_id,
            Consent.consent_type == consent_type,
        ).first()

        if existing:
            existing.is_granted = True
            existing.granted_at = datetime.utcnow()
            existing.revoked_at = None
            existing.ip_address = ip_address
            existing.notes = notes
        else:
            existing = Consent(
                person_id=person_id,
                consent_type=consent_type,
                is_granted=True,
                granted_at=datetime.utcnow(),
                ip_address=ip_address,
                notes=notes,
            )
            db.add(existing)

        db.commit()
        db.refresh(existing)
        return existing

    @staticmethod
    def revoke_consent(db: Session, person_id: int, consent_type: str) -> dict:
        """동의 철회 + 관련 데이터 삭제 (개인정보보호법 준수)"""
        consent = db.query(Consent).filter(
            Consent.person_id == person_id,
            Consent.consent_type == consent_type,
        ).first()

        if not consent:
            return {"revoked": False, "deleted": {}}

        consent.is_granted = False
        consent.revoked_at = datetime.utcnow()

        deleted = {}
        # voice_recording 또는 data_storage 철회 시 녹음 세션 삭제
        if consent_type in ("voice_recording", "data_storage"):
            count = db.query(RecordingSession).filter(
                RecordingSession.person_id == person_id
            ).delete()
            deleted["recording_sessions"] = count

        # ai_clone 또는 data_storage 철회 시 대화 기록 삭제
        if consent_type in ("ai_clone", "data_storage"):
            count = db.query(Conversation).filter(
                Conversation.person_id == person_id
            ).delete()
            deleted["conversations"] = count

        # data_storage 철회 시 인물 비활성화
        if consent_type == "data_storage":
            person = db.query(Person).filter(Person.id == person_id).first()
            if person:
                person.is_active = False
                deleted["person_deactivated"] = True

        db.commit()
        return {"revoked": True, "deleted": deleted}

    @staticmethod
    def check_all_consents(db: Session, person_id: int) -> dict:
        """모든 필수 동의 확인"""
        consents = db.query(Consent).filter(
            Consent.person_id == person_id,
            Consent.is_granted == True,
        ).all()

        granted_types = {c.consent_type for c in consents}
        required_types = {c["type"] for c in REQUIRED_CONSENTS}

        return {
            "all_granted": required_types.issubset(granted_types),
            "granted": list(granted_types),
            "missing": list(required_types - granted_types),
        }
