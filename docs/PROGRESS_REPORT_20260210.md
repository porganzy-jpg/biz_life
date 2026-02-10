# BIZ LIFE 프로젝트 진행 보고서

> **보고일**: 2026-02-10
> **버전**: v1.0
> **상태**: 전 프로젝트 기반 구축 완료 + BarcodeQuest 디자인 확장 완료

---

## 1. 전체 진행 현황 요약

### 1.1 프로젝트 포트폴리오 현황

| # | 프로젝트 | 상태 | 완성도 | 다음 단계 |
|---|---------|------|--------|----------|
| 1 | **PromoMap** (위치기반 할인앱) | v2.0 리팩토링 완료 | 85% | Flutter 앱 배포, 실 데이터 연동 |
| 2 | **BarcodeQuest** (바코드 몬스터 게임) | 디자인 컨셉 + 게임엔진 완료 | 60% | 프론트엔드 개발, 서버 연동 |
| 3 | **VoiceMemory** (AI 음성 보존) | 백엔드 + AI 모델 기반 완료 | 40% | 실 AI 모델 연동, 음성 데이터 파이프라인 |
| 4 | **CryptoBot** (암호화폐 자동매매) | 스캘핑 봇 + 6전략 앙상블 완성 | 75% | 실전 API 키 연동, Paper Trading |
| 5 | **StockBot** (주식 자동매매) | 5전략 앙상블 + 뉴스 분석 기반 완료 | 45% | **실전 업그레이드 예정** |

### 1.2 기술 인프라 현황

| 구성요소 | 상태 | 비고 |
|---------|------|------|
| Git Repository | ✅ 운영 중 | github.com:porganzy-jpg/biz_life.git |
| Python 3.13 | ✅ 설치 완료 | 전 프로젝트 공통 |
| FastAPI 서버 | ✅ 5개 프로젝트 가동 | 포트 8000~8004 |
| 공유 모듈 (JWT/bcrypt) | ✅ 구현 완료 | shared/ 디렉터리 |
| Docker 인프라 | ✅ 기본 설정 | docker-compose.yml |
| 문서화 | ✅ 마스터플랜 + 특허초안 | docs/ 디렉터리 |

---

## 2. 프로젝트별 상세 진행 내역

### 2.1 PromoMap (프로젝트 01) - 위치기반 임직원 할인앱

**달성 사항:**
- FastAPI 백엔드 완전 구현 (20개+ API 엔드포인트)
- Repository-Service-Schema 3계층 아키텍처 적용
- Flutter 모바일 앱 전체 프레임워크 구축 (137개 파일)
  - AdMob 광고 통합
  - Dio HTTP 클라이언트 + Auth Interceptor
  - Riverpod 상태관리
  - 카카오맵 연동 준비
- 관리자 대시보드 (HTML 템플릿 7개 화면)
- 지오펜싱(Geofencing) 시스템 구현
- 배포 가이드 (DEPLOY.md) + 아키텍처 문서 (ARCHITECTURE.md)

**파일 수:** 201개 | **API:** 20개+ | **포트:** 8000

---

### 2.2 BarcodeQuest (프로젝트 02) - 바코드 몬스터 수집 게임

**달성 사항:**

#### A. 게임 컨셉 기획 (30개 시놉시스)
- 5개 카테고리 × 6개씩 총 30개 게임 컨셉 시놉시스 작성
  - (A) 감정과 내면 | (B) 기억과 시간 | (C) 성장과 변화 | (D) 인연과 관계 | (E) 꿈과 일상
- 각 컨셉별 제목, 스토리, 크리처 디자인 방향, 바코드 연동 방식, 감성 키워드 포함
- TOP 5 추천 + 4개 하이브리드 믹스 제안

#### B. 핵심 게임 시스템 코딩 (7개 모듈)
| 모듈 | 파일 | 기능 |
|------|------|------|
| 바코드 몬스터 생성기 | barcode_monster_generator.py | 바코드 → 몬스터 변환 알고리즘 |
| 배틀 시스템 | battle_system.py | 턴제 전투 + 스킬 시스템 |
| 컬렉션 | collection.py | 도감 + 수집 시스템 |
| 원정 시스템 | expedition_system.py | 탐험 + 보상 시스템 |
| 아이템 시스템 | item_system.py | 장비 + 소비 아이템 |
| 진화 시스템 | evolution_system.py | 다단계 진화 + 분기 진화 |
| 일일 퀘스트 | daily_quest_system.py | 데일리 미션 + 보상 |

