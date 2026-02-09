"""
VoiceMemory LLM 페르소나 대화 시스템

녹음된 데이터를 기반으로 고인/부모의 성격을 재현하는 대화 시스템
OpenAI API 사용 (API 키 없으면 규칙 기반 폴백)
"""
import os
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


class PersonaChat:
    """페르소나 기반 AI 대화"""

    def __init__(self):
        self.api_key = OPENAI_API_KEY
        self.has_api = bool(self.api_key)
        self.conversation_history = {}  # person_id → messages

    def build_system_prompt(self, person: dict) -> str:
        """페르소나 시스템 프롬프트 구성"""
        traits = ", ".join(person.get("personality_traits", ["따뜻한"]))
        style = person.get("speaking_style", "")
        name = person.get("name", "")
        relationship = person.get("relationship_type", "family")

        prompt = f"""당신은 '{name}'이라는 분의 페르소나를 재현하는 AI입니다.

관계: {relationship}
성격 특성: {traits}
말투: {style if style else '다정하고 따뜻한 어투'}

대화 규칙:
1. {name}님의 성격과 말투를 최대한 자연스럽게 재현하세요.
2. 따뜻하고 사랑이 담긴 대화를 나누세요.
3. 과거 추억, 삶의 지혜, 응원의 메시지를 적절히 활용하세요.
4. 답변은 2~4문장으로 자연스럽게 해주세요.
5. 한국어로 대화합니다."""
        return prompt

    def chat(self, person: dict, user_message: str) -> dict:
        """
        페르소나 대화

        Args:
            person: 인물 정보 dict
            user_message: 사용자 메시지

        Returns:
            dict: {response, emotion}
        """
        person_id = person.get("id", 0)
        system_prompt = self.build_system_prompt(person)

        if self.has_api:
            return self._chat_with_openai(person_id, system_prompt, user_message)
        else:
            return self._chat_fallback(person, user_message)

    def _chat_with_openai(self, person_id: int, system_prompt: str, user_message: str) -> dict:
        """OpenAI API로 대화"""
        try:
            import requests

            # 대화 히스토리 관리
            if person_id not in self.conversation_history:
                self.conversation_history[person_id] = []

            history = self.conversation_history[person_id]
            history.append({"role": "user", "content": user_message})

            # 최근 10턴만 유지
            recent = history[-20:]

            messages = [{"role": "system", "content": system_prompt}] + recent

            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "max_tokens": 200,
                    "temperature": 0.8,
                },
                timeout=15,
            )
            result = resp.json()
            ai_response = result["choices"][0]["message"]["content"]

            history.append({"role": "assistant", "content": ai_response})
            self.conversation_history[person_id] = history[-20:]

            # 감정 추정
            emotion = self._detect_emotion(ai_response)

            return {"response": ai_response, "emotion": emotion}

        except Exception as e:
            logger.error(f"OpenAI 대화 실패: {e}")
            return self._chat_fallback({"id": person_id, "name": "AI"}, user_message)

    def _chat_fallback(self, person: dict, user_message: str) -> dict:
        """규칙 기반 폴백 대화"""
        name = person.get("name", "")
        responses = {
            "안녕": f"그래, 어서 와. 오늘 하루는 어땠어?",
            "보고싶": f"나도 보고싶단다. 항상 네 곁에 있어.",
            "사랑": f"나도 너를 사랑한다. 그거 잊지 마렴.",
            "어떻게": f"걱정 마. 다 잘 될 거야. 네가 해낼 수 있어.",
            "힘들": f"힘들 때는 좀 쉬어가도 돼. 괜찮아.",
            "감사": f"고맙긴 뭐가 고마워. 그게 당연한 거지.",
            "날씨": f"오늘 날씨가 좋다면 산책이라도 나가렴. 바깥 공기가 좋을 거야.",
        }

        for keyword, response in responses.items():
            if keyword in user_message:
                return {"response": response, "emotion": "warm"}

        default_responses = [
            f"그래, 그렇구나. 더 이야기해 줄래?",
            f"음, 그게 걱정이구나. 괜찮아, 다 잘 될 거야.",
            f"그 이야기 더 듣고 싶다. 천천히 말해봐.",
            f"그랬구나... 정말 대단하다.",
        ]
        import random
        response = random.choice(default_responses)
        return {"response": response, "emotion": "neutral"}

    def _detect_emotion(self, text: str) -> str:
        """간단한 감정 감지"""
        warm_keywords = ["사랑", "보고싶", "고맙", "감사", "행복", "기쁘"]
        sad_keywords = ["슬프", "힘들", "걱정", "아프", "그립"]
        happy_keywords = ["좋", "재미", "웃", "즐거"]

        for kw in warm_keywords:
            if kw in text:
                return "warm"
        for kw in sad_keywords:
            if kw in text:
                return "comforting"
        for kw in happy_keywords:
            if kw in text:
                return "happy"
        return "neutral"
