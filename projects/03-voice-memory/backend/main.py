"""
VoiceMemory - FastAPI 메인 앱
AI 음성 보존 서비스
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai-model"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared"))

from fastapi import FastAPI, Depends, Query, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime, timedelta
from collections import Counter
import uvicorn

from database import init_db, get_db
from models import Person, RecordingSession, Conversation, Consent, SessionTag
from schemas import (
    PersonCreate, ChatRequest, ConsentCreate, RecordingSessionCreate,
    RecordingSessionUpdate, TagCreate, SessionNotesUpdate,
)
from consent_service import ConsentService
from recording_service import RecordingService
from persona_chat import PersonaChat
from transcription_service import (
    TranscriptionService, queue_transcription, start_transcription_worker,
)
from memory_engine import MemoryEngine
from voice_clone_service import VoiceCloneService, RESPONSES_AUDIO_DIR
from pydantic import BaseModel as _BaseModel
import json as _json

app = FastAPI(title="VoiceMemory API", version="1.0.0")
persona_chat = PersonaChat()
voice_service = VoiceCloneService()


class SynthesizeRequest(_BaseModel):
    text: str


@app.on_event("startup")
async def startup():
    init_db()
    start_transcription_worker()


@app.get("/", response_class=HTMLResponse)
async def index():
    return TEMPLATE_HTML


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "VoiceMemory"}


# === Person API ===
@app.post("/api/persons")
async def create_person(data: PersonCreate, db: Session = Depends(get_db)):
    person = Person(
        name=data.name,
        relationship_type=data.relationship_type,
        birth_year=data.birth_year,
        personality_traits=data.personality_traits,
        speaking_style=data.speaking_style,
        created_by_user_id=1,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return {"id": person.id, "name": person.name, "message": "인물이 등록되었습니다."}


@app.get("/api/persons")
async def list_persons(db: Session = Depends(get_db)):
    persons = db.query(Person).filter(Person.is_active == True).all()
    return {"persons": [
        {
            "id": p.id, "name": p.name, "relationship_type": p.relationship_type,
            "personality_traits": p.personality_traits, "speaking_style": p.speaking_style,
            "session_count": len(p.sessions), "conversation_count": len(p.conversations),
        }
        for p in persons
    ]}


@app.get("/api/persons/{person_id}")
async def get_person(person_id: int, db: Session = Depends(get_db)):
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        return {"error": "Person not found"}
    consents = ConsentService.check_all_consents(db, person_id)
    return {
        "id": person.id, "name": person.name,
        "relationship_type": person.relationship_type,
        "personality_traits": person.personality_traits,
        "speaking_style": person.speaking_style,
        "consents": consents,
        "session_count": len(person.sessions),
    }


# === Person Analytics API ===
@app.get("/api/persons/{person_id}/analytics")
async def get_person_analytics(person_id: int, db: Session = Depends(get_db)):
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    sessions = db.query(RecordingSession).filter(
        RecordingSession.person_id == person_id
    ).all()

    # --- Basic stats ---
    total_duration = sum(s.duration_seconds or 0 for s in sessions)
    session_count = len(sessions)
    avg_duration = round(total_duration / session_count) if session_count else 0

    # --- Topic coverage ---
    from recording_service import GUIDED_TOPICS
    total_topics = len(GUIDED_TOPICS)
    all_topic_names = {t["topic"] for t in GUIDED_TOPICS}
    covered_topics = {s.topic for s in sessions if s.status == "completed" and s.topic}
    topic_coverage_pct = round(len(covered_topics & all_topic_names) / total_topics * 100) if total_topics else 0
    uncovered_topics = list(all_topic_names - covered_topics)[:5]

    # --- Last recording date & days since ---
    recorded_dates = [s.recorded_at for s in sessions if s.recorded_at]
    last_recording_date = None
    days_since_last = None
    if recorded_dates:
        last_dt = max(recorded_dates)
        last_recording_date = last_dt.isoformat()
        days_since_last = (datetime.utcnow() - last_dt).days

    # --- Emotional tone distribution ---
    tone_counter = Counter()
    for s in sessions:
        if s.emotional_tone and s.emotional_tone.strip():
            tone_counter[s.emotional_tone.strip()] += 1
    tone_distribution = [{"tone": t, "count": c} for t, c in tone_counter.most_common()]

    # --- Transcription completion rate ---
    sessions_with_audio = [s for s in sessions if s.audio_file_path]
    transcribed = [s for s in sessions_with_audio if s.transcription_status == "completed"]
    transcription_rate = round(len(transcribed) / len(sessions_with_audio) * 100) if sessions_with_audio else 0

    # --- Keywords frequency (top 20) ---
    keyword_counter = Counter()
    for s in sessions:
        if s.keywords:
            try:
                kw_list = _json.loads(s.keywords)
                for kw in kw_list:
                    keyword_counter[kw.strip()] += 1
            except (ValueError, TypeError):
                pass
    top_keywords = [{"keyword": k, "count": c} for k, c in keyword_counter.most_common(20)]

    # --- Recording frequency by week (last 8 weeks) ---
    now = datetime.utcnow()
    weekly_counts = []
    for i in range(7, -1, -1):
        week_start = now - timedelta(weeks=i+1)
        week_end = now - timedelta(weeks=i)
        count = sum(
            1 for s in sessions
            if s.recorded_at and week_start <= s.recorded_at < week_end
        )
        label = week_start.strftime("%m/%d")
        weekly_counts.append({"week_label": label, "count": count})

    return {
        "person_id": person_id,
        "person_name": person.name,
        "total_duration_seconds": total_duration,
        "session_count": session_count,
        "avg_duration_seconds": avg_duration,
        "topic_coverage_pct": topic_coverage_pct,
        "total_topics": total_topics,
        "covered_topic_count": len(covered_topics & all_topic_names),
        "last_recording_date": last_recording_date,
        "days_since_last_recording": days_since_last,
        "tone_distribution": tone_distribution,
        "transcription_completion_rate": transcription_rate,
        "top_keywords": top_keywords,
        "weekly_recording_frequency": weekly_counts,
        "suggested_topics": uncovered_topics,
    }


# === Consent API ===
@app.get("/api/consents/required")
async def get_required_consents():
    return {"consents": ConsentService.get_required_consents()}


@app.post("/api/consents")
async def grant_consent(data: ConsentCreate, db: Session = Depends(get_db)):
    if data.is_granted:
        ConsentService.grant_consent(db, data.person_id, data.consent_type, notes=data.notes)
        return {"status": "ok"}
    else:
        result = ConsentService.revoke_consent(db, data.person_id, data.consent_type)
        return {"status": "ok", "revocation": result}


@app.get("/api/consents/{person_id}")
async def check_consents(person_id: int, db: Session = Depends(get_db)):
    return ConsentService.check_all_consents(db, person_id)


# === Recording API ===
@app.get("/api/recording/topics")
async def get_topics():
    return {"topics": RecordingService.get_guided_topics()}


@app.post("/api/recording/session")
async def create_recording_session(data: RecordingSessionCreate, db: Session = Depends(get_db)):
    # 동의 확인
    consents = ConsentService.check_all_consents(db, data.person_id)
    if not consents["all_granted"]:
        return {"error": "모든 동의가 필요합니다.", "missing": consents["missing"]}

    next_topic = RecordingService.get_next_topic(db, data.person_id)
    session = RecordingService.create_session(db, data.person_id, next_topic["topic_index"])
    return {
        "session_id": session.id,
        "topic": session.topic,
        "questions": session.guide_questions,
        "session_number": session.session_number,
    }


@app.put("/api/recording/session/{session_id}")
async def update_recording_session(session_id: int, data: RecordingSessionUpdate, db: Session = Depends(get_db)):
    session = RecordingService.complete_session(
        db, session_id,
        duration_seconds=data.duration_seconds or 0,
        audio_file_path=data.audio_file_path or "",
        transcript=data.transcript or "",
        status=data.status or "completed",
    )
    if not session:
        return {"error": "Session not found"}
    return {
        "id": session.id, "topic": session.topic, "status": session.status,
        "duration_seconds": session.duration_seconds,
        "recorded_at": session.recorded_at.isoformat() if session.recorded_at else None,
    }


@app.get("/api/recording/sessions/{person_id}")
async def get_sessions(person_id: int, db: Session = Depends(get_db)):
    sessions = RecordingService.get_sessions(db, person_id)
    result_sessions = []
    for s in sessions:
        kw = []
        if s.keywords:
            try:
                kw = _json.loads(s.keywords)
            except (ValueError, TypeError):
                kw = []
        result_sessions.append({
            "id": s.id, "topic": s.topic, "status": s.status, "number": s.session_number,
            "duration_seconds": s.duration_seconds, "has_transcript": bool(s.transcript and s.transcript.strip()),
            "has_audio": bool(s.audio_file_path),
            "user_notes": s.user_notes or "",
            "emotional_tone": s.emotional_tone or "",
            "tags": [t.tag_name for t in s.tags],
            "transcription_status": s.transcription_status or "none",
            "transcript_summary": s.transcript_summary or "",
            "keywords": kw,
        })
    return {"sessions": result_sessions}


# === Tag API ===
@app.post("/api/recording/sessions/{session_id}/tags")
async def add_tag(session_id: int, data: TagCreate, db: Session = Depends(get_db)):
    session = db.query(RecordingSession).filter(RecordingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    tag_name = data.tag_name.strip().lower()
    if not tag_name:
        raise HTTPException(status_code=400, detail="Tag name is required")
    # Check if tag already exists on this session
    existing = db.query(SessionTag).filter(
        SessionTag.session_id == session_id,
        SessionTag.tag_name == tag_name,
    ).first()
    if existing:
        return {"status": "already_exists", "tag_name": tag_name}
    tag = SessionTag(session_id=session_id, tag_name=tag_name)
    db.add(tag)
    db.commit()
    return {"status": "ok", "tag_name": tag_name}


@app.delete("/api/recording/sessions/{session_id}/tags/{tag_name}")
async def remove_tag(session_id: int, tag_name: str, db: Session = Depends(get_db)):
    tag = db.query(SessionTag).filter(
        SessionTag.session_id == session_id,
        SessionTag.tag_name == tag_name.strip().lower(),
    ).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.delete(tag)
    db.commit()
    return {"status": "ok"}


@app.get("/api/tags")
async def get_all_tags(db: Session = Depends(get_db)):
    results = db.query(
        SessionTag.tag_name, func.count(SessionTag.id).label("count")
    ).group_by(SessionTag.tag_name).order_by(func.count(SessionTag.id).desc()).all()
    return {"tags": [{"tag_name": r[0], "count": r[1]} for r in results]}


# === Session Notes API ===
@app.put("/api/recording/sessions/{session_id}/notes")
async def update_session_notes(session_id: int, data: SessionNotesUpdate, db: Session = Depends(get_db)):
    session = db.query(RecordingSession).filter(RecordingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if data.user_notes is not None:
        session.user_notes = data.user_notes
    if data.emotional_tone is not None:
        session.emotional_tone = data.emotional_tone
    db.commit()
    db.refresh(session)
    return {
        "status": "ok",
        "user_notes": session.user_notes or "",
        "emotional_tone": session.emotional_tone or "",
    }


# === Search API ===
@app.get("/api/search")
async def search(
    q: str = Query(default="", description="Search keyword"),
    person_id: int = Query(default=0, description="Filter by person ID"),
    tag: str = Query(default="", description="Filter by tag name"),
    db: Session = Depends(get_db),
):
    results = []
    keyword = q.strip()
    tag_filter = tag.strip().lower()

    if not keyword and not tag_filter and not person_id:
        return {"results": []}

    # Start with all sessions
    session_query = db.query(RecordingSession)

    if person_id:
        session_query = session_query.filter(RecordingSession.person_id == person_id)

    # If tag filter is specified, filter sessions that have that tag
    if tag_filter:
        tagged_session_ids = db.query(SessionTag.session_id).filter(
            SessionTag.tag_name == tag_filter
        ).subquery()
        session_query = session_query.filter(RecordingSession.id.in_(tagged_session_ids))

    # If keyword is specified, search across multiple fields
    if keyword:
        like_pattern = f"%{keyword}%"

        # Find session IDs that match in conversations
        conv_session_ids = db.query(RecordingSession.id).join(
            Conversation, Conversation.person_id == RecordingSession.person_id
        ).filter(
            or_(
                Conversation.user_message.ilike(like_pattern),
                Conversation.ai_response.ilike(like_pattern),
            )
        ).distinct().all()
        conv_session_id_set = {r[0] for r in conv_session_ids}

        # Find session IDs that match in tags
        tag_session_ids = db.query(SessionTag.session_id).filter(
            SessionTag.tag_name.ilike(like_pattern)
        ).distinct().all()
        tag_session_id_set = {r[0] for r in tag_session_ids}

        # Combine: sessions matching topic, notes, transcript, or matched via convs/tags
        session_query = session_query.filter(
            or_(
                RecordingSession.topic.ilike(like_pattern),
                RecordingSession.user_notes.ilike(like_pattern),
                RecordingSession.transcript.ilike(like_pattern),
                RecordingSession.transcript_summary.ilike(like_pattern),
                RecordingSession.id.in_(conv_session_id_set | tag_session_id_set),
            )
        )

    sessions = session_query.order_by(RecordingSession.created_at.desc()).limit(50).all()

    for s in sessions:
        # Build context snippets showing where keyword matched
        snippets = []
        if keyword:
            kw_lower = keyword.lower()
            if s.topic and kw_lower in s.topic.lower():
                snippets.append({"field": "topic", "text": s.topic})
            if s.user_notes and kw_lower in s.user_notes.lower():
                # Extract snippet around match
                idx = s.user_notes.lower().find(kw_lower)
                start = max(0, idx - 40)
                end = min(len(s.user_notes), idx + len(keyword) + 40)
                snippet = ("..." if start > 0 else "") + s.user_notes[start:end] + ("..." if end < len(s.user_notes) else "")
                snippets.append({"field": "notes", "text": snippet})
            if s.transcript and kw_lower in s.transcript.lower():
                idx = s.transcript.lower().find(kw_lower)
                start = max(0, idx - 40)
                end = min(len(s.transcript), idx + len(keyword) + 40)
                snippet = ("..." if start > 0 else "") + s.transcript[start:end] + ("..." if end < len(s.transcript) else "")
                snippets.append({"field": "transcript", "text": snippet})
            if s.transcript_summary and kw_lower in s.transcript_summary.lower():
                snippets.append({"field": "summary", "text": s.transcript_summary})
            # Check tags
            for t in s.tags:
                if kw_lower in t.tag_name.lower():
                    snippets.append({"field": "tag", "text": t.tag_name})
            # Check conversations for this person
            if s.person_id:
                convs = db.query(Conversation).filter(
                    Conversation.person_id == s.person_id,
                    or_(
                        Conversation.user_message.ilike(f"%{keyword}%"),
                        Conversation.ai_response.ilike(f"%{keyword}%"),
                    )
                ).limit(3).all()
                for c in convs:
                    for field_name, field_val in [("user_message", c.user_message), ("ai_response", c.ai_response)]:
                        if field_val and kw_lower in field_val.lower():
                            idx = field_val.lower().find(kw_lower)
                            start = max(0, idx - 40)
                            end = min(len(field_val), idx + len(keyword) + 40)
                            snippet = ("..." if start > 0 else "") + field_val[start:end] + ("..." if end < len(field_val) else "")
                            snippets.append({"field": field_name, "text": snippet})

        # Get person name
        person = db.query(Person).filter(Person.id == s.person_id).first()
        person_name = person.name if person else "Unknown"

        results.append({
            "session_id": s.id,
            "person_id": s.person_id,
            "person_name": person_name,
            "topic": s.topic,
            "session_number": s.session_number,
            "status": s.status,
            "user_notes": s.user_notes or "",
            "emotional_tone": s.emotional_tone or "",
            "tags": [t.tag_name for t in s.tags],
            "snippets": snippets,
        })

    return {"results": results, "count": len(results)}


# === Audio Upload / Playback API ===
@app.post("/api/recordings/upload")
async def upload_recording(
    session_id: int,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload an audio recording for a session.
    Accepts WAV, WebM, OGG, MP3, M4A files (max 100 MB).
    """
    # Validate session exists
    session = db.query(RecordingSession).filter(RecordingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Read file content
    file_bytes = await audio.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(file_bytes) > 100 * 1024 * 1024:  # 100 MB limit
        raise HTTPException(status_code=400, detail="File too large (max 100 MB)")

    # Save to disk
    result = RecordingService.save_audio_file(
        session_id=session_id,
        person_id=session.person_id,
        file_bytes=file_bytes,
        original_filename=audio.filename or "recording.webm",
    )

    # Update session record
    session.audio_file_path = result["file_path"]
    session.status = "completed"
    if result["duration_seconds"] > 0:
        session.duration_seconds = int(result["duration_seconds"])
    from datetime import datetime
    session.recorded_at = datetime.utcnow()
    db.commit()
    db.refresh(session)

    return {
        "session_id": session.id,
        "filename": result["filename"],
        "size_bytes": result["size_bytes"],
        "format": result["format"],
        "duration_seconds": result["duration_seconds"],
        "status": session.status,
    }


@app.get("/api/recordings/{session_id}/audio")
async def get_recording_audio(session_id: int, db: Session = Depends(get_db)):
    """Stream audio file for playback."""
    file_path = RecordingService.get_audio_file_path(db, session_id)
    if not file_path:
        raise HTTPException(status_code=404, detail="Audio not found for this session")

    content_type = RecordingService.get_audio_content_type(file_path)
    return FileResponse(
        path=file_path,
        media_type=content_type,
        filename=os.path.basename(file_path),
    )


# === Transcription API ===
@app.post("/api/recording/sessions/{session_id}/transcribe")
async def transcribe_session(session_id: int, db: Session = Depends(get_db)):
    """Queue transcription for a recording session."""
    session = db.query(RecordingSession).filter(RecordingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.audio_file_path or not os.path.exists(session.audio_file_path):
        raise HTTPException(status_code=400, detail="No audio file for this session")
    if session.transcription_status == "processing":
        return {"status": "already_processing", "session_id": session_id}

    result = queue_transcription(session_id, session.audio_file_path)
    return result


@app.get("/api/recording/sessions/{session_id}/transcript")
async def get_transcript(session_id: int, db: Session = Depends(get_db)):
    """Get transcript, summary, and keywords for a session."""
    session = db.query(RecordingSession).filter(RecordingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    keywords = []
    if session.keywords:
        try:
            keywords = _json.loads(session.keywords)
        except (ValueError, TypeError):
            keywords = []

    return {
        "session_id": session_id,
        "transcription_status": session.transcription_status or "none",
        "transcript": session.transcript or "",
        "transcript_summary": session.transcript_summary or "",
        "keywords": keywords,
    }


@app.get("/api/search/transcript")
async def search_transcripts(
    q: str = Query(default="", description="Keyword to search in transcripts"),
    db: Session = Depends(get_db),
):
    """Search across all transcripts."""
    keyword = q.strip()
    if not keyword:
        return {"results": [], "count": 0}

    like_pattern = f"%{keyword}%"
    sessions = db.query(RecordingSession).filter(
        or_(
            RecordingSession.transcript.ilike(like_pattern),
            RecordingSession.transcript_summary.ilike(like_pattern),
            RecordingSession.keywords.ilike(like_pattern),
        )
    ).order_by(RecordingSession.created_at.desc()).limit(50).all()

    results = []
    for s in sessions:
        person = db.query(Person).filter(Person.id == s.person_id).first()
        person_name = person.name if person else "Unknown"

        # Build snippet from transcript
        snippet = ""
        if s.transcript and keyword.lower() in s.transcript.lower():
            idx = s.transcript.lower().find(keyword.lower())
            start = max(0, idx - 60)
            end = min(len(s.transcript), idx + len(keyword) + 60)
            snippet = ("..." if start > 0 else "") + s.transcript[start:end] + ("..." if end < len(s.transcript) else "")

        keywords = []
        if s.keywords:
            try:
                keywords = _json.loads(s.keywords)
            except (ValueError, TypeError):
                keywords = []

        results.append({
            "session_id": s.id,
            "person_id": s.person_id,
            "person_name": person_name,
            "topic": s.topic,
            "session_number": s.session_number,
            "transcript_snippet": snippet,
            "transcript_summary": s.transcript_summary or "",
            "keywords": keywords,
            "transcription_status": s.transcription_status or "none",
        })

    return {"results": results, "count": len(results)}


# === Chat API ===
@app.post("/api/chat")
async def chat(data: ChatRequest, db: Session = Depends(get_db)):
    person = db.query(Person).filter(Person.id == data.person_id).first()
    if not person:
        return {"error": "Person not found"}

    person_dict = {
        "id": person.id, "name": person.name,
        "personality_traits": person.personality_traits,
        "speaking_style": person.speaking_style,
        "relationship_type": person.relationship_type,
    }

    # Generate memory context for the chat
    memory_ctx = {}
    source_sessions = []
    try:
        memory_ctx = MemoryEngine.generate_context(data.person_id, data.message, db)
        if memory_ctx.get("memory_context"):
            person_dict["memory_context"] = memory_ctx["memory_context"]
        source_sessions = memory_ctx.get("source_sessions", [])
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Memory context generation failed: {e}")

    result = persona_chat.chat(person_dict, data.message)

    # 대화 기록 저장
    conv = Conversation(
        person_id=data.person_id,
        user_id=data.user_id,
        user_message=data.message,
        ai_response=result["response"],
        emotion=result["emotion"],
    )
    db.add(conv)
    db.commit()

    # Build enhanced memory attribution with keyword highlighting info
    relevant_memories = memory_ctx.get("relevant_memories", [])
    memory_attribution = []
    for mem in relevant_memories:
        if mem.get("score", 0) >= 0.05:
            memory_attribution.append({
                "session_id": mem.get("session_id"),
                "session_number": mem.get("session_number", 0),
                "topic": mem.get("topic", ""),
                "score": mem.get("score", 0),
                "keywords": mem.get("keywords", []),
                "emotional_tone": mem.get("emotional_tone", ""),
                "text_preview": (mem.get("text", "")[:120] + "...") if len(mem.get("text", "")) > 120 else mem.get("text", ""),
            })

    return {
        "person_name": person.name,
        "user_message": data.message,
        "ai_response": result["response"],
        "emotion": result["emotion"],
        "memory_sources": source_sessions,
        "memory_attribution": memory_attribution,
    }


# === Memory Search & Profile API ===
@app.get("/api/persons/{person_id}/memories")
async def search_memories(
    person_id: int,
    q: str = Query(default="", description="Search query for memory search"),
    top_k: int = Query(default=5, description="Number of results"),
    db: Session = Depends(get_db),
):
    """Semantic memory search across person's recordings."""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    query = q.strip()
    if not query:
        return {"results": [], "count": 0, "person_name": person.name}

    try:
        results = MemoryEngine.search_memories(person_id, query, db, top_k=top_k)
        return {
            "results": results,
            "count": len(results),
            "person_name": person.name,
            "query": query,
        }
    except Exception as e:
        return {"results": [], "count": 0, "error": str(e)}


@app.get("/api/persons/{person_id}/profile")
async def get_person_profile(person_id: int, db: Session = Depends(get_db)):
    """Get aggregated person knowledge profile."""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    try:
        profile = MemoryEngine.get_person_profile(person_id, db)
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/history/{person_id}")
async def chat_history(person_id: int, limit: int = 20, db: Session = Depends(get_db)):
    convs = db.query(Conversation).filter(
        Conversation.person_id == person_id
    ).order_by(Conversation.created_at.desc()).limit(limit).all()

    return {"conversations": [
        {
            "user_message": c.user_message,
            "ai_response": c.ai_response,
            "emotion": c.emotion,
            "created_at": c.created_at.isoformat(),
        }
        for c in reversed(convs)
    ]}


# === Voice Synthesis API ===
@app.post("/api/chat/{person_id}/synthesize")
async def synthesize_speech(person_id: int, data: SynthesizeRequest):
    """
    AI 응답 텍스트를 음성으로 합성

    Args:
        person_id: 인물 ID
        data.text: 합성할 텍스트

    Returns:
        audio_url: 합성된 오디오 파일 URL
    """
    text = data.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="텍스트가 비어있습니다")

    # 텍스트 길이 제한 (너무 긴 텍스트는 TTS에 부적합)
    if len(text) > 2000:
        text = text[:2000]

    try:
        file_path = await voice_service.synthesize_response(text, person_id)
        if file_path and os.path.exists(file_path):
            filename = os.path.basename(file_path)
            return {
                "audio_url": f"/api/audio/responses/{filename}",
                "filename": filename,
                "status": "ok",
            }
        else:
            raise HTTPException(
                status_code=503,
                detail="음성 합성에 실패했습니다. edge-tts가 설치되어 있는지 확인하세요 (pip install edge-tts)."
            )
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Synthesize error: {e}")
        raise HTTPException(status_code=500, detail=f"음성 합성 오류: {str(e)}")


@app.get("/api/audio/responses/{filename}")
async def serve_synthesized_audio(filename: str):
    """합성된 음성 오디오 파일 제공"""
    # 보안: 파일 이름에 path traversal 방지
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(RESPONSES_AUDIO_DIR, safe_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="오디오 파일을 찾을 수 없습니다")

    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=safe_filename,
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
        },
    )


