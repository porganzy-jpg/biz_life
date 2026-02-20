"""
백그라운드 모니터링 엔진
- 프로젝트 헬스체크 + 자동 재시작
- 시스템 리소스 임계치 알림 (텔레그램)
"""
import asyncio
import logging
import os
import time
from datetime import datetime

import httpx
import psutil
from dotenv import load_dotenv

from config import PROJECTS
from services import check_port, find_pid_by_port, start_project as _start_project, log_event
from anomaly import get_collector, start_anomaly_thread

load_dotenv()
logger = logging.getLogger(__name__)

# === 설정 ===
HEALTH_CHECK_INTERVAL = 30       # 30초마다 헬스체크
RESOURCE_CHECK_INTERVAL = 60     # 60초마다 리소스 체크
ALERT_COOLDOWN = 300             # 같은 알림 5분 쿨다운
AUTO_RESTART_ENABLED = True
CPU_THRESHOLD = 85
RAM_THRESHOLD = 80
DISK_THRESHOLD = 90

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

_last_alerts: dict[str, float] = {}  # 알림 쿨다운 추적
_restart_failures: dict[str, int] = {}  # 재시작 실패 횟수 추적
MAX_RESTART_ATTEMPTS = 3  # 최대 재시작 시도 (초과 시 포기)


# === 텔레그램 알림 ===

async def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("텔레그램 토큰/채팅ID 미설정, 알림 스킵")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})
    except Exception as e:
        logger.error(f"텔레그램 전송 실패: {e}")


def _can_alert(key: str) -> bool:
    now = time.time()
    if key in _last_alerts and now - _last_alerts[key] < ALERT_COOLDOWN:
        return False
    _last_alerts[key] = now
    return True


async def health_check_loop():
    """30초마다 프로젝트 상태 확인, 죽은 서비스 자동 재시작"""
    logger.info("헬스체크 루프 시작 (간격: %ds)", HEALTH_CHECK_INTERVAL)
    start_anomaly_thread()
    await asyncio.sleep(10)  # 초기 시작 대기

    while True:
        try:
            for name, proj in PROJECTS.items():
                alive = await check_port(proj["port"])
                if alive:
                    # 살아있으면 실패 카운터 초기화
                    _restart_failures.pop(name, None)
                elif AUTO_RESTART_ENABLED:
                    failures = _restart_failures.get(name, 0)
                    if failures >= MAX_RESTART_ATTEMPTS:
                        # 최대 시도 초과 → 재시작 포기, 30분 후 리셋
                        if _can_alert(f"giveup_{name}"):
                            log_event(name, "error", f"{MAX_RESTART_ATTEMPTS}회 재시작 실패, 자동 재시작 중단")
                            msg = f"⛔ {name}: {MAX_RESTART_ATTEMPTS}회 재시작 실패, 자동 재시작 중단"
                            logger.error(msg)
                            await send_telegram(msg)
                        continue

                    pid = find_pid_by_port(proj["port"])
                    if pid:
                        try:
                            proc = psutil.Process(pid)
                            for child in proc.children(recursive=True):
                                child.terminate()
                            proc.terminate()
                            proc.wait(timeout=5)
                        except Exception:
                            pass

                    result = _start_project(name, verify=False)["msg"]
                    _restart_failures[name] = failures + 1
                    ts = datetime.now().strftime("%H:%M:%S")
                    log_event(name, "auto_restart", f"자동 재시작 ({failures+1}/{MAX_RESTART_ATTEMPTS}): {result}")
                    msg = f"🔄 자동 재시작: {name} ({failures+1}/{MAX_RESTART_ATTEMPTS})\n시간: {ts}\n결과: {result}"
                    logger.warning(msg)
                    if _can_alert(f"restart_{name}"):
                        await send_telegram(msg)
        except Exception as e:
            logger.error(f"헬스체크 오류: {e}")

        # 매 사이클마다 시스템 메트릭 수집 및 저장
        try:
            get_collector().collect_and_store()
        except Exception as e:
            logger.error(f"메트릭 수집 오류: {e}")

        await asyncio.sleep(HEALTH_CHECK_INTERVAL)


# === 리소스 모니터링 ===

async def resource_alert_loop():
    """60초마다 시스템 리소스 확인, 임계치 초과 시 텔레그램 알림"""
    logger.info("리소스 모니터링 시작 (CPU>%d%%, RAM>%d%%, Disk>%d%%)",
                CPU_THRESHOLD, RAM_THRESHOLD, DISK_THRESHOLD)
    await asyncio.sleep(15)

    while True:
        try:
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("C:\\")

            alerts = []
            if cpu > CPU_THRESHOLD and _can_alert("cpu"):
                alerts.append(f"CPU: {cpu}% (>{CPU_THRESHOLD}%)")
            if mem.percent > RAM_THRESHOLD and _can_alert("ram"):
                alerts.append(f"RAM: {mem.percent}% (>{RAM_THRESHOLD}%)")
            if disk.percent > DISK_THRESHOLD and _can_alert("disk"):
                alerts.append(f"Disk: {round(disk.percent, 1)}% (>{DISK_THRESHOLD}%)")

            if alerts:
                alert_summary = ", ".join(alerts)
                log_event("system", "resource_alert", alert_summary)
                msg = "⚠️ 리소스 경고\n\n" + "\n".join(alerts)
                msg += f"\n\nCPU: {cpu}% | RAM: {mem.percent}% | Disk: {round(disk.percent, 1)}%"
                logger.warning(msg)
                await send_telegram(msg)
        except Exception as e:
            logger.error(f"리소스 모니터링 오류: {e}")

        await asyncio.sleep(RESOURCE_CHECK_INTERVAL)
