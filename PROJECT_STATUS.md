# BIZ LIFE - 5대 프로젝트 통합 현황

**최종 업데이트**: 2026-02-15

## 프로젝트 요약

| # | 프로젝트 | 포트 | 파일수 | API | 상태 |
|---|---------|------|--------|-----|------|
| 1 | **PromoMap** (위치기반 할인) | :8000 | 57 | 20개+ | v2.0 리팩토링 완료 |
| 2 | **BarcodeQuest** (바코드 몬스터) | :8001 | 9 | 7개 | 전체 통과 |
| 3 | **VoiceMemory** (AI 음성 보존) | :8002 | 11 | 13개 | 전체 통과 |
| 4 | **CryptoBot** (암호화폐 트레이딩) | :8081 | 20+ | 8개+WS | v3.0 전략개선+WS실시간+24/7 |
| 5 | **StockBot** (주식 자동매매) | :8004 | 19 | 7개 | 전체 통과 |
| - | **shared** (공유 모듈) | - | 6 | - | 사용 중 |

**총 118개 Python 파일, 53개+ API 엔드포인트**

## 기술 스택 공통
- Python 3.13 + pip
- FastAPI + Uvicorn (모든 서버)
- SQLAlchemy + SQLite (개발용 DB)
- Jinja2 템플릿 + 인라인 HTML (Node.js 불필요)
- JWT 인증 (shared 모듈)
- bcrypt 비밀번호 해싱 (shared 모듈)

## 빠른 실행 가이드
```bash
# 1. PromoMap
cd projects/01-promo-map/backend && python main.py  # http://localhost:8000

# 2. BarcodeQuest
cd projects/02-barcode-game/backend && python main.py  # http://localhost:8001

# 3. VoiceMemory
cd projects/03-voice-memory/backend && python main.py  # http://localhost:8002

# 4. CryptoBot (v3.0 - WebSocket + 3분봉 스캘퍼)
cd projects/04-crypto-trader && python -m scalper.run --with-dashboard  # http://localhost:8081

# 5. StockBot
cd projects/05-stock-trader/dashboard && python app.py  # http://localhost:8004
```

## 테스트 중 수정된 버그

| 프로젝트 | 문제 | 수정 내용 |
|---------|------|----------|
| shared | passlib + bcrypt Python 3.13 호환성 | passlib 제거, bcrypt 직접 사용 |
| PromoMap | auth.py와 shared/auth 모듈 이름 충돌 | auth.py → auth_routes.py 이름 변경 |
| PromoMap | shared 모듈 우선순위 문제 | sys.path.insert → sys.path.append |
| CryptoBot | dashboard analyze 응답 키 불일치 | consensus → action, avg_confidence → confidence |
| StockBot | OHLCV DataFrame 길이 불일치 | freq="B" → len(dates) 사용 |
| StockBot | /api/history 엔드포인트 누락 | 엔드포인트 추가 |

## 디렉터리 구조
```
biz_life/
├── PROJECT_STATUS.md          ← 이 파일
├── shared/                    # 공유 모듈
│   ├── auth/                  # JWT, bcrypt
│   └── utils/                 # 로거, 설정 로더
├── projects/
│   ├── 01-promo-map/          # 위치기반 임직원 할인
│   ├── 02-barcode-game/       # 바코드 몬스터 수집 게임
│   ├── 03-voice-memory/       # AI 음성 보존 서비스
│   ├── 04-crypto-trader/      # 암호화폐 자동매매
│   └── 05-stock-trader/       # 주식 자동매매
└── docs/                      # 마스터플랜, 기획서
```

## 각 프로젝트별 상세 현황
각 프로젝트 폴더의 `PROJECT_STATUS.md` 참조.
