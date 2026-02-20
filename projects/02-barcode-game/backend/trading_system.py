"""
BarcodeQuest Monster Trading System

Marketplace for listing and buying monsters between players.
"""
import json
from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text
from sqlalchemy import desc, asc, func
from sqlalchemy.orm import Session as DBSession

from database import Base, SessionLocal


# =====================================================
#  SQLAlchemy Models
# =====================================================

class TradeListing(Base):
    """
    A monster listed for sale on the marketplace.
    status: 'active', 'sold', 'cancelled'
    """
    __tablename__ = "trade_listings"

    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(String(100), nullable=False, index=True)
    monster_json = Column(JSON, nullable=False)
    monster_name = Column(String(100), default="")
    monster_rarity = Column(String(20), default="Common")
    monster_level = Column(Integer, default=1)
    monster_type = Column(String(30), default="")
    price = Column(Integer, nullable=False)
    status = Column(String(20), default="active", index=True)
    buyer_id = Column(String(100), nullable=True)
    listed_at = Column(DateTime, default=datetime.utcnow)
    sold_at = Column(DateTime, nullable=True)


class TradeHistory(Base):
    """
    Record of completed trades for history display.
    """
    __tablename__ = "trade_history"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, nullable=False)
    seller_id = Column(String(100), nullable=False, index=True)
    buyer_id = Column(String(100), nullable=False, index=True)
    monster_name = Column(String(100), default="")
    monster_rarity = Column(String(20), default="Common")
    price = Column(Integer, default=0)
    traded_at = Column(DateTime, default=datetime.utcnow)


# =====================================================
#  Constants
# =====================================================

MIN_PRICE = 10
MAX_PRICE = 999999
MAX_ACTIVE_LISTINGS = 5  # max listings per player
TRADE_FEE_PERCENT = 5   # 5% marketplace fee


# =====================================================
#  TradeManager
# =====================================================

