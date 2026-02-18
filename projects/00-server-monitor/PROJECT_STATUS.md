# Server Monitor v1.0 - 프로젝트 현황

**최종 업데이트**: 2026-02-17

## 개요
노트북을 홈서버로 운영하기 위한 **통합 모니터링 + 제어 시스템**.
FastAPI 웹 대시보드(포트 9000)와 텔레그램 봇을 통해 6개 biz_life 프로젝트의 상태 확인, 시작/중지/재시작, 시스템 리소스 모니터링을 원격으로 수행.

## 기술 스택
- **Backend**: Python 3.13, FastAPI + Uvicorn (포트 9000)
- **텔레그램 봇**: python-telegram-bot 22.5
- **시스템 모니터링**: psutil (CPU, RAM, Disk)
- **HTTP 헬스체크**: httpx (비동기)
- **프로세스 관리**: subprocess + psutil (Windows)

## 실행 방법
```bash
cd projects/00-server-monitor

# 웹 대시보드 실행
python app.py
# -> http://localhost:9000

# 텔레그램 봇 실행
python bot.py
# -> .env에 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 필요
```

## 파일 구조
```
00-server-monitor/
├── app.py              # FastAPI 웹 대시보드 (포트 9000)
├── bot.py              # 텔레그램 서버 관리 봇
├── config.py           # 프로젝트 설정 (포트, 실행 명령)
├── .env                # 텔레그램 토큰 (git 미추적)
├── requirements.txt    # 의존성
├── logs/               # 로그 디렉토리
└── PROJECT_STATUS.md   # <- 이 파일
```

## 관리 대상 프로젝트

| # | 프로젝트 | 포트 | 설명 |
|---|---------|------|------|
| 01 | promo-map | :8000 | 프로모션 지도 |
| 02 | barcode-game | :8001 | 바코드 게임 |
| 03 | voice-memory | :8002 | 음성 메모리 |
| 04 | crypto-trader | :8081 | 암호화폐 트레이더 |
| 05 | stock-trader | :8082 | 주식 트레이더 |
| 06 | home-finder | :8006 | 집 찾기 |

## 웹 대시보드 기능 (포트 9000)

### API 엔드포인트 (6개)
| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 대시보드 UI (시스템 리소스 + 프로젝트 카드) |
| GET | `/api/status` | 전체 상태 JSON (시스템 + 프로젝트) |
| POST | `/api/start/{name}` | 프로젝트 시작 |
| POST | `/api/stop/{name}` | 프로젝트 중지 (graceful, 5초 타임아웃) |
| POST | `/api/restart/{name}` | 프로젝트 재시작 (2초 대기) |

### 대시보드 UI
- **시스템 리소스**: CPU 사용률, RAM 사용량, Disk(C:) 사용량 + 색상 게이지
- **프로젝트 카드**: 상태 표시(실행/중지), 시작/중지/재시작 버튼, 브라우저 열기 링크
- **전체 제어**: 전체 시작/중지/재시작 버튼
- **로그 뷰어**: 각 프로젝트의 최근 15줄 로그 (토글)
- **자동 새로고침**: 30초 주기

## 텔레그램 봇 명령어 (8개)

| 명령 | 설명 |
|------|------|
| `/start` | 봇 도움말 |
| `/status` | 전체 프로젝트 상태 (실행/중지 아이콘) |
| `/system` | CPU, RAM, Disk 리소스 |
| `/begin <프로젝트>` | 프로젝트 시작 (`/start`는 봇 예약어) |
| `/stop <프로젝트>` | 프로젝트 중지 |
| `/restart <프로젝트>` | 프로젝트 재시작 |
| `/logs <프로젝트>` | 최근 10줄 로그 |
| `/panel` | 인라인 버튼 제어 패널 |

### 보안
- `TELEGRAM_CHAT_ID`로 허용된 사용자만 명령 실행 가능
- 미설정 시 모든 사용자 접근 가능 (경고 출력)

## 주요 기능 체크리스트
- [x] FastAPI 웹 대시보드 (포트 9000)
- [x] 실시간 프로젝트 상태 확인 (비동기 헬스체크)
- [x] 프로세스 관리 (시작/중지/재시작)
- [x] 시스템 리소스 모니터링 (CPU, RAM, Disk)
- [x] 텔레그램 봇 원격 제어 (8개 명령)
- [x] 인라인 키보드 제어 패널
- [x] 로그 뷰어
- [x] 인증 (Chat ID 기반)

## 향후 과제
- [ ] 리소스 임계치 자동 알림 (CPU/RAM 90% 초과 시 텔레그램 알림)
- [ ] 프로젝트 자동 재시작 (크래시 감지)
- [ ] 리소스 사용 이력 그래프 (시계열 DB)
- [ ] Windows 서비스 등록 (자동 시작)
- [ ] Cloudflare Tunnel 통합 (외부 접근)
- [ ] 00-server-monitor 자체 모니터링 (Watchdog)