TEMPLATE_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VoiceMemory - AI 음성 보존</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, 'Malgun Gothic', sans-serif; background: #f8f6f4; color: #333; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #8e6b47, #a0845c); color: white; padding: 20px; text-align: center; }
        .header h1 { font-size: 1.4rem; font-weight: 700; }
        .header p { font-size: 0.85rem; opacity: 0.9; margin-top: 4px; }
        .container { max-width: 600px; margin: 0 auto; padding: 16px; }
        .tabs { display: flex; gap: 4px; margin-bottom: 16px; background: white; border-radius: 12px; padding: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .tab { flex: 1; padding: 10px; text-align: center; border-radius: 10px; cursor: pointer; font-weight: 600; font-size: 0.85rem; color: #888; transition: all 0.2s; }
        .tab.active { background: #8e6b47; color: white; }
        .panel { display: none; }
        .panel.active { display: block; }
        .card { background: white; border-radius: 14px; padding: 16px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .card h3 { font-size: 1rem; margin-bottom: 10px; color: #5d4037; }
        .input-group { margin-bottom: 10px; }
        .input-group label { display: block; font-size: 0.8rem; color: #888; margin-bottom: 4px; }
        .input-group input, .input-group select, .input-group textarea { width: 100%; padding: 10px; border: 1px solid #e0d5c8; border-radius: 10px; font-size: 0.9rem; background: #faf8f5; }
        .btn { padding: 10px 24px; border: none; border-radius: 10px; font-weight: 600; cursor: pointer; font-size: 0.9rem; }
        .btn-primary { background: #8e6b47; color: white; }
        .btn-primary:hover { background: #7a5c3c; }
        .btn-danger { background: #c0392b; color: white; }
        .btn-danger:hover { background: #a93226; }
        .btn-sm { padding: 6px 16px; font-size: 0.8rem; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        /* Chat */
        .chat-area { max-height: 400px; overflow-y: auto; padding: 10px 0; }
        .chat-msg { margin-bottom: 10px; display: flex; }
        .chat-msg.user { justify-content: flex-end; }
        .chat-msg .bubble { max-width: 80%; padding: 10px 14px; border-radius: 14px; font-size: 0.9rem; line-height: 1.5; }
        .chat-msg.user .bubble { background: #8e6b47; color: white; border-bottom-right-radius: 4px; }
        .chat-msg.ai .bubble { background: white; border: 1px solid #e0d5c8; border-bottom-left-radius: 4px; }
        .chat-input-area { display: flex; gap: 8px; padding-top: 10px; border-top: 1px solid #e0d5c8; }
        .chat-input { flex: 1; padding: 10px 14px; border: 1px solid #e0d5c8; border-radius: 20px; font-size: 0.9rem; }
        .send-btn { background: #8e6b47; color: white; border: none; border-radius: 50%; width: 40px; height: 40px; cursor: pointer; font-size: 1.1rem; }
        .person-card { display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid #e0d5c8; border-radius: 12px; margin: 8px 0; cursor: pointer; transition: background 0.2s; }
        .person-card:hover { background: #faf5f0; }
        .person-avatar { width: 48px; height: 48px; border-radius: 50%; background: #d7c4a8; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; color: #5d4037; }
        .person-info { flex: 1; }
        .person-info .name { font-weight: 700; }
        .person-info .sub { font-size: 0.8rem; color: #999; }
        .consent-item { display: flex; align-items: center; gap: 10px; padding: 10px; border: 1px solid #e0d5c8; border-radius: 10px; margin: 6px 0; }
        .consent-check { width: 20px; height: 20px; accent-color: #8e6b47; }
        .topic-card { padding: 10px; background: #faf5f0; border-radius: 10px; margin: 6px 0; }
        .topic-card .title { font-weight: 600; color: #5d4037; }
        .topic-card .questions { font-size: 0.8rem; color: #888; margin-top: 4px; }
        .empty-state { text-align: center; padding: 30px; color: #aaa; }

        /* ====== Audio Recorder Styles ====== */
        .recorder-widget { margin-top: 12px; }
        .recorder-controls { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
        .rec-btn {
            width: 52px; height: 52px; border-radius: 50%; border: 3px solid #e0d5c8;
            background: white; cursor: pointer; display: flex; align-items: center;
            justify-content: center; transition: all 0.2s; position: relative;
        }
        .rec-btn .rec-dot {
            width: 20px; height: 20px; border-radius: 50%; background: #c0392b;
            transition: all 0.2s;
        }
        .rec-btn.recording { border-color: #c0392b; animation: pulse-border 1.5s infinite; }
        .rec-btn.recording .rec-dot {
            width: 16px; height: 16px; border-radius: 3px; background: #c0392b;
        }
        @keyframes pulse-border {
            0%, 100% { box-shadow: 0 0 0 0 rgba(192,57,43,0.4); }
            50% { box-shadow: 0 0 0 8px rgba(192,57,43,0); }
        }
        .rec-timer {
            font-size: 1.4rem; font-weight: 700; color: #5d4037;
            font-variant-numeric: tabular-nums; min-width: 70px;
        }
        .rec-timer.recording { color: #c0392b; }
        .rec-status {
            font-size: 0.8rem; color: #888; flex: 1; text-align: right;
        }
        .rec-status.recording { color: #c0392b; font-weight: 600; }

        /* Waveform visualization */
        .waveform-container {
            background: #faf5f0; border-radius: 10px; padding: 8px;
            margin-bottom: 10px; height: 64px; display: flex;
            align-items: center; justify-content: center; overflow: hidden;
        }
        .waveform-canvas { width: 100%; height: 48px; display: block; }
        .waveform-placeholder { color: #ccc; font-size: 0.8rem; }

        /* Playback area */
        .playback-area { margin-top: 10px; }
        .playback-area audio { width: 100%; border-radius: 8px; }
        .upload-status {
            font-size: 0.8rem; padding: 6px 10px; border-radius: 8px;
            margin-top: 6px; text-align: center;
        }
        .upload-status.success { background: #e8f5e9; color: #2e7d32; }
        .upload-status.error { background: #fce4ec; color: #c62828; }
        .upload-status.uploading { background: #fff3e0; color: #e65100; }

        /* Session list with audio */
        .session-item {
            display: flex; flex-direction: column; gap: 8px; padding: 12px;
            border: 1px solid #e0d5c8; border-radius: 10px; margin: 6px 0;
        }
        .session-header { display: flex; align-items: center; gap: 10px; }
        .session-header .session-info { flex: 1; }
        .session-header .session-info .topic { font-weight: 600; color: #5d4037; font-size: 0.9rem; }
        .session-header .session-info .meta { font-size: 0.75rem; color: #999; }
        .play-btn {
            width: 36px; height: 36px; border-radius: 50%; border: none;
            background: #8e6b47; color: white; font-size: 1rem; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
        }
        .play-btn:hover { background: #7a5c3c; }

        /* Tags */
        .tag-area { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
        .tag-chip {
            display: inline-flex; align-items: center; gap: 3px;
            padding: 2px 10px; border-radius: 12px; font-size: 0.72rem; font-weight: 600;
            cursor: default; color: white;
        }
        .tag-chip .tag-remove {
            cursor: pointer; margin-left: 2px; font-size: 0.8rem; opacity: 0.7;
        }
        .tag-chip .tag-remove:hover { opacity: 1; }
        .add-tag-btn {
            padding: 2px 8px; border-radius: 12px; border: 1px dashed #bbb;
            background: none; font-size: 0.72rem; color: #888; cursor: pointer;
        }
        .add-tag-btn:hover { border-color: #8e6b47; color: #8e6b47; }
        .tag-input-wrap {
            display: inline-flex; align-items: center; gap: 4px;
        }
        .tag-input-wrap input {
            width: 90px; padding: 2px 8px; border: 1px solid #d0c4b4; border-radius: 10px;
            font-size: 0.75rem; background: #faf8f5;
        }
        .tag-input-wrap button {
            padding: 2px 8px; border: none; border-radius: 10px; font-size: 0.7rem;
            background: #8e6b47; color: white; cursor: pointer;
        }

        /* Emotional tone selector */
        .tone-select {
            padding: 3px 8px; border: 1px solid #e0d5c8; border-radius: 8px;
            font-size: 0.75rem; background: #faf8f5; color: #5d4037;
        }

        /* Session notes */
        .notes-toggle {
            font-size: 0.75rem; color: #8e6b47; cursor: pointer; border: none;
            background: none; font-weight: 600; padding: 0;
        }
        .notes-toggle:hover { text-decoration: underline; }
        .notes-section { margin-top: 6px; }
        .notes-section textarea {
            width: 100%; min-height: 60px; padding: 8px; border: 1px solid #e0d5c8;
            border-radius: 8px; font-size: 0.8rem; background: #faf8f5; resize: vertical;
            font-family: inherit;
        }
        .notes-section .notes-actions {
            display: flex; align-items: center; gap: 8px; margin-top: 6px;
        }

        /* Search */
        .search-bar {
            display: flex; gap: 8px; margin-bottom: 12px;
        }
        .search-bar input {
            flex: 1; padding: 10px 14px; border: 1px solid #e0d5c8; border-radius: 20px;
            font-size: 0.9rem; background: white;
        }
        .search-bar button {
            padding: 8px 16px; border: none; border-radius: 20px;
            background: #8e6b47; color: white; font-weight: 600; cursor: pointer;
            font-size: 0.85rem;
        }
        .search-bar button:hover { background: #7a5c3c; }
        .search-results { margin-top: 8px; }
        .search-result-item {
            background: white; border-radius: 10px; padding: 12px; margin-bottom: 8px;
            border: 1px solid #e0d5c8;
        }
        .search-result-item .sr-header { font-weight: 600; color: #5d4037; font-size: 0.9rem; }
        .search-result-item .sr-person { font-size: 0.75rem; color: #999; }
        .search-result-item .sr-snippet {
            font-size: 0.8rem; color: #666; margin-top: 4px; padding: 4px 8px;
            background: #faf5f0; border-radius: 6px; border-left: 3px solid #d7c4a8;
        }
        .search-result-item .sr-snippet mark { background: #ffe082; padding: 0 2px; border-radius: 2px; }
        .search-result-item .sr-tags { margin-top: 4px; }
        .search-filter-row {
            display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; align-items: center;
        }
        .search-filter-row select {
            padding: 6px 10px; border: 1px solid #e0d5c8; border-radius: 10px;
            font-size: 0.8rem; background: white;
        }
        .search-filter-row .filter-label { font-size: 0.8rem; color: #888; }

        /* Transcription UI */
        .transcribe-btn {
            padding: 4px 12px; border: none; border-radius: 8px; font-size: 0.72rem;
            font-weight: 600; cursor: pointer; background: #2980b9; color: white;
        }
        .transcribe-btn:hover { background: #2472a4; }
        .transcribe-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .transcription-status {
            font-size: 0.7rem; font-weight: 600; padding: 2px 8px;
            border-radius: 8px; display: inline-block;
        }
        .transcription-status.pending { background: #fff3e0; color: #e65100; }
        .transcription-status.processing { background: #e3f2fd; color: #1565c0; }
        .transcription-status.completed { background: #e8f5e9; color: #2e7d32; }
        .transcription-status.failed { background: #fce4ec; color: #c62828; }
        .transcript-section {
            margin-top: 8px; padding: 10px; background: #faf8f5; border-radius: 8px;
            border: 1px solid #e0d5c8; font-size: 0.8rem; color: #444;
            max-height: 200px; overflow-y: auto; line-height: 1.5;
        }
        .transcript-summary {
            margin-top: 6px; padding: 8px 10px; background: #f0f7ff;
            border-radius: 8px; font-size: 0.8rem; color: #333;
            border-left: 3px solid #2980b9;
        }
        .keyword-badges { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px; }
        .keyword-badge {
            padding: 2px 8px; border-radius: 10px; font-size: 0.68rem;
            background: #e8eaf6; color: #3949ab; font-weight: 500;
        }
        .transcript-toggle {
            font-size: 0.75rem; color: #2980b9; cursor: pointer; border: none;
            background: none; font-weight: 600; padding: 0;
        }
        .transcript-toggle:hover { text-decoration: underline; }

        /* Transcript search bar */
        .transcript-search-bar {
            display: flex; gap: 8px; margin-bottom: 8px; margin-top: 8px;
        }
        .transcript-search-bar input {
            flex: 1; padding: 8px 12px; border: 1px solid #c8d6e5; border-radius: 16px;
            font-size: 0.85rem; background: white;
        }
        .transcript-search-bar button {
            padding: 6px 14px; border: none; border-radius: 16px;
            background: #2980b9; color: white; font-weight: 600; cursor: pointer;
            font-size: 0.8rem;
        }
        .transcript-search-bar button:hover { background: #2472a4; }
        .transcript-search-results { margin-top: 6px; }
        .transcript-search-result {
            background: white; border-radius: 8px; padding: 10px; margin-bottom: 6px;
            border: 1px solid #c8d6e5;
        }
        .transcript-search-result .tsr-header { font-weight: 600; color: #2c3e50; font-size: 0.85rem; }
        .transcript-search-result .tsr-person { font-size: 0.72rem; color: #999; }
        .transcript-search-result .tsr-snippet {
            font-size: 0.8rem; color: #555; margin-top: 4px; padding: 4px 8px;
            background: #f0f7ff; border-radius: 6px; border-left: 3px solid #2980b9;
        }
        .transcript-search-result .tsr-snippet mark { background: #ffe082; padding: 0 2px; border-radius: 2px; }
        .transcript-search-result .tsr-keywords { margin-top: 4px; }

        /* ====== Analytics Panel ====== */
        .analytics-overlay {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.45); z-index: 1000;
            display: flex; align-items: center; justify-content: center;
            padding: 16px;
        }
        .analytics-panel {
            background: #f8f6f4; border-radius: 18px; width: 100%; max-width: 560px;
            max-height: 88vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,0.2);
            padding: 0;
        }
        .analytics-header {
            background: linear-gradient(135deg, #5d4037, #8e6b47);
            color: white; padding: 18px 20px; border-radius: 18px 18px 0 0;
            display: flex; align-items: center; justify-content: space-between;
            position: sticky; top: 0; z-index: 10;
        }
        .analytics-header h3 { font-size: 1.05rem; font-weight: 700; margin: 0; }
        .analytics-close {
            background: rgba(255,255,255,0.2); border: none; color: white;
            width: 32px; height: 32px; border-radius: 50%; font-size: 1.1rem;
            cursor: pointer; display: flex; align-items: center; justify-content: center;
        }
        .analytics-close:hover { background: rgba(255,255,255,0.35); }
        .analytics-body { padding: 16px 20px 20px; }

        /* Stats cards row */
        .stats-row {
            display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
            margin-bottom: 16px;
        }
        .stat-card {
            background: white; border-radius: 12px; padding: 14px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06); text-align: center;
        }
        .stat-card .stat-value {
            font-size: 1.5rem; font-weight: 800; color: #5d4037;
            line-height: 1.2;
        }
        .stat-card .stat-label {
            font-size: 0.72rem; color: #999; margin-top: 2px;
            text-transform: uppercase; letter-spacing: 0.5px;
        }
        .stat-card .stat-sub {
            font-size: 0.7rem; color: #bbb; margin-top: 2px;
        }

        /* Analytics section card */
        .analytics-section {
            background: white; border-radius: 12px; padding: 14px;
            margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }
        .analytics-section h4 {
            font-size: 0.85rem; font-weight: 700; color: #5d4037;
            margin: 0 0 10px 0;
        }

        /* Tone badges */
        .tone-badge-list { display: flex; flex-wrap: wrap; gap: 6px; }
        .tone-badge {
            display: inline-flex; align-items: center; gap: 5px;
            padding: 5px 12px; border-radius: 20px; font-size: 0.78rem;
            font-weight: 600; color: white;
        }
        .tone-badge .tone-count {
            background: rgba(255,255,255,0.3); border-radius: 50%;
            width: 20px; height: 20px; display: inline-flex;
            align-items: center; justify-content: center;
            font-size: 0.7rem; font-weight: 700;
        }
        .tone-badge-happy { background: #f39c12; }
        .tone-badge-sad { background: #3498db; }
        .tone-badge-grateful { background: #27ae60; }
        .tone-badge-nostalgic { background: #8e44ad; }
        .tone-badge-calm { background: #16a085; }
        .tone-badge-default { background: #7f8c8d; }

        /* Keyword tags */
        .kw-tag-cloud { display: flex; flex-wrap: wrap; gap: 5px; }
        .kw-tag {
            display: inline-block; padding: 3px 10px; border-radius: 12px;
            font-size: 0.73rem; font-weight: 600; cursor: default;
            transition: transform 0.15s;
        }
        .kw-tag:hover { transform: scale(1.05); }
        .kw-tag-1 { background: #e8eaf6; color: #3949ab; }
        .kw-tag-2 { background: #fff3e0; color: #e65100; }
        .kw-tag-3 { background: #e8f5e9; color: #2e7d32; }
        .kw-tag-4 { background: #fce4ec; color: #c62828; }
        .kw-tag-5 { background: #f3e5f5; color: #7b1fa2; }
        .kw-tag-6 { background: #e0f7fa; color: #00838f; }

        /* Frequency bar chart */
        .freq-chart { display: flex; align-items: flex-end; gap: 6px; height: 100px; padding-top: 8px; }
        .freq-bar-col {
            flex: 1; display: flex; flex-direction: column;
            align-items: center; justify-content: flex-end; height: 100%;
        }
        .freq-bar {
            width: 100%; border-radius: 5px 5px 0 0;
            background: linear-gradient(180deg, #8e6b47, #a0845c);
            min-height: 2px; transition: height 0.4s ease;
        }
        .freq-bar-label {
            font-size: 0.6rem; color: #999; margin-top: 4px;
            white-space: nowrap; text-align: center;
        }
        .freq-bar-count {
            font-size: 0.65rem; color: #5d4037; font-weight: 700;
            margin-bottom: 2px; min-height: 14px;
        }

        /* Recommendation */
        .recommendation-box {
            background: #faf5f0; border-radius: 10px; padding: 12px;
            border-left: 4px solid #d7c4a8; font-size: 0.82rem;
            color: #5d4037; line-height: 1.5;
        }
        .recommendation-box strong { color: #8e6b47; }

        /* Analytics button on person card */
        .btn-analytics {
            padding: 5px 12px; border: 1px solid #d7c4a8; border-radius: 8px;
            background: #faf5f0; color: #8e6b47; font-size: 0.75rem;
            font-weight: 600; cursor: pointer; white-space: nowrap;
        }
        .btn-analytics:hover { background: #f0e6d6; border-color: #8e6b47; }

        /* Progress bar */
        .progress-bar-bg {
            background: #e0d5c8; border-radius: 6px; height: 8px;
            overflow: hidden; margin-top: 6px;
        }
        .progress-bar-fill {
            height: 100%; border-radius: 6px;
            background: linear-gradient(90deg, #8e6b47, #d7c4a8);
            transition: width 0.5s ease;
        }

        /* ====== Memory Search Styles ====== */
        .memory-search-card {
            background: linear-gradient(135deg, #f0f7ff, #e8f0fe);
            border: 1px solid #c8d6e5; border-radius: 14px;
            padding: 16px; margin-bottom: 12px;
        }
        .memory-search-card h3 {
            font-size: 0.95rem; color: #2c3e50; margin-bottom: 10px;
            display: flex; align-items: center; gap: 6px;
        }
        .memory-search-bar {
            display: flex; gap: 8px;
        }
        .memory-search-bar input {
            flex: 1; padding: 10px 14px; border: 1px solid #c8d6e5; border-radius: 20px;
            font-size: 0.9rem; background: white;
        }
        .memory-search-bar button {
            padding: 8px 18px; border: none; border-radius: 20px;
            background: #2980b9; color: white; font-weight: 600; cursor: pointer;
            font-size: 0.85rem;
        }
        .memory-search-bar button:hover { background: #2472a4; }
        .memory-results { margin-top: 10px; }
        .memory-result-item {
            background: white; border-radius: 10px; padding: 12px; margin-bottom: 8px;
            border: 1px solid #d5e1ed; position: relative;
        }
        .memory-result-item .mr-score {
            position: absolute; top: 8px; right: 10px;
            font-size: 0.65rem; font-weight: 700; padding: 2px 8px;
            border-radius: 8px; background: #e3f2fd; color: #1565c0;
        }
        .memory-result-item .mr-header {
            font-weight: 600; color: #2c3e50; font-size: 0.85rem;
        }
        .memory-result-item .mr-meta {
            font-size: 0.72rem; color: #999; margin-top: 2px;
        }
        .memory-result-item .mr-text {
            font-size: 0.82rem; color: #444; margin-top: 6px; line-height: 1.5;
            padding: 8px 10px; background: #f8fafc; border-radius: 8px;
            border-left: 3px solid #2980b9;
        }
        .memory-result-item .mr-keywords {
            margin-top: 4px; display: flex; flex-wrap: wrap; gap: 3px;
        }

        /* ====== Profile Card Styles ====== */
        .profile-overlay {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.45); z-index: 1000;
            display: flex; align-items: center; justify-content: center;
            padding: 16px;
        }
        .profile-panel {
            background: #f8f6f4; border-radius: 18px; width: 100%; max-width: 560px;
            max-height: 88vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        }
        .profile-header {
            background: linear-gradient(135deg, #2c3e50, #3498db);
            color: white; padding: 18px 20px; border-radius: 18px 18px 0 0;
            display: flex; align-items: center; justify-content: space-between;
            position: sticky; top: 0; z-index: 10;
        }
        .profile-header h3 { font-size: 1.05rem; font-weight: 700; margin: 0; }
        .profile-close {
            background: rgba(255,255,255,0.2); border: none; color: white;
            width: 32px; height: 32px; border-radius: 50%; font-size: 1.1rem;
            cursor: pointer; display: flex; align-items: center; justify-content: center;
        }
        .profile-close:hover { background: rgba(255,255,255,0.35); }
        .profile-body { padding: 16px 20px 20px; }
        .profile-section {
            background: white; border-radius: 12px; padding: 14px;
            margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }
        .profile-section h4 {
            font-size: 0.85rem; font-weight: 700; color: #2c3e50;
            margin: 0 0 8px 0;
        }
        .profile-personality {
            font-size: 0.85rem; color: #444; line-height: 1.6;
            padding: 10px; background: #f0f7ff; border-radius: 8px;
            border-left: 3px solid #3498db;
        }
        .profile-topics-list {
            display: flex; flex-wrap: wrap; gap: 5px;
        }
        .profile-topic-chip {
            padding: 3px 10px; border-radius: 12px; font-size: 0.75rem;
            font-weight: 600; background: #e8f5e9; color: #2e7d32;
        }
        .profile-summary-item {
            padding: 8px 10px; margin-bottom: 6px; background: #faf8f5;
            border-radius: 8px; font-size: 0.8rem; color: #555;
            border-left: 3px solid #d7c4a8;
        }
        .profile-summary-item .psi-topic {
            font-weight: 600; color: #5d4037; font-size: 0.78rem;
        }

        /* ====== Chat Suggestions ====== */
        .chat-suggestions {
            padding: 8px 0; margin-bottom: 8px;
        }
        .chat-suggestions-label {
            font-size: 0.75rem; color: #999; margin-bottom: 6px;
        }
        .chat-suggestion-chips {
            display: flex; flex-wrap: wrap; gap: 6px;
        }
        .chat-suggestion-chip {
            padding: 6px 12px; border: 1px solid #d7c4a8; border-radius: 16px;
            font-size: 0.78rem; color: #5d4037; background: #faf5f0;
            cursor: pointer; transition: all 0.2s;
        }
        .chat-suggestion-chip:hover {
            background: #8e6b47; color: white; border-color: #8e6b47;
        }

        /* ====== Memory Source Tag ====== */
        .memory-source-tag {
            display: inline-flex; align-items: center; gap: 3px;
            font-size: 0.62rem; color: #2980b9; background: #e3f2fd;
            padding: 1px 7px; border-radius: 8px; margin-top: 4px;
            font-weight: 600;
        }

        /* ====== Profile Button on Person Card ====== */
        .btn-profile {
            padding: 5px 12px; border: 1px solid #c8d6e5; border-radius: 8px;
            background: #f0f7ff; color: #2980b9; font-size: 0.75rem;
            font-weight: 600; cursor: pointer; white-space: nowrap;
        }
        .btn-profile:hover { background: #dbeafe; border-color: #2980b9; }

        /* ====== Voice Playback Button ====== */
        .voice-play-btn {
            display: inline-flex; align-items: center; gap: 4px;
            padding: 3px 10px; border: 1px solid #d7c4a8; border-radius: 14px;
            background: #faf5f0; color: #8e6b47; font-size: 0.72rem;
            font-weight: 600; cursor: pointer; margin-top: 6px;
            transition: all 0.2s;
        }
        .voice-play-btn:hover { background: #8e6b47; color: white; border-color: #8e6b47; }
        .voice-play-btn.loading {
            opacity: 0.7; cursor: wait;
        }
        .voice-play-btn.playing {
            background: #8e6b47; color: white; border-color: #8e6b47;
        }
        .voice-play-btn .spinner {
            display: inline-block; width: 10px; height: 10px;
            border: 2px solid currentColor; border-top-color: transparent;
            border-radius: 50%; animation: spin-anim 0.6s linear infinite;
        }
        @keyframes spin-anim {
            to { transform: rotate(360deg); }
        }

        /* Volume Control */
        .voice-volume-wrap {
            display: flex; align-items: center; gap: 6px;
            margin-top: 6px; padding: 4px 8px;
            background: #faf5f0; border-radius: 10px;
        }
        .voice-volume-wrap label {
            font-size: 0.7rem; color: #888;
        }
        .voice-volume-slider {
            width: 80px; height: 4px; accent-color: #8e6b47;
            cursor: pointer;
        }
        .voice-volume-val {
            font-size: 0.65rem; color: #aaa; min-width: 28px;
        }

        /* ====== Memory Attribution ====== */
        .memory-attr-toggle {
            display: inline-flex; align-items: center; gap: 3px;
            font-size: 0.7rem; color: #2980b9; cursor: pointer;
            border: none; background: none; font-weight: 600;
            padding: 2px 0; margin-top: 4px;
        }
        .memory-attr-toggle:hover { text-decoration: underline; }
        .memory-attr-section {
            margin-top: 6px; padding: 8px; background: #f0f7ff;
            border-radius: 8px; border: 1px solid #d5e1ed;
            font-size: 0.78rem;
        }
        .memory-attr-title {
            font-weight: 700; color: #2c3e50; font-size: 0.78rem;
            margin-bottom: 6px;
        }
        .memory-attr-item {
            padding: 6px 8px; margin-bottom: 5px; background: white;
            border-radius: 6px; border: 1px solid #e0ecf7;
        }
        .memory-attr-item:last-child { margin-bottom: 0; }
        .memory-attr-header {
            display: flex; align-items: center; justify-content: space-between;
            margin-bottom: 4px;
        }
        .memory-attr-session {
            font-weight: 600; color: #2c3e50; font-size: 0.75rem;
        }
        .memory-attr-score-wrap {
            display: flex; align-items: center; gap: 4px;
        }
        .memory-attr-score-bar {
            width: 50px; height: 5px; background: #e0ecf7;
            border-radius: 3px; overflow: hidden;
        }
        .memory-attr-score-fill {
            height: 100%; border-radius: 3px;
            background: linear-gradient(90deg, #2980b9, #5dade2);
            transition: width 0.3s ease;
        }
        .memory-attr-score-pct {
            font-size: 0.65rem; font-weight: 700; color: #1565c0;
            min-width: 28px; text-align: right;
        }
        .memory-attr-text {
            font-size: 0.72rem; color: #555; line-height: 1.4;
            margin-top: 2px;
        }
        .memory-attr-text mark {
            background: #ffe082; padding: 0 2px; border-radius: 2px;
        }
        .memory-attr-keywords {
            display: flex; flex-wrap: wrap; gap: 3px; margin-top: 4px;
        }
        .memory-attr-kw {
            padding: 1px 6px; border-radius: 8px; font-size: 0.62rem;
            background: #e8eaf6; color: #3949ab; font-weight: 600;
        }
        .memory-attr-kw.highlighted {
            background: #ffe082; color: #8e6b47;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>VoiceMemory</h1>
        <p>소중한 사람의 목소리를 영원히</p>
    </div>
    <div class="container">
        <div class="tabs">
            <div class="tab active" onclick="showTab('persons')">Persons</div>
            <div class="tab" onclick="showTab('record')">Record</div>
            <div class="tab" onclick="showTab('chat')">Chat</div>
        </div>

        <!-- PERSONS TAB -->
        <div class="panel active" id="panel-persons">
            <div class="card">
                <h3>New Person</h3>
                <div class="input-group"><label>Name</label><input id="pName" placeholder="이름" /></div>
                <div class="input-group"><label>Relationship</label>
                    <select id="pRel"><option value="family">가족</option><option value="friend">친구</option><option value="mentor">스승</option></select>
                </div>
                <div class="input-group"><label>Personality</label><input id="pTraits" placeholder="따뜻한, 유머러스, 다정한" /></div>
                <div class="input-group"><label>Speaking Style</label><input id="pStyle" placeholder="말투 특징 (예: ~란다, ~하렴)" /></div>
                <button class="btn btn-primary" onclick="createPerson()">Register</button>
            </div>
            <div id="personList"></div>
        </div>

        <!-- RECORD TAB -->
        <div class="panel" id="panel-record">
            <!-- Search Bar -->
            <div class="search-bar">
                <input id="searchInput" placeholder="Search sessions, notes, tags, conversations..." onkeypress="if(event.key==='Enter')performSearch()" />
                <button onclick="performSearch()">Search</button>
            </div>
            <div class="search-filter-row" id="searchFilterRow" style="display:none;">
                <span class="filter-label">Filter by tag:</span>
                <select id="searchTagFilter" onchange="performSearch()">
                    <option value="">All tags</option>
                </select>
                <button class="btn btn-sm" style="background:#e0d5c8;color:#5d4037;padding:4px 10px;font-size:0.75rem;" onclick="clearSearch()">Clear Search</button>
            </div>
            <div class="search-results" id="searchResults" style="display:none;"></div>

            <!-- Transcript Search -->
            <div class="transcript-search-bar">
                <input id="transcriptSearchInput" placeholder="Search transcripts..." onkeypress="if(event.key==='Enter')searchTranscripts()" />
                <button onclick="searchTranscripts()">Search Transcripts</button>
            </div>
            <div class="transcript-search-results" id="transcriptSearchResults" style="display:none;"></div>

            <div class="card" id="consentArea">
                <h3>Consent Required</h3>
                <p style="font-size:0.85rem;color:#888;margin-bottom:10px">녹음 전 아래 동의가 필요합니다.</p>
                <div id="consentList"></div>
                <button class="btn btn-primary btn-sm" style="margin-top:8px" onclick="grantAllConsents()">모두 동의</button>
            </div>
            <div class="card">
                <h3>Recording Topics</h3>
                <div id="topicList"></div>
            </div>
            <!-- Audio recorder widget -->
            <div class="card" id="recorderCard">
                <h3 id="recorderTitle">Audio Recorder</h3>
                <p id="recorderGuide" style="font-size:0.85rem;color:#888;margin-bottom:10px">
                    Start a session to begin recording. Answer the guided questions naturally.
                </p>
                <div id="sessionQuestions" style="display:none;margin-bottom:12px;padding:10px;background:#faf5f0;border-radius:10px;">
                    <div style="font-weight:600;color:#5d4037;font-size:0.85rem;margin-bottom:4px">Guide Questions:</div>
                    <div id="questionList" style="font-size:0.8rem;color:#666;"></div>
                </div>
                <div class="recorder-widget">
                    <div class="recorder-controls">
                        <button class="rec-btn" id="recBtn" onclick="toggleRecording()" disabled title="Start recording">
                            <div class="rec-dot"></div>
                        </button>
                        <div class="rec-timer" id="recTimer">0:00</div>
                        <div class="rec-status" id="recStatus">Create a session first</div>
                    </div>
                    <div class="waveform-container" id="waveformContainer">
                        <canvas class="waveform-canvas" id="waveformCanvas"></canvas>
                    </div>
                    <div class="playback-area" id="playbackArea" style="display:none;">
                        <audio id="audioPlayback" controls style="width:100%;"></audio>
                        <div style="display:flex;gap:8px;margin-top:8px;">
                            <button class="btn btn-primary btn-sm" id="uploadBtn" onclick="uploadRecording()">Upload Recording</button>
                            <button class="btn btn-sm" style="background:#e0d5c8;color:#5d4037;" onclick="discardRecording()">Discard</button>
                        </div>
                        <div id="uploadStatus"></div>
                    </div>
                </div>
                <button class="btn btn-primary" style="margin-top:10px;width:100%;" id="startSessionBtn" onclick="startRecordingSession()">Start New Session</button>
            </div>
            <!-- Memory Search -->
            <div class="memory-search-card" id="memorySearchCard" style="display:none;">
                <h3>&#x1F50D; 기억 검색 (Memory Search)</h3>
                <div class="memory-search-bar">
                    <input id="memorySearchInput" placeholder="기억을 검색하세요... (예: 어린 시절, 좋아하는 음식)" onkeypress="if(event.key==='Enter')searchMemories()" />
                    <button onclick="searchMemories()">검색</button>
                </div>
                <div class="memory-results" id="memoryResults"></div>
            </div>

            <!-- Past recordings -->
            <div class="card">
                <h3>Past Recordings</h3>
                <div id="sessionList"><div class="empty-state">No recordings yet.</div></div>
            </div>
        </div>

        <!-- CHAT TAB -->
        <div class="panel" id="panel-chat">
            <div class="card">
                <h3 id="chatTitle">Select a person to chat</h3>
                <div class="voice-volume-wrap" id="chatVolumeWrap">
                    <label>&#x1F50A; 음량</label>
                    <input type="range" class="voice-volume-slider" id="chatVolumeSlider" min="0" max="100" value="80" oninput="updateChatVolume(this.value)" />
                    <span class="voice-volume-val" id="chatVolumeVal">80%</span>
                </div>
                <div class="chat-suggestions" id="chatSuggestions" style="display:none;">
                    <div class="chat-suggestions-label">이런 질문을 해보세요:</div>
                    <div class="chat-suggestion-chips" id="chatSuggestionChips"></div>
                </div>
                <div class="chat-area" id="chatArea">
                    <div class="empty-state">인물을 선택하고 대화를 시작하세요.</div>
                </div>
                <div class="chat-input-area">
                    <input class="chat-input" id="chatInput" placeholder="메시지를 입력하세요..." onkeypress="if(event.key==='Enter')sendChat()" />
                    <button class="send-btn" onclick="sendChat()">&#x27A4;</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Analytics overlay (hidden by default) -->
    <div class="analytics-overlay" id="analyticsOverlay" style="display:none;" onclick="if(event.target===this)closeAnalytics()">
        <div class="analytics-panel">
            <div class="analytics-header">
                <h3 id="analyticsTitle">Analytics</h3>
                <button class="analytics-close" onclick="closeAnalytics()">&times;</button>
            </div>
            <div class="analytics-body" id="analyticsBody">
                <div class="empty-state">Loading...</div>
            </div>
        </div>
    </div>

    <!-- Profile overlay (hidden by default) -->
    <div class="profile-overlay" id="profileOverlay" style="display:none;" onclick="if(event.target===this)closeProfile()">
        <div class="profile-panel">
            <div class="profile-header">
                <h3 id="profileTitle">Profile</h3>
                <button class="profile-close" onclick="closeProfile()">&times;</button>
            </div>
            <div class="profile-body" id="profileBody">
                <div class="empty-state">Loading...</div>
            </div>
        </div>
    </div>

    <!-- Hidden audio player for session playback -->
    <audio id="sessionAudioPlayer" style="display:none;"></audio>

    <script>
        let selectedPersonId = null;
        let selectedPersonName = '';

        // ====== Audio Recording State ======
        let mediaRecorder = null;
        let audioChunks = [];
        let audioBlob = null;
        let audioStream = null;
        let recordingStartTime = null;
        let timerInterval = null;
        let currentSessionId = null;
        let analyserNode = null;
        let audioContext = null;
        let animFrameId = null;

        // ====== Tab Navigation ======
        function showTab(name) {
            document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active',['persons','record','chat'][i]===name));
            document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
            document.getElementById('panel-'+name).classList.add('active');
            if(name==='persons') loadPersons();
            if(name==='record') loadRecordTab();
            if(name==='chat') loadChatHistory();
        }

        // ====== Person Management ======
        async function createPerson() {
            const traits = document.getElementById('pTraits').value.split(',').map(s=>s.trim()).filter(Boolean);
            const r = await fetch('/api/persons', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
                name: document.getElementById('pName').value,
                relationship_type: document.getElementById('pRel').value,
                personality_traits: traits,
                speaking_style: document.getElementById('pStyle').value,
            })});
            const d = await r.json();
            alert(d.message || 'Created!');
            loadPersons();
        }

        async function loadPersons() {
            const r = await fetch('/api/persons');
            const d = await r.json();
            const el = document.getElementById('personList');
            if (!d.persons.length) { el.innerHTML='<div class="empty-state">등록된 인물이 없습니다.</div>'; return; }
            el.innerHTML = d.persons.map(p=>
                `<div class="person-card">
                    <div class="person-avatar" onclick="selectPerson(${p.id},'${p.name}')">${p.name[0]}</div>
                    <div class="person-info" onclick="selectPerson(${p.id},'${p.name}')"><div class="name">${p.name}</div><div class="sub">${p.relationship_type} | Sessions: ${p.session_count} | Chats: ${p.conversation_count}</div></div>
                    <button class="btn-profile" onclick="event.stopPropagation();openProfile(${p.id},'${p.name}')" title="프로필">&#x1F4CB; 프로필</button>
                    <button class="btn-analytics" onclick="event.stopPropagation();openAnalytics(${p.id},'${p.name}')"><svg width="12" height="12" viewBox="0 0 12 12" style="vertical-align:-1px;margin-right:3px;"><rect x="1" y="7" width="2" height="4" fill="#8e6b47"/><rect x="5" y="4" width="2" height="7" fill="#8e6b47"/><rect x="9" y="1" width="2" height="10" fill="#8e6b47"/></svg>&#xBD84;&#xC11D;</button>
                </div>`
            ).join('');
        }

        function selectPerson(id, name) {
            selectedPersonId = id;
            selectedPersonName = name;
            showTab('record');
        }

        // ====== Record Tab ======
        async function loadRecordTab() {
            if (!selectedPersonId) {
                document.getElementById('consentList').innerHTML='<p style="color:#aaa">먼저 인물을 선택하세요 (Persons 탭).</p>';
                document.getElementById('startSessionBtn').disabled = true;
                document.getElementById('memorySearchCard').style.display = 'none';
                return;
            }
            document.getElementById('startSessionBtn').disabled = false;
            // Show memory search card
            document.getElementById('memorySearchCard').style.display = 'block';
            // Consent
            const cr = await fetch('/api/consents/required');
            const cd = await cr.json();
            document.getElementById('consentList').innerHTML = cd.consents.map(c=>
                `<div class="consent-item"><input type="checkbox" class="consent-check" data-type="${c.type}" /><div><strong>${c.title}</strong><br><span style="font-size:0.8rem;color:#888">${c.description}</span></div></div>`
            ).join('');
            // Check existing consents
            const existCr = await fetch('/api/consents/' + selectedPersonId);
            const existCd = await existCr.json();
            if (existCd.granted) {
                existCd.granted.forEach(t => {
                    const el = document.querySelector('.consent-check[data-type="'+t+'"]');
                    if (el) el.checked = true;
                });
            }
            // Topics
            const tr = await fetch('/api/recording/topics');
            const td = await tr.json();
            document.getElementById('topicList').innerHTML = td.topics.slice(0,5).map(t=>
                `<div class="topic-card"><div class="title">${t.topic}</div><div class="questions">${t.questions.join(' / ')}</div></div>`
            ).join('');
            // Load past sessions
            loadSessionList();
            // Init waveform canvas
            initWaveformCanvas();
        }

        async function grantAllConsents() {
            if (!selectedPersonId) { alert('인물을 먼저 선택하세요!'); return; }
            const types = ['voice_recording','ai_clone','data_storage'];
            for (const t of types) {
                await fetch('/api/consents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({person_id:selectedPersonId,consent_type:t,is_granted:true})});
            }
            document.querySelectorAll('.consent-check').forEach(el=>el.checked=true);
            alert('모든 동의가 완료되었습니다.');
        }

        // ====== Recording Session ======
        async function startRecordingSession() {
            if (!selectedPersonId) { alert('인물을 먼저 선택하세요!'); return; }
            const r = await fetch('/api/recording/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({person_id:selectedPersonId})});
            const d = await r.json();
            if (d.error) { alert(d.error); return; }

            currentSessionId = d.session_id;
            document.getElementById('recorderTitle').textContent = 'Session #' + d.session_number + ': ' + d.topic;
            document.getElementById('recorderGuide').textContent = 'Press the record button and answer the questions below.';
            document.getElementById('sessionQuestions').style.display = 'block';
            document.getElementById('questionList').innerHTML = d.questions.map((q,i) =>
                '<div style="margin:2px 0;">' + (i+1) + '. ' + q + '</div>'
            ).join('');

            // Enable record button
            document.getElementById('recBtn').disabled = false;
            document.getElementById('recStatus').textContent = 'Ready to record';
            document.getElementById('recStatus').className = 'rec-status';

            // Reset playback area
            document.getElementById('playbackArea').style.display = 'none';
            document.getElementById('uploadStatus').innerHTML = '';
            audioBlob = null;
        }

        // ====== Audio Recording (MediaRecorder API) ======
        async function toggleRecording() {
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                stopRecording();
            } else {
                await startAudioRecording();
            }
        }

        async function startAudioRecording() {
            if (!currentSessionId) {
                alert('Start a session first!');
                return;
            }
            try {
                // Request microphone access
                audioStream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        channelCount: 1,
                        sampleRate: 44100,
                        echoCancellation: true,
                        noiseSuppression: true,
                    }
                });

                // Determine best supported MIME type
                let mimeType = 'audio/webm;codecs=opus';
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = 'audio/webm';
                }
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = 'audio/ogg;codecs=opus';
                }
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = ''; // Let browser decide
                }

                const options = mimeType ? { mimeType: mimeType } : {};
                mediaRecorder = new MediaRecorder(audioStream, options);
                audioChunks = [];

                mediaRecorder.ondataavailable = function(e) {
                    if (e.data.size > 0) {
                        audioChunks.push(e.data);
                    }
                };

                mediaRecorder.onstop = function() {
                    const actualMime = mediaRecorder.mimeType || mimeType || 'audio/webm';
                    audioBlob = new Blob(audioChunks, { type: actualMime });
                    const audioUrl = URL.createObjectURL(audioBlob);
                    const player = document.getElementById('audioPlayback');
                    player.src = audioUrl;
                    document.getElementById('playbackArea').style.display = 'block';

                    // Stop all tracks
                    if (audioStream) {
                        audioStream.getTracks().forEach(t => t.stop());
                        audioStream = null;
                    }
                    stopWaveformVisualization();
                };

                mediaRecorder.start(250); // Collect data every 250ms

                // Update UI
                recordingStartTime = Date.now();
                updateTimer();
                timerInterval = setInterval(updateTimer, 200);

                document.getElementById('recBtn').classList.add('recording');
                document.getElementById('recTimer').classList.add('recording');
                document.getElementById('recStatus').textContent = 'Recording...';
                document.getElementById('recStatus').className = 'rec-status recording';
                document.getElementById('playbackArea').style.display = 'none';

                // Start waveform visualization
                startWaveformVisualization(audioStream);

            } catch (err) {
                console.error('Microphone access error:', err);
                if (err.name === 'NotAllowedError') {
                    alert('Microphone access denied. Please allow microphone access in your browser settings.');
                } else if (err.name === 'NotFoundError') {
                    alert('No microphone found. Please connect a microphone.');
                } else {
                    alert('Could not access microphone: ' + err.message);
                }
            }
        }

        function stopRecording() {
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
            }
            clearInterval(timerInterval);
            timerInterval = null;

            document.getElementById('recBtn').classList.remove('recording');
            document.getElementById('recTimer').classList.remove('recording');
            document.getElementById('recStatus').textContent = 'Recording stopped. Review and upload below.';
            document.getElementById('recStatus').className = 'rec-status';
        }

        function updateTimer() {
            if (!recordingStartTime) return;
            const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
            const min = Math.floor(elapsed / 60);
            const sec = elapsed % 60;
            document.getElementById('recTimer').textContent = min + ':' + (sec < 10 ? '0' : '') + sec;
        }

        function discardRecording() {
            audioBlob = null;
            audioChunks = [];
            document.getElementById('playbackArea').style.display = 'none';
            document.getElementById('uploadStatus').innerHTML = '';
            document.getElementById('recTimer').textContent = '0:00';
            document.getElementById('recStatus').textContent = 'Recording discarded. Press record to try again.';
            clearWaveformCanvas();
        }

        // ====== Upload Recording ======
        async function uploadRecording() {
            if (!audioBlob || !currentSessionId) {
                alert('No recording to upload.');
                return;
            }

            const statusEl = document.getElementById('uploadStatus');
            statusEl.innerHTML = '<div class="upload-status uploading">Uploading...</div>';
            document.getElementById('uploadBtn').disabled = true;

            try {
                // Determine file extension from blob type
                let ext = '.webm';
                if (audioBlob.type.includes('ogg')) ext = '.ogg';
                else if (audioBlob.type.includes('wav')) ext = '.wav';
                else if (audioBlob.type.includes('mp4') || audioBlob.type.includes('m4a')) ext = '.m4a';

                const formData = new FormData();
                formData.append('audio', audioBlob, 'recording' + ext);
                formData.append('session_id', currentSessionId);

                const r = await fetch('/api/recordings/upload?session_id=' + currentSessionId, {
                    method: 'POST',
                    body: formData,
                });
                const d = await r.json();

                if (r.ok) {
                    const sizeKB = Math.round(d.size_bytes / 1024);
                    statusEl.innerHTML = '<div class="upload-status success">Uploaded successfully! (' + d.format.toUpperCase() + ', ' + sizeKB + ' KB)</div>';
                    // Update session with duration
                    const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
                    await fetch('/api/recording/session/' + currentSessionId, {
                        method: 'PUT',
                        headers: {'Content-Type':'application/json'},
                        body: JSON.stringify({ status: 'completed', duration_seconds: elapsed }),
                    });
                    // Reload session list
                    loadSessionList();
                    // Reset for next recording
                    currentSessionId = null;
                    document.getElementById('recBtn').disabled = true;
                    document.getElementById('recStatus').textContent = 'Upload complete! Start a new session to record again.';
                } else {
                    statusEl.innerHTML = '<div class="upload-status error">Upload failed: ' + (d.detail || 'Unknown error') + '</div>';
                }
            } catch (err) {
                statusEl.innerHTML = '<div class="upload-status error">Upload failed: ' + err.message + '</div>';
            }
            document.getElementById('uploadBtn').disabled = false;
        }

        // ====== Tag Colors ======
        const TAG_COLORS = ['#8e6b47','#c0392b','#2980b9','#27ae60','#8e44ad','#d35400','#16a085','#2c3e50','#f39c12','#7f8c8d'];
        function tagColor(name) {
            let hash = 0;
            for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
            return TAG_COLORS[Math.abs(hash) % TAG_COLORS.length];
        }

        // ====== Session List & Playback ======
        async function loadSessionList() {
            if (!selectedPersonId) return;
            const r = await fetch('/api/recording/sessions/' + selectedPersonId);
            const d = await r.json();
            const el = document.getElementById('sessionList');
            if (!d.sessions || !d.sessions.length) {
                el.innerHTML = '<div class="empty-state">No recordings yet.</div>';
                return;
            }
            el.innerHTML = d.sessions.map(s => {
                const durMin = Math.floor((s.duration_seconds || 0) / 60);
                const durSec = (s.duration_seconds || 0) % 60;
                const durStr = durMin + ':' + (durSec < 10 ? '0' : '') + durSec;
                const statusBadge = s.status === 'completed'
                    ? '<span style="color:#2e7d32;font-size:0.7rem;">Completed</span>'
                    : '<span style="color:#e65100;font-size:0.7rem;">' + s.status + '</span>';
                const playBtn = s.has_audio
                    ? '<button class="play-btn" onclick="playSessionAudio(' + s.id + ', this)" title="Play recording">&#9654;</button>'
                    : '';

                // Tags
                const tagsHtml = (s.tags || []).map(t =>
                    '<span class="tag-chip" style="background:' + tagColor(t) + '">' +
                        escapeHtml(t) +
                        '<span class="tag-remove" onclick="removeTag(' + s.id + ',\'' + escapeHtml(t) + '\')">&times;</span>' +
                    '</span>'
                ).join('');

                // Emotional tone
                const toneOptions = ['','행복','슬픔','감사','그리움','평온'];
                const toneSelect = toneOptions.map(opt =>
                    '<option value="' + opt + '"' + (opt === (s.emotional_tone || '') ? ' selected' : '') + '>' +
                    (opt || '-- tone --') + '</option>'
                ).join('');

                // Transcription UI
                let transcribeBtn = '';
                if (s.has_audio && s.transcription_status !== 'completed' && s.transcription_status !== 'processing' && s.transcription_status !== 'pending') {
                    transcribeBtn = '<button class="transcribe-btn" onclick="transcribeSession(' + s.id + ')">Transcribe</button>';
                }
                let tsStatusHtml = '';
                if (s.transcription_status && s.transcription_status !== 'none') {
                    tsStatusHtml = '<span class="transcription-status ' + s.transcription_status + '">' + s.transcription_status + '</span>';
                }

                // Transcript display (collapsible)
                let transcriptHtml = '';
                if (s.has_transcript || s.transcript_summary || (s.keywords && s.keywords.length)) {
                    transcriptHtml += '<button class="transcript-toggle" onclick="toggleTranscript(' + s.id + ')">Transcript &#9662;</button>';
                    transcriptHtml += '<div id="transcript-' + s.id + '" style="display:none;">';
                    if (s.transcript_summary) {
                        transcriptHtml += '<div class="transcript-summary">' + escapeHtml(s.transcript_summary) + '</div>';
                    }
                    if (s.keywords && s.keywords.length) {
                        transcriptHtml += '<div class="keyword-badges">';
                        s.keywords.forEach(function(kw) {
                            transcriptHtml += '<span class="keyword-badge">' + escapeHtml(kw) + '</span>';
                        });
                        transcriptHtml += '</div>';
                    }
                    if (s.has_transcript) {
                        transcriptHtml += '<button class="transcript-toggle" style="margin-top:6px;" onclick="loadFullTranscript(' + s.id + ')">Show full transcript</button>';
                        transcriptHtml += '<div class="transcript-section" id="full-transcript-' + s.id + '" style="display:none;">Loading...</div>';
                    }
                    transcriptHtml += '</div>';
                }

                return '<div class="session-item" id="session-' + s.id + '">' +
                    '<div class="session-header">' +
                        '<div class="session-info">' +
                            '<div class="topic">#' + s.number + ' ' + escapeHtml(s.topic) + '</div>' +
                            '<div class="meta">' + durStr + ' | ' + statusBadge + ' ' + tsStatusHtml + '</div>' +
                        '</div>' +
                        transcribeBtn +
                        playBtn +
                    '</div>' +
                    '<div class="tag-area" id="tags-' + s.id + '">' +
                        tagsHtml +
                        '<button class="add-tag-btn" onclick="showTagInput(' + s.id + ')">+ tag</button>' +
                        '<div class="tag-input-wrap" id="tag-input-' + s.id + '" style="display:none;">' +
                            '<input id="tag-val-' + s.id + '" placeholder="tag name" onkeypress="if(event.key===\'Enter\')addTag(' + s.id + ')" />' +
                            '<button onclick="addTag(' + s.id + ')">Add</button>' +
                        '</div>' +
                    '</div>' +
                    transcriptHtml +
                    '<div style="display:flex;align-items:center;gap:8px;">' +
                        '<select class="tone-select" onchange="saveTone(' + s.id + ',this.value)">' + toneSelect + '</select>' +
                        '<button class="notes-toggle" onclick="toggleNotes(' + s.id + ')">Notes &#9662;</button>' +
                    '</div>' +
                    '<div class="notes-section" id="notes-' + s.id + '" style="display:none;">' +
                        '<textarea id="notes-text-' + s.id + '" placeholder="Add your notes about this session...">' + escapeHtml(s.user_notes || '') + '</textarea>' +
                        '<div class="notes-actions">' +
                            '<button class="btn btn-primary btn-sm" onclick="saveNotes(' + s.id + ')">Save Notes</button>' +
                        '</div>' +
                    '</div>' +
                '</div>';
            }).join('');
            // Load tags for search filter
            loadTagFilter();
        }

        // ====== Tag Management ======
        function showTagInput(sessionId) {
            const el = document.getElementById('tag-input-' + sessionId);
            el.style.display = el.style.display === 'none' ? 'inline-flex' : 'none';
            if (el.style.display === 'inline-flex') {
                document.getElementById('tag-val-' + sessionId).focus();
            }
        }

        async function addTag(sessionId) {
            const input = document.getElementById('tag-val-' + sessionId);
            const tagName = input.value.trim();
            if (!tagName) return;
            await fetch('/api/recording/sessions/' + sessionId + '/tags', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({tag_name: tagName}),
            });
            input.value = '';
            document.getElementById('tag-input-' + sessionId).style.display = 'none';
            loadSessionList();
        }

        async function removeTag(sessionId, tagName) {
            await fetch('/api/recording/sessions/' + sessionId + '/tags/' + encodeURIComponent(tagName), {
                method: 'DELETE',
            });
            loadSessionList();
        }

        // ====== Notes & Emotional Tone ======
        function toggleNotes(sessionId) {
            const el = document.getElementById('notes-' + sessionId);
            el.style.display = el.style.display === 'none' ? 'block' : 'none';
        }

        async function saveNotes(sessionId) {
            const text = document.getElementById('notes-text-' + sessionId).value;
            await fetch('/api/recording/sessions/' + sessionId + '/notes', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_notes: text}),
            });
            alert('Notes saved!');
        }

        async function saveTone(sessionId, tone) {
            await fetch('/api/recording/sessions/' + sessionId + '/notes', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({emotional_tone: tone}),
            });
        }

        // ====== Transcription ======
        async function transcribeSession(sessionId) {
            const r = await fetch('/api/recording/sessions/' + sessionId + '/transcribe', {method: 'POST'});
            const d = await r.json();
            if (d.status === 'queued' || d.status === 'already_processing') {
                // Start polling
                pollTranscriptionStatus(sessionId);
                loadSessionList();
            } else {
                alert('Transcription request failed.');
            }
        }

        function pollTranscriptionStatus(sessionId) {
            const interval = setInterval(async function() {
                const r = await fetch('/api/recording/sessions/' + sessionId + '/transcript');
                const d = await r.json();
                if (d.transcription_status === 'completed' || d.transcription_status === 'failed') {
                    clearInterval(interval);
                    loadSessionList();
                } else if (d.transcription_status === 'processing' || d.transcription_status === 'pending') {
                    // Keep polling
                }
            }, 3000);
            // Stop polling after 5 minutes max
            setTimeout(function() { clearInterval(interval); }, 300000);
        }

        function toggleTranscript(sessionId) {
            const el = document.getElementById('transcript-' + sessionId);
            if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
        }

        async function loadFullTranscript(sessionId) {
            const el = document.getElementById('full-transcript-' + sessionId);
            if (!el) return;
            if (el.style.display === 'block' && el.textContent !== 'Loading...') {
                el.style.display = 'none';
                return;
            }
            el.style.display = 'block';
            el.textContent = 'Loading...';
            const r = await fetch('/api/recording/sessions/' + sessionId + '/transcript');
            const d = await r.json();
            el.textContent = d.transcript || '(No transcript available)';
        }

        // ====== Transcript Search ======
        async function searchTranscripts() {
            const q = document.getElementById('transcriptSearchInput').value.trim();
            if (!q) {
                document.getElementById('transcriptSearchResults').style.display = 'none';
                return;
            }
            const r = await fetch('/api/search/transcript?q=' + encodeURIComponent(q));
            const d = await r.json();
            const el = document.getElementById('transcriptSearchResults');
            el.style.display = 'block';
            if (!d.results || !d.results.length) {
                el.innerHTML = '<div class="empty-state">No transcript results found.</div>';
                return;
            }
            el.innerHTML = '<div style="font-size:0.8rem;color:#888;margin-bottom:4px;">' + d.count + ' transcript result(s)</div>' +
                d.results.map(function(r) {
                    let snippetHtml = '';
                    if (r.transcript_snippet) {
                        let text = escapeHtml(r.transcript_snippet);
                        const re = new RegExp('(' + q.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
                        text = text.replace(re, '<mark>$1</mark>');
                        snippetHtml = '<div class="tsr-snippet">' + text + '</div>';
                    }
                    let kwHtml = '';
                    if (r.keywords && r.keywords.length) {
                        kwHtml = '<div class="tsr-keywords">' +
                            r.keywords.map(function(kw) { return '<span class="keyword-badge">' + escapeHtml(kw) + '</span>'; }).join(' ') +
                        '</div>';
                    }
                    let summaryHtml = r.transcript_summary
                        ? '<div style="font-size:0.78rem;color:#555;margin-top:3px;">' + escapeHtml(r.transcript_summary) + '</div>'
                        : '';
                    return '<div class="transcript-search-result">' +
                        '<div class="tsr-header">#' + r.session_number + ' ' + escapeHtml(r.topic) + '</div>' +
                        '<div class="tsr-person">' + escapeHtml(r.person_name) + '</div>' +
                        summaryHtml + snippetHtml + kwHtml +
                    '</div>';
                }).join('');
        }

        // ====== Search ======
        async function loadTagFilter() {
            const r = await fetch('/api/tags');
            const d = await r.json();
            const sel = document.getElementById('searchTagFilter');
            const current = sel.value;
            sel.innerHTML = '<option value="">All tags</option>' +
                (d.tags || []).map(t =>
                    '<option value="' + escapeHtml(t.tag_name) + '"' + (t.tag_name === current ? ' selected' : '') + '>' +
                    escapeHtml(t.tag_name) + ' (' + t.count + ')</option>'
                ).join('');
        }

        async function performSearch() {
            const q = document.getElementById('searchInput').value.trim();
            const tag = document.getElementById('searchTagFilter').value;
            if (!q && !tag) {
                clearSearch();
                return;
            }

            let url = '/api/search?q=' + encodeURIComponent(q);
            if (selectedPersonId) url += '&person_id=' + selectedPersonId;
            if (tag) url += '&tag=' + encodeURIComponent(tag);

            const r = await fetch(url);
            const d = await r.json();

            document.getElementById('searchFilterRow').style.display = 'flex';
            const el = document.getElementById('searchResults');
            el.style.display = 'block';

            if (!d.results || !d.results.length) {
                el.innerHTML = '<div class="empty-state">No results found.</div>';
                return;
            }

            el.innerHTML = '<div style="font-size:0.8rem;color:#888;margin-bottom:6px;">' + d.count + ' result(s)</div>' +
                d.results.map(r => {
                    const tagsHtml = (r.tags || []).map(t =>
                        '<span class="tag-chip" style="background:' + tagColor(t) + '">' + escapeHtml(t) + '</span>'
                    ).join('');
                    const snippetsHtml = (r.snippets || []).map(sn => {
                        let text = escapeHtml(sn.text);
                        if (q) {
                            const re = new RegExp('(' + q.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
                            text = text.replace(re, '<mark>$1</mark>');
                        }
                        return '<div class="sr-snippet"><span style="font-size:0.7rem;color:#aaa;">[' + sn.field + ']</span> ' + text + '</div>';
                    }).join('');
                    const toneLabel = r.emotional_tone ? ' | ' + r.emotional_tone : '';
                    return '<div class="search-result-item">' +
                        '<div class="sr-header">#' + r.session_number + ' ' + escapeHtml(r.topic) + '</div>' +
                        '<div class="sr-person">' + escapeHtml(r.person_name) + toneLabel + '</div>' +
                        (tagsHtml ? '<div class="sr-tags">' + tagsHtml + '</div>' : '') +
                        snippetsHtml +
                    '</div>';
                }).join('');
        }

        function clearSearch() {
            document.getElementById('searchInput').value = '';
            document.getElementById('searchTagFilter').value = '';
            document.getElementById('searchResults').style.display = 'none';
            document.getElementById('searchResults').innerHTML = '';
            document.getElementById('searchFilterRow').style.display = 'none';
        }

        let currentlyPlayingBtn = null;
        function playSessionAudio(sessionId, btnEl) {
            const player = document.getElementById('sessionAudioPlayer');

            // If already playing this session, toggle pause
            if (player.dataset.sessionId === String(sessionId) && !player.paused) {
                player.pause();
                if (btnEl) btnEl.innerHTML = '&#9654;';
                return;
            }

            // Stop previous
            player.pause();
            if (currentlyPlayingBtn) currentlyPlayingBtn.innerHTML = '&#9654;';

            player.src = '/api/recordings/' + sessionId + '/audio';
            player.dataset.sessionId = String(sessionId);
            currentlyPlayingBtn = btnEl;
            if (btnEl) btnEl.innerHTML = '&#9646;&#9646;';

            player.onended = function() {
                if (btnEl) btnEl.innerHTML = '&#9654;';
                currentlyPlayingBtn = null;
            };
            player.onerror = function() {
                if (btnEl) btnEl.innerHTML = '&#9654;';
                currentlyPlayingBtn = null;
                alert('Failed to play audio.');
            };
            player.play();
        }

        // ====== Waveform Visualization ======
        function initWaveformCanvas() {
            const canvas = document.getElementById('waveformCanvas');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            canvas.width = canvas.offsetWidth * (window.devicePixelRatio || 1);
            canvas.height = canvas.offsetHeight * (window.devicePixelRatio || 1);
            ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
            clearWaveformCanvas();
        }

        function clearWaveformCanvas() {
            const canvas = document.getElementById('waveformCanvas');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const w = canvas.offsetWidth;
            const h = canvas.offsetHeight;
            ctx.clearRect(0, 0, w, h);
            // Draw center line
            ctx.strokeStyle = '#ddd';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(0, h / 2);
            ctx.lineTo(w, h / 2);
            ctx.stroke();
        }

        function startWaveformVisualization(stream) {
            try {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const source = audioContext.createMediaStreamSource(stream);
                analyserNode = audioContext.createAnalyser();
                analyserNode.fftSize = 256;
                source.connect(analyserNode);
                // Do NOT connect to destination (avoid feedback)

                drawWaveform();
            } catch (e) {
                console.warn('Waveform visualization not available:', e);
            }
        }

        function drawWaveform() {
            if (!analyserNode) return;
            const canvas = document.getElementById('waveformCanvas');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const w = canvas.offsetWidth;
            const h = canvas.offsetHeight;
            const bufferLength = analyserNode.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);

            function draw() {
                animFrameId = requestAnimationFrame(draw);
                analyserNode.getByteTimeDomainData(dataArray);

                ctx.clearRect(0, 0, w, h);

                // Background center line
                ctx.strokeStyle = '#e0d5c8';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(0, h / 2);
                ctx.lineTo(w, h / 2);
                ctx.stroke();

                // Waveform
                ctx.lineWidth = 2;
                ctx.strokeStyle = '#c0392b';
                ctx.beginPath();

                const sliceWidth = w / bufferLength;
                let x = 0;
                for (let i = 0; i < bufferLength; i++) {
                    const v = dataArray[i] / 128.0;
                    const y = (v * h) / 2;
                    if (i === 0) { ctx.moveTo(x, y); } else { ctx.lineTo(x, y); }
                    x += sliceWidth;
                }
                ctx.lineTo(w, h / 2);
                ctx.stroke();
            }
            draw();
        }

        function stopWaveformVisualization() {
            if (animFrameId) {
                cancelAnimationFrame(animFrameId);
                animFrameId = null;
            }
            if (audioContext) {
                audioContext.close().catch(function(){});
                audioContext = null;
            }
            analyserNode = null;
        }

        // ====== Chat ======
        let chatAudioPlayer = null;        // shared HTML5 Audio for TTS playback
        let chatVolume = 0.8;              // 0.0 - 1.0
        let currentPlayBtnEl = null;       // currently active play button
        let ttsIdCounter = 0;              // unique id for each AI response

        function getChatAudioPlayer() {
            if (!chatAudioPlayer) {
                chatAudioPlayer = new Audio();
                chatAudioPlayer.volume = chatVolume;
                chatAudioPlayer.addEventListener('ended', function() {
                    if (currentPlayBtnEl) {
                        currentPlayBtnEl.innerHTML = '&#x1F50A; \uB4E4\uAE30';
                        currentPlayBtnEl.classList.remove('playing');
                        currentPlayBtnEl = null;
                    }
                });
                chatAudioPlayer.addEventListener('error', function() {
                    if (currentPlayBtnEl) {
                        currentPlayBtnEl.innerHTML = '&#x1F50A; \uB4E4\uAE30';
                        currentPlayBtnEl.classList.remove('playing', 'loading');
                        currentPlayBtnEl = null;
                    }
                });
            }
            return chatAudioPlayer;
        }

        function updateChatVolume(val) {
            chatVolume = parseInt(val) / 100;
            document.getElementById('chatVolumeVal').textContent = val + '%';
            if (chatAudioPlayer) {
                chatAudioPlayer.volume = chatVolume;
            }
        }

        async function loadChatHistory() {
            if (!selectedPersonId) return;
            document.getElementById('chatTitle').textContent = selectedPersonName + '\uC640(\uACFC) \uB300\uD654';
            const r = await fetch('/api/chat/history/' + selectedPersonId + '?limit=20');
            const d = await r.json();
            const area = document.getElementById('chatArea');
            if (!d.conversations.length) { area.innerHTML='<div class="empty-state">\uCCAB \uBA54\uC2DC\uC9C0\uB97C \uBCF4\uB0B4\uBCF4\uC138\uC694.</div>'; return; }
            area.innerHTML = d.conversations.map(function(c) {
                ttsIdCounter++;
                var ttsId = 'tts-hist-' + ttsIdCounter;
                var safeText = escapeHtml(c.ai_response).replace(/"/g, '&quot;');
                return '<div class="chat-msg user"><div class="bubble">' + escapeHtml(c.user_message) + '</div></div>' +
                    '<div class="chat-msg ai"><div class="bubble">' + escapeHtml(c.ai_response) +
                    '<div><button class="voice-play-btn" id="' + ttsId + '" data-tts-text="' + safeText + '" onclick="synthesizeAndPlay(' + selectedPersonId + ', this, this.dataset.ttsText)">&#x1F50A; \uB4E4\uAE30</button></div>' +
                    '</div></div>';
            }).join('');
            area.scrollTop = area.scrollHeight;
            loadChatSuggestions();
        }

        async function synthesizeAndPlay(personId, btnEl, textOrId) {
            const player = getChatAudioPlayer();
            // If this button is already playing, toggle pause/resume
            if (currentPlayBtnEl === btnEl && !player.paused) {
                player.pause();
                btnEl.innerHTML = '&#x1F50A; \uB4E4\uAE30';
                btnEl.classList.remove('playing');
                currentPlayBtnEl = null;
                return;
            }
            if (currentPlayBtnEl === btnEl && player.paused && player.currentTime > 0) {
                player.play();
                btnEl.innerHTML = '&#x23F8; \uC77C\uC2DC\uC815\uC9C0';
                btnEl.classList.add('playing');
                return;
            }

            // Get text to synthesize
            var text = '';
            if (typeof textOrId === 'string') {
                text = textOrId;
            } else {
                text = btnEl.dataset.ttsText || '';
            }
            if (!text) return;

            // Stop any currently playing audio
            player.pause();
            player.currentTime = 0;
            if (currentPlayBtnEl) {
                currentPlayBtnEl.innerHTML = '&#x1F50A; \uB4E4\uAE30';
                currentPlayBtnEl.classList.remove('playing', 'loading');
            }

            // Show loading state
            btnEl.innerHTML = '<span class="spinner"></span> \uC900\uBE44 \uC911...';
            btnEl.classList.add('loading');
            currentPlayBtnEl = btnEl;

            try {
                const r = await fetch('/api/chat/' + personId + '/synthesize', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text: text}),
                });
                if (!r.ok) {
                    var errData = await r.json().catch(function() { return {}; });
                    throw new Error(errData.detail || 'TTS \uC2E4\uD328');
                }
                const d = await r.json();

                // Play the audio
                player.src = d.audio_url;
                player.volume = chatVolume;
                await player.play();

                btnEl.innerHTML = '&#x23F8; \uC77C\uC2DC\uC815\uC9C0';
                btnEl.classList.remove('loading');
                btnEl.classList.add('playing');
            } catch (err) {
                console.error('TTS error:', err);
                btnEl.innerHTML = '&#x1F50A; \uB4E4\uAE30';
                btnEl.classList.remove('loading', 'playing');
                currentPlayBtnEl = null;
                btnEl.title = err.message || '\uC74C\uC131 \uD569\uC131 \uC2E4\uD328';
            }
        }

        function buildMemoryAttributionHtml(memoryAttribution, userMessage) {
            if (!memoryAttribution || memoryAttribution.length === 0) return '';

            var attrId = 'mem-attr-' + (++ttsIdCounter);
            var html = '<button class="memory-attr-toggle" onclick="toggleMemAttr(\\'' + attrId + '\\')">&#x1F4DA; \uCC38\uC870\uB41C \uAE30\uC5B5 (' + memoryAttribution.length + ') &#x25BC;</button>';
            html += '<div class="memory-attr-section" id="' + attrId + '" style="display:none;">';
            html += '<div class="memory-attr-title">\uCC38\uC870\uB41C \uAE30\uC5B5</div>';

            // Get user query tokens for keyword highlighting
            var queryTokens = (userMessage || '').split(/\\s+/).filter(function(t) { return t.length >= 2; });

            memoryAttribution.forEach(function(mem) {
                var scorePct = Math.round(mem.score * 100);
                html += '<div class="memory-attr-item">';
                html += '<div class="memory-attr-header">';
                html += '<span class="memory-attr-session">\uC138\uC158 #' + mem.session_number + ' - ' + escapeHtml(mem.topic) + '</span>';
                html += '<div class="memory-attr-score-wrap">';
                html += '<div class="memory-attr-score-bar"><div class="memory-attr-score-fill" style="width:' + scorePct + '%"></div></div>';
                html += '<span class="memory-attr-score-pct">' + scorePct + '%</span>';
                html += '</div></div>';

                // Text preview with query term highlighting
                if (mem.text_preview) {
                    var textHtml = escapeHtml(mem.text_preview);
                    queryTokens.forEach(function(term) {
                        var re = new RegExp('(' + term.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
                        textHtml = textHtml.replace(re, '<mark>$1</mark>');
                    });
                    html += '<div class="memory-attr-text">' + textHtml + '</div>';
                }

                // Keywords with highlighting
                if (mem.keywords && mem.keywords.length > 0) {
                    html += '<div class="memory-attr-keywords">';
                    mem.keywords.slice(0, 8).forEach(function(kw) {
                        var isMatch = queryTokens.some(function(t) { return kw.toLowerCase().indexOf(t.toLowerCase()) >= 0 || t.toLowerCase().indexOf(kw.toLowerCase()) >= 0; });
                        html += '<span class="memory-attr-kw' + (isMatch ? ' highlighted' : '') + '">' + escapeHtml(kw) + '</span>';
                    });
                    html += '</div>';
                }

                html += '</div>';
            });
            html += '</div>';
            return html;
        }

        function toggleMemAttr(id) {
            var el = document.getElementById(id);
            if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
        }

        async function sendChat() {
            const input = document.getElementById('chatInput');
            const msg = input.value.trim();
            if (!msg || !selectedPersonId) return;
            input.value = '';
            const area = document.getElementById('chatArea');
            if (area.querySelector('.empty-state')) area.innerHTML='';
            area.innerHTML += '<div class="chat-msg user"><div class="bubble">' + escapeHtml(msg) + '</div></div>';
            area.innerHTML += '<div class="chat-msg ai"><div class="bubble" id="typing">...</div></div>';
            area.scrollTop = area.scrollHeight;

            const r = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({person_id:selectedPersonId,message:msg})});
            const d = await r.json();
            const typingEl = document.getElementById('typing');
            ttsIdCounter++;
            const ttsId = 'tts-' + ttsIdCounter;
            let responseHtml = escapeHtml(d.ai_response);

            // Play button for TTS
            responseHtml += '<div><button class="voice-play-btn" id="' + ttsId + '" data-tts-text="' + escapeHtml(d.ai_response).replace(/"/g, '&quot;') + '" onclick="synthesizeAndPlay(' + selectedPersonId + ', this, this.dataset.ttsText)">&#x1F50A; \uB4E4\uAE30</button></div>';

            // Memory attribution section
            if (d.memory_attribution && d.memory_attribution.length > 0) {
                responseHtml += buildMemoryAttributionHtml(d.memory_attribution, msg);
            }
            // Also show old-style source tags for backward compat
            if (d.memory_sources && d.memory_sources.length > 0) {
                const sourceTags = d.memory_sources
                    .filter(function(s) { return s.score > 0.1; })
                    .slice(0, 2)
                    .map(function(s) {
                        return '<span class="memory-source-tag" title="Session #' + s.session_number + ': ' + escapeHtml(s.topic) + '">' +
                            '&#x1F4DD; #' + s.session_number + ' ' + escapeHtml(s.topic) + '</span>';
                    }).join(' ');
                if (sourceTags) {
                    responseHtml += '<div style="margin-top:4px;">' + sourceTags + '</div>';
                }
            }

            typingEl.innerHTML = responseHtml;
            typingEl.removeAttribute('id');
            area.scrollTop = area.scrollHeight;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // ====== Analytics ======
        function openAnalytics(personId, personName) {
            document.getElementById('analyticsOverlay').style.display = 'flex';
            document.getElementById('analyticsTitle').textContent = personName + ' - 분석';
            document.getElementById('analyticsBody').innerHTML = '<div class="empty-state">Loading analytics...</div>';
            document.body.style.overflow = 'hidden';
            loadAnalytics(personId);
        }

        function closeAnalytics() {
            document.getElementById('analyticsOverlay').style.display = 'none';
            document.body.style.overflow = '';
        }

        // Tone display mapping
        const TONE_MAP = {
            '행복': {cls: 'tone-badge-happy', label: '행복'},
            '슬픔': {cls: 'tone-badge-sad', label: '슬픔'},
            '감사': {cls: 'tone-badge-grateful', label: '감사'},
            '그리움': {cls: 'tone-badge-nostalgic', label: '그리움'},
            '평온': {cls: 'tone-badge-calm', label: '평온'},
        };

        function formatDuration(totalSec) {
            if (totalSec < 60) return totalSec + '초';
            const h = Math.floor(totalSec / 3600);
            const m = Math.floor((totalSec % 3600) / 60);
            const s = totalSec % 60;
            if (h > 0) return h + '시간 ' + m + '분';
            return m + '분 ' + s + '초';
        }

        async function loadAnalytics(personId) {
            try {
                const r = await fetch('/api/persons/' + personId + '/analytics');
                if (!r.ok) throw new Error('Failed to load analytics');
                const d = await r.json();
                renderAnalytics(d);
            } catch (err) {
                document.getElementById('analyticsBody').innerHTML =
                    '<div class="empty-state">Failed to load analytics: ' + escapeHtml(err.message) + '</div>';
            }
        }

        function renderAnalytics(data) {
            const body = document.getElementById('analyticsBody');
            let html = '';

            // --- Stats Cards Row ---
            const lastRecStr = data.last_recording_date
                ? new Date(data.last_recording_date).toLocaleDateString('ko-KR')
                : '-';
            const daysSinceStr = data.days_since_last_recording !== null
                ? data.days_since_last_recording + '일 전'
                : '-';

            html += '<div class="stats-row">';
            html += '<div class="stat-card"><div class="stat-value">' + formatDuration(data.total_duration_seconds) +
                    '</div><div class="stat-label">총 녹음 시간</div></div>';
            html += '<div class="stat-card"><div class="stat-value">' + data.session_count +
                    '</div><div class="stat-label">세션 수</div>' +
                    '<div class="stat-sub">평균 ' + formatDuration(data.avg_duration_seconds) + '</div></div>';
            html += '<div class="stat-card"><div class="stat-value">' + data.topic_coverage_pct + '%' +
                    '</div><div class="stat-label">주제 커버리지</div>' +
                    '<div class="stat-sub">' + data.covered_topic_count + ' / ' + data.total_topics + ' 주제</div>' +
                    '<div class="progress-bar-bg"><div class="progress-bar-fill" style="width:' + data.topic_coverage_pct + '%"></div></div></div>';
            html += '<div class="stat-card"><div class="stat-value">' + daysSinceStr +
                    '</div><div class="stat-label">마지막 녹음</div>' +
                    '<div class="stat-sub">' + lastRecStr + '</div></div>';
            html += '</div>';

            // --- Transcription completion rate ---
            html += '<div class="analytics-section">';
            html += '<h4>전사 완료율</h4>';
            html += '<div style="display:flex;align-items:center;gap:10px;">';
            html += '<div style="font-size:1.3rem;font-weight:800;color:#2980b9;">' + data.transcription_completion_rate + '%</div>';
            html += '<div style="flex:1;"><div class="progress-bar-bg"><div class="progress-bar-fill" style="width:' + data.transcription_completion_rate + '%;background:linear-gradient(90deg,#2980b9,#5dade2);"></div></div></div>';
            html += '</div></div>';

            // --- Emotional Tone Distribution ---
            if (data.tone_distribution && data.tone_distribution.length) {
                html += '<div class="analytics-section">';
                html += '<h4>감정 톤 분포</h4>';
                html += '<div class="tone-badge-list">';
                data.tone_distribution.forEach(function(item) {
                    const info = TONE_MAP[item.tone] || {cls: 'tone-badge-default', label: item.tone};
                    html += '<span class="tone-badge ' + info.cls + '">' +
                            escapeHtml(info.label) +
                            '<span class="tone-count">' + item.count + '</span></span>';
                });
                html += '</div></div>';
            }

            // --- Top Keywords ---
            if (data.top_keywords && data.top_keywords.length) {
                html += '<div class="analytics-section">';
                html += '<h4>주요 키워드 (Top ' + Math.min(20, data.top_keywords.length) + ')</h4>';
                html += '<div class="kw-tag-cloud">';
                const KW_STYLES = ['kw-tag-1','kw-tag-2','kw-tag-3','kw-tag-4','kw-tag-5','kw-tag-6'];
                data.top_keywords.forEach(function(item, idx) {
                    const sizeClass = KW_STYLES[idx % KW_STYLES.length];
                    const fontSize = Math.max(0.68, Math.min(1.05, 0.68 + (item.count - 1) * 0.08));
                    html += '<span class="kw-tag ' + sizeClass + '" style="font-size:' + fontSize + 'rem;" title="' + item.count + '회">' +
                            escapeHtml(item.keyword) +
                            '<span style="opacity:0.6;font-size:0.6rem;margin-left:2px;">(' + item.count + ')</span></span>';
                });
                html += '</div></div>';
            }

            // --- Recording Frequency (last 8 weeks) ---
            if (data.weekly_recording_frequency && data.weekly_recording_frequency.length) {
                html += '<div class="analytics-section">';
                html += '<h4>주간 녹음 빈도 (최근 8주)</h4>';
                const maxCount = Math.max(1, Math.max.apply(null, data.weekly_recording_frequency.map(function(w){return w.count;})));
                html += '<div class="freq-chart">';
                data.weekly_recording_frequency.forEach(function(w) {
                    const heightPct = (w.count / maxCount) * 100;
                    const barHeight = Math.max(2, heightPct * 0.75);
                    html += '<div class="freq-bar-col">' +
                            '<div class="freq-bar-count">' + (w.count > 0 ? w.count : '') + '</div>' +
                            '<div class="freq-bar" style="height:' + barHeight + 'px;' + (w.count === 0 ? 'opacity:0.25;' : '') + '"></div>' +
                            '<div class="freq-bar-label">' + escapeHtml(w.week_label) + '</div>' +
                            '</div>';
                });
                html += '</div></div>';
            }

            // --- Recommendation ---
            html += '<div class="analytics-section">';
            html += '<h4>추천</h4>';
            if (data.suggested_topics && data.suggested_topics.length) {
                html += '<div class="recommendation-box">';
                html += '<strong>다음 주제를 시도해보세요:</strong><br>';
                data.suggested_topics.forEach(function(topic) {
                    html += '<span style="display:inline-block;margin:3px 4px 3px 0;padding:2px 10px;background:#e8eaf6;border-radius:10px;font-size:0.78rem;color:#3949ab;">' + escapeHtml(topic) + '</span>';
                });
                html += '</div>';
            } else {
                html += '<div class="recommendation-box"><strong>모든 주제를 완료했습니다!</strong> 훌륭합니다.</div>';
            }
            html += '</div>';

            body.innerHTML = html;
        }

        // ====== Memory Search ======
        async function searchMemories() {
            if (!selectedPersonId) { alert('인물을 먼저 선택하세요!'); return; }
            const q = document.getElementById('memorySearchInput').value.trim();
            if (!q) {
                document.getElementById('memoryResults').innerHTML = '';
                return;
            }
            document.getElementById('memoryResults').innerHTML = '<div class="empty-state">검색 중...</div>';
            try {
                const r = await fetch('/api/persons/' + selectedPersonId + '/memories?q=' + encodeURIComponent(q) + '&top_k=8');
                const d = await r.json();
                const el = document.getElementById('memoryResults');
                if (!d.results || !d.results.length) {
                    el.innerHTML = '<div class="empty-state">관련 기억을 찾지 못했습니다.</div>';
                    return;
                }
                el.innerHTML = '<div style="font-size:0.78rem;color:#666;margin-bottom:6px;">' + d.count + '개의 관련 기억을 찾았습니다</div>' +
                    d.results.map(function(m) {
                        const scorePct = Math.round(m.score * 100);
                        const kwHtml = (m.keywords || []).slice(0, 5).map(function(kw) {
                            return '<span class="keyword-badge">' + escapeHtml(kw) + '</span>';
                        }).join('');
                        const toneLabel = m.emotional_tone ? '<span style="font-size:0.7rem;color:#8e44ad;margin-left:6px;">' + escapeHtml(m.emotional_tone) + '</span>' : '';
                        // Highlight query terms in text
                        let textHtml = escapeHtml(m.text);
                        const queryTerms = q.split(/\s+/).filter(function(t){ return t.length >= 2; });
                        queryTerms.forEach(function(term) {
                            const re = new RegExp('(' + term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
                            textHtml = textHtml.replace(re, '<mark>$1</mark>');
                        });
                        return '<div class="memory-result-item">' +
                            '<span class="mr-score">' + scorePct + '% 관련</span>' +
                            '<div class="mr-header">#' + m.session_number + ' ' + escapeHtml(m.topic) + toneLabel + '</div>' +
                            '<div class="mr-text">' + textHtml + '</div>' +
                            (kwHtml ? '<div class="mr-keywords">' + kwHtml + '</div>' : '') +
                        '</div>';
                    }).join('');
            } catch (err) {
                document.getElementById('memoryResults').innerHTML =
                    '<div class="empty-state">검색 오류: ' + escapeHtml(err.message) + '</div>';
            }
        }

        // ====== Person Profile ======
        function openProfile(personId, personName) {
            document.getElementById('profileOverlay').style.display = 'flex';
            document.getElementById('profileTitle').textContent = personName + ' - 프로필';
            document.getElementById('profileBody').innerHTML = '<div class="empty-state">Loading...</div>';
            document.body.style.overflow = 'hidden';
            loadProfile(personId);
        }

        function closeProfile() {
            document.getElementById('profileOverlay').style.display = 'none';
            document.body.style.overflow = '';
        }

        async function loadProfile(personId) {
            try {
                const r = await fetch('/api/persons/' + personId + '/profile');
                if (!r.ok) throw new Error('Failed to load profile');
                const d = await r.json();
                renderProfile(d);
            } catch (err) {
                document.getElementById('profileBody').innerHTML =
                    '<div class="empty-state">프로필 로드 실패: ' + escapeHtml(err.message) + '</div>';
            }
        }

        function renderProfile(data) {
            const body = document.getElementById('profileBody');
            let html = '';

            // Personality summary
            if (data.personality_summary) {
                html += '<div class="profile-section">';
                html += '<h4>인물 요약</h4>';
                html += '<div class="profile-personality">' + escapeHtml(data.personality_summary) + '</div>';
                html += '</div>';
            }

            // Stats row
            html += '<div class="stats-row">';
            html += '<div class="stat-card"><div class="stat-value">' + (data.total_memories || 0) +
                    '</div><div class="stat-label">기억 조각</div></div>';
            html += '<div class="stat-card"><div class="stat-value">' + (data.topics_discussed ? data.topics_discussed.length : 0) +
                    '</div><div class="stat-label">대화 주제</div></div>';
            html += '</div>';

            // Topics discussed
            if (data.topics_discussed && data.topics_discussed.length) {
                html += '<div class="profile-section">';
                html += '<h4>다룬 주제</h4>';
                html += '<div class="profile-topics-list">';
                data.topics_discussed.forEach(function(topic) {
                    html += '<span class="profile-topic-chip">' + escapeHtml(topic) + '</span>';
                });
                html += '</div></div>';
            }

            // Emotional patterns
            if (data.emotional_patterns && data.emotional_patterns.length) {
                html += '<div class="profile-section">';
                html += '<h4>감정 패턴</h4>';
                html += '<div class="tone-badge-list">';
                data.emotional_patterns.forEach(function(item) {
                    const info = TONE_MAP[item.tone] || {cls: 'tone-badge-default', label: item.tone};
                    html += '<span class="tone-badge ' + info.cls + '">' +
                            escapeHtml(info.label) +
                            '<span class="tone-count">' + item.count + '</span></span>';
                });
                html += '</div></div>';
            }

            // Key facts / keywords
            if (data.key_facts && data.key_facts.length) {
                html += '<div class="profile-section">';
                html += '<h4>주요 키워드</h4>';
                html += '<div class="kw-tag-cloud">';
                const KW_STYLES = ['kw-tag-1','kw-tag-2','kw-tag-3','kw-tag-4','kw-tag-5','kw-tag-6'];
                data.key_facts.forEach(function(item, idx) {
                    const sizeClass = KW_STYLES[idx % KW_STYLES.length];
                    const fontSize = Math.max(0.7, Math.min(1.05, 0.7 + (item.count - 1) * 0.08));
                    html += '<span class="kw-tag ' + sizeClass + '" style="font-size:' + fontSize + 'rem;">' +
                            escapeHtml(item.keyword) +
                            '<span style="opacity:0.6;font-size:0.6rem;margin-left:2px;">(' + item.count + ')</span></span>';
                });
                html += '</div></div>';
            }

            // Session summaries
            if (data.summaries && data.summaries.length) {
                html += '<div class="profile-section">';
                html += '<h4>녹음 요약</h4>';
                data.summaries.slice(0, 8).forEach(function(s) {
                    html += '<div class="profile-summary-item">' +
                        '<div class="psi-topic">#' + s.session_number + ' ' + escapeHtml(s.topic) + '</div>' +
                        '<div>' + escapeHtml(s.summary) + '</div>' +
                    '</div>';
                });
                html += '</div>';
            }

            // Suggested questions
            if (data.suggested_questions && data.suggested_questions.length) {
                html += '<div class="profile-section">';
                html += '<h4>추천 질문</h4>';
                html += '<div class="chat-suggestion-chips">';
                data.suggested_questions.forEach(function(q) {
                    html += '<span class="chat-suggestion-chip" onclick="closeProfile();selectPerson(' + data.person_id + ',\'' + escapeHtml(data.person_name) + '\');showTab(\'chat\');useSuggestion(\'' + escapeHtml(q).replace(/'/g, "\\'") + '\')">' + escapeHtml(q) + '</span>';
                });
                html += '</div></div>';
            }

            body.innerHTML = html;
        }

        // ====== Chat Suggestions ======
        async function loadChatSuggestions() {
            if (!selectedPersonId) {
                document.getElementById('chatSuggestions').style.display = 'none';
                return;
            }
            try {
                const r = await fetch('/api/persons/' + selectedPersonId + '/profile');
                const d = await r.json();
                const suggestions = d.suggested_questions || [];
                if (suggestions.length === 0) {
                    document.getElementById('chatSuggestions').style.display = 'none';
                    return;
                }
                document.getElementById('chatSuggestions').style.display = 'block';
                document.getElementById('chatSuggestionChips').innerHTML = suggestions.map(function(q) {
                    return '<span class="chat-suggestion-chip" onclick="useSuggestion(\'' + escapeHtml(q).replace(/'/g, "\\'") + '\')">' + escapeHtml(q) + '</span>';
                }).join('');
            } catch (err) {
                document.getElementById('chatSuggestions').style.display = 'none';
            }
        }

        function useSuggestion(text) {
            document.getElementById('chatInput').value = text;
            document.getElementById('chatInput').focus();
        }

        loadPersons();
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    print("=" * 50)
    print("  VoiceMemory Server - http://localhost:8002")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8002)
