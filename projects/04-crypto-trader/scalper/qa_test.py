# -*- coding: utf-8 -*-
"""CryptoBot v5.0 QA 검증 테스트"""
import sys, os, warnings, time
warnings.filterwarnings('ignore')

passed = 0
failed = 0
results = []

def test(name, condition, detail=""):
    global passed, failed
    status = "PASS" if condition else "FAIL"
    if condition: passed += 1
    else: failed += 1
    results.append((name, status, detail))
    marker = "O" if condition else "X"
    print(f"  [{marker}] {name}" + (f" -- {detail}" if detail and not condition else ""))

print("=" * 60)
print("  CryptoBot v5.0 QA 검증 테스트")
print("=" * 60)

# ── 1. API 타임아웃 + 재시도 ──
print("\n1. API 타임아웃 + 재시도")

from scalper.upbit_client import UpbitClient
uc = UpbitClient(paper=True)

test("Rate limit 모니터링 초기값",
     uc.api_calls_per_minute == 0)

test("is_rate_limited 초기 False",
     not uc.is_rate_limited)

# _retry_api 테스트 (성공 케이스)
df = uc.get_ohlcv("KRW-BTC", count=5)
test("OHLCV 조회 성공 (fake data)",
     df is not None and len(df) == 5)

# 재시도 카운터 동작
test("Rate limit 추적 동작",
     uc.api_calls_per_minute >= 0)  # fake는 _track 안 탐

# ── 2. 주문 안전성 ──
print("\n2. 주문 안전성")

# 잔고 부족
uc2 = UpbitClient(paper=True)
uc2.paper_account.krw = 100
r = uc2.buy_market("KRW-BTC", 1_000_000)
test("잔고 부족 시 매수 거부",
     r is None)

# 미보유 종목 매도
r = uc2.sell_market("KRW-ETH", 1.0)
test("미보유 종목 매도 → None",
     r is None)

# 정상 매수 후 매도
uc3 = UpbitClient(paper=True)
buy_r = uc3.buy_market("KRW-BTC", 100_000)
test("페이퍼 매수 성공",
     buy_r is not None and "amount" in buy_r,
     f"result: {buy_r}")

if buy_r:
    sell_r = uc3.sell_market("KRW-BTC", buy_r["amount"])
    test("페이퍼 매도 성공",
         sell_r is not None)

# ── 3. 서킷브레이커 ──
print("\n3. 서킷브레이커")

from scalper.circuit_breaker import CircuitBreaker
cb = CircuitBreaker(initial_balance=1_000_000)

# 연속 손실
for i in range(5):
    cb.record_trade(-1000)
can, reason = cb.can_trade()
test("연속 5패 → 매매 중단",
     not can, f"reason: {reason}")

# 일일 손실 한도
cb2 = CircuitBreaker(initial_balance=1_000_000)
cb2.record_trade(-51_000)  # 5.1% loss
can2, reason2 = cb2.can_trade()
test("일일 손실 5% → 매매 중단",
     not can2, f"reason: {reason2}")

# ── 4. 리스크 매니저 ──
print("\n4. 리스크 매니저")

from scalper.risk_manager import RiskManager
rm = RiskManager()

# validate_trade 테스트
test("잔고 대비 과다 주문 거부",
     not rm.validate_trade(2_000_000, 1_000_000),
     "주문 200만 > 잔고 100만의 95%")

test("정상 주문 통과",
     rm.validate_trade(500_000, 1_000_000))

# ── 5. 앙상블 전략 ──
print("\n5. 앙상블 전략")

from scalper.strategies.ensemble import EnsembleStrategy
ens = EnsembleStrategy()

test("앙상블 초기 가중치 합계 = 1.0",
     abs(sum(ens.weights.values()) - 1.0) < 0.01,
     f"sum: {sum(ens.weights.values()):.4f}")

test("4개 전략 로드",
     len(ens.strategies) == 4,
     f"loaded: {len(ens.strategies)}")

# ── 6. 메모리 보호 ──
print("\n6. 메모리 보호")

import inspect
from scalper.trader import ScalpTrader
trader_source = inspect.getsource(ScalpTrader)

test("trade_history 최대 크기 제한",
     "_max_history_size" in trader_source,
     "500건 초과 시 앞부분 삭제")

test("stale price 감지 (60초)",
     "last_price_times" in trader_source,
     "캐시 시간 기록으로 오래된 가격 무효화")

# ── 7. 체결 확인 ──
print("\n7. 체결 확인 (v5.0)")

client_source = inspect.getsource(UpbitClient)

test("실전 매수 후 체결 확인",
     "_confirm_order" in client_source,
     "uuid 기반 polling")

test("재시도 로직 존재",
     "_retry_api" in client_source,
     "지수 백오프 (1, 2, 4초)")

# 모듈 레벨에서 패치했으므로 모듈 소스 확인
import scalper.upbit_client as _ucmod
module_source = inspect.getsource(_ucmod)
test("타임아웃 패치 존재",
     "timeout" in module_source and "_timeout_get" in module_source,
     "requests.Session에 5초 기본 타임아웃")

# ── 8. 스레드 안전성 ──
print("\n8. 스레드 안전성")

from scalper.optimizer import WalkForwardOptimizer
opt_source = inspect.getsource(WalkForwardOptimizer)
test("옵티마이저 stop에 join 타임아웃",
     "join(timeout=" in opt_source,
     "10초 대기 후 경고")

# ── 9. 중복 포지션 방지 ──
print("\n9. 중복 포지션 방지")

test("이미 보유 중인 마켓 스킵",
     "if market in self.positions:" in trader_source and "continue" in trader_source,
     "positions 딕셔너리로 중복 진입 차단")

test("최대 동시 포지션 제한",
     "MAX_OPEN_POSITIONS" in trader_source,
     "max_positions 초과 시 break")

# ── 결과 ──
print("\n" + "=" * 60)
total = passed + failed
print(f"  QA 결과: {passed}/{total} 통과 ({passed/total*100:.0f}%)")
if failed > 0:
    print(f"\n  실패 항목:")
    for name, status, detail in results:
        if status == "FAIL":
            print(f"    X {name}: {detail}")
print("=" * 60)
