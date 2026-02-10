# StockBot v2.0 - 프로젝트 현황

## 개요
한국 주식 자동매매 봇. **8가지 퀀트 전략 앙상블** + 뉴스 감성 분석 + 서킷브레이커 + SQLite DB 영속성.
한국투자증권 API(mojito SDK) 연동, Telegram 알림, 장 시간 자동 스케줄러.

## v2.0 업그레이드 내역 (2026-02-10)
- **전략 확장**: 5전략 → 8전략 (모멘텀, 듀얼모멘텀, 변동성타겟 추가)
- **뉴스 크롤러**: 네이버 금융 실제 크롤링 + Google News RSS
- **서킷브레이커**: 일일 손실한도, 연속 손실, 일일 거래횟수 제한
- **DB 영속성**: SQLite (거래이력, 포지션, 일일성과, 뉴스감성)
- **텔레그램 알림**: 매매 체결, 일일 리포트, 서킷브레이커 발동
- **스케줄러**: 장 시간 연동 자동 매매 (08:30 사전분석 ~ 16:00 일일리포트)
- **트레일링 스탑**: 고점 대비 -5% 자동 매도
- **대시보드 v2**: 서킷브레이커 UI, 통계 테이블, 뉴스 감성 표시

## 기술 스택
- **Backend**: Python 3.13, FastAPI (대시보드)
- **증권 연동**: mojito SDK (한국투자증권 Open API)
- **분석**: pandas, numpy, ta (기술적 분석)
- **뉴스**: requests, beautifulsoup4, feedparser (크롤링)
- **감성 분석**: 키워드 기반 + OpenAI GPT (옵션)
- **DB**: SQLite (WAL 모드)
- **알림**: Telegram Bot API

## 실행 방법
```bash
# 대시보드 실행
cd projects/05-stock-trader/dashboard
python app.py
# → http://localhost:8081

# CLI 자동매매 실행
cd projects/05-stock-trader/trading-bot
python trader.py

# .env 파일에 API 키 설정
cp .env.example .env
# KIS_APP_KEY, KIS_APP_SECRET, TELEGRAM_BOT_TOKEN 등 입력
```

## 파일 구조
```
05-stock-trader/
├── strategy/                      # 8가지 퀀트 전략
│   ├── base_strategy.py           # StockSignal + BaseStockStrategy ABC
│   ├── bollinger_strategy.py      # 볼린저밴드 %B 전략
│   ├── rsi_strategy.py            # RSI 과매수/과매도 전략
│   ├── macd_strategy.py           # MACD 크로스 전략
│   ├── ma_strategy.py             # 이동평균선 정배열/역배열
│   ├── institutional_flow.py      # 기관/외국인 수급 분석 (OBV 기반)
│   ├── momentum_strategy.py       # [NEW] 모멘텀 전략 (1M/3M/6M)
│   ├── dual_momentum.py           # [NEW] 듀얼 모멘텀 (절대+상대)
│   ├── volatility_target.py       # [NEW] 변동성 타겟팅
│   ├── stock_selector.py          # 8전략 앙상블 (가중 스코어링)
│   └── backtester.py              # 주식 백테스터
├── trading-bot/
│   ├── config.py                  # 한투 API + 매매 + 서킷브레이커 설정
│   ├── broker_client.py           # 한국투자증권 API 클라이언트 (시뮬레이션)
│   ├── trader.py                  # [v2.0] StockTrader (스케줄러+DB+알림)
│   ├── risk_manager.py            # 포트폴리오 리스크 관리
│   ├── database.py                # [NEW] SQLite DB 영속성
│   ├── circuit_breaker.py         # [NEW] 서킷브레이커 (비상 정지)
│   ├── alert_system.py            # [NEW] 텔레그램 알림
│   ├── scheduler.py               # [NEW] 장 시간 자동 스케줄러
│   └── stock_analyzer.py          # 퀀트 분석기 + 뉴스 감성 분석
├── news/
│   ├── crawler.py                 # [v2.0] 네이버 금융 + RSS 실제 크롤링
│   └── sentiment.py               # 감성 분석 (키워드 + OpenAI)
├── dashboard/
│   └── app.py                     # [v2.0] FastAPI 대시보드 (12개 API)
├── .env.example                   # 환경변수 (한투+OpenAI+Telegram)
├── docs/
│   └── PROJECT_PLAN.md
├── requirements.txt
└── PROJECT_STATUS.md              # ← 이 파일
```

