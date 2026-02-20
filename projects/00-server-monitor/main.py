"""
통합 서버 관리 런처
- FastAPI 대시보드 (포트 9000)
- 텔레그램 관리 봇
- 백그라운드 헬스체크 + 리소스 알림

사용법:
    python main.py              # 전체 실행 (대시보드 + 봇 + 모니터링)
    python main.py --no-bot     # 봇 없이 대시보드 + 모니터링만
    python main.py --no-monitor # 모니터링 없이 대시보드 + 봇만
"""
import argparse
import asyncio
import logging
import multiprocessing
import os
import signal
import sys
import time

from dotenv import load_dotenv

load_dotenv()

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "main.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("main")


def run_dashboard():
    """FastAPI 대시보드 서브프로세스"""
    import uvicorn
    from config import SCHEDULE_CONFIG, HEALING_CONFIG
    # 대시보드 프로세스 안에서 스케줄러 스레드 시작 (같은 프로세스에서 동작해야 API와 공유)
    if SCHEDULE_CONFIG.get("SCHEDULE_ENABLED", True):
        from scheduler import start_scheduler_thread
        start_scheduler_thread()
        logger.info("예약 재시작 스케줄러 시작됨")
    # 자동 복구 엔진 백그라운드 스레드 시작
    if HEALING_CONFIG.get("HEALING_ENABLED", True):
        from auto_healer import start_healing_thread
        start_healing_thread()
        logger.info("자동 복구 엔진 시작됨")
    from app import app
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="warning")


def run_bot():
    """텔레그램 봇 서브프로세스"""
    from bot import main as bot_main
    bot_main()


def run_monitor():
    """모니터링 루프 (asyncio)"""
    from monitor import health_check_loop, resource_alert_loop

    async def _run():
        logger.info("모니터링 엔진 시작")
        await asyncio.gather(
            health_check_loop(),
            resource_alert_loop(),
        )
    asyncio.run(_run())


def main():
    parser = argparse.ArgumentParser(description="Server Monitor 통합 런처")
    parser.add_argument("--no-bot", action="store_true", help="텔레그램 봇 비활성화")
    parser.add_argument("--no-monitor", action="store_true", help="자동 모니터링 비활성화")
    args = parser.parse_args()

    processes = []
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")

    logger.info("=" * 50)
    logger.info("Server Monitor 시작")
    logger.info("=" * 50)

    # 1. 대시보드
    p_dash = multiprocessing.Process(target=run_dashboard, name="dashboard", daemon=True)
    p_dash.start()
    processes.append(p_dash)
    logger.info("대시보드 시작 → http://localhost:9000")

    # 2. 텔레그램 봇
    if not args.no_bot and bot_token:
        p_bot = multiprocessing.Process(target=run_bot, name="telegram-bot", daemon=True)
        p_bot.start()
        processes.append(p_bot)
        logger.info("텔레그램 봇 시작")
    elif not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN 미설정 → 봇 비활성")
    else:
        logger.info("--no-bot → 봇 비활성")

    # 3. 모니터링
    if not args.no_monitor:
        p_mon = multiprocessing.Process(target=run_monitor, name="monitor", daemon=True)
        p_mon.start()
        processes.append(p_mon)
        logger.info("헬스체크 + 리소스 알림 시작")
    else:
        logger.info("--no-monitor → 모니터링 비활성")

    logger.info("모든 서비스 실행 중 (Ctrl+C로 종료)")

    # 종료 시그널 처리
    def shutdown(signum=None, frame=None):
        logger.info("종료 신호 수신, 서비스 중지 중...")
        for p in processes:
            if p.is_alive():
                p.terminate()
        for p in processes:
            p.join(timeout=5)
        logger.info("모든 서비스 종료 완료")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 서브프로세스 감시
    try:
        while True:
            for p in processes:
                if not p.is_alive():
                    logger.error(f"{p.name} 프로세스 종료 감지 (exit={p.exitcode})")
                    # 자동 재시작
                    if p.name == "dashboard":
                        new_p = multiprocessing.Process(target=run_dashboard, name="dashboard", daemon=True)
                    elif p.name == "telegram-bot":
                        new_p = multiprocessing.Process(target=run_bot, name="telegram-bot", daemon=True)
                    elif p.name == "monitor":
                        new_p = multiprocessing.Process(target=run_monitor, name="monitor", daemon=True)
                    else:
                        continue
                    new_p.start()
                    processes[processes.index(p)] = new_p
                    logger.info(f"{p.name} 재시작 완료")
            time.sleep(5)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
