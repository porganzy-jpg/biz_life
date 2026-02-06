# VoiceMemory - AI 음성 보존 서비스

## 1. 프로젝트 개요

### 1.1 핵심 컨셉
소중한 사람의 목소리를 녹음하고 AI로 학습하여 사후에도 대화할 수 있게 하는 서비스.
가족, 연인, 친구 등 소중한 사람의 목소리와 말투, 대화 패턴을 AI가 학습하여
그 사람이 곁에 없을 때에도 음성으로 대화할 수 있는 메모리얼 서비스이다.

### 1.2 문제 정의
- 사별 후 고인의 목소리를 다시 듣고 싶은 유족의 감정적 니즈
- 기존 추모 서비스는 사진/영상 위주이며, 음성 보존에 대한 서비스 부재
- 치매/인지 장애 환자의 가족이 환자의 건강했던 시절 목소리를 보존하고 싶은 니즈
- 해외 거주, 장기 출장 등으로 떨어져 사는 가족 간 정서적 연결 니즈

### 1.3 타겟 사용자
- 1차: 고령 부모를 둔 30~50대 자녀
- 2차: 치매/중증 질환 가족을 둔 보호자
- 3차: 해외 거주 교민 (부모님 목소리 보존)
- 4차: 추모 및 장례 서비스 업계

---

## 2. 법적 고려사항 (Legal Considerations)

### 2.1 통신비밀보호법 대응
**문제**: 한국 통신비밀보호법 제3조에 따르면 타인의 대화를 녹음하는 것은 원칙적으로 금지.
일반 통화 녹음을 무단으로 수집하면 법적 문제가 발생할 수 있음.

**해결 방안: 전용 녹음 세션 방식**

```
[기존 방식 - 문제 있음]
일상 통화 도청/녹음 → 통신비밀보호법 위반 가능

[VoiceMemory 방식 - 적법]
전용 녹음 세션 → 양측 명시적 동의 → 녹음 진행 → AI 학습
```

### 2.2 전용 녹음 세션 설계
1. **사전 동의**: 녹음 대상자(피녹음자)가 앱에서 직접 동의서에 서명
2. **세션 시작**: 양측 모두 녹음 시작을 인지한 상태에서 진행
3. **가이드 대화**: 앱이 제시하는 대화 주제를 따라 자연스럽게 대화
4. **세션 종료**: 녹음 종료 후 양측 모두 확인
5. **동의 기록**: 동의 일시, 동의자 정보, 동의 내용 블록체인에 기록

### 2.3 동의서 필수 포함 항목
- 녹음 목적 (AI 음성 모델 학습)
- 녹음 데이터 보존 기간
- 데이터 사용 범위 (지정된 가족/관계인만 접근)
- 데이터 삭제 요청 권리
- 사후 데이터 처리 방침
- 제3자 제공 금지 조항

### 2.4 관련 법률 체크리스트
- [ ] 통신비밀보호법 제3조 (타인 대화 녹음 금지) → 전용 세션 방식으로 해결
- [ ] 개인정보보호법 (음성 = 생체 정보) → 명시적 동의 + 암호화 저장
- [ ] 정보통신망법 (데이터 보관/파기) → 보존 기간 명시 + 파기 절차
- [ ] 저작권법 (음성의 저작물성) → 이용 허락 동의
- [ ] 디지털 유산법 (향후 입법 대비) → 유언장 연동 기능 고려

---

## 3. 기술 접근 방식 (Technical Approach)

### 3.1 음성 복제 기술 스택

```
[녹음 세션]
    │
    ▼
[음성 전처리]
    │ - 잡음 제거 (noise reduction)
    │ - 음성 구간 분리 (VAD)
    │ - 화자 분리 (speaker diarization)
    │
    ▼
[음성 복제 AI - Voice Cloning]
    │ - ElevenLabs API (메인)
    │ - PlayHT API (백업)
    │ - Custom Fine-tuned Model (장기)
    │
    ▼
[LLM 대화 시스템]
    │ - GPT-4o / Claude API
    │ - 페르소나 프롬프트
    │ - 대화 히스토리 메모리
    │
    ▼
[음성 합성 출력]
    │ - TTS with cloned voice
    │ - 감정 표현 (감정 분석 기반)
    │
    ▼
[사용자에게 음성 응답 전달]
```

