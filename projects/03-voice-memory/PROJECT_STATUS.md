# VoiceMemory - 프로젝트 현황

## 개요
소중한 사람의 음성을 보존하고 AI로 대화할 수 있는 서비스. 가이드 대화를 통해 음성 데이터를 수집하고, AI 음성 클론 + LLM 페르소나로 추억의 대화를 재현.

## 기술 스택
- **Backend**: Python 3.13, FastAPI, SQLAlchemy + SQLite
- **AI 대화**: OpenAI GPT-4o-mini (API 키 없으면 규칙 기반 폴백)
- **음성 복제**: ElevenLabs API (API 키 없으면 시뮬레이션 모드)
- **Frontend**: 인라인 HTML 템플릿 (vanilla JS)

## 실행 방법
```bash
cd projects/03-voice-memory/backend
python main.py
# → http://localhost:8002
```

## 파일 구조
```
03-voice-memory/
├── ai-model/
│   ├── persona_chat.py          # LLM 페르소나 대화 (OpenAI + 규칙 기반 폴백)
│   ├── voice_clone_service.py   # ElevenLabs API 래퍼 (시뮬레이션 지원)
│   └── audio_processor.py       # 오디오 유효성 검증, 품질 추정
├── backend/
│   ├── main.py                  # FastAPI 앱 + HTML 인터페이스
│   ├── database.py              # DB 설정
│   ├── models.py                # Person, RecordingSession, Conversation, Consent
│   ├── schemas.py               # Pydantic 스키마
│   ├── consent_service.py       # 3단계 동의 관리 (녹음/AI클론/데이터저장)
│   └── recording_service.py     # 녹음 세션 + 12개 가이드 대화 주제
├── docs/
│   └── PROJECT_PLAN.md
└── requirements.txt
```

## API 엔드포인트 (13개)
| Method | Path | 설명 | 테스트 결과 |
|--------|------|------|-------------|
| GET | `/` | 메인 인터페이스 (HTML) | OK - 13,191 bytes |
| GET | `/api/health` | 헬스체크 | OK |
| GET | `/api/persons` | 인물 목록 조회 | OK |
| POST | `/api/persons` | 인물 등록 | OK |
| GET | `/api/persons/{id}` | 인물 상세 | OK |
| GET | `/api/consents/required` | 필수 동의 항목 | OK |
| POST | `/api/consents` | 동의 부여/철회 | OK |
| GET | `/api/consents/{person_id}` | 동의 상태 확인 | OK |
| GET | `/api/recording/topics` | 가이드 대화 주제 (12개) | OK |
| POST | `/api/recording/session` | 녹음 세션 생성 | OK |
| GET | `/api/recording/sessions/{person_id}` | 녹음 세션 목록 | OK |
| POST | `/api/chat` | AI 페르소나 대화 | OK |
| GET | `/api/chat/history/{person_id}` | 대화 이력 조회 | OK |

## 동의 관리 (3단계 필수)
1. `voice_recording` - 음성 녹음 동의
2. `ai_clone` - AI 음성 복제 동의
3. `data_storage` - 데이터 저장 동의

3개 모두 동의해야 녹음 세션 생성 가능.

## 가이드 대화 주제 (12개)
어린 시절 추억, 가족 이야기, 학창 시절, 첫 직장, 결혼과 사랑, 자녀 이야기, 좋아하는 음식, 취미와 여가, 좋아하는 노래, 계절과 날씨, 인생 조언, 감사한 것들

## AI 대화 시스템
- **OpenAI 모드**: GPT-4o-mini로 페르소나 기반 대화 (성격, 말투, 관계 반영)
- **폴백 모드**: 키워드 매칭 + 랜덤 따뜻한 응답
- 감정 감지: warm, comforting, happy, neutral

## 테스트 결과
- 2025-02-07 전체 API 엔드포인트 테스트 통과
- 인물 등록 → 동의 관리 → 녹음 세션 → AI 대화 전체 플로우 정상
- 폴백 대화: "안녕" → "그래, 어서 와. 오늘 하루는 어땠어?" (warm)

## 주요 기능
- [x] 인물 등록 (이름, 관계, 성격, 말투)
- [x] 3단계 동의 관리 (윤리적 AI 사용)
- [x] 12개 가이드 대화 주제 + 질문
- [x] 녹음 세션 관리
- [x] AI 페르소나 대화 (OpenAI + 폴백)
- [x] 음성 품질 추정 (30초~30분+)
- [x] 대화 이력 저장/조회

## 향후 과제
- [ ] 실제 음성 녹음 기능 (WebRTC)
- [ ] ElevenLabs 음성 클론 연동
- [ ] 음성 합성 TTS 재생
- [ ] 오디오 노이즈 제거 전처리
- [ ] 감정 분석 고도화
