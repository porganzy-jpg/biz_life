"""
HomeFinder - APScheduler 기반 작업 스케줄러
데이터 수집, 채점, 가격 변동 감지, 알림 발송 자동화
"""
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("homefinder.scheduler")


class HomefinderScheduler:
    """HomeFinder 스케줄러 (백그라운드 작업 관리)"""

    def __init__(self, settings, db_session_factory):
        self.settings = settings
        self.db_factory = db_session_factory
        self.scheduler = BackgroundScheduler(timezone="Asia/Seoul")
        self._register_jobs()

    def _add_job(self, func, trigger, job_id, name):
        """작업 등록 헬퍼 (공통 옵션 적용)"""
        self.scheduler.add_job(
            func, trigger, id=job_id, name=name,
            max_instances=1, replace_existing=True,
        )

    def _register_jobs(self):
        """모든 스케줄 작업 등록"""

        # ── 데이터 수집 ──
        self._add_job(self.job_collect_molit,
                       CronTrigger(hour=6, minute=0),
                       "collect_molit", "국토부 실거래가 수집")
        self._add_job(self.job_collect_naver,
                       IntervalTrigger(hours=6),
                       "collect_naver", "네이버 부동산 수집")
        self._add_job(self.job_collect_auctions,
                       CronTrigger(hour=8, minute=0),
                       "collect_auctions", "경매 데이터 수집")
        self._add_job(self.job_collect_subscriptions,
                       CronTrigger(day_of_week="mon,thu", hour=9, minute=0),
                       "collect_subscriptions", "청약 데이터 수집")
        self._add_job(self.job_collect_kb_index,
                       CronTrigger(day_of_week="mon", hour=7, minute=0),
                       "collect_kb_index", "KB 부동산 지수 수집")

        # ── 분석 & 채점 ──
        self._add_job(self.job_score_new_properties,
                       IntervalTrigger(hours=2),
                       "score_properties", "신규 매물 채점")
        self._add_job(self.job_detect_price_changes,
                       CronTrigger(hour=10, minute=0),
                       "detect_price_changes", "가격 변동 감지")

        # ── 알림 ──
        self._add_job(self.job_daily_report,
                       CronTrigger(hour=21, minute=0),
                       "daily_report", "일일 리포트 발송")
        self._add_job(self.job_weekly_report,
                       CronTrigger(day_of_week="sun", hour=20, minute=0),
                       "weekly_report", "주간 리포트 발송")
        self._add_job(self.job_match_saved_searches,
                       CronTrigger(hour=11, minute=0),
                       "match_searches", "저장검색 매칭")

        logger.info("All scheduler jobs registered")

    # ──────────── Job implementations ────────────

    def _run_collector(self, name, create_fn, **run_kwargs):
        """수집기 공통 실행 헬퍼"""
        logger.info(f"[Scheduler] Starting {name} collection...")
        try:
            collector = create_fn()
            result = collector.run(**run_kwargs)
            logger.info(f"  {name} done: {result}")
        except Exception as e:
            logger.error(f"{name} collection failed: {e}")
            self._send_alert_safe("error", name, str(e))

    def job_collect_molit(self):
        """국토부 실거래가 수집"""
        from collectors.molit_collector import MolitCollector
        self._run_collector("molit", lambda: MolitCollector(
            api_key=self.settings.PUBLIC_DATA_API_KEY,
            target_districts=self.settings.TARGET_DISTRICTS,
        ), months_back=1)

    def job_collect_naver(self):
        """네이버 부동산 수집"""
        from collectors.naver_collector import NaverCollector
        self._run_collector("naver", lambda: NaverCollector(
            target_districts=self.settings.TARGET_DISTRICTS,
        ))

    def job_collect_auctions(self):
        """경매 데이터 수집"""
        from collectors.auction_collector import AuctionCollector
        self._run_collector("auction", lambda: AuctionCollector(
            target_districts=self.settings.TARGET_DISTRICTS,
        ))

    def job_collect_subscriptions(self):
        """청약 데이터 수집"""
        from collectors.subscription_collector import SubscriptionCollector
        self._run_collector("subscription", lambda: SubscriptionCollector(
            target_cities=self.settings.TARGET_CITIES,
        ))

    def job_collect_kb_index(self):
        """KB 지수 수집"""
        from collectors.kb_index_collector import KBIndexCollector
        self._run_collector("kb_index", lambda: KBIndexCollector())

    def job_score_new_properties(self):
        """채점되지 않은 매물 자동 채점"""
        logger.info("[Scheduler] Scoring new properties...")
        db = self.db_factory()
        try:
            from scoring.composite_scorer import CompositeScorer
            from services.scoring_service import ScoringService
            from models.property import Property

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
        """가격 변동 감지 및 알림 (TODO: 구현 예정)"""
        logger.info("[Scheduler] Detecting price changes...")
        logger.warning("  Price change detection not yet implemented")

    def _send_report(self, report_type: str):
        """리포트 생성 & 발송 공통 헬퍼"""
        logger.info(f"[Scheduler] Generating {report_type} report...")
        try:
            alert = self._get_alert_system()
            if not alert:
                logger.info("  Telegram not configured, skipping report")
                return
        except Exception as e:
            logger.error(f"{report_type.capitalize()} report failed: {e}")

    def job_daily_report(self):
        """일일 리포트 생성 & 발송"""
        self._send_report("daily")

    def job_weekly_report(self):
        """주간 리포트 생성 & 발송"""
        self._send_report("weekly")

    def job_match_saved_searches(self):
        """저장검색 매칭 (TODO: 구현 예정)"""
        logger.info("[Scheduler] Matching saved searches...")
        logger.warning("  Saved search matching not yet implemented")

    # ──────────── Helpers ────────────

    def _get_alert_system(self):
        """텔레그램 알림 시스템 생성"""
        if self.settings.TELEGRAM_BOT_TOKEN and self.settings.TELEGRAM_CHAT_ID:
            from alerts.alert_system import TelegramAlertSystem
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
        jobs = self.scheduler.get_jobs()
        logger.info(f"Scheduler started with {len(jobs)} jobs")
        for job in jobs:
            logger.info(f"  - {job.name}: next={job.next_run_time}")

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
            KST = timezone(timedelta(hours=9))
            job.modify(next_run_time=datetime.now(tz=KST))
            logger.info(f"Job '{job_id}' scheduled for immediate execution")
            return True
        return False