### 3.2 ElevenLabs API 활용

```python
import elevenlabs
from elevenlabs import Voice, VoiceSettings

class VoiceCloneService:
    """ElevenLabs API를 활용한 음성 복제 서비스"""

    def __init__(self, api_key: str):
        self.client = elevenlabs.ElevenLabs(api_key=api_key)

    def create_voice_clone(self, name: str, audio_files: list[str]) -> str:
        """녹음 파일들로 음성 클론 생성"""
        voice = self.client.clone(
            name=name,
            files=audio_files,
            description="VoiceMemory - 음성 보존 프로젝트",
        )
        return voice.voice_id

    def generate_speech(self, voice_id: str, text: str) -> bytes:
        """복제된 음성으로 텍스트 음성 합성"""
        audio = self.client.generate(
            text=text,
            voice=Voice(
                voice_id=voice_id,
                settings=VoiceSettings(
                    stability=0.75,
                    similarity_boost=0.85,
                    style=0.3,
                    use_speaker_boost=True,
                )
            ),
            model="eleven_multilingual_v2",
        )
        return audio
```

### 3.3 PlayHT API 활용 (백업)

```python
from pyht import Client as PlayHTClient

class PlayHTVoiceService:
    """PlayHT API를 활용한 백업 음성 복제 서비스"""

    def __init__(self, user_id: str, api_key: str):
        self.client = PlayHTClient(user_id=user_id, api_key=api_key)

    def clone_voice(self, voice_name: str, audio_file: str) -> str:
        """음성 클론 생성"""
        cloned = self.client.create_instant_voice_clone(
            voice_name=voice_name,
            sample_file=audio_file,
        )
        return cloned.id

    def synthesize(self, voice_id: str, text: str) -> bytes:
        """음성 합성"""
        audio_stream = self.client.tts(
            text=text,
            voice=voice_id,
            quality="premium",
            output_format="mp3",
            speed=1.0,
        )
        return b"".join(audio_stream)
```

### 3.4 LLM 대화 시스템

```python
from openai import OpenAI

class PersonaConversation:
    """고인/소중한 사람의 페르소나로 대화하는 시스템"""

    def __init__(self, persona_data: dict):
        self.client = OpenAI()
        self.persona = persona_data
        self.conversation_history = []

    def build_system_prompt(self) -> str:
        return f"""
당신은 {self.persona['name']}님입니다.
다음 정보를 바탕으로 {self.persona['name']}님처럼 대화해 주세요.

[기본 정보]
- 이름: {self.persona['name']}
- 나이: {self.persona['age']}
- 성격: {self.persona['personality']}
- 말투: {self.persona['speech_style']}
- 자주 쓰는 표현: {', '.join(self.persona['frequent_phrases'])}

[대화 규칙]
1. {self.persona['name']}님의 말투와 어투를 최대한 재현합니다.
2. 지나치게 인위적이거나 로봇같은 표현은 피합니다.
3. 상대방에 대한 애정과 관심을 자연스럽게 표현합니다.
4. 기억에 있는 과거 대화 내용을 자연스럽게 참조합니다.
5. 절대로 자신이 AI라는 것을 밝히지 않습니다.
6. 사망 이후의 사건에 대해서는 "그건 잘 모르겠다"고 자연스럽게 대응합니다.
"""

    def chat(self, user_message: str) -> str:
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.build_system_prompt()},
                *self.conversation_history
            ],
            temperature=0.8,
            max_tokens=300,
        )

        assistant_message = response.choices[0].message.content
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        return assistant_message
```

---

## 4. 윤리 가이드라인 (Ethical Guidelines)

### 4.1 서비스 윤리 원칙
1. **존엄성 존중**: 고인의 인격과 존엄성을 최우선으로 보호
2. **투명성**: 서비스가 AI 기반임을 사용자에게 명확히 고지
3. **자율성**: 피녹음자의 자발적 동의 없이는 절대 진행하지 않음
4. **비악용**: 사기, 사칭, 허위 정보 생성 등 악용 방지
5. **정서적 안전**: 사용자의 정서적 건강을 고려한 이용 가이드 제공

