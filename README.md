# BIZ LIFE - 퇴직 후 6대 사업 프로젝트 + 서버 인프라

> 기술 기반 6개 사업 프로젝트 + 통합 서버 모니터링의 개발 레포지토리

## 프로젝트 목록

| # | 이름 | 설명 | 포트 | 상태 |
|---|------|------|------|------|
| 00 | **ServerMonitor** | 통합 서버 모니터링 + 텔레그램 제어 | :9000 | v1.0 운영 중 |
| 01 | **PromoMap** | 위치 기반 임직원 할인 프로모션 앱 | :8000 | v2.0 완료 |
| 02 | **BarcodeQuest** | 바코드 스캔 기반 몬스터 수집 게임 | :8001 | API 완료 |
| 03 | **VoiceMemory** | AI 음성 보존 서비스 | :8002 | API 완료 |
| 04 | **CryptoBot** | 암호화폐 자동매매 스캘핑 봇 | :8081 | v4.0 운영 중 |
| 05 | **StockBot** | 주식 자동매매 봇 (8전략 앙상블) | :8082 | v2.0 완료 |
| 06 | **HomeFinder** | 마지막 집 찾기 (건물 + 토지) | :8006 | v1.5 토지 추가 |
| 07 | **Novel** | 자유투 소설 집필 | - | 집필 중 |

## 기술 스택
- **Backend**: Python 3.13, FastAPI + Uvicorn
- **Frontend**: Jinja2 + 인라인 HTML/JS, Flutter (PromoMap)
- **Database**: SQLAlchemy + SQLite (개발), PostgreSQL (배포)
- **AI/ML**: OpenAI API (감성분석, 페르소나)
- **Trading**: pyupbit, mojito SDK, TA-Lib
- **모니터링**: psutil, python-telegram-bot
- **인프라**: Cloudflare Tunnel, Windows 서비스

## 빠른 시작

```bash
# 레포지토리 클론
git clone git@github.com:porganzy-jpg/biz_life.git

# 0. 서버 모니터 (전체 프로젝트 관리)
cd projects/00-server-monitor && python app.py      # http://localhost:9000

# 1~6. 개별 프로젝트 실행
cd projects/01-promo-map/backend && python main.py   # http://localhost:8000
cd projects/04-crypto-trader && python -m scalper.run --with-dashboard  # http://localhost:8081
cd projects/06-home-finder && python main.py         # http://localhost:8006

# 전체 일괄 시작
startup_all.bat
```

## 문서
- [마스터 기획서](docs/master-plan/MASTER_PLAN.md)
- [특허 전략](docs/patents/)
- [진행 보고서](docs/)

## 로드맵
- **Phase 1** (1-2개월): CryptoBot 프로토타입 + 실전 테스트
- **Phase 2** (2-4개월): PromoMap MVP + StockBot 기본
- **Phase 3** (4-8개월): BarcodeQuest 프로토타입 + 특허 출원
- **Phase 4** (8-12개월): VoiceMemory PoC
- **Phase 5** (12개월+): 고도화 및 사업화
