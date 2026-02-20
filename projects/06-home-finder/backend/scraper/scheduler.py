"""
스크래핑 스케줄러 (Scraping Scheduler)

Manages periodic scraping, deduplication, and auto-scoring of new properties.
Runs scans in a background thread with configurable intervals and targets.
"""
import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

logger = logging.getLogger("homefinder.scraper.scheduler")


class ScanResult:
    """Result of a single scan operation."""

    def __init__(self, district: str, property_type: str):
        self.district = district
        self.property_type = property_type
        self.started_at: datetime = datetime.utcnow()
        self.finished_at: Optional[datetime] = None
        self.fetched: int = 0
        self.new: int = 0
        self.updated: int = 0
        self.skipped: int = 0
        self.errors: List[str] = []
        self.status: str = "running"  # running, success, failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "district": self.district,
            "property_type": self.property_type,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "fetched": self.fetched,
            "new": self.new,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "status": self.status,
        }


class ScrapingScheduler:
    """
    Orchestrates scraping, deduplication, and auto-scoring.

    Can be run manually (single scan) or configured for periodic
    background execution.
    """

    def __init__(self, db_session_factory, settings):
        """
        Args:
            db_session_factory: Callable that returns a new DB session (SessionLocal).
            settings: Application settings instance.
        """
        self.db_factory = db_session_factory
        self.settings = settings

        # Scan state
        self._scan_history: List[Dict[str, Any]] = []
        self._last_scan_time: Optional[datetime] = None
        self._is_scanning: bool = False
        self._total_new: int = 0
        self._total_updated: int = 0
        self._total_errors: int = 0

        # Background scheduler state
        self._scheduler_thread: Optional[threading.Thread] = None
        self._scheduler_running: bool = False
        self._scheduled_districts: List[str] = []
        self._scheduled_types: List[str] = ["아파트"]
        self._interval_hours: float = 24.0

    # ──────────── Schedule Management ────────────

    def schedule_scan(
        self,
        districts: List[str],
        property_types: Optional[List[str]] = None,
        interval_hours: float = 24.0,
    ) -> Dict[str, Any]:
        """
        Set up recurring scans.

        Args:
            districts: List of district names to scan.
            property_types: List of property types to scan (default: ["아파트"]).
            interval_hours: Hours between scan cycles.

        Returns:
            Schedule configuration summary.
        """
        self._scheduled_districts = districts
        self._scheduled_types = property_types or ["아파트"]
        self._interval_hours = interval_hours

        # Start background thread if not running
        if not self._scheduler_running:
            self._start_background_scheduler()

        logger.info(
            "Scan scheduled: districts=%s, types=%s, interval=%sh",
            districts, self._scheduled_types, interval_hours,
        )

        return {
            "districts": self._scheduled_districts,
            "property_types": self._scheduled_types,
            "interval_hours": self._interval_hours,
            "scheduler_running": self._scheduler_running,
        }

    def stop_schedule(self):
        """Stop the background scheduler."""
        self._scheduler_running = False
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)
        self._scheduler_thread = None
        logger.info("Background scheduler stopped")

    def _start_background_scheduler(self):
        """Start the background scheduling thread."""
        self._scheduler_running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="scraper-scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()
        logger.info("Background scheduler started")

    def _scheduler_loop(self):
        """Background loop that runs scans at the configured interval."""
        while self._scheduler_running:
            try:
                # Run a full scan cycle
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    for district in self._scheduled_districts:
                        if not self._scheduler_running:
                            break
                        for ptype in self._scheduled_types:
                            if not self._scheduler_running:
                                break
                            loop.run_until_complete(
                                self.run_scan(district, ptype)
                            )
                finally:
                    loop.close()

                logger.info("Scheduled scan cycle completed")
            except Exception as e:
                logger.error("Scheduler loop error: %s", e)

            # Wait for next cycle
            sleep_seconds = self._interval_hours * 3600
            check_interval = 10  # Check every 10 seconds if we should stop
            elapsed = 0
            while elapsed < sleep_seconds and self._scheduler_running:
                time.sleep(min(check_interval, sleep_seconds - elapsed))
                elapsed += check_interval

    # ──────────── Scan Execution ────────────

    async def run_scan(
        self, district: str, property_type: str = "아파트"
    ) -> ScanResult:
        """
        Execute a single scan for a district and property type.

        Fetches listings from Naver, deduplicates, saves new entries,
        updates changed prices, and triggers auto-scoring.

        Args:
            district: District name (e.g., "마포구").
            property_type: Property type to scan.

        Returns:
            ScanResult with counts and status.
        """
        result = ScanResult(district, property_type)
        self._is_scanning = True

        logger.info("Starting scan: district=%s, type=%s", district, property_type)

        try:
            # Import here to avoid circular imports
            from backend.scraper.naver_scraper import NaverRealEstateScraper
            from backend.scraper.data_mapper import map_naver_to_property

            rate_limit = getattr(self.settings, "SCRAPER_RATE_LIMIT_SEC", 2.0)
            scraper = NaverRealEstateScraper(rate_limit_sec=rate_limit)

            try:
                # Fetch raw data
                if property_type == "토지":
                    raw_articles = await scraper.search_land(district)
                else:
                    raw_articles = await scraper.search_apartments(district)

                result.fetched = len(raw_articles)

                # Map to our schema and add district info
                mapped_properties = []
                for article in raw_articles:
                    article["_district"] = district
                    mapped = map_naver_to_property(article)
                    if mapped and mapped.get("source_id"):
                        mapped_properties.append(mapped)

                # Process results (deduplicate, save, score)
                process_result = self.process_results(mapped_properties)
                result.new = process_result.get("new", 0)
                result.updated = process_result.get("updated", 0)
                result.skipped = process_result.get("skipped", 0)
                result.errors = process_result.get("errors", [])
                result.status = "success"

            finally:
                await scraper.close()

        except Exception as e:
            error_msg = f"Scan error for {district}/{property_type}: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            result.status = "failed"

        result.finished_at = datetime.utcnow()
        self._is_scanning = False
        self._last_scan_time = result.finished_at
        self._total_new += result.new
        self._total_updated += result.updated
        self._total_errors += len(result.errors)

        # Save to history (keep last 100)
        self._scan_history.append(result.to_dict())
        if len(self._scan_history) > 100:
            self._scan_history = self._scan_history[-100:]

        # Log to data_collection_logs table
        self._log_scan_to_db(result)

        logger.info(
            "Scan completed: district=%s, type=%s, fetched=%d, new=%d, "
            "updated=%d, skipped=%d, errors=%d",
            district, property_type, result.fetched, result.new,
            result.updated, result.skipped, len(result.errors),
        )

        return result

    def process_results(
        self, raw_properties: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Deduplicate and save scraped properties to the database.

        For each property:
        - Check source + source_id for duplicates
        - Create new properties via PropertyService
        - Update existing properties if price changed
        - Auto-score new properties

        Args:
            raw_properties: List of mapped property dicts.

        Returns:
            {"new": int, "updated": int, "skipped": int, "errors": list}
        """
        db = self.db_factory()
        new_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        new_property_ids = []

        try:
            from models.property import Property
            from repositories.property_repo import PropertyRepository
            from services.property_service import PropertyService

            repo = PropertyRepository(db)
            svc = PropertyService(db)

            for prop_data in raw_properties:
                try:
                    source = prop_data.get("source", "naver")
                    source_id = prop_data.get("source_id", "")

                    if not source_id:
                        skipped_count += 1
                        continue

                    # Check for existing property
                    existing = repo.get_by_source_id(source, source_id)

                    if existing:
                        # Check if price changed
                        new_price = prop_data.get("price_krw")
                        if new_price and existing.price_krw and new_price != existing.price_krw:
                            # Price changed - update
                            update_data = {
                                "price_krw": new_price,
                                "updated_at": datetime.utcnow(),
                            }
                            new_area = prop_data.get("area_m2", existing.area_m2)
                            if new_price and new_area and new_area > 0:
                                update_data["price_per_m2"] = int(new_price / new_area)

                            repo.update(existing, **update_data)
                            updated_count += 1
                            logger.debug(
                                "Updated property %s price: %s -> %s",
                                source_id, existing.price_krw, new_price,
                            )
                        else:
                            skipped_count += 1
                    else:
                        # New property - create
                        # Convert enum string values for PropertyService
                        create_data = dict(prop_data)
                        prop = svc.create_property(create_data)
                        new_count += 1
                        new_property_ids.append(prop.id)

                except Exception as e:
                    error_msg = f"Process property error (source_id={prop_data.get('source_id', '?')}): {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    # Rollback any partial changes for this property
                    db.rollback()

            db.commit()

            # Auto-score new properties
            scored = self._auto_score_properties(db, new_property_ids)
            logger.info("Auto-scored %d new properties", scored)

        except Exception as e:
            db.rollback()
            error_msg = f"Process results error: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
        finally:
            db.close()

        return {
            "new": new_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "errors": errors,
        }

    def _auto_score_properties(
        self, db: Session, property_ids: List[int]
    ) -> int:
        """
        Auto-score newly created properties.

        Args:
            db: Database session.
            property_ids: List of property IDs to score.

        Returns:
            Number of properties successfully scored.
        """
        if not property_ids:
            return 0

        scored = 0
        try:
            from backend.config import settings
            from scoring.composite_scorer import CompositeScorer
            from services.scoring_service import ScoringService
            from models.subway_station import SubwayStation
            from models.park import Park

            scorer = CompositeScorer(settings)

            # Load reference data for scoring
            stations = db.query(SubwayStation).all()
            parks = db.query(Park).filter(Park.park_type != "한강").all()
            rivers = db.query(Park).filter(Park.park_type == "한강").all()

            scorer.set_reference_data(
                [{"name": s.name, "lat": s.lat, "lng": s.lng, "line": s.line}
                 for s in stations],
                [{"name": p.name, "lat": p.lat, "lng": p.lng} for p in parks],
                [{"name": p.name, "lat": p.lat, "lng": p.lng} for p in rivers],
            )

            svc = ScoringService(db, scorer)

            for pid in property_ids:
                try:
                    svc.score_property(pid)
                    scored += 1
                except Exception as e:
                    logger.debug("Auto-score failed for property %d: %s", pid, e)

        except Exception as e:
            logger.warning("Auto-scoring setup error: %s", e)

        return scored

    def _log_scan_to_db(self, result: ScanResult):
        """Log scan result to the data_collection_logs table."""
        db = self.db_factory()
        try:
            from models.data_collection_log import DataCollectionLog

            log = DataCollectionLog(
                collector_name=f"scraper_{result.district}_{result.property_type}",
                started_at=result.started_at,
                finished_at=result.finished_at,
                status=result.status,
                records_fetched=result.fetched,
                records_new=result.new,
                records_updated=result.updated,
                error_message="; ".join(result.errors[:3]) if result.errors else None,
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.warning("Failed to log scan result to DB: %s", e)
            db.rollback()
        finally:
            db.close()

    # ──────────── Status & History ────────────

    def get_scan_status(self) -> Dict[str, Any]:
        """
        Return current scraper status.

        Returns:
            Dict with status information:
            {
                "is_scanning": bool,
                "last_scan_time": str or None,
                "total_new": int,
                "total_updated": int,
                "total_errors": int,
                "scheduler_running": bool,
                "scheduled_districts": list,
                "scheduled_types": list,
                "interval_hours": float,
                "recent_scans": list (last 10),
            }
        """
        return {
            "is_scanning": self._is_scanning,
            "last_scan_time": self._last_scan_time.isoformat() if self._last_scan_time else None,
            "total_new": self._total_new,
            "total_updated": self._total_updated,
            "total_errors": self._total_errors,
            "scheduler_running": self._scheduler_running,
            "scheduled_districts": self._scheduled_districts,
            "scheduled_types": self._scheduled_types,
            "interval_hours": self._interval_hours,
            "recent_scans": self._scan_history[-10:],
        }

    def get_scan_history(
        self, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get paginated scan history (most recent first)."""
        history = list(reversed(self._scan_history))
        return history[offset : offset + limit]

    async def preview_scan(
        self, district: str, property_type: str = "아파트"
    ) -> Dict[str, Any]:
        """
        Preview what a scan would find without saving to DB (dry run).

        Args:
            district: District to preview.
            property_type: Property type to preview.

        Returns:
            Dict with preview data including matched properties.
        """
        from backend.scraper.naver_scraper import NaverRealEstateScraper
        from backend.scraper.data_mapper import map_naver_to_property

        rate_limit = getattr(self.settings, "SCRAPER_RATE_LIMIT_SEC", 2.0)
        scraper = NaverRealEstateScraper(rate_limit_sec=rate_limit)

        try:
            if property_type == "토지":
                raw_articles = await scraper.search_land(district)
            else:
                raw_articles = await scraper.search_apartments(district)

            # Map to our schema
            mapped = []
            for article in raw_articles:
                article["_district"] = district
                prop = map_naver_to_property(article)
                if prop and prop.get("source_id"):
                    mapped.append(prop)

            # Check which ones are duplicates
            db = self.db_factory()
            try:
                from repositories.property_repo import PropertyRepository
                repo = PropertyRepository(db)

                new_count = 0
                existing_count = 0
                for prop in mapped:
                    existing = repo.get_by_source_id(
                        prop.get("source", "naver"),
                        prop.get("source_id", ""),
                    )
                    if existing:
                        existing_count += 1
                        prop["_status"] = "existing"
                    else:
                        new_count += 1
                        prop["_status"] = "new"
            finally:
                db.close()

            return {
                "district": district,
                "property_type": property_type,
                "total_found": len(raw_articles),
                "new_count": new_count,
                "existing_count": existing_count,
                "properties": mapped[:20],  # Preview first 20
            }
        finally:
            await scraper.close()
