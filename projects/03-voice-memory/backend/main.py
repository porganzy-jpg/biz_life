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
import uvicorn

from database import init_db, get_db
from models import Person, RecordingSession, Conversation, Consent
from schemas import PersonCreate, ChatRequest, ConsentCreate, RecordingSessionCreate, RecordingSessionUpdate
from consent_service import ConsentService
from recording_service import RecordingService
from persona_chat import PersonaChat

app = FastAPI(title="VoiceMemory API", version="1.0.0")
persona_chat = PersonaChat()


@app.on_event("startup")
async def startup():
    init_db()


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
    return {"sessions": [
        {"id": s.id, "topic": s.topic, "status": s.status, "number": s.session_number,
         "duration_seconds": s.duration_seconds, "has_transcript": bool(s.transcript),
         "has_audio": bool(s.audio_file_path)}
        for s in sessions
    ]}


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

    return {
        "person_name": person.name,
        "user_message": data.message,
        "ai_response": result["response"],
        "emotion": result["emotion"],
    }


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
            display: flex; align-items: center; gap: 10px; padding: 10px;
            border: 1px solid #e0d5c8; border-radius: 10px; margin: 6px 0;
        }
        .session-item .session-info { flex: 1; }
        .session-item .session-info .topic { font-weight: 600; color: #5d4037; font-size: 0.9rem; }
        .session-item .session-info .meta { font-size: 0.75rem; color: #999; }
        .play-btn {
            width: 36px; height: 36px; border-radius: 50%; border: none;
            background: #8e6b47; color: white; font-size: 1rem; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
        }
        .play-btn:hover { background: #7a5c3c; }
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
                `<div class="person-card" onclick="selectPerson(${p.id},'${p.name}')">
                    <div class="person-avatar">${p.name[0]}</div>
                    <div class="person-info"><div class="name">${p.name}</div><div class="sub">${p.relationship_type} | Sessions: ${p.session_count} | Chats: ${p.conversation_count}</div></div>
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
                return;
            }
            document.getElementById('startSessionBtn').disabled = false;
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
                return '<div class="session-item">' +
                    '<div class="session-info">' +
                        '<div class="topic">#' + s.number + ' ' + s.topic + '</div>' +
                        '<div class="meta">' + durStr + ' | ' + statusBadge + '</div>' +
                    '</div>' +
                    playBtn +
                '</div>';
            }).join('');
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
        async function loadChatHistory() {
            if (!selectedPersonId) return;
            document.getElementById('chatTitle').textContent = selectedPersonName + '와(과) 대화';
            const r = await fetch('/api/chat/history/' + selectedPersonId + '?limit=20');
            const d = await r.json();
            const area = document.getElementById('chatArea');
            if (!d.conversations.length) { area.innerHTML='<div class="empty-state">첫 메시지를 보내보세요.</div>'; return; }
            area.innerHTML = d.conversations.map(c=>
                '<div class="chat-msg user"><div class="bubble">' + escapeHtml(c.user_message) + '</div></div>' +
                '<div class="chat-msg ai"><div class="bubble">' + escapeHtml(c.ai_response) + '</div></div>'
            ).join('');
            area.scrollTop = area.scrollHeight;
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
            document.getElementById('typing').textContent = d.ai_response;
            document.getElementById('typing').removeAttribute('id');
            area.scrollTop = area.scrollHeight;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
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
