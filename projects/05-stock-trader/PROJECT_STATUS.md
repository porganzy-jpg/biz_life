# StockBot - 프로젝트 현황

## 개요
한국 주식 자동매매 봇. 5가지 퀀트 전략 앙상블 + 뉴스 감성 분석으로 종목을 선별하고, 한국투자증권 API(mojito SDK)를 통해 매매 실행.

## 기술 스택
- **Backend**: Python 3.13, FastAPI (대시보드)
- **증권 연동**: mojito SDK (한국투자증권 Open API)
- **분석**: pandas, numpy, ta (기술적 분석)
- **뉴스**: aiohttp, beautifulsoup4, feedparser (크롤링)
- **감성 분석**: 키워드 기반 + OpenAI GPT (옵션)

## 실행 방법
```bash
# 대시보드 실행
cd projects/05-stock-trader/dashboard
python app.py
# → http://localhost:8004

# .env 파일에 API 키 설정 (선택)
cp .env.example .env
# KIS_APP_KEY, KIS_APP_SECRET 등 입력
```

## 파일 구조
```
05-stock-trader/
├── strategy/
│   ├── base_strategy.py          # StockSignal + BaseStockStrategy ABC
│   ├── bollinger_strategy.py     # 볼린저밴드 %B 전략
│   ├── rsi_strategy.py           # RSI 과매수/과매도 전략
│   ├── macd_strategy.py          # MACD 크로스 전략
│   ├── ma_strategy.py            # 이동평균선 정배열/역배열
│   ├── institutional_flow.py     # 기관/외국인 수급 분석 (OBV 기반)
│   ├── stock_selector.py         # 5전략 앙상블 (가중 스코어링)
│   └── backtester.py             # 주식 백테스터
├── trading-bot/
│   ├── config.py                 # 한투 API 설정, 관심 종목 10개
│   ├── broker_client.py          # 한국투자증권 API 클라이언트 (시뮬레이션)
│   ├── trader.py                 # StockTrader (워치리스트 스캔, 매매)
│   ├── risk_manager.py           # 포트폴리오 리스크 관리
│   └── stock_analyzer.py         # 퀀트 분석기 + 뉴스 감성 분석
├── news/
│   ├── crawler.py                # 네이버 금융 + RSS 뉴스 크롤러
│   └── sentiment.py              # 감성 분석 (키워드 + OpenAI)
├── dashboard/
│   └── app.py                    # FastAPI 대시보드
├── .env.example                  # 환경변수 예시
├── docs/
│   └── PROJECT_PLAN.md
└── requirements.txt
```

## API 엔드포인트 (대시보드, 7개)
| Method | Path | 설명 | 테스트 결과 |
|--------|------|------|-------------|
| GET | `/` | 대시보드 UI | OK - 7,957 bytes |
| GET | `/api/status` | 봇 상태 (잔고 1억원) | OK |
| GET | `/api/scan` | 워치리스트 10종목 분석 | OK - 10종목 |
| GET | `/api/analyze/{symbol}` | 특정 종목 분석 | OK |
| GET | `/api/history` | 매매 이력 | OK |
| POST | `/api/bot/start` | 봇 시작 | OK |
| POST | `/api/bot/stop` | 봇 정지 | OK |

## 관심 종목 (10개)
| 코드 | 종목 | 섹터 |
|------|------|------|
| 005930 | 삼성전자 | IT |
| 000660 | SK하이닉스 | IT |
| 035420 | NAVER | IT |
| 035720 | 카카오 | IT |
| 005380 | 현대자동차 | 자동차 |
| 105560 | KB금융 | 금융 |
| 055550 | 신한지주 | 금융 |
| 003670 | 포스코퓨처엠 | 소재 |
| 006400 | 삼성SDI | 배터리 |
| 207940 | 삼성바이오로직스 | 바이오 |

## 5가지 전략 앙상블
| 전략 | 가중치 | 설명 |
|------|--------|------|
| 볼린저밴드 | 0.20 | %B 기반 과매수/과매도 스코어링 |
| RSI | 0.20 | RSI 14일 기반 스코어링 |
| MACD | 0.20 | 골든/데드 크로스 스코어링 |
| 이동평균선 | 0.20 | MA5/20/60/120 정배열/역배열 |
| 기관수급 | 0.20 | OBV + 거래량 비율 분석 |

점수 0-100 스케일, 60점 이상 BUY / 40점 이하 SELL.

## 테스트 결과
- 2025-02-07 전체 테스트 통과
- 워치리스트 스캔: 10종목 분석 성공 (포스코퓨처엠 60.9점 최고)
- 시뮬레이션 잔고: 1억원, 수수료 0.015%, 거래세 0.18%
- 수정사항: OHLCV DataFrame 길이 불일치 수정 (business day freq)
- 수정사항: `/api/history` 엔드포인트 추가

## 주요 기능
- [x] 5가지 퀀트 전략 앙상블
- [x] 한국투자증권 API 래핑 (mojito SDK)
- [x] 시뮬레이션 모드 (API 키 없이도 실행)
- [x] 뉴스 크롤러 (네이버 금융 + RSS)
- [x] 감성 분석 (키워드 + OpenAI 옵션)
- [x] 포트폴리오 리스크 관리
- [x] 웹 대시보드
- [x] 백테스팅

## 향후 과제
- [ ] 한국투자증권 실전 API 연동
- [ ] 실시간 호가 WebSocket
- [ ] 기관/외국인 실제 수급 데이터 연동
- [ ] 종목 토론방 감성 분석
- [ ] 포트폴리오 리밸런싱 자동화
