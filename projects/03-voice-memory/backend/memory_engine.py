"""
VoiceMemory - Semantic Memory Engine

Pure Python TF-IDF 기반 의미론적 기억 검색 시스템
녹음 전사 데이터를 분석하여 관련 기억을 찾고, AI 대화에 컨텍스트를 제공합니다.
"""
import re
import math
import json
import logging
from collections import Counter, defaultdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session as DBSession
from models import Person, RecordingSession, Conversation

logger = logging.getLogger(__name__)


# ============================================================
# Pure Python TF-IDF Utilities (no sklearn dependency)
# ============================================================

# Korean stop words for tokenization
_STOP_WORDS = {
    "그", "이", "저", "것", "거", "수", "등", "때", "중",
    "더", "안", "못", "잘", "좀", "다", "또", "다시",
    "그래서", "그런데", "그리고", "하지만", "그래도", "근데",
    "네", "예", "아", "어", "음", "응", "글쎄",
    "있다", "없다", "하다", "되다", "있는", "없는", "하는", "되는",
    "했다", "됐다", "있었", "없었", "했는데", "됐는데",
    "제가", "저는", "나는", "내가", "우리", "저희",
    "그거", "이거", "저거", "여기", "거기", "저기",
    "정말", "진짜", "매우", "아주", "너무", "많이",
    "그래", "그렇", "이런", "저런", "그런",
    "했어", "했죠", "했고", "해서", "하고",
    "는데", "인데", "었는데", "니까", "으니까",
    "the", "a", "an", "is", "are", "was", "were", "be",
    "to", "of", "and", "in", "that", "it", "for", "on",
}

# Korean particles to strip from token ends
_PARTICLES = [
    "에서는", "으로는", "에게서", "에서", "으로", "에게", "한테",
    "부터", "까지", "처럼", "같이", "보다", "마저", "조차", "밖에",
    "이랑", "하고",
    "은", "는", "이", "가", "을", "를", "에", "로",
    "와", "과", "의", "도", "만", "랑",
    "께서",
]
# Sort by length descending so longest match is tried first
_PARTICLES.sort(key=len, reverse=True)


def _tokenize(text: str) -> List[str]:
    """
    Split text into tokens for TF-IDF.
    Handles Korean (Hangul) words and basic Latin words.
    Strips common Korean particles from word endings.
    """
    if not text:
        return []

    # Extract Hangul words (2+ chars) and Latin words (2+ chars)
    raw_tokens = re.findall(r'[가-힣]{2,}|[a-zA-Z]{2,}', text.lower())

    cleaned = []
    for token in raw_tokens:
        # Skip stop words
        if token in _STOP_WORDS:
            continue

        # For Korean tokens, try stripping particles
        if re.match(r'^[가-힣]+$', token):
            stripped = token
            for p in _PARTICLES:
                if stripped.endswith(p) and len(stripped) > len(p) + 1:
                    stripped = stripped[:-len(p)]
                    break
            if len(stripped) >= 2 and stripped not in _STOP_WORDS:
                cleaned.append(stripped)
        else:
            # Latin token
            if len(token) >= 2:
                cleaned.append(token)

    return cleaned


def _compute_tfidf(documents: List[List[str]]) -> List[Dict[str, float]]:
    """
    Compute TF-IDF vectors for a list of tokenized documents.

    Args:
        documents: List of token lists, one per document

    Returns:
        List of dicts mapping term -> TF-IDF weight for each document
    """
    n_docs = len(documents)
    if n_docs == 0:
        return []

    # Document frequency: how many docs contain each term
    df = Counter()
    for doc_tokens in documents:
        unique_terms = set(doc_tokens)
        for term in unique_terms:
            df[term] += 1

    tfidf_vectors = []
    for doc_tokens in documents:
        if not doc_tokens:
            tfidf_vectors.append({})
            continue

        # Term frequency in this document
        tf = Counter(doc_tokens)
        total_terms = len(doc_tokens)

        vec = {}
        for term, count in tf.items():
            # Normalized TF
            term_freq = count / total_terms
            # IDF with smoothing
            idf = math.log((1 + n_docs) / (1 + df.get(term, 0))) + 1
            vec[term] = term_freq * idf

        tfidf_vectors.append(vec)

    return tfidf_vectors


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """
    Compute cosine similarity between two sparse TF-IDF vectors (dicts).

    Returns:
        float between 0.0 and 1.0
    """
    if not vec_a or not vec_b:
        return 0.0

    # Dot product (only over shared keys)
    shared_keys = set(vec_a.keys()) & set(vec_b.keys())
    if not shared_keys:
        return 0.0

    dot = sum(vec_a[k] * vec_b[k] for k in shared_keys)

    # Magnitudes
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot / (mag_a * mag_b)


