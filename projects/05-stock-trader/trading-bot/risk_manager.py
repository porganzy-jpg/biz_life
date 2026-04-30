"""
StockBot 포트폴리오 리스크 관리 v3.7

포지션 사이징, 섹터 배분, 자동 리밸런싱 관리
v3.7: 현재가 기반 리밸런싱, 섹터 집중도 리밸런싱 추가
"""
import logging
from config import STOCK_TRADING_CONFIG

logger = logging.getLogger(__name__)


class StockRiskManager:
    """주식 포트폴리오 리스크 관리"""

    def __init__(self, config: dict = None):
        self.config = config or STOCK_TRADING_CONFIG

    def calculate_position_size(self, total_assets: float, confidence: float,
                                current_positions: int,
                                current_price: float = 0,
                                atr: float = 0) -> float:
        """
        ATR 기반 적정 투자 금액 계산

        거래당 자본의 2% 리스크, 포지션 = 리스크금액 / (ATR x 2)
        ATR 사이징은 변동성 높은 종목에서 포지션을 줄이고,
        안정적 종목에서 포지션을 키워 위험조정 수익률을 개선한다.
        (백테스트 결과: +11.2%p 수익률 개선, Sharpe 2.44→2.56)

        Args:
            total_assets: 총 자산
            confidence: 신뢰도 (0~1)
            current_positions: 현재 보유 종목 수
            current_price: 현재 주가 (ATR 사이징에 필요)
            atr: ATR 값 (0이면 균등 분배 폴백)

        Returns:
            float: 투자 금액
        """
        if current_positions >= self.config["max_positions"]:
            return 0

        max_per_stock = total_assets * (self.config["max_single_pct"] / 100)

        # ATR 기반 사이징: 거래당 자본의 2% 리스크
        if atr > 0 and current_price > 0:
            risk_pct = self.config.get("atr_risk_pct", 2.0) / 100
            risk_amount = total_assets * risk_pct
            risk_per_share = 2 * atr  # 2x ATR 손절 거리
            qty = int(risk_amount / risk_per_share)
            if qty <= 0:
                logger.warning(f"ATR 사이징 수량=0: ATR={atr:,.0f} price={current_price:,.0f} risk={risk_amount:,.0f} → 변동성 과다")
                return 0
            adjusted = qty * current_price
            # 최대 총자산의 40%까지 (과도한 집중 방지)
            adjusted = min(adjusted, total_assets * 0.40)
        else:
            # 폴백: 기존 균등 분배
            max_investable = total_assets * (1 - self.config["min_cash_reserve_pct"] / 100)
            remaining = self.config["max_positions"] - current_positions
            adjusted = max_investable / max(remaining, 1)

        adjusted = min(adjusted, max_per_stock)
        return round(adjusted, -3)  # 천원 단위 반올림

    def check_sector_limit(self, positions: dict, sector: str,
                           new_amount: float, total_assets: float) -> bool:
        """섹터 비율 한도 확인"""
        sector_total = new_amount
        for pos in positions.values():
            if pos.get("sector") == sector:
                sector_total += pos.get("qty", 0) * pos.get("avg_price", 0)

        sector_pct = sector_total / total_assets * 100
        return sector_pct <= self.config["max_sector_pct"]

    def should_rebalance(self, positions: dict, total_assets: float,
                         current_prices: dict = None) -> list:
        """
        리밸런싱 필요 종목 확인 (v3.7: 현재가 기반)

        Args:
            positions: {symbol: {qty, avg_price, name, sector, ...}}
            total_assets: 총 자산
            current_prices: {symbol: price} 현재가 딕셔너리 (없으면 avg_price 사용)

        Returns:
            list: [{symbol, name, current_pct, target_pct, action, qty_to_sell}, ...]
        """
        rebalance_needed = []
        max_pct = self.config["max_single_pct"]  # 35%
        rebalance_trigger = max_pct * 1.4  # v3.8.1: 1.2→1.4 (49%, 더 여유 있게)

        for symbol, pos in positions.items():
            qty = pos.get("qty", 0)
            if qty <= 0:
                continue

            # 현재가 우선, 없으면 avg_price
            if current_prices and symbol in current_prices:
                price = current_prices[symbol]
            else:
                price = pos.get("avg_price", 0)

            value = qty * price
            pct = value / total_assets * 100 if total_assets > 0 else 0

            if pct > rebalance_trigger:
                # 목표: max_pct(30%)까지 축소
                target_value = total_assets * (max_pct / 100)
                excess_value = value - target_value
                qty_to_sell = int(excess_value / price) if price > 0 else 0

                if qty_to_sell > 0:
                    rebalance_needed.append({
                        "symbol": symbol,
                        "name": pos.get("name", symbol),
                        "current_pct": round(pct, 1),
                        "target_pct": max_pct,
                        "action": "REDUCE",
                        "qty_to_sell": qty_to_sell,
                        "price": price,
                    })

        return rebalance_needed

    def should_rebalance_sector(self, positions: dict, total_assets: float,
                                current_prices: dict = None) -> list:
        """
        섹터 집중도 리밸런싱 (v3.7)

        섹터 비중 55% 초과 시 해당 섹터 내 최대 포지션 축소.

        Returns:
            list: [{symbol, name, sector, sector_pct, qty_to_sell, price}, ...]
        """
        rebalance_needed = []
        max_sector_pct = self.config["max_sector_pct"]  # 60%
        sector_trigger = max_sector_pct * 1.3  # v3.8.1: 1.1→1.3 (78%, 더 여유 있게)

        if total_assets <= 0:
            return []

        # 섹터별 포지션 집계
        sector_positions = {}  # {sector: [(symbol, name, value, qty, price), ...]}
        for symbol, pos in positions.items():
            qty = pos.get("qty", 0)
            if qty <= 0:
                continue

            sector = pos.get("sector", "기타")
            if current_prices and symbol in current_prices:
                price = current_prices[symbol]
            else:
                price = pos.get("avg_price", 0)

            value = qty * price
            if sector not in sector_positions:
                sector_positions[sector] = []
            sector_positions[sector].append((symbol, pos.get("name", symbol), value, qty, price))

        for sector, items in sector_positions.items():
            sector_value = sum(v for _, _, v, _, _ in items)
            sector_pct = sector_value / total_assets * 100

            if sector_pct > sector_trigger:
                # 최대 포지션부터 축소하여 50%로 낮춤
                target_value = total_assets * (max_sector_pct / 100)
                excess = sector_value - target_value
                # 가장 큰 포지션 축소
                items_sorted = sorted(items, key=lambda x: x[2], reverse=True)
                top_sym, top_name, top_val, top_qty, top_price = items_sorted[0]

                if top_price > 0:
                    qty_to_sell = min(int(excess / top_price), top_qty - 1)
                    if qty_to_sell > 0:
                        rebalance_needed.append({
                            "symbol": top_sym,
                            "name": top_name,
                            "sector": sector,
                            "sector_pct": round(sector_pct, 1),
                            "target_sector_pct": max_sector_pct,
                            "qty_to_sell": qty_to_sell,
                            "price": top_price,
                        })

        return rebalance_needed

    def can_afford_stock(self, stock_price: float, total_assets: float) -> bool:
        """
        1주 가격이 포지션 한도 내인지 확인.

        Args:
            stock_price: 1주 가격
            total_assets: 총 자산

        Returns:
            bool: 매수 가능 여부
        """
        max_per_stock = total_assets * (self.config["max_single_pct"] / 100)
        return stock_price <= max_per_stock

    def validate_trade(self, action: str, amount: float, cash: float,
                       positions: dict, confidence: float) -> tuple:
        """매매 전 검증"""
        if action == "BUY":
            if cash < amount:
                return False, "현금 부족"
            if len(positions) >= self.config["max_positions"]:
                return False, "최대 보유 종목 초과"
            min_conf = self.config.get("min_confidence", 0.15)
            if confidence < min_conf:
                return False, f"신뢰도 부족: {confidence:.2f} < {min_conf}"
        return True, "통과"
