"""
KB부동산 가격지수 수집기
"""
import logging
from datetime import datetime
from collectors.base_collector import BaseCollector
from database import SessionLocal
from models.price_index import PriceIndex

logger = logging.getLogger("homefinder.collector.kb")


class KBIndexCollector(BaseCollector):
    name = "kb_index"
    rate_limit_seconds = 2.0

    def __init__(self):
        super().__init__()

    def collect(self, **kwargs) -> dict:
        """KB 가격지수 수집"""
        try:
            import PublicDataReader as pdr
            api = pdr.Kbland()
        except ImportError:
            logger.error("PublicDataReader not installed")
            return {"fetched": 0, "new": 0, "updated": 0}
        except Exception as e:
            logger.error(f"KB API init failed: {e}")
            return {"fetched": 0, "new": 0, "updated": 0}

        total_new = 0
        db = SessionLocal()

        try:
            # 서울 매매지수
            regions = ["서울", "마포구", "용산구", "성동구", "영등포구", "강동구"]
            for region in regions:
                try:
                    self._rate_limit()
                    df = api.get_price_index(
                        "아파트",
                        "매매",
                        region,
                    )
                    if df is None or df.empty:
                        continue

                    for _, row in df.tail(12).iterrows():  # Last 12 months
                        try:
                            date_val = row.get("날짜") or row.get("date")
                            if date_val is None:
                                continue
                            if hasattr(date_val, "date"):
                                date_val = date_val.date()
                            else:
                                date_val = datetime.strptime(str(date_val)[:10], "%Y-%m-%d").date()

                            value = float(row.get("지수") or row.get("index") or 0)
                            change = float(row.get("증감률") or row.get("change") or 0)

                            # Check duplicate
                            existing = db.query(PriceIndex).filter(
                                PriceIndex.source == "kb",
                                PriceIndex.region == region,
                                PriceIndex.date == date_val,
                            ).first()
                            if existing:
                                continue

                            idx = PriceIndex(
                                source="kb",
                                index_type="매매지수",
                                region=region,
                                date=date_val,
                                value=value,
                                change_pct=change,
                            )
                            db.add(idx)
                            total_new += 1
                        except Exception as e:
                            logger.debug(f"Row parse error: {e}")
                            continue

                except Exception as e:
                    logger.warning(f"KB index fetch failed for {region}: {e}")
                    continue

            db.commit()
        finally:
            db.close()

        return {"fetched": total_new, "new": total_new, "updated": 0}