class TradeManager:
    """Monster marketplace trading manager."""

    def _get_db(self) -> DBSession:
        return SessionLocal()

    # ----- List Monster -----

    def list_monster(self, session_id: str, monster_data: dict,
                     monster_index: int, price: int,
                     source: str = "party") -> dict:
        """
        List a monster for sale on the marketplace.

        The monster is removed from the player's party/inventory by the caller.
        This method creates the listing record.

        Args:
            session_id: Seller's session ID
            monster_data: The monster dict to sell
            monster_index: Index in party/inventory (for caller reference)
            price: Asking price in gold
            source: 'party' or 'inventory'

        Returns:
            dict with listing info or error
        """
        if not monster_data:
            return {"error": "유효하지 않은 몬스터 데이터입니다."}

        if price < MIN_PRICE or price > MAX_PRICE:
            return {"error": f"가격은 {MIN_PRICE:,}G ~ {MAX_PRICE:,}G 범위여야 합니다."}

        db = self._get_db()
        try:
            # Check active listings count
            active_count = db.query(func.count(TradeListing.id)).filter(
                TradeListing.seller_id == session_id,
                TradeListing.status == "active",
            ).scalar()
            if active_count >= MAX_ACTIVE_LISTINGS:
                return {"error": f"최대 {MAX_ACTIVE_LISTINGS}개까지만 등록할 수 있습니다."}

            listing = TradeListing(
                seller_id=session_id,
                monster_json=monster_data,
                monster_name=monster_data.get("name", "???"),
                monster_rarity=monster_data.get("rarity", "Common"),
                monster_level=monster_data.get("level", 1),
                monster_type=monster_data.get("primary_type", ""),
                price=price,
                status="active",
                listed_at=datetime.utcnow(),
            )
            db.add(listing)
            db.commit()

            return {
                "ok": True,
                "listing_id": listing.id,
                "monster_name": listing.monster_name,
                "price": price,
                "source": source,
                "monster_index": monster_index,
                "message": f"{listing.monster_name}을(를) {price:,}G에 등록했습니다!",
            }
        finally:
            db.close()

    # ----- Buy Monster -----

    def buy_monster(self, buyer_id: str, listing_id: int, buyer_gold: int) -> dict:
        """
        Buy a monster from the marketplace.

        Gold transfer is handled by the caller.  This method updates
        listing status and creates trade history.

        Args:
            buyer_id: Buyer's session ID
            listing_id: ID of the listing to purchase
            buyer_gold: Buyer's current gold (checked but NOT deducted here)

        Returns:
            dict with trade result including monster data, price, seller_id
        """
        db = self._get_db()
        try:
            listing = db.query(TradeListing).filter(
                TradeListing.id == listing_id
            ).first()

            if not listing:
                return {"error": "해당 거래를 찾을 수 없습니다."}

            if listing.status != "active":
                return {"error": "이미 판매 완료되었거나 취소된 거래입니다."}

            if listing.seller_id == buyer_id:
                return {"error": "자신이 등록한 몬스터는 구매할 수 없습니다."}

            if buyer_gold < listing.price:
                return {
                    "error": f"골드가 부족합니다! (필요: {listing.price:,}G, 보유: {buyer_gold:,}G)"
                }

            # Calculate fee
            fee = int(listing.price * TRADE_FEE_PERCENT / 100)
            seller_receives = listing.price - fee

            # Update listing
            listing.status = "sold"
            listing.buyer_id = buyer_id
            listing.sold_at = datetime.utcnow()

            # Create trade history
            history = TradeHistory(
                listing_id=listing.id,
                seller_id=listing.seller_id,
                buyer_id=buyer_id,
                monster_name=listing.monster_name,
                monster_rarity=listing.monster_rarity,
                price=listing.price,
                traded_at=datetime.utcnow(),
            )
            db.add(history)
            db.commit()

            return {
                "ok": True,
                "listing_id": listing.id,
                "monster": listing.monster_json,
                "monster_name": listing.monster_name,
                "price": listing.price,
                "fee": fee,
                "seller_receives": seller_receives,
                "seller_id": listing.seller_id,
                "message": f"{listing.monster_name}을(를) {listing.price:,}G에 구매했습니다!",
            }
        finally:
            db.close()

    # ----- Cancel Listing -----

    def cancel_listing(self, session_id: str, listing_id: int) -> dict:
        """
        Cancel an active listing and return the monster data.

        Args:
            session_id: Must be the seller
            listing_id: ID of the listing to cancel

        Returns:
            dict with monster data to be restored to player
        """
        db = self._get_db()
        try:
            listing = db.query(TradeListing).filter(
                TradeListing.id == listing_id
            ).first()

            if not listing:
                return {"error": "해당 거래를 찾을 수 없습니다."}

            if listing.seller_id != session_id:
                return {"error": "자신이 등록한 거래만 취소할 수 있습니다."}

            if listing.status != "active":
                return {"error": "이미 완료되었거나 취소된 거래입니다."}

            listing.status = "cancelled"
            db.commit()

            return {
                "ok": True,
                "listing_id": listing.id,
                "monster": listing.monster_json,
                "monster_name": listing.monster_name,
                "message": f"{listing.monster_name}의 판매가 취소되었습니다. 몬스터가 복구됩니다.",
            }
        finally:
            db.close()

    # ----- Get Marketplace -----

    def get_marketplace(self, sort: str = "newest",
                        filter_type: str = "",
                        filter_rarity: str = "",
                        limit: int = 50) -> list:
        """
        Get active marketplace listings.

        Args:
            sort: 'newest', 'price_low', 'price_high', 'level_high', 'rarity'
            filter_type: Filter by monster type (e.g., 'Fire')
            filter_rarity: Filter by rarity (e.g., 'Epic')
            limit: Max results

        Returns:
            list of listing dicts
        """
        db = self._get_db()
        try:
            query = db.query(TradeListing).filter(
                TradeListing.status == "active"
            )

            if filter_type:
                query = query.filter(TradeListing.monster_type == filter_type)
            if filter_rarity:
                query = query.filter(TradeListing.monster_rarity == filter_rarity)

            # Sort
            if sort == "price_low":
                query = query.order_by(asc(TradeListing.price))
            elif sort == "price_high":
                query = query.order_by(desc(TradeListing.price))
            elif sort == "level_high":
                query = query.order_by(desc(TradeListing.monster_level))
            elif sort == "rarity":
                # Custom rarity ordering
                rarity_order = {"Legendary": 0, "Epic": 1, "Rare": 2, "Uncommon": 3, "Common": 4}
                query = query.order_by(asc(TradeListing.monster_rarity))
            else:  # newest
                query = query.order_by(desc(TradeListing.listed_at))

            listings = query.limit(limit).all()

            result = []
            for l in listings:
                result.append({
                    "listing_id": l.id,
                    "seller_id": l.seller_id,
                    "monster": l.monster_json,
                    "monster_name": l.monster_name,
                    "monster_rarity": l.monster_rarity,
                    "monster_level": l.monster_level,
                    "monster_type": l.monster_type,
                    "price": l.price,
                    "listed_at": l.listed_at.isoformat() if l.listed_at else "",
                })
            return result
        finally:
            db.close()

    # ----- Get Trade History -----

    def get_trade_history(self, session_id: str, limit: int = 20) -> list:
        """
        Get trade history for a player (both as buyer and seller).

        Returns:
            list of trade history dicts
        """
        db = self._get_db()
        try:
            rows = db.query(TradeHistory).filter(
                (TradeHistory.seller_id == session_id) |
                (TradeHistory.buyer_id == session_id)
            ).order_by(desc(TradeHistory.traded_at)).limit(limit).all()

            history = []
            for r in rows:
                is_seller = r.seller_id == session_id
                history.append({
                    "id": r.id,
                    "listing_id": r.listing_id,
                    "role": "seller" if is_seller else "buyer",
                    "counterpart": r.buyer_id if is_seller else r.seller_id,
                    "monster_name": r.monster_name,
                    "monster_rarity": r.monster_rarity,
                    "price": r.price,
                    "traded_at": r.traded_at.isoformat() if r.traded_at else "",
                })
            return history
        finally:
            db.close()

    # ----- Get My Listings -----

    def get_my_listings(self, session_id: str) -> list:
        """Get all active listings for a player."""
        db = self._get_db()
        try:
            listings = db.query(TradeListing).filter(
                TradeListing.seller_id == session_id,
                TradeListing.status == "active",
            ).order_by(desc(TradeListing.listed_at)).all()

            result = []
            for l in listings:
                result.append({
                    "listing_id": l.id,
                    "monster_name": l.monster_name,
                    "monster_rarity": l.monster_rarity,
                    "monster_level": l.monster_level,
                    "price": l.price,
                    "listed_at": l.listed_at.isoformat() if l.listed_at else "",
                })
            return result
        finally:
            db.close()
