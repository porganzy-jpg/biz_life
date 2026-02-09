"""
VoiceMemory 녹음 세션 관리

가이드 대화 주제를 제공하고, 녹음 세션을 관리합니다.
50가지 대화 주제로 자연스러운 음성 데이터를 수집합니다.
"""
from sqlalchemy.orm import Session
from models import RecordingSession, Person


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
    def create_session(db: Session, person_id: int, topic_index: int = 0) -> RecordingSession:
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
    def get_sessions(db: Session, person_id: int) -> list:
        """특정 인물의 녹음 세션 목록"""
        return db.query(RecordingSession).filter(
            RecordingSession.person_id == person_id
        ).order_by(RecordingSession.session_number).all()

    @staticmethod
    def get_next_topic(db: Session, person_id: int) -> dict:
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
