"""리포트 서비스 - 일간/주간 보고서 생성"""
from datetime import datetime, date, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from models.property import Property
from models.auction import AuctionListing
from models.subscription import SubscriptionOpportunity
from models.candidate import CandidateProperty
from models.transaction import TransactionHistory
from repositories.property_repo import PropertyRepository
from repositories.auction_repo import AuctionRepository
from repositories.subscription_repo import SubscriptionRepository
from repositories.candidate_repo import CandidateRepository
from repositories.price_index_repo import PriceIndexRepository


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.property_repo = PropertyRepository(db)
        self.auction_repo = AuctionRepository(db)
        self.subscription_repo = SubscriptionRepository(db)
        self.candidate_repo = CandidateRepository(db)
        self.price_idx_repo = PriceIndexRepository(db)

    def daily_report(self) -> dict:
        """일간 보고서 생성"""
        today = date.today()
        yesterday = today - timedelta(days=1)

        # New listings since yesterday
        new_properties = (
            self.db.query(Property)
            .filter(Property.is_active == 1)
            .filter(Property.created_at >= datetime.combine(yesterday, datetime.min.time()))
            .count()
        )

        # Price changes: properties updated recently (proxy for price changes)
        price_changes = (
            self.db.query(Property)
            .filter(Property.is_active == 1)
            .filter(Property.updated_at >= datetime.combine(yesterday, datetime.min.time()))
            .filter(Property.created_at < datetime.combine(yesterday, datetime.min.time()))
            .all()
        )
        price_change_list = []
        for p in price_changes:
            price_change_list.append({
                "id": p.id,
                "complex_name": p.complex_name,
                "district": p.district,
                "price_krw": p.price_krw,
            })

        # Upcoming auctions (next 7 days)
        upcoming_auctions = self.auction_repo.get_upcoming(days=7, limit=10)
        auction_list = []
        for a in upcoming_auctions:
            auction_list.append({
                "id": a.id,
                "case_number": a.case_number,
                "district": a.district,
                "address": a.address,
                "auction_date": a.auction_date.isoformat() if a.auction_date else None,
                "minimum_bid": a.minimum_bid,
                "discount_rate": a.discount_rate,
            })

        # Ending subscriptions (next 7 days)
        ending_subs = (
            self.db.query(SubscriptionOpportunity)
            .filter(SubscriptionOpportunity.subscription_end >= today)
            .filter(SubscriptionOpportunity.subscription_end <= today + timedelta(days=7))
            .order_by(SubscriptionOpportunity.subscription_end)
            .all()
        )
        sub_list = []
        for s in ending_subs:
            sub_list.append({
                "id": s.id,
                "name": s.name,
                "district": s.district,
                "subscription_end": s.subscription_end.isoformat() if s.subscription_end else None,
                "min_price": s.min_price,
                "max_price": s.max_price,
            })

        # Top scored properties
        top_scored = self.property_repo.get_top_scored(limit=5)
        top_list = []
        for p in top_scored:
            top_list.append({
                "id": p.id,
                "complex_name": p.complex_name,
                "district": p.district,
                "price_krw": p.price_krw,
                "score_composite": p.score_composite,
            })

        return {
            "date": today.isoformat(),
            "new_properties": new_properties,
            "price_changes": price_change_list,
            "upcoming_auctions": auction_list,
            "ending_subscriptions": sub_list,
            "top_scored": top_list,
        }

    def weekly_report(self) -> dict:
        """주간 보고서 생성"""
        today = date.today()
        week_ago = today - timedelta(days=7)

        # Market summary
        total_active = (
            self.db.query(Property)
            .filter(Property.is_active == 1)
            .count()
        )
        new_this_week = (
            self.db.query(Property)
            .filter(Property.is_active == 1)
            .filter(Property.created_at >= datetime.combine(week_ago, datetime.min.time()))
            .count()
        )

        # Average score of all active properties
        avg_score = (
            self.db.query(func.avg(Property.score_composite))
            .filter(Property.is_active == 1)
            .filter(Property.score_composite.isnot(None))
            .scalar()
        )

        # Recent transaction price trend
        recent_txs = (
            self.db.query(
                func.avg(TransactionHistory.price_per_m2).label("avg_price"),
                func.count(TransactionHistory.id).label("count"),
            )
            .filter(TransactionHistory.transaction_date >= week_ago)
            .first()
        )

        market_summary = {
            "total_active_properties": total_active,
            "new_this_week": new_this_week,
            "avg_composite_score": round(avg_score, 1) if avg_score else None,
            "weekly_avg_price_per_m2": int(recent_txs.avg_price) if recent_txs and recent_txs.avg_price else None,
            "weekly_transaction_count": recent_txs.count if recent_txs else 0,
        }

        # Pipeline summary
        pipeline = self.candidate_repo.get_pipeline_counts()

        # Top candidates
        top_candidates = self.candidate_repo.get_shortlist()
        top_cand_list = []
        for c in top_candidates[:10]:
            prop = self.property_repo.get_by_id(c.property_id)
            top_cand_list.append({
                "candidate_id": c.id,
                "status": c.status,
                "priority": c.priority,
                "rating": c.rating,
                "property_id": c.property_id,
                "complex_name": prop.complex_name if prop else None,
                "district": prop.district if prop else None,
                "price_krw": prop.price_krw if prop else None,
                "score_composite": prop.score_composite if prop else None,
            })

        # Price index trend (latest)
        latest_idx = self.price_idx_repo.get_latest("kb", "서울")
        price_trend = {}
        if latest_idx:
            price_trend = {
                "date": latest_idx.date.isoformat() if latest_idx.date else None,
                "value": latest_idx.value,
                "change_pct": latest_idx.change_pct,
            }

        return {
            "week": f"{week_ago.isoformat()} ~ {today.isoformat()}",
            "market_summary": market_summary,
            "pipeline": pipeline,
            "top_candidates": top_cand_list,
            "price_trend": price_trend,
        }

    def format_daily_text(self, report: dict) -> str:
        """일간 보고서를 텔레그램용 한국어 텍스트로 포맷"""
        lines = []
        lines.append(f"📊 HomeFinder 일간 리포트 ({report['date']})")
        lines.append("")

        # New listings
        lines.append(f"🏠 신규 매물: {report['new_properties']}건")

        # Price changes
        changes = report.get("price_changes", [])
        if changes:
            lines.append(f"💰 가격 변동: {len(changes)}건")
            for c in changes[:3]:
                name = c.get("complex_name") or c.get("district", "")
                price = c.get("price_krw", 0)
                price_eok = price / 100000000 if price else 0
                lines.append(f"  • {name} - {price_eok:.1f}억")
        else:
            lines.append("💰 가격 변동: 없음")

        # Upcoming auctions
        auctions = report.get("upcoming_auctions", [])
        if auctions:
            lines.append(f"⚖️ 7일내 경매: {len(auctions)}건")
            for a in auctions[:3]:
                discount = a.get("discount_rate", 0)
                discount_pct = discount * 100 if discount and discount < 1 else discount or 0
                lines.append(
                    f"  • {a.get('district', '')} {a.get('auction_date', '')} "
                    f"(할인 {discount_pct:.0f}%)"
                )
        else:
            lines.append("⚖️ 7일내 경매: 없음")

        # Ending subscriptions
        subs = report.get("ending_subscriptions", [])
        if subs:
            lines.append(f"📝 마감 임박 청약: {len(subs)}건")
            for s in subs[:3]:
                lines.append(
                    f"  • {s.get('name', '')} ({s.get('district', '')}) "
                    f"~{s.get('subscription_end', '')}"
                )
        else:
            lines.append("📝 마감 임박 청약: 없음")

        # Top scored
        top = report.get("top_scored", [])
        if top:
            lines.append("")
            lines.append("⭐ TOP 매물:")
            for t in top:
                name = t.get("complex_name") or t.get("district", "")
                score = t.get("score_composite", 0) or 0
                price = t.get("price_krw", 0) or 0
                price_eok = price / 100000000
                lines.append(f"  • {name} ({t.get('district', '')}) {score:.0f}점 {price_eok:.1f}억")

        return "\n".join(lines)

    def format_weekly_text(self, report: dict) -> str:
        """주간 보고서를 텔레그램용 한국어 텍스트로 포맷"""
        lines = []
        lines.append(f"📈 HomeFinder 주간 리포트 ({report['week']})")
        lines.append("")

        # Market summary
        ms = report.get("market_summary", {})
        lines.append("🏙️ 시장 현황:")
        lines.append(f"  • 활성 매물: {ms.get('total_active_properties', 0)}건")
        lines.append(f"  • 금주 신규: {ms.get('new_this_week', 0)}건")
        avg_score = ms.get("avg_composite_score")
        if avg_score:
            lines.append(f"  • 평균 점수: {avg_score:.1f}점")
        weekly_avg = ms.get("weekly_avg_price_per_m2")
        if weekly_avg:
            lines.append(f"  • 금주 평균 m²당: {weekly_avg:,}원")
        lines.append(f"  • 금주 거래: {ms.get('weekly_transaction_count', 0)}건")

        # Price trend
        pt = report.get("price_trend", {})
        if pt:
            lines.append("")
            lines.append("📊 KB 가격지수:")
            change = pt.get("change_pct", 0) or 0
            arrow = "↑" if change > 0 else ("↓" if change < 0 else "→")
            lines.append(f"  • {pt.get('value', '-')} ({arrow}{abs(change):.2f}%)")

        # Pipeline
        pipeline = report.get("pipeline", {})
        if pipeline:
            lines.append("")
            lines.append("📋 파이프라인:")
            for status, count in pipeline.items():
                lines.append(f"  • {status}: {count}건")

        # Top candidates
        candidates = report.get("top_candidates", [])
        if candidates:
            lines.append("")
            lines.append("🌟 주요 후보:")
            for c in candidates[:5]:
                name = c.get("complex_name") or c.get("district", "")
                price = c.get("price_krw", 0) or 0
                price_eok = price / 100000000
                score = c.get("score_composite", 0) or 0
                status = c.get("status", "")
                lines.append(f"  • {name} {score:.0f}점 {price_eok:.1f}억 [{status}]")

        return "\n".join(lines)
