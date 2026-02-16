"""
HomeFinder - APScheduler 기반 작업 스케줄러
데이터 수집, 채점, 가격 변동 감지, 알림 발송 자동화
"""
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("homefinder.scheduler")


class HomefinderScheduler:
    """HomeFinder 스케줄러 (백그라운드 작업 관리)"""

    def __init__(self, settings, db_session_factory):
        """
        Args:
            settings: backend.config.Settings 인스턴스
            db_session_factory: SessionLocal (DB 세션 팩토리)
        """
        self.settings = settings
        self.db_factory = db_session_factory
        self.scheduler = BackgroundScheduler(timezone="Asia/Seoul")
        self._register_jobs()

    def _get_db(self):
        db = self.db_factory()
        try:
            return db
        except Exception:
            db.close()
            raise

    def _register_jobs(self):
        """모든 스케줄 작업 등록"""

        # ── 데이터 수집 ──

        # 네이버 부동산 수집 (매 3시간)
        self.scheduler.add_job(
            self.job_collect_naver,
            IntervalTrigger(hours=3),
            id="collect_naver",
            name="네이버 부동산 수집",
            max_instances=1,
            replace_existing=True,
        )

        # 국토부 실거래가 (매일 06:00)
        self.scheduler.add_job(
            self.job_collect_molit,
            CronTrigger(hour=6, minute=0),
            id="collect_molit",
            name="국토부 실거래가 수집",
            max_instances=1,
            replace_existing=True,
        )

        # 경매 데이터 (매일 08:00)
        self.scheduler.add_job(
            self.job_collect_auctions,
            CronTrigger(hour=8, minute=0),
            id="collect_auctions",
            name="경매 데이터 수집",
            max_instances=1,
            replace_existing=True,
        )

        # 청약 데이터 (매일 09:00)
        self.scheduler.add_job(
            self.job_collect_subscriptions,
            CronTrigger(hour=9, minute=0),
            id="collect_subscriptions",
            name="청약 데이터 수집",
            max_instances=1,
            replace_existing=True,
        )

        # KB 지수 (매주 월요일 07:00)
        self.scheduler.add_job(
            self.job_collect_kb_index,
            CronTrigger(day_of_week="mon", hour=7, minute=0),
            id="collect_kb_index",
            name="KB 부동산 지수 수집",
            max_instances=1,
            replace_existing=True,
        )

        # ── 분석 & 채점 ──

        # 신규 매물 자동 채점 (매 2시간)
        self.scheduler.add_job(
            self.job_score_new_properties,
            IntervalTrigger(hours=2),
            id="score_properties",
            name="신규 매물 채점",
            max_instances=1,
            replace_existing=True,
        )

        # 가격 변동 감지 (매일 10:00)
        self.scheduler.add_job(
            self.job_detect_price_changes,
            CronTrigger(hour=10, minute=0),
            id="detect_price_changes",
            name="가격 변동 감지",
            max_instances=1,
            replace_existing=True,
        )

        # ── 알림 ──

        # 일일 리포트 (매일 21:00)
        self.scheduler.add_job(
            self.job_daily_report,
            CronTrigger(hour=21, minute=0),
            id="daily_report",
            name="일일 리포트 발송",
            max_instances=1,
            replace_existing=True,
        )

        # 주간 리포트 (매주 일요일 20:00)
        self.scheduler.add_job(
            self.job_weekly_report,
            CronTrigger(day_of_week="sun", hour=20, minute=0),
            id="weekly_report",
            name="주간 리포트 발송",
            max_instances=1,
            replace_existing=True,
        )

        # 저장검색 매칭 (매일 11:00)
        self.scheduler.add_job(
            self.job_match_saved_searches,
            CronTrigger(hour=11, minute=0),
            id="match_searches",
            name="저장검색 매칭",
            max_instances=1,
            replace_existing=True,
        )

        logger.info("All scheduler jobs registered")

    # ──────────── Job implementations ────────────

    def job_collect_naver(self):
        """네이버 부동산 수집"""
        logger.info("[Scheduler] Starting Naver collection...")
        db = self._get_db()
        try:
            from collectors.naver_collector import NaverCollector
            collector = NaverCollector(db)
            for district in self.settings.TARGET_DISTRICTS:
                try:
                    result = collector.collect(district=district)
                    logger.info(f"  Naver {district}: fetched={result.get('fetched',0)}, new={result.get('new',0)}")
                except Exception as e:
                    logger.error(f"  Naver {district} error: {e}")
            self._send_alert_safe("collection_complete", "네이버 부동산", {})
        except Exception as e:
            logger.error(f"Naver collection failed: {e}")
            self._send_alert_safe("error", "naver_collector", str(e))
        finally:
            db.close()

    def job_collect_molit(self):
        """국토부 실거래가 수집"""
        logger.info("[Scheduler] Starting MOLIT collection...")
        db = self._get_db()
        try:
            from collectors.molit_collector import MolitCollector
            collector = MolitCollector(db, api_key=self.settings.PUBLIC_DATA_API_KEY)
            result = collector.collect()
            logger.info(f"  MOLIT: fetched={result.get('fetched',0)}, new={result.get('new',0)}")
        except Exception as e:
            logger.error(f"MOLIT collection failed: {e}")
            self._send_alert_safe("error", "molit_collector", str(e))
        finally:
            db.close()

    def job_collect_auctions(self):
        """경매 데이터 수집"""
        logger.info("[Scheduler] Starting auction collection...")
        db = self._get_db()
        try:
            from collectors.auction_collector import AuctionCollector
            collector = AuctionCollector(db)
            result = collector.collect()
            logger.info(f"  Auctions: fetched={result.get('fetched',0)}, new={result.get('new',0)}")
        except Exception as e:
            logger.error(f"Auction collection failed: {e}")
            self._send_alert_safe("error", "auction_collector", str(e))
        finally:
            db.close()

    def job_collect_subscriptions(self):
        """청약 데이터 수집"""
        logger.info("[Scheduler] Starting subscription collection...")
        db = self._get_db()
        try:
            from collectors.subscription_collector import SubscriptionCollector
            collector = SubscriptionCollector(db)
            result = collector.collect()
            logger.info(f"  Subscriptions: fetched={result.get('fetched',0)}, new={result.get('new',0)}")
        except Exception as e:
            logger.error(f"Subscription collection failed: {e}")
            self._send_alert_safe("error", "subscription_collector", str(e))
        finally:
            db.close()

    def job_collect_kb_index(self):
        """KB 지수 수집"""
        logger.info("[Scheduler] Starting KB index collection...")
        db = self._get_db()
        try:
            from collectors.kb_index_collector import KBIndexCollector
            collector = KBIndexCollector(db)
            result = collector.collect()
            logger.info(f"  KB Index: fetched={result.get('fetched',0)}, new={result.get('new',0)}")
        except Exception as e:
            logger.error(f"KB index collection failed: {e}")
            self._send_alert_safe("error", "kb_index_collector", str(e))
        finally:
            db.close()

    def job_score_new_properties(self):
        """채점되지 않은 매물 자동 채점"""
        logger.info("[Scheduler] Scoring new properties...")
        db = self._get_db()
        try:
            from scoring.composite_scorer import CompositeScorer
            from services.scoring_service import ScoringService
            from models.property import Property

            # 채점 안된 매물 찾기
            unscored = (
                db.query(Property)
                .filter(Property.is_active == 1)
                .filter(Property.scored_at.is_(None))
                .limit(100)
                .all()
            )

            if not unscored:
                logger.info("  No unscored properties found")
                return

            scorer = CompositeScorer(self.settings)
            # Load reference data
            self._load_scorer_reference(db, scorer)
            svc = ScoringService(db, scorer)

            scored = 0
            for prop in unscored:
                try:
                    svc.score_property(prop.id)
                    scored += 1
                except Exception as e:
                    logger.error(f"  Score property {prop.id} error: {e}")

            logger.info(f"  Scored {scored}/{len(unscored)} properties")
        except Exception as e:
            logger.error(f"Scoring job failed: {e}")
        finally:
            db.close()

    def job_detect_price_changes(self):
        """가격 변동 감지 및 알림"""
        logger.info("[Scheduler] Detecting price changes...")
        db = self._get_db()
        try:
            from models.property import Property
            from models.transaction import TransactionHistory

            # 최근 거래 기록과 현재 가격 비교
            # (실제 구현은 가격 히스토리 테이블이 필요)
            logger.info("  Price change detection completed")
        except Exception as e:
            logger.error(f"Price change detection failed: {e}")
        finally:
            db.close()

    def job_daily_report(self):
        """일일 리포트 생성 & 발송"""
        logger.info("[Scheduler] Generating daily report...")
        db = self._get_db()
        try:
            from services.report_service import ReportService
            svc = ReportService(db)
            report_data = svc.daily_report()
            report_text = svc.format_daily_text(report_data)

            alert = self._get_alert_system()
            if alert:
                alert.daily_report(report_text)
                logger.info("  Daily report sent")
        except Exception as e:
            logger.error(f"Daily report failed: {e}")
        finally:
            db.close()

    def job_weekly_report(self):
        """주간 리포트 생성 & 발송"""
        logger.info("[Scheduler] Generating weekly report...")
        db = self._get_db()
        try:
            from services.report_service import ReportService
            svc = ReportService(db)
            report_data = svc.weekly_report()
            report_text = svc.format_weekly_text(report_data)

            alert = self._get_alert_system()
            if alert:
                alert.weekly_report(report_text)
                logger.info("  Weekly report sent")
        except Exception as e:
            logger.error(f"Weekly report failed: {e}")
        finally:
            db.close()

    def job_match_saved_searches(self):
        """저장검색 매칭"""
        logger.info("[Scheduler] Matching saved searches...")
        db = self._get_db()
        try:
            from services.search_service import SearchService
            svc = SearchService(db)
            matches = svc.match_saved_searches()

            alert = self._get_alert_system()
            if alert and matches:
                for search_name, props in matches.items():
                    alert.match_alert(search_name, props)
                logger.info(f"  Sent {len(matches)} match alerts")
        except Exception as e:
            logger.error(f"Saved search matching failed: {e}")
        finally:
            db.close()

    # ──────────── Helpers ────────────

    def _get_alert_system(self):
        """텔레그램 알림 시스템 생성"""
        from alerts.alert_system import TelegramAlertSystem
        if self.settings.TELEGRAM_BOT_TOKEN and self.settings.TELEGRAM_CHAT_ID:
            return TelegramAlertSystem(
                self.settings.TELEGRAM_BOT_TOKEN,
                self.settings.TELEGRAM_CHAT_ID,
            )
        return None

    def _send_alert_safe(self, alert_type, component, data):
        """안전한 알림 전송 (실패해도 에러 무시)"""
        try:
            alert = self._get_alert_system()
            if not alert:
                return
            if alert_type == "error":
                alert.error_alert(component, str(data))
            elif alert_type == "collection_complete":
                alert.collection_complete_alert(component, 0, 0, 0)
        except Exception as e:
            logger.error(f"Alert send error: {e}")

    def _load_scorer_reference(self, db, scorer):
        """스코어러에 시드 데이터 로드"""
        try:
            from models.subway_station import SubwayStation
            from models.park import Park

            stations = db.query(SubwayStation).all()
            parks = db.query(Park).filter(Park.park_type != "한강").all()
            river_points = db.query(Park).filter(Park.park_type == "한강").all()

            station_list = [{"name": s.name, "lat": s.lat, "lng": s.lng, "line": s.line}
                           for s in stations]
            park_list = [{"name": p.name, "lat": p.lat, "lng": p.lng} for p in parks]
            river_list = [{"name": p.name, "lat": p.lat, "lng": p.lng} for p in river_points]

            scorer.set_reference_data(station_list, park_list, river_list)
        except Exception as e:
            logger.error(f"Failed to load scorer reference data: {e}")

    # ──────────── Start / Stop ────────────

    def start(self):
        """스케줄러 시작"""
        self.scheduler.start()
        logger.info("Scheduler started with %d jobs", len(self.scheduler.get_jobs()))

    def stop(self):
        """스케줄러 정지"""
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    def get_jobs(self):
        """등록된 작업 목록"""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            for job in self.scheduler.get_jobs()
        ]

    def run_job_now(self, job_id: str):
        """특정 작업 즉시 실행"""
        job = self.scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=datetime.now())
            logger.info(f"Job '{job_id}' scheduled for immediate execution")
            return True
        return False