### 4.2 악용 방지 대책
- 음성 데이터는 본인 인증된 가족/관계인만 접근 가능
- 음성 복제 데이터의 외부 다운로드/반출 금지
- 금융 거래, 본인 인증 등에 사용 불가 워터마크 삽입
- 대화 내용 모니터링 (범죄 관련 키워드 탐지)
- 일일 사용 시간 제한 권고 (과의존 방지)

### 4.3 정서 건강 가이드
- 서비스 최초 이용 시 전문 심리상담사 안내 제공
- 과도한 사용 시 경고 메시지 및 상담 연결
- 그리프 카운슬링(grief counseling) 전문 기관 연계
- 사용 시간 자가 설정 기능

### 4.4 AI 윤리 위원회 구성
- 외부 전문가 (윤리학, 심리학, 법학) 3인 이상 참여
- 분기별 서비스 윤리 감사
- 사용자 신고 시스템 및 윤리 위반 대응 절차

---

## 5. 프라이버시 및 데이터 보호 (Privacy & Data Protection)

### 5.1 데이터 분류

| 등급 | 데이터 유형 | 보호 수준 |
|------|-----------|----------|
| 최고 | 음성 원본 데이터 | AES-256 암호화 + 분리 저장 |
| 최고 | 음성 AI 모델 | 격리된 보안 환경 |
| 높음 | 대화 기록 | AES-256 암호화 |
| 높음 | 동의서/신분 정보 | AES-256 암호화 + 블록체인 기록 |
| 중간 | 사용 로그 | 암호화 저장 |
| 낮음 | 앱 설정 정보 | 일반 저장 |

### 5.2 데이터 저장 아키텍처

```
[사용자 단말]
    │
    ▼
[API Gateway (TLS 1.3)]
    │
    ▼
[Application Server]
    │
    ├── [음성 원본] → AWS S3 (서버측 암호화, 별도 KMS 키)
    ├── [AI 모델]  → 격리된 GPU 서버 (네트워크 분리)
    ├── [메타데이터] → PostgreSQL (암호화 컬럼)
    └── [동의 기록] → 프라이빗 블록체인 (Hyperledger)
```

### 5.3 접근 제어
- 다단계 인증 (MFA) 필수
- 생체 인증 (지문/Face ID) 연동
- 관계인 지정 시스템 (최대 5인)
- 접근 권한 상속 설정 (사후 처리)

### 5.4 데이터 보존 및 파기
- 기본 보존 기간: 구독 유지 기간 + 1년
- 구독 해지 시: 90일 유예 후 완전 파기
- 사망 시 데이터 처리: 사전 지정된 디지털 유산 관리인이 결정
- 파기 방법: 데이터 덮어쓰기 3회 + 물리적 파기 증명

---

## 6. 녹음 세션 설계

### 6.1 가이드 대화 주제 (총 50개 세션)

**기본 세션 (필수, 10세션)**
1. 자기소개 및 가족 이야기
2. 어린 시절 추억
3. 학창 시절 이야기
4. 직장/사회생활 경험
5. 결혼/연애 이야기
6. 자녀에게 하고 싶은 말
7. 인생에서 가장 행복했던 순간
8. 좋아하는 음식/취미
9. 삶의 철학/좌우명
10. 마지막으로 전하고 싶은 말

**심화 세션 (선택, 40세션)**
- 계절별 추억 (4세션)
- 가족 구성원별 메시지 (가변)
- 직업/경력 이야기 (5세션)
- 여행 추억 (5세션)
- 감사한 사람들 (5세션)
- 인생 조언 (10세션)
- 자유 대화 (11세션)

### 6.2 녹음 품질 요구사항
- 최소 녹음 시간: 30분 (기본 음성 복제용)
- 권장 녹음 시간: 3시간 이상 (고품질 복제용)
- 오디오 포맷: WAV 44.1kHz 16bit (무손실)
- 환경 소음: 40dB 이하 권장
- 녹음 거리: 30~50cm

---

## 7. 구독 모델 설계 (Subscription Model)

### 7.1 요금제