## API 엔드포인트 (대시보드, 12개)
| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 대시보드 UI |
| GET | `/api/status` | 봇 상태 (잔고, 포지션, 서킷브레이커) |
| GET | `/api/scan` | 워치리스트 15종목 분석 |
| GET | `/api/analyze/{symbol}` | 특정 종목 분석 |
| GET | `/api/history` | 거래 이력 (DB) |
| GET | `/api/performance` | 일일 성과 (30일) |
| GET | `/api/stats` | 거래 통계 (7일/30일/전체) |
| POST | `/api/bot/start` | 자동매매 시작 (스케줄러) |
| POST | `/api/bot/stop` | 자동매매 중지 |
| POST | `/api/cycle` | 1회 매매 사이클 실행 |
| POST | `/api/circuit-breaker/reset` | 서킷브레이커 해제 |

## 8가지 전략 앙상블
| 전략 | 가중치 | 설명 |
|------|--------|------|
| 볼린저밴드 | 0.15 | %B 기반 과매수/과매도 |
| RSI | 0.20 | RSI 14일 기반 |
| MACD | 0.20 | 골든/데드 크로스 |
| 이동평균선 | 0.20 | MA5/20/60/120 정배열/역배열 |
| 기관수급 | 0.25 | OBV + 거래량 비율 |
| **모멘텀** | 0.20 | 1M/3M/6M 수익률 기반 |
| **듀얼모멘텀** | 0.15 | 절대+상대 모멘텀, Sharpe 비율 |
| **변동성타겟** | 0.15 | 목표 변동성 15%, 포지션 조절 |

## 리스크 관리
| 항목 | 설정 |
|------|------|
| 손절 | -5% |
| 익절 | +15% (50% 물량), 나머지 트레일링 |
| 트레일링 스탑 | 고점 대비 -5% |
| 종목당 최대 비중 | 10% |
| 섹터당 최대 비중 | 30% |
| 최소 현금 보유 | 20% |
| 일일 최대 손실 | -3% (서킷브레이커) |
| 연속 손실 한도 | 5회 (서킷브레이커) |

## 관심 종목 (15개)
| 코드 | 종목 | 섹터 |
|------|------|------|
| 005930 | 삼성전자 | 반도체 |
| 000660 | SK하이닉스 | 반도체 |
| 035420 | NAVER | 인터넷 |
| 035720 | 카카오 | 인터넷 |
| 051910 | LG화학 | 화학 |
| 006400 | 삼성SDI | 2차전지 |
| 003670 | 포스코퓨처엠 | 2차전지 |
| 373220 | LG에너지솔루션 | 2차전지 |
| 028260 | 삼성물산 | 건설 |
| 105560 | KB금융 | 금융 |
| 055550 | 신한지주 | 금융 |
| 005380 | 현대자동차 | 자동차 |
| 000270 | 기아 | 자동차 |
| 207940 | 삼성바이오로직스 | 바이오 |
| 068270 | 셀트리온 | 바이오 |

## 주요 기능
- [x] 8가지 퀀트 전략 앙상블
- [x] 한국투자증권 API 래핑 (mojito SDK)
- [x] 시뮬레이션 모드 (API 키 없이도 실행)
- [x] 뉴스 크롤러 (네이버 금융 실제 크롤링 + RSS)
- [x] 감성 분석 (키워드 + OpenAI 옵션)
- [x] 포트폴리오 리스크 관리
- [x] 트레일링 스탑
- [x] 서킷브레이커 (비상 정지)
- [x] SQLite DB 영속성
- [x] 텔레그램 알림
- [x] 장 시간 자동 스케줄러
- [x] 웹 대시보드 v2.0
- [x] 백테스팅

## 향후 과제
- [ ] 한국투자증권 실전 API 키 발급 및 연동
- [ ] Paper Trading 8주 검증
- [ ] 실시간 호가 WebSocket
- [ ] 기관/외국인 실제 수급 데이터 연동
- [ ] 머신러닝 기반 종목 선정 모델
- [ ] 포트폴리오 자동 리밸런싱