#### C. 몬스터 타입 디자인 시트 (8개 타입, SVG 이미지)

**핵심 컨셉:** "한때 '선택된 아이들'이었던 어른들이 성장하며 안타깝게 헤어진 추억의 동심을 찾아가는 이야기"

| 파일 | 타입 | 테마 | 변형 수 |
|------|------|------|---------|
| M01_로봇메카_타입_몬스터.svg | Robot/Mecha | 토요일 아침 TV 앞의 꿈 | 4 (Tank Bot, Sky Wing, Fix Bot, Ancient Gear★) |
| M02_마법소녀_타입_몬스터.svg | Magical Girl | 서랍 속 변신 완구 | 4 (Ribbon, Crystal, Luna Cat, Prism★) |
| M03_열혈소년만화_타입_몬스터.svg | Hot-blooded/Shonen | 필살기를 따라하던 열정 | 4 (Fist Fighter, Dash, Guard Spirit, Dragon Fist★) |
| M04_봉제인형토이_타입_몬스터.svg | Plush Toy/Doll | 다락방 곰인형 + 킨츠기 미학 | 4 (Knit Bunny, Tin Soldier, Sock Pal, Golden Bear★) |
| M05_레트로게임_타입_몬스터.svg | Retro Game/Pixel | 오락실 동전과 이불 속 게임보이 | 4 (Slime, Invader, Ghost, Pixel Dragon★) |
| M06_동화그림책_타입_몬스터.svg | Storybook/Fairy Tale | 잠자리 동화책 삽화 | 6 (Story Fox, Mushroom Sprite, Cloud Sheep, Candy Witch, Star Knight, Golden Dragon★) |
| M07_괴수특촬_타입_몬스터.svg | Kaiju/Tokusatsu | 소프비 피규어로 놀던 시절 | 4 (Moth Queen, Mecha Rex, Deep One, Cosmos King★) |
| M08_탐험모험_타입_몬스터.svg | Explorer/Adventure | 뒷산이 정글이던 탐험가 시절 | 4 (Sand Scout, Deep Diver, Sky Nav, World Walker★) |

**디자인 철학:**
- **Stage 1 (잊혀진 상태):** 바래고, 닳고, 부서진 상태 — 잊혀진 어린 시절의 친구
- **Stage 3 (각성 상태):** 유대가 깊어져 빛나고, 복원된 상태 — 킨츠기(금수선) 미학
- 각 타입별 고유 컬러 팔레트 + 추억 연결 콘셉트 문구

#### D. 일반 디자인 컨셉 (10개 SVG)
| 파일 | 내용 |
|------|------|
| 01_마음날씨_컬러팔레트.svg | 감정별 컬러 팔레트 |
| 02_수묵화풍_아트스타일.svg | 아트 스타일 가이드 |
| 03_추억필름_무드보드.svg | 무드보드 |
| 04_바코드_UI_방향성.svg | UI 디자인 방향 |
| 05_로고_컨셉_시안.svg | 로고 컨셉 |
| 06_카드_컬렉션_UI.svg | 카드 수집 UI |
| 07_세계관_환경_컨셉.svg | 월드 환경 컨셉 |
| 08_크리처_타입_시스템.svg | 타입 시스템 |
| 09_진화_비주얼_컨셉.svg | 진화 시각 효과 |
| 10_바코드_스캔_UX플로우.svg | 스캔 UX 플로우 |

**파일 수:** 41개 | **API:** 7개 | **포트:** 8001

---

### 2.3 VoiceMemory (프로젝트 03) - AI 음성 보존 서비스

**달성 사항:**
- 음성 처리 파이프라인 (audio_processor.py)
- 음성 복제 서비스 프레임워크 (voice_clone_service.py)
- 페르소나 채팅 시스템 (persona_chat.py)
- 동의 관리 서비스 (consent_service.py)
- 녹음 서비스 (recording_service.py)
- FastAPI 백엔드 + DB 모델

**파일 수:** 13개 | **API:** 13개 | **포트:** 8002

---

### 2.4 CryptoBot (프로젝트 04) - 암호화폐 자동매매

**달성 사항:**
- **스캘핑 봇 완전 구현** (고급 모듈)
  - 6가지 전략 앙상블: EMA Crossover, RSI+BB Scalp, Stochastic RSI, VWAP+Volume, 앙상블
  - 실시간 Upbit 클라이언트
  - 서킷 브레이커 (비상 정지)
  - 리스크 매니저 (자금 관리)
  - 알림 시스템 (Telegram)
  - 백테스터
  - Streamlit 대시보드