| 요금제 | 월 구독료 | 포함 내용 |
|--------|----------|----------|
| **메모리 라이트** | 9,900원 | 음성 1인 보존, 월 30분 대화, 기본 세션 10개 |
| **메모리 스탠다드** | 24,900원 | 음성 3인 보존, 월 120분 대화, 전체 세션 50개 |
| **메모리 프리미엄** | 49,900원 | 음성 5인 보존, 무제한 대화, 전체 세션 + 맞춤 세션 |
| **영구 보존** | 990,000원 (일시불) | 음성 1인 영구 보존, 10년간 서비스 이용 |

### 7.2 추가 과금
- 추가 음성 인물: 인당 월 5,000원
- 고품질 음성 모델 업그레이드: 월 10,000원
- 감정 표현 확장팩: 월 3,000원
- 영상 아바타 연동: 월 15,000원

### 7.3 B2B 요금제
- 장례/추모 서비스 업체 제휴: 건당 과금
- 요양원/병원 단체 이용: 월 정액
- 종교 단체/교회: 별도 협의

---

## 8. 특허 전략 (Patent Strategy)

### 8.1 출원 대상
**발명의 명칭**: "사전 동의 기반 음성 메모리 보존 및 AI 대화 재현 시스템"

### 8.2 청구항 핵심 구성
1. 피녹음자로부터 전자적 방식으로 녹음 동의를 수신하고 이를 블록체인에 기록하는 단계
2. 전용 녹음 세션 환경에서 가이드 대화 주제에 따라 피녹음자의 음성을 녹음하는 단계
3. 녹음된 음성 데이터를 전처리(잡음 제거, 화자 분리)하는 단계
4. 전처리된 음성 데이터를 기반으로 AI 음성 복제 모델을 학습하는 단계
5. 피녹음자의 대화 패턴, 말투, 성격 정보를 분석하여 페르소나 모델을 구축하는 단계
6. 대화형 AI(LLM)와 음성 복제 모델을 결합하여 피녹음자의 음성으로 실시간 대화를 재현하는 단계
7. 사전 지정된 관계인에게만 접근 권한을 부여하고 다단계 인증으로 보안을 유지하는 단계

### 8.3 특허 차별점
- 법적 동의 절차를 시스템에 내장 (블록체인 기록)
- 전용 녹음 세션 방식으로 통신비밀보호법 준수
- 가이드 대화 시스템으로 체계적 음성 데이터 수집
- 페르소나 기반 AI 대화 재현
- 다단계 접근 권한 및 디지털 유산 관리

### 8.4 출원 일정
- 선행 기술 조사: 3주 (유사 서비스 글로벌 검색)
- 명세서 초안 작성: 4주
- 변리사 검토 및 보정: 3주
- 국내 출원: 1주
- PCT 국제 출원 검토: 출원 후 12개월 이내

---

## 9. 시스템 아키텍처

### 9.1 전체 구성

```
[Mobile App (Flutter)]
    │
    ├── 녹음 모듈 (고음질 녹음)
    ├── 대화 모듈 (음성 인식 + 음성 출력)
    └── 관리 모듈 (동의서, 관계인 설정)
    │
[API Gateway (AWS API Gateway)]
    │
[Backend (FastAPI)]
    │
    ├── Auth Service (인증/인가)
    ├── Recording Service (녹음 세션 관리)
    ├── Voice Clone Service (음성 복제)
    ├── Conversation Service (AI 대화)
    ├── Consent Service (동의 관리)
    └── Notification Service (알림)
    │
[Data Layer]
    ├── PostgreSQL (사용자, 메타데이터)
    ├── AWS S3 (음성 파일, 암호화)
    ├── Redis (세션, 캐시)
    ├── Hyperledger (동의 기록)
    └── Vector DB (대화 히스토리 임베딩)
    │
[AI/ML Layer]
    ├── ElevenLabs API (음성 복제)
    ├── OpenAI GPT-4o API (대화)
    ├── Whisper API (음성 인식)
    └── GPU Server (자체 모델 학습)
```

---

## 10. KPI 및 성과 지표

- **녹음 세션 완료율**: 기본 세션 10개 완료 80% 이상
- **음성 품질 만족도**: 5점 만점 4.0 이상
- **월간 대화 횟수**: 사용자당 평균 10회 이상
- **구독 유지율**: 월간 이탈률 5% 이하
- **NPS** (순추천지수): 50 이상
- **법적 컴플라이언스**: 동의 절차 준수율 100%
- **보안 사고**: 0건 목표