# ============================================================
# Memory Chunk Data Structure
# ============================================================

class MemoryChunk:
    """A single chunk of memory from a recording session."""

    def __init__(
        self,
        text: str,
        session_id: int,
        topic: str,
        session_number: int,
        emotional_tone: str = "",
        keywords: List[str] = None,
        summary: str = "",
        chunk_index: int = 0,
    ):
        self.text = text
        self.session_id = session_id
        self.topic = topic
        self.session_number = session_number
        self.emotional_tone = emotional_tone
        self.keywords = keywords or []
        self.summary = summary
        self.chunk_index = chunk_index
        self.tokens: List[str] = []
        self.tfidf_vector: Dict[str, float] = {}

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "session_id": self.session_id,
            "topic": self.topic,
            "session_number": self.session_number,
            "emotional_tone": self.emotional_tone,
            "keywords": self.keywords,
            "summary": self.summary,
            "chunk_index": self.chunk_index,
        }


# ============================================================
# MemoryEngine Class
# ============================================================

class MemoryEngine:
    """
    Semantic memory search system for VoiceMemory.

    Builds TF-IDF index from recording transcripts and provides:
    - Memory search (find relevant transcript chunks for a query)
    - Person profile aggregation (topics, emotions, key facts)
    - Rich context generation for AI chat
    """

    # Cache: person_id -> (chunks, timestamp)
    _cache: Dict[int, Tuple[List[MemoryChunk], float]] = {}
    _CACHE_TTL = 300  # 5 minutes

    @classmethod
    def _split_into_chunks(cls, transcript: str, max_chunk_size: int = 300) -> List[str]:
        """
        Split a transcript into meaningful chunks.
        Split by double newline (paragraph), then by sentence if too long.
        """
        if not transcript or not transcript.strip():
            return []

        # First try splitting by paragraph
        paragraphs = re.split(r'\n\s*\n', transcript.strip())
        # If no paragraphs, split by single newlines
        if len(paragraphs) <= 1:
            paragraphs = re.split(r'\n', transcript.strip())
        # If still one block, split by sentence endings
        if len(paragraphs) <= 1:
            paragraphs = re.split(r'(?<=[.!?。])\s+', transcript.strip())

        chunks = []
        current_chunk = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 1 <= max_chunk_size:
                current_chunk = (current_chunk + " " + para).strip()
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # If paragraph itself is too long, split by sentences
                if len(para) > max_chunk_size:
                    sentences = re.split(r'(?<=[.!?。])\s*', para)
                    sub_chunk = ""
                    for sent in sentences:
                        sent = sent.strip()
                        if not sent:
                            continue
                        if len(sub_chunk) + len(sent) + 1 <= max_chunk_size:
                            sub_chunk = (sub_chunk + " " + sent).strip()
                        else:
                            if sub_chunk:
                                chunks.append(sub_chunk)
                            sub_chunk = sent
                    current_chunk = sub_chunk
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(current_chunk)

        # Filter out very short chunks (less than 10 chars)
        return [c for c in chunks if len(c) >= 10]

    @classmethod
    def build_memory_chunks(cls, person_id: int, db: DBSession) -> List[MemoryChunk]:
        """
        Build memory chunks from all transcripts for a person.
        Tokenizes each chunk and computes TF-IDF vectors.

        Args:
            person_id: Target person ID
            db: Database session

        Returns:
            List of MemoryChunk objects with TF-IDF vectors computed
        """
        # Check cache
        now = datetime.utcnow().timestamp()
        if person_id in cls._cache:
            cached_chunks, cached_time = cls._cache[person_id]
            if now - cached_time < cls._CACHE_TTL:
                return cached_chunks

        sessions = db.query(RecordingSession).filter(
            RecordingSession.person_id == person_id,
            RecordingSession.transcript.isnot(None),
            RecordingSession.transcript != "",
        ).order_by(RecordingSession.session_number).all()

        all_chunks: List[MemoryChunk] = []

        for session in sessions:
            transcript = session.transcript or ""
            if not transcript.strip():
                continue

            # Parse keywords
            kw_list = []
            if session.keywords:
                try:
                    kw_list = json.loads(session.keywords)
                except (ValueError, TypeError):
                    kw_list = []

            text_chunks = cls._split_into_chunks(transcript)

            for idx, chunk_text in enumerate(text_chunks):
                chunk = MemoryChunk(
                    text=chunk_text,
                    session_id=session.id,
                    topic=session.topic or "",
                    session_number=session.session_number or 0,
                    emotional_tone=session.emotional_tone or "",
                    keywords=kw_list,
                    summary=session.transcript_summary or "",
                    chunk_index=idx,
                )
                chunk.tokens = _tokenize(chunk_text)
                all_chunks.append(chunk)

            # Also add summary as a chunk if it exists (it captures key themes)
            if session.transcript_summary and session.transcript_summary.strip():
                summary_chunk = MemoryChunk(
                    text=session.transcript_summary,
                    session_id=session.id,
                    topic=session.topic or "",
                    session_number=session.session_number or 0,
                    emotional_tone=session.emotional_tone or "",
                    keywords=kw_list,
                    summary=session.transcript_summary,
                    chunk_index=-1,  # -1 indicates summary chunk
                )
                summary_chunk.tokens = _tokenize(session.transcript_summary)
                all_chunks.append(summary_chunk)

        # Compute TF-IDF vectors across all chunks
        if all_chunks:
            all_token_lists = [c.tokens for c in all_chunks]
            tfidf_vectors = _compute_tfidf(all_token_lists)
            for chunk, vec in zip(all_chunks, tfidf_vectors):
                chunk.tfidf_vector = vec

        # Update cache
        cls._cache[person_id] = (all_chunks, now)
        logger.info(f"Built {len(all_chunks)} memory chunks for person {person_id}")

        return all_chunks

    @classmethod
    def search_memories(
        cls,
        person_id: int,
        query: str,
        db: DBSession,
        top_k: int = 5,
    ) -> List[Dict]:
        """
        Find the most relevant memory chunks for a given query.

        Args:
            person_id: Target person ID
            query: Search query text
            db: Database session
            top_k: Number of top results to return

        Returns:
            List of dicts with chunk info and similarity score
        """
        chunks = cls.build_memory_chunks(person_id, db)
        if not chunks:
            return []

        # Tokenize query
        query_tokens = _tokenize(query)
        if not query_tokens:
            # Fallback: try exact keyword match in chunk text
            query_lower = query.lower().strip()
            results = []
            for chunk in chunks:
                if query_lower in chunk.text.lower():
                    results.append({
                        **chunk.to_dict(),
                        "score": 0.5,  # Fixed score for exact match fallback
                    })
            results.sort(key=lambda x: -x["score"])
            return results[:top_k]

        # Build TF-IDF vector for query within the same vocabulary
        # We add the query as an extra document, compute TF-IDF, then use last vector
        all_token_lists = [c.tokens for c in chunks] + [query_tokens]
        all_vectors = _compute_tfidf(all_token_lists)
        query_vector = all_vectors[-1]

        # Score each chunk
        scored = []
        for i, chunk in enumerate(chunks):
            similarity = _cosine_similarity(all_vectors[i], query_vector)

            # Boost: if query words appear directly in chunk text
            text_lower = chunk.text.lower()
            query_lower = query.lower()
            keyword_bonus = 0.0
            for token in query_tokens:
                if token in text_lower:
                    keyword_bonus += 0.05

            # Boost: topic match
            if chunk.topic and any(t in chunk.topic.lower() for t in query_tokens):
                keyword_bonus += 0.1

            final_score = min(1.0, similarity + keyword_bonus)

            if final_score > 0.01:
                scored.append({
                    **chunk.to_dict(),
                    "score": round(final_score, 4),
                })

        # Sort by score descending
        scored.sort(key=lambda x: -x["score"])
        return scored[:top_k]

    @classmethod
    def get_person_profile(cls, person_id: int, db: DBSession) -> Dict:
        """
        Aggregate a person's knowledge profile from all recordings.

        Returns:
            Dict with topics_discussed, emotional_patterns, key_facts,
            total_memories, suggested_questions
        """
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            return {"error": "Person not found"}

        sessions = db.query(RecordingSession).filter(
            RecordingSession.person_id == person_id,
        ).order_by(RecordingSession.session_number).all()

        # Topics discussed
        topics = []
        for s in sessions:
            if s.topic and s.status == "completed":
                topics.append(s.topic)

        # Emotional patterns
        tone_counter = Counter()
        for s in sessions:
            if s.emotional_tone and s.emotional_tone.strip():
                tone_counter[s.emotional_tone.strip()] += 1
        emotional_patterns = [
            {"tone": tone, "count": count}
            for tone, count in tone_counter.most_common()
        ]

        # Key facts / keywords across all sessions
        keyword_counter = Counter()
        for s in sessions:
            if s.keywords:
                try:
                    kw_list = json.loads(s.keywords)
                    for kw in kw_list:
                        keyword_counter[kw.strip()] += 1
                except (ValueError, TypeError):
                    pass
        key_facts = [
            {"keyword": kw, "count": cnt}
            for kw, cnt in keyword_counter.most_common(20)
        ]

        # Summaries
        summaries = []
        for s in sessions:
            if s.transcript_summary and s.transcript_summary.strip():
                summaries.append({
                    "session_number": s.session_number,
                    "topic": s.topic or "",
                    "summary": s.transcript_summary,
                })

        # Total memory count (transcript chunks)
        chunks = cls.build_memory_chunks(person_id, db)
        total_memories = len(chunks)

        # Generate suggested questions based on topics
        suggested_questions = cls._generate_suggestions(topics, key_facts)

        # Personality summary
        personality_summary = cls._build_personality_summary(person, emotional_patterns, key_facts)

        return {
            "person_id": person_id,
            "person_name": person.name,
            "relationship_type": person.relationship_type,
            "personality_traits": person.personality_traits or [],
            "speaking_style": person.speaking_style or "",
            "topics_discussed": topics,
            "emotional_patterns": emotional_patterns,
            "key_facts": key_facts,
            "summaries": summaries,
            "total_memories": total_memories,
            "suggested_questions": suggested_questions,
            "personality_summary": personality_summary,
        }

    @classmethod
    def generate_context(
        cls,
        person_id: int,
        user_message: str,
        db: DBSession,
    ) -> Dict:
        """
        Build rich context for AI chat by combining:
        1. Relevant memory search results
        2. Person profile summary

        Returns a dict with:
        - memory_context: formatted string for system prompt injection
        - relevant_memories: list of matching memory chunks (for UI)
        - profile_snippet: brief profile for prompt
        """
        # Search relevant memories
        relevant = cls.search_memories(person_id, user_message, db, top_k=5)

        # Build memory context string for system prompt
        memory_lines = []
        source_sessions = []
        for i, mem in enumerate(relevant):
            if mem["score"] < 0.05:
                continue
            memory_lines.append(
                f"[기억 {i+1} - 세션#{mem['session_number']} \"{mem['topic']}\"]: "
                f"{mem['text'][:200]}"
            )
            source_sessions.append({
                "session_id": mem["session_id"],
                "session_number": mem["session_number"],
                "topic": mem["topic"],
                "score": mem["score"],
            })

        # Get profile snippet
        profile = cls.get_person_profile(person_id, db)
        profile_snippet_parts = []

        if profile.get("topics_discussed"):
            topics_str = ", ".join(profile["topics_discussed"][:5])
            profile_snippet_parts.append(f"이 분과 나눈 대화 주제: {topics_str}")

        if profile.get("emotional_patterns"):
            top_emotions = [e["tone"] for e in profile["emotional_patterns"][:3]]
            profile_snippet_parts.append(f"주요 감정 패턴: {', '.join(top_emotions)}")

        if profile.get("key_facts"):
            top_keywords = [f["keyword"] for f in profile["key_facts"][:8]]
            profile_snippet_parts.append(f"자주 언급한 키워드: {', '.join(top_keywords)}")

        profile_snippet = "; ".join(profile_snippet_parts) if profile_snippet_parts else ""

        # Compose the full memory context
        memory_context = ""
        if memory_lines:
            memory_context = (
                "\n\n--- 관련 기억 (녹음에서 발견된 실제 내용) ---\n"
                + "\n".join(memory_lines)
                + "\n--- 기억 끝 ---\n\n"
                "위의 기억 내용을 참고하여 자연스럽게 대화하세요. "
                "기억에 나온 구체적인 내용을 활용하되, 기억을 인용하고 있다는 것을 직접적으로 말하지 마세요. "
                "자연스럽게 그 사람답게 대화하세요."
            )

        if profile_snippet:
            memory_context = f"\n[프로필 정보] {profile_snippet}\n" + memory_context

        return {
            "memory_context": memory_context,
            "relevant_memories": relevant,
            "source_sessions": source_sessions,
            "profile_snippet": profile_snippet,
        }

    @staticmethod
    def _generate_suggestions(topics: List[str], key_facts: List[Dict]) -> List[str]:
        """Generate suggested questions based on recorded topics and keywords."""
        suggestions = []

        topic_templates = {
            "어린 시절": "어린 시절에 가장 행복했던 기억이 뭐예요?",
            "가족": "가족들과 함께했던 특별한 순간이 있나요?",
            "직업": "일하면서 가장 보람을 느꼈던 때는 언제였어요?",
            "취미": "요즘 가장 즐기는 취미가 뭐예요?",
            "인생 조언": "살면서 가장 중요하게 생각하는 가치가 뭐예요?",
            "음식": "가장 좋아하는 음식이 뭐예요? 특별한 이유가 있나요?",
            "여행": "가장 기억에 남는 여행지가 어디예요?",
            "친구": "가장 오래된 친구와의 추억을 들려주세요.",
            "건강": "건강하게 사는 비결이 뭐예요?",
            "계절": "가장 좋아하는 계절과 그 이유를 알려주세요.",
        }

        # Add generic suggestions for covered topics
        for topic in topics[:5]:
            for key, question in topic_templates.items():
                if key in topic:
                    suggestions.append(question)
                    break

        # Add keyword-based suggestions
        if key_facts:
            top_kw = [f["keyword"] for f in key_facts[:3]]
            for kw in top_kw:
                suggestions.append(f"'{kw}'에 대해 더 이야기해 주세요.")

        # Default suggestions if none generated
        if not suggestions:
            suggestions = [
                "오늘 기분이 어떠세요?",
                "요즘 무슨 생각을 하고 계세요?",
                "가장 행복했던 기억이 뭐예요?",
                "저에게 해주고 싶은 말이 있으세요?",
            ]

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        return unique[:6]

    @staticmethod
    def _build_personality_summary(
        person: Person,
        emotional_patterns: List[Dict],
        key_facts: List[Dict],
    ) -> str:
        """Build a natural language personality summary."""
        parts = []
        name = person.name

        traits = person.personality_traits or []
        if traits:
            parts.append(f"{name}님은 {', '.join(traits[:4])} 성격의 분입니다.")

        if person.speaking_style:
            parts.append(f"말투 특징: {person.speaking_style}")

        if emotional_patterns:
            dominant_emotions = [e["tone"] for e in emotional_patterns[:2]]
            parts.append(f"대화에서 주로 {', '.join(dominant_emotions)} 감정이 나타납니다.")

        if key_facts:
            top_topics = [f["keyword"] for f in key_facts[:5]]
            parts.append(f"자주 이야기하는 주제: {', '.join(top_topics)}")

        return " ".join(parts) if parts else f"{name}님에 대한 정보가 아직 충분하지 않습니다."


# ============================================================
# Module-level instance for easy import
# ============================================================
memory_engine = MemoryEngine()
