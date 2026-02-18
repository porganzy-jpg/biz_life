# BIZ LIFE - 프로젝트 통합 현황

**최종 업데이트**: 2026-02-17

## 프로젝트 요약

| # | 프로젝트 | 포트 | 파일수 | API | 상태 |
|---|---------|------|--------|-----|------|
| 0 | **ServerMonitor** (통합 모니터링) | :9000 | 4 | 6개 | v1.0 대시보드+텔레그램 |
| 1 | **PromoMap** (위치기반 할인) | :8000 | 57 | 20개+ | v2.0 리팩토링 완료 |
| 2 | **BarcodeQuest** (바코드 몬스터) | :8001 | 9 | 7개 | 전체 통과 |
| 3 | **VoiceMemory** (AI 음성 보존) | :8002 | 11 | 13개 | 전체 통과 |
| 4 | **CryptoBot** (암호화폐 트레이딩) | :8081 | 22+ | 8개+WS | v4.0 동적마켓스캐너+적응형최적화 |
| 5 | **StockBot** (주식 자동매매) | :8082 | 19 | 12개 | v2.0 실전 전환 |
| 6 | **HomeFinder** (마지막 집 찾기) | :8006 | 90+ | 10개+ | v1.5 토지 매물 추가 |
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
# 0. ServerMonitor (통합 관리 + 텔레그램 봇)
cd projects/00-server-monitor && python app.py       # http://localhost:9000
cd projects/00-server-monitor && python bot.py       # 텔레그램 봇

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

# 6. HomeFinder (v1.5 - 건물 + 토지)
cd projects/06-home-finder && python main.py          # http://localhost:8006

# 전체 일괄 시작
startup_all.bat
```

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
│   └── 07-Novel/              # 자유투 소설 집필
└── docs/                      # 마스터플랜, 기획서, 진행 보고서
```

## 각 프로젝트별 상세 현황
각 프로젝트 폴더의 `PROJECT_STATUS.md` 참조.
