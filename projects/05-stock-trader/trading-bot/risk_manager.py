"""
StockBot 포트폴리오 리스크 관리

포지션 사이징, 섹터 배분, 리밸런싱 관리
"""
import logging
from config import STOCK_TRADING_CONFIG

logger = logging.getLogger(__name__)


class StockRiskManager:
    """주식 포트폴리오 리스크 관리"""

    def __init__(self, config: dict = None):
        self.config = config or STOCK_TRADING_CONFIG

    def calculate_position_size(self, total_assets: float, confidence: float,
                                current_positions: int) -> float:
        """
        적정 투자 금액 계산

        Args:
            total_assets: 총 자산
            confidence: 신뢰도 (0~1)
            current_positions: 현재 보유 종목 수

        Returns:
            float: 투자 금액
        """
        if current_positions >= self.config["max_positions"]:
            return 0

        # 현금 보유 비율 확인
        max_investable = total_assets * (1 - self.config["min_cash_reserve_pct"] / 100)
        max_per_stock = total_assets * (self.config["max_single_pct"] / 100)

        # 남은 슬롯에 균등 분배
        remaining = self.config["max_positions"] - current_positions
        base_amount = max_investable / max(remaining, 1)

        # 신뢰도에 비례한 조정
        adjusted = base_amount * (0.5 + confidence * 0.5)
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

    def should_rebalance(self, positions: dict, total_assets: float) -> list:
        """리밸런싱 필요 종목 확인"""
        rebalance_needed = []
        for symbol, pos in positions.items():
            value = pos.get("qty", 0) * pos.get("avg_price", 0)
            pct = value / total_assets * 100 if total_assets > 0 else 0

            if pct > self.config["max_single_pct"] * 1.2:  # 20% 초과 시
                excess_pct = pct - self.config["max_single_pct"]
                rebalance_needed.append({
                    "symbol": symbol,
                    "current_pct": round(pct, 1),
                    "target_pct": self.config["max_single_pct"],
                    "action": "REDUCE",
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
