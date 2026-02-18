"""
백그라운드 모니터링 엔진
- 프로젝트 헬스체크 + 자동 재시작
- 시스템 리소스 임계치 알림 (텔레그램)
"""
import asyncio
import logging
import os
import subprocess
import time
from datetime import datetime

import httpx
import psutil
from dotenv import load_dotenv

from config import PROJECTS, PROJECTS_DIR

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


# === 프로젝트 헬스체크 ===

async def check_port(port: int) -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"http://localhost:{port}/")
            return resp.status_code < 500
    except Exception:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"http://localhost:{port}/health")
                return resp.status_code < 500
        except Exception:
            return False


def find_pid_by_port(port: int):
    for conn in psutil.net_connections(kind="tcp"):
        if conn.laddr.port == port and conn.status == "LISTEN":
            return conn.pid
    return None


def start_project(name: str) -> str:
    proj = PROJECTS[name]
    project_dir = PROJECTS_DIR / name
    work_dir = project_dir / proj["cwd"]
    cmd = list(proj["cmd"])
    cmd[0] = str(project_dir / cmd[0])

    log_dir = project_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    with open(log_dir / "server.log", "a", encoding="utf-8") as lf:
        subprocess.Popen(
            cmd, cwd=str(work_dir), stdout=lf, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    return f"시작됨 (포트 {proj['port']})"


async def health_check_loop():
    """30초마다 프로젝트 상태 확인, 죽은 서비스 자동 재시작"""
    logger.info("헬스체크 루프 시작 (간격: %ds)", HEALTH_CHECK_INTERVAL)
    await asyncio.sleep(10)  # 초기 시작 대기

    while True:
        try:
            for name, proj in PROJECTS.items():
                alive = await check_port(proj["port"])
                if not alive and AUTO_RESTART_ENABLED:
                    pid = find_pid_by_port(proj["port"])
                    if pid:
                        # 포트는 안 응답하는데 프로세스는 있음 → 좀비
                        try:
                            proc = psutil.Process(pid)
                            for child in proc.children(recursive=True):
                                child.terminate()
                            proc.terminate()
                            proc.wait(timeout=5)
                        except Exception:
                            pass

                    # 재시작
                    result = start_project(name)
                    ts = datetime.now().strftime("%H:%M:%S")
                    msg = f"🔄 자동 재시작: {name}\n시간: {ts}\n결과: {result}"
                    logger.warning(msg)
                    if _can_alert(f"restart_{name}"):
                        await send_telegram(msg)
        except Exception as e:
            logger.error(f"헬스체크 오류: {e}")

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
                msg = "⚠️ 리소스 경고\n\n" + "\n".join(alerts)
                msg += f"\n\nCPU: {cpu}% | RAM: {mem.percent}% | Disk: {round(disk.percent, 1)}%"
                logger.warning(msg)
                await send_telegram(msg)
        except Exception as e:
            logger.error(f"리소스 모니터링 오류: {e}")

        await asyncio.sleep(RESOURCE_CHECK_INTERVAL)
