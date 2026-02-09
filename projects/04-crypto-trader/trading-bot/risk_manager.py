"""
CryptoBot 리스크 관리 모듈

포지션 사이징, 자산 배분, 리스크 한도 관리
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class RiskManager:
    """리스크 관리"""

    def __init__(self, config: dict = None):
        default_config = {
            "max_total_exposure_pct": 30.0,    # 전체 자산 대비 최대 투자 비율
            "max_single_position_pct": 10.0,   # 단일 포지션 최대 비율
            "max_open_positions": 5,            # 최대 동시 포지션
            "min_trade_amount": 5000,           # 최소 주문 금액 (KRW)
            "max_trade_amount": 1_000_000,      # 최대 1회 주문 금액
            "risk_per_trade_pct": 1.0,          # 1회 거래 최대 리스크 (자산의 1%)
            "min_confidence": 0.5,              # 최소 신뢰도 (앙상블 기준)
        }
        self.config = {**default_config, **(config or {})}
        self.trade_count_today = 0

    def calculate_position_size(self, total_balance: float, confidence: float,
                                current_positions: int) -> float:
        """
        포지션 사이즈 계산 (Kelly Criterion 변형)

        Args:
            total_balance: 총 잔고
            confidence: 전략 신뢰도 (0~1)
            current_positions: 현재 보유 포지션 수

        Returns:
            float: 적정 매수 금액
        """
        if current_positions >= self.config["max_open_positions"]:
            return 0.0

        if confidence < self.config["min_confidence"]:
            return 0.0

        # 남은 포지션 수에 따른 분배
        remaining_slots = self.config["max_open_positions"] - current_positions
        max_per_position = total_balance * (self.config["max_single_position_pct"] / 100)

        # 신뢰도에 비례한 사이즈 조정 (Half-Kelly)
        kelly_fraction = confidence * 0.5
        position_size = total_balance * kelly_fraction * (self.config["risk_per_trade_pct"] / 100)

        # 최소/최대 한도 적용
        position_size = max(self.config["min_trade_amount"], position_size)
        position_size = min(max_per_position, position_size)
        position_size = min(self.config["max_trade_amount"], position_size)

        # 전체 노출도 확인
        max_total = total_balance * (self.config["max_total_exposure_pct"] / 100)
        position_size = min(position_size, max_total / max(remaining_slots, 1))

        return round(position_size, 0)

    def validate_trade(self, action: str, symbol: str, amount: float,
                       balance: float, positions: dict, confidence: float) -> tuple:
        """
        매매 전 리스크 검증

        Returns:
            (bool, str): (통과 여부, 사유)
        """
        if action == "BUY":
            # 잔고 확인
            if balance < amount:
                return False, f"잔고 부족: {balance:,.0f} < {amount:,.0f}"

            # 최대 포지션 수
            if len(positions) >= self.config["max_open_positions"]:
                return False, f"최대 포지션 초과: {len(positions)}"

            # 최소 금액
            if amount < self.config["min_trade_amount"]:
                return False, f"최소 주문 금액 미달: {amount:,.0f}"

            # 신뢰도 확인
            if confidence < self.config["min_confidence"]:
                return False, f"신뢰도 부족: {confidence:.2f} < {self.config['min_confidence']}"

            # 단일 포지션 한도
            max_single = balance * (self.config["max_single_position_pct"] / 100)
            if amount > max_single:
                return False, f"단일 포지션 한도 초과: {amount:,.0f} > {max_single:,.0f}"

        return True, "통과"

    def calculate_stop_loss(self, entry_price: float, confidence: float) -> float:
        """동적 손절가 계산"""
        # 신뢰도가 높을수록 손절 범위 좁게 (자신감)
        base_stop_pct = 3.0
        adjusted = base_stop_pct - (confidence * 1.0)  # 최대 1% 축소
        adjusted = max(1.5, adjusted)  # 최소 1.5%
        return entry_price * (1 - adjusted / 100)

    def calculate_take_profit(self, entry_price: float, confidence: float) -> float:
        """동적 익절가 계산"""
        base_tp_pct = 5.0
        adjusted = base_tp_pct + (confidence * 2.0)  # 최대 2% 확대
        return entry_price * (1 + adjusted / 100)

    def get_status(self) -> dict:
        """리스크 관리 상태"""
        return {
            "config": self.config,
            "trades_today": self.trade_count_today,
        }