- **레거시 전략 모듈** (5가지)
  - 볼린저+RSI, MACD, 이동평균, 변동성 돌파, 전략 앙상블
- **기술 분석 문서** (17,815 bytes)

**파일 수:** 35개 | **API:** 6개 | **포트:** 8003

---

### 2.5 StockBot (프로젝트 05) - 주식 자동매매

**달성 사항:**
- 5가지 퀀트 전략 앙상블 (볼린저, RSI, MACD, 이동평균, 기관수급)
- 한국투자증권 API 래핑 (mojito SDK, 시뮬레이션 모드)
- 뉴스 크롤러 (네이버 금융 + RSS)
- 감성 분석 (키워드 기반 + OpenAI 옵션)
- 포트폴리오 리스크 관리
- 웹 대시보드 + 백테스팅

**파일 수:** 20개 | **API:** 7개 | **포트:** 8004

**향후 강화 예정:**
- 한국투자증권 실전 API 연동
- 실시간 호가 WebSocket
- 기관/외국인 실제 수급 데이터
- 고급 전략 추가 (모멘텀, 페어 트레이딩, 머신러닝)
- 포트폴리오 자동 리밸런싱
- 스케줄러 기반 자동 실행

---

## 3. 생성 문서 목록

| 경로 | 문서명 | 크기 | 설명 |
|------|--------|------|------|
| docs/master-plan/MASTER_PLAN.md | 마스터플랜 | 12.9KB | 5대 프로젝트 종합 전략 |
| docs/02-BarcodeQuest_게임기획서.md | 게임기획서 | 22.4KB | BarcodeQuest 상세 기획 |
| docs/02-BarcodeQuest_컨셉_시놉시스_30.md | 컨셉 시놉시스 | 46.9KB | 30개 게임 컨셉 |
| docs/04-CryptoBot_기술분석_문서.md | CryptoBot 기술문서 | 17.8KB | 스캘핑 봇 기술 분석 |
| docs/patents/01_barcode_game_patent_draft.md | 특허초안 #1 | 7.3KB | 바코드 게임 특허 |
| docs/patents/02_promo_map_patent_draft.md | 특허초안 #2 | 2.2KB | 프로모맵 특허 |

---

## 4. Git 커밋 이력

| 해시 | 메시지 | 일자 |
|------|--------|------|
| 8329eb7 | Initial commit: BIZ LIFE 5대 프로젝트 기반 구축 | 2026-02-06 |
| 537e81a | feat: PromoMap Flutter 앱 + 백엔드 + 배포 인프라 + 광고 통합 | 2026-02-07 |
| 3c2e851 | feat: 전 프로젝트 핵심 모듈 구현 + CryptoBot 스캘핑 봇 완성 | 2026-02-07 |
| (예정) | feat: BarcodeQuest 몬스터 디자인 + 게임시스템 확장 + StockBot 강화 | 2026-02-10 |

---

## 5. 총 프로젝트 규모

| 지표 | 수치 |
|------|------|
| 전체 파일 수 | 310+ |
| Python 소스 파일 | 118+ |
| API 엔드포인트 | 53+ |
| SVG 디자인 에셋 | 18개 |
| 문서 파일 | 7개 (99KB+) |
| Git 커밋 | 3개 (4번째 예정) |
| Flutter Dart 파일 | 137+ |
| HTML 템플릿 | 16+ |

---

## 6. 다음 단계 (Next Steps)

### 즉시 실행 (2026-02-10~)
1. **StockBot 실전 업그레이드** ← 현재 진행
   - 한국투자증권 실전 API 연동
   - 고급 전략 추가 (모멘텀, 듀얼 모멘텀, 변동성 타겟팅)
   - 실시간 데이터 파이프라인
   - 자동 스케줄러 (장 시작/종료 연동)
   - 고급 대시보드 (포트폴리오 시각화)

### 단기 목표 (1~2주)
2. StockBot Paper Trading 시작
3. CryptoBot 실전 API 키 연동
4. BarcodeQuest 프론트엔드 프로토타입

### 중기 목표 (1~3개월)
5. StockBot 소액 실전 전환
6. PromoMap 베타 배포
7. VoiceMemory AI 모델 실연동

---

*본 보고서는 BIZ LIFE 프로젝트의 2026-02-10 기준 진행 현황을 정리한 것입니다.*
