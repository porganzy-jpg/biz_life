"""
StockBot 뉴스 감성 분석 엔진

키워드 기반 감성 분석 + (선택적) OpenAI API 활용 고급 분석
"""
import os
import logging
from typing import List

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """뉴스 감성 분석"""

    # 한국 주식시장 키워드 사전
    POSITIVE_KEYWORDS = [
        "상승", "급등", "호재", "실적개선", "매수", "신고가", "돌파", "성장",
        "수주", "흑자전환", "목표가상향", "긍정적", "기대", "호실적",
        "증가", "순매수", "비중확대", "매출증가", "상회", "호조",
        "투자", "확대", "개선", "반등", "회복", "수혜",
    ]

    NEGATIVE_KEYWORDS = [
        "하락", "급락", "악재", "실적부진", "매도", "신저가", "이탈",
        "감소", "적자", "적자전환", "목표가하향", "부정적", "우려",
        "리스크", "순매도", "하향", "감소", "부진", "위축",
        "손실", "축소", "위기", "약세", "불안", "하회",
    ]

    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY", "")

    def analyze_keyword(self, text: str) -> float:
        """
        키워드 기반 감성 분석

        Returns:
            float: -1.0 (매우 부정) ~ +1.0 (매우 긍정)
        """
        pos = sum(1 for k in self.POSITIVE_KEYWORDS if k in text)
        neg = sum(1 for k in self.NEGATIVE_KEYWORDS if k in text)

        if pos + neg == 0:
            return 0.0
        return (pos - neg) / (pos + neg)

    def analyze_batch(self, news_list: List[dict]) -> dict:
        """
        뉴스 배치 감성 분석

        Returns:
            dict: {
                "overall": float,  # 종합 감성
                "positive_count": int,
                "negative_count": int,
                "neutral_count": int,
                "details": list,
            }
        """
        if not news_list:
            return {"overall": 0.0, "positive_count": 0, "negative_count": 0,
                    "neutral_count": 0, "details": []}

        details = []
        for news in news_list:
            text = news.get("title", "") + " " + news.get("content", "")
            score = self.analyze_keyword(text)
            details.append({
                "title": news.get("title", "")[:50],
                "score": round(score, 2),
                "label": "긍정" if score > 0.2 else "부정" if score < -0.2 else "중립",
            })

        scores = [d["score"] for d in details]
        overall = sum(scores) / len(scores) if scores else 0

        return {
            "overall": round(overall, 3),
            "positive_count": sum(1 for d in details if d["label"] == "긍정"),
            "negative_count": sum(1 for d in details if d["label"] == "부정"),
            "neutral_count": sum(1 for d in details if d["label"] == "중립"),
            "details": details,
        }

    def analyze_with_llm(self, text: str) -> float:
        """
        OpenAI API를 활용한 고급 감성 분석 (선택적)

        API 키가 없으면 키워드 분석으로 폴백
        """
        if not self.openai_key:
            return self.analyze_keyword(text)

        try:
            import requests
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.openai_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "한국 주식시장 뉴스의 감성을 -1.0(매우 부정)~+1.0(매우 긍정)으로 평가하세요. 숫자만 응답하세요."},
                        {"role": "user", "content": text[:500]},
                    ],
                    "max_tokens": 10,
                },
                timeout=10,
            )
            result = resp.json()["choices"][0]["message"]["content"].strip()
            return float(result)
        except Exception as e:
            logger.debug(f"LLM 분석 실패, 키워드 분석 폴백: {e}")
            return self.analyze_keyword(text)
