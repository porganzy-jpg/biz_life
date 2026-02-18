"""
VoiceMemory - FastAPI 메인 앱
AI 음성 보존 서비스
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai-model"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared"))

from fastapi import FastAPI, Depends, Query
from fastapi.responses import HTMLResponse
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
         "duration_seconds": s.duration_seconds, "has_transcript": bool(s.transcript)}
        for s in sessions
    ]}


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
        .btn-sm { padding: 6px 16px; font-size: 0.8rem; }
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
                <button class="btn btn-primary btn-sm" style="margin-top:8px" onclick="startRecording()">Start Session</button>
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

    <script>
        let selectedPersonId = null;
        let selectedPersonName = '';

        function showTab(name) {
            document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active',['persons','record','chat'][i]===name));
            document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
            document.getElementById('panel-'+name).classList.add('active');
            if(name==='persons') loadPersons();
            if(name==='record') loadRecordTab();
            if(name==='chat') loadChatHistory();
        }

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
            showTab('chat');
        }

        async function loadRecordTab() {
            if (!selectedPersonId) { document.getElementById('consentList').innerHTML='<p style="color:#aaa">먼저 인물을 선택하세요.</p>'; return; }
            // Consent
            const cr = await fetch('/api/consents/required');
            const cd = await cr.json();
            document.getElementById('consentList').innerHTML = cd.consents.map(c=>
                `<div class="consent-item"><input type="checkbox" class="consent-check" data-type="${c.type}" /><div><strong>${c.title}</strong><br><span style="font-size:0.8rem;color:#888">${c.description}</span></div></div>`
            ).join('');
            // Topics
            const tr = await fetch('/api/recording/topics');
            const td = await tr.json();
            document.getElementById('topicList').innerHTML = td.topics.slice(0,5).map(t=>
                `<div class="topic-card"><div class="title">${t.topic}</div><div class="questions">${t.questions.join(' / ')}</div></div>`
            ).join('');
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

        async function startRecording() {
            if (!selectedPersonId) { alert('인물을 먼저 선택하세요!'); return; }
            const r = await fetch('/api/recording/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({person_id:selectedPersonId})});
            const d = await r.json();
            if (d.error) { alert(d.error); return; }
            alert(`세션 #${d.session_number}: ${d.topic}\\n\\n질문:\\n${d.questions.join('\\n')}`);
        }

        async function loadChatHistory() {
            if (!selectedPersonId) return;
            document.getElementById('chatTitle').textContent = `${selectedPersonName}와(과) 대화`;
            const r = await fetch(`/api/chat/history/${selectedPersonId}?limit=20`);
            const d = await r.json();
            const area = document.getElementById('chatArea');
            if (!d.conversations.length) { area.innerHTML='<div class="empty-state">첫 메시지를 보내보세요.</div>'; return; }
            area.innerHTML = d.conversations.map(c=>
                `<div class="chat-msg user"><div class="bubble">${c.user_message}</div></div>
                 <div class="chat-msg ai"><div class="bubble">${c.ai_response}</div></div>`
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
            area.innerHTML += `<div class="chat-msg user"><div class="bubble">${msg}</div></div>`;
            area.innerHTML += `<div class="chat-msg ai"><div class="bubble" id="typing">...</div></div>`;
            area.scrollTop = area.scrollHeight;

            const r = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({person_id:selectedPersonId,message:msg})});
            const d = await r.json();
            document.getElementById('typing').textContent = d.ai_response;
            document.getElementById('typing').removeAttribute('id');
            area.scrollTop = area.scrollHeight;
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
