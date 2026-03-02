# BIZ LIFE - 프로젝트 통합 현황

**최종 업데이트**: 2026-03-03

## 프로젝트 요약

| # | 프로젝트 | 포트 | 파일수 | API | 상태 |
|---|---------|------|--------|-----|------|
| 0 | **ServerMonitor** (통합 모니터링) | :9000 | 6 | 6개 | v2.1 안정화+재시도제한+CMD깜빡임수정 |
| 1 | **PromoMap** (위치기반 할인) | :8000 | 57 | 20개+ | v2.0 리팩토링 완료 |
| 2 | **BarcodeQuest** (바코드 몬스터) | :8001 | 9+110 | 7개 | 수채화 아트 업그레이드 |
| 3 | **VoiceMemory** (AI 음성 보존) | :8002 | 11 | 13개 | 전체 통과 |
| 4 | **CryptoBot** (암호화폐 트레이딩) | :8081 | 22+ | 8개+WS | v4.0 동적마켓스캐너+적응형최적화 |
| 5 | **StockBot** (주식 자동매매) | :8082 | 19 | 12개 | v2.0 실전 전환 |
| 6 | **HomeFinder** (마지막 집 찾기) | :8006 | 90+ | 10개+ | v2.0 토지 CRUD UI + 검색필터 강화 |
| 7 | **자유투** (장편소설) | - | 55+ | - | 4권 27장 완성 + 퇴고 완료 |
| - | **shared** (공유 모듈) | - | 6 | - | 사용 중 |

**총 220개+ Python 파일, 76개+ API 엔드포인트**

## 기술 스택 공통
- Python 3.13 + pip
- FastAPI + Uvicorn (모든 서버)
- SQLAlchemy + SQLite (개발용 DB)
- Jinja2 템플릿 + 인라인 HTML (Node.js 불필요)
- JWT 인증 (shared 모듈)
- bcrypt 비밀번호 해싱 (shared 모듈)

## 빠른 실행 가이드
```bash
# 0. ServerMonitor (통합 런처: 대시보드 + 봇 + 모니터링)
cd projects/00-server-monitor && python main.py      # http://localhost:9000

# 1. PromoMap
cd projects/01-promo-map/backend && python main.py   # http://localhost:8000

# 2. BarcodeQuest
cd projects/02-barcode-game/backend && python main.py # http://localhost:8001

# 3. VoiceMemory
cd projects/03-voice-memory/backend && python main.py # http://localhost:8002

# 4. CryptoBot (v4.0 - 동적 마켓 + 적응형 최적화)
cd projects/04-crypto-trader && python -m scalper.run --with-dashboard  # http://localhost:8081

# 5. StockBot (v2.0 - 8전략 앙상블)
cd projects/05-stock-trader/dashboard && python app.py # http://localhost:8082

# 6. HomeFinder (v2.0 - 건물 + 토지 CRUD)
cd projects/06-home-finder && python main.py          # http://localhost:8006

# 전체 일괄 시작
startup_all.bat
```

## 2026-03-03 변경사항

| 프로젝트 | 변경 내용 |
|---------|----------|
| **02-BarcodeQuest** | 수채화 판타지 아트 업그레이드: 캐릭터 10장 + 몬스터 100장 자동 생성, makePixelArtSVG→makeMonsterImage 전면 교체, CSS 색상변형/희귀도글로우/홀로그래픽, 이모지 폴백 |

## 2026-02-18 변경사항

| 프로젝트 | 변경 내용 |
|---------|----------|
| **00-ServerMonitor** | v2.1 - 시작검증 + 안전재시작 + CREATE_NO_WINDOW + 재시도제한3회 |
| **01-PromoMap** | Python 3.13 업그레이드 + N+1 쿼리 수정 + FK 인덱스 추가 |
| **02-BarcodeQuest** | 몬스터 레벨링 시스템 + 파티 관리 API |
| **03-VoiceMemory** | 세션 완료 API + 동의 철회 연쇄 삭제 (개인정보보호법) |
| **04-CryptoBot** | 가격 캐시 (API 60%↓) + 조기 손실 매도 신호 |
| **05-StockBot** | 섹터 한도 정상화 + 매매 건너뜀 로깅 |
| **06-HomeFinder** | v2.0 토지 CRUD + N+1 쿼리 수정 + 검색 쿼리 중복 제거 |
| **07-자유투(소설)** | 전체 퇴고 완료 + GitHub 저장소(free-throw-novel) 생성 |
| **인프라** | Python 3.13 전체 업그레이드, gh CLI, Tailscale, 보안 점검, 노트북 서버화 |

## 2026-02-17 변경사항

| 프로젝트 | 변경 내용 |
|---------|----------|
| **00-ServerMonitor** | 신규 프로젝트 - 웹 대시보드 + 텔레그램 봇으로 6개 프로젝트 통합 관리 |
| **04-CryptoBot** | requirements.txt 버전 유연화, start_bot.bat 경로 수정 |
| **05-StockBot** | 포트 8081→8082 변경, paper_trading→실전 전환, requirements.txt 유연화 |
| **06-HomeFinder** | 토지 매물 전체 기능 추가 (DB 7컬럼 + API 필터 + 5차원 채점 + 프론트엔드 UI) |

## 디렉터리 구조
```
biz_life/
├── PROJECT_STATUS.md          ← 이 파일
├── README.md
├── startup_all.bat            # 전체 프로젝트 일괄 시작
├── setup_firewall.bat         # Windows 방화벽 설정
├── shared/                    # 공유 모듈
│   ├── auth/                  # JWT, bcrypt
│   └── utils/                 # 로거, 설정 로더
├── projects/
│   ├── 00-server-monitor/     # 통합 모니터링 + 텔레그램 봇 (NEW)
│   ├── 01-promo-map/          # 위치기반 임직원 할인
│   ├── 02-barcode-game/       # 바코드 몬스터 수집 게임
│   ├── 03-voice-memory/       # AI 음성 보존 서비스
│   ├── 04-crypto-trader/      # 암호화폐 자동매매
│   ├── 05-stock-trader/       # 주식 자동매매
│   ├── 06-home-finder/        # 마지막 집 찾기 (건물+토지)
│   └── 07-Novel/              # 자유투 소설 (기획 자료)
├── docs/                      # 마스터플랜, 기획서, 진행 보고서
└── ~/자유투/                   # 자유투 소설 원고 (별도 Git 저장소)
```

## 각 프로젝트별 상세 현황
각 프로젝트 폴더의 `PROJECT_STATUS.md` 참조.
