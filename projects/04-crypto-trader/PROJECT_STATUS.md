# CryptoBot - 프로젝트 현황

## 개요
암호화폐 자동매매 봇. 4가지 전략의 앙상블 가중 투표로 매매 신호를 생성하고, 서킷브레이커/리스크 관리/알림 시스템을 통합한 트레이딩 엔진.

## 기술 스택
- **Backend**: Python 3.13, FastAPI (대시보드)
- **거래소 연동**: ccxt (업비트, 빗썸 등)
- **기술적 분석**: pandas, numpy, ta
- **대시보드**: 인라인 HTML 템플릿

## 실행 방법
```bash
# 대시보드 실행
cd projects/04-crypto-trader/dashboard
python app.py
# → http://localhost:8003

# 트레이더 직접 실행
cd projects/04-crypto-trader/trading-bot
python trader.py
```

## 파일 구조
```
04-crypto-trader/
├── strategy/
│   ├── base_strategy.py              # Signal 클래스 + BaseStrategy ABC
│   ├── bollinger_rsi_strategy.py     # 볼린저밴드 + RSI 복합 전략
│   ├── volatility_breakout_strategy.py # 래리 윌리엄스 변동성 돌파
│   ├── macd_strategy.py              # MACD 골든/데드 크로스
│   ├── moving_average_strategy.py    # MA5/20/60/120 정배열/역배열
│   ├── strategy_ensemble.py          # 가중 투표 앙상블
│   └── backtester.py                 # 백테스팅 엔진
├── trading-bot/
│   ├── config.py                     # 거래소 API, 매매 설정
│   ├── exchange_client.py            # ccxt 거래소 클라이언트 (페이퍼 트레이딩)
│   ├── trader.py                     # CryptoTrader v2.0 (앙상블 통합)
│   ├── circuit_breaker.py            # 비상 정지 시스템
│   ├── alert_system.py               # 텔레그램/콘솔 알림
│   └── risk_manager.py               # 켈리 기준 포지션 사이징
├── dashboard/
│   └── app.py                        # FastAPI 대시보드
├── docs/
│   └── PROJECT_PLAN.md
└── requirements.txt
```

## API 엔드포인트 (대시보드, 6개)
| Method | Path | 설명 | 테스트 결과 |
|--------|------|------|-------------|
| GET | `/` | 대시보드 UI | OK - 11,388 bytes |
| GET | `/api/status` | 봇 상태 (잔고, 매매수) | OK |
| GET | `/api/history` | 매매 이력 | OK |
| GET | `/api/analyze/{symbol}` | 특정 심볼 분석 | OK - 4개 전략 앙상블 |
| POST | `/api/bot/start` | 봇 시작 | OK |
| POST | `/api/bot/stop` | 봇 정지 | OK |

## 4개 전략 앙상블
| 전략 | 가중치 | 설명 |
|------|--------|------|
| BollingerBand+RSI | 0.35 | BB %B + RSI 과매수/과매도 |
| VolatilityBreakout | 0.25 | 래리 윌리엄스 변동성 돌파 (k=0.5) |
| MACD | 0.20 | MACD 골든/데드 크로스 |
| MovingAverage | 0.20 | MA5/20/60/120 정배열/역배열 |

## 리스크 관리 시스템
- **서킷브레이커**: 일/월 손실 한도, 연속 손실 제한, 가격 급락 감지, 쿨다운
- **리스크 매니저**: 켈리 기준 포지션 사이징, 동적 손절/익절, 매매 검증
- **알림**: 텔레그램 봇 + 콘솔 알림 (매매, 손절, 서킷브레이커 발동)

## 테스트 결과
- 2025-02-07 전체 테스트 통과
- 분석 테스트: KRW-BTC → 4개 전략 모두 HOLD (시뮬레이션 데이터)
- 봇 시작/정지: 정상
- 수정사항: dashboard analyze 엔드포인트 응답 키 이름 수정 (`consensus` → `action`)

## 주요 기능
- [x] 4가지 기술적 분석 전략
- [x] 가중 투표 앙상블 시스템
- [x] 서킷브레이커 (비상 정지)
- [x] 켈리 기준 포지션 사이징
- [x] 텔레그램/콘솔 알림
- [x] 페이퍼 트레이딩 모드
- [x] 웹 대시보드 (실시간 모니터링)
- [x] 백테스팅 엔진

## 향후 과제
- [ ] 실제 거래소 API 키 연동
- [ ] WebSocket 실시간 데이터
- [ ] 전략 성과 기반 동적 가중치 조정
- [ ] 다중 거래소 지원
- [ ] 수익률 차트/리포트
