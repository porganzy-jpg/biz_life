# -*- coding: utf-8 -*-
"""
자동 복구 엔진 (Auto-Healing Engine)
- 프로세스 헬스 모니터 & 자동 재시작 (지수 백오프 + 서킷 브레이커)
- 디스크 압력 자동 정리
- 포트 충돌 해결
- 연쇄 장애 방지 (우선순위 기반 시차 재시작)
- 복구 액션 감사 로그
- 프로젝트별 + 시스템 건강 점수

백그라운드 스레드로 동작하며, app.py API 및 텔레그램 봇과 통합됨
"""
import gzip
import json
import logging
import math
import os
import shutil
import socket
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import psutil

from config import PROJECTS, PROJECTS_DIR, HEALING_CONFIG
from services import (
    check_port_sync,
    find_pid_by_port,
    start_project,
    stop_project,
    restart_project,
    log_event,
    get_uptime_stats,
    _load_events,
)
from anomaly import (
    get_collector,
    get_alert_manager,
    AlertLevel,
    MaintenanceWindow,
)

logger = logging.getLogger("auto_healer")

# === 파일 경로 ===
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
HEALING_HISTORY_FILE = DATA_DIR / "healing_history.json"
HEALTH_SCORES_FILE = DATA_DIR / "health_scores.json"

_healing_lock = threading.Lock()
_scores_lock = threading.Lock()


# ============================================================
# Healing History (감사 로그)
# ============================================================

def _load_healing_history() -> list:
    """복구 이력 로드"""
    if not HEALING_HISTORY_FILE.exists():
        return []
    try:
        with open(HEALING_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_healing_history(history: list):
    """복구 이력 저장 (rolling 30일)"""
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    history = [h for h in history if h.get("timestamp", "") >= cutoff]
    # 최대 2000개 유지
    history = history[-2000:]
    with open(HEALING_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def record_healing_action(
    trigger: str,
    action: str,
    result: str,
    project: str = "",
    details: dict = None,
    severity: str = "INFO",
):
    """
    복구 액션 기록 및 텔레그램 알림
    severity: INFO, WARNING, CRITICAL
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "trigger": trigger,
        "action": action,
        "result": result,
        "project": project,
        "details": details or {},
        "severity": severity,
    }

    with _healing_lock:
        history = _load_healing_history()
        history.append(entry)
        _save_healing_history(history)

    logger.info(f"[HEAL] [{severity}] {trigger} -> {action} -> {result} (project={project})")

    # 이벤트 로그에도 기록
    if project:
        log_event(project, "auto_heal", f"{action}: {result}")

    # 텔레그램 알림
    _send_healing_telegram(entry)


def get_healing_history(limit: int = 50, project: str = None) -> list:
    """최근 복구 이력 반환"""
    with _healing_lock:
        history = _load_healing_history()
    if project:
        history = [h for h in history if h.get("project") == project]
    return history[-limit:][::-1]


def _send_healing_telegram(entry: dict):
    """복구 액션 텔레그램 알림"""
    import httpx

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        return

    severity = entry.get("severity", "INFO")
    severity_icons = {
        "INFO": "\u2139\ufe0f",       # info
        "WARNING": "\u26a0\ufe0f",    # warning
        "CRITICAL": "\U0001f6a8",     # siren
    }
    icon = severity_icons.get(severity, "\U0001f527")

    project_str = f"\n\ud83d\udce6 \ud504\ub85c\uc81d\ud2b8: {entry.get('project')}" if entry.get("project") else ""

    message = (
        f"{icon} [\uc790\ub3d9 \ubcf5\uad6c] {entry.get('action', '')}\n"
        f"\n\ud2b8\ub9ac\uac70: {entry.get('trigger', '')}"
        f"{project_str}\n"
        f"\uacb0\uacfc: {entry.get('result', '')}\n"
        f"\uc2dc\uac04: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        with httpx.Client(timeout=10) as client:
            client.post(url, json={"chat_id": chat_id, "text": message})
    except Exception as e:
        logger.error(f"복구 알림 텔레그램 전송 실패: {e}")


# ============================================================
# Circuit Breaker (서킷 브레이커)
# ============================================================

class CircuitBreaker:
    """
    프로젝트별 서킷 브레이커: N분 이내 M회 재시작 실패 시 자동 재시작 중단
    """

    def __init__(self):
        self.max_failures = HEALING_CONFIG.get("CIRCUIT_BREAKER_MAX_FAILURES", 3)
        self.window_minutes = HEALING_CONFIG.get("CIRCUIT_BREAKER_WINDOW_MINUTES", 15)
        self._failures: dict[str, list[float]] = {}  # project -> [failure_timestamps]
        self._open_until: dict[str, float] = {}  # project -> open_until_timestamp
        self._lock = threading.Lock()

    def record_failure(self, project: str):
        """재시작 실패 기록"""
        with self._lock:
            now = time.time()
            if project not in self._failures:
                self._failures[project] = []
            self._failures[project].append(now)
            # 윈도우 밖의 오래된 실패 제거
            cutoff = now - (self.window_minutes * 60)
            self._failures[project] = [t for t in self._failures[project] if t > cutoff]

            # 실패 횟수가 임계치 초과 시 서킷 오픈
            if len(self._failures[project]) >= self.max_failures:
                cooldown_minutes = HEALING_CONFIG.get("CIRCUIT_BREAKER_COOLDOWN_MINUTES", 30)
                self._open_until[project] = now + (cooldown_minutes * 60)
                logger.warning(
                    f"서킷 브레이커 OPEN: {project} "
                    f"({len(self._failures[project])}회 실패 / {self.window_minutes}분)"
                )
                record_healing_action(
                    trigger=f"서킷 브레이커",
                    action=f"자동 재시작 중단",
                    result=f"{self.max_failures}회 실패로 {cooldown_minutes}분간 재시작 중단",
                    project=project,
                    severity="CRITICAL",
                )

    def record_success(self, project: str):
        """재시작 성공 시 실패 기록 초기화"""
        with self._lock:
            self._failures.pop(project, None)
            self._open_until.pop(project, None)

    def is_open(self, project: str) -> bool:
        """서킷이 열려있으면 (자동 재시작 차단) True"""
        with self._lock:
            until = self._open_until.get(project)
            if until is None:
                return False
            if time.time() > until:
                # 쿨다운 종료 -> 서킷 닫기 (half-open -> closed)
                self._open_until.pop(project, None)
                self._failures.pop(project, None)
                logger.info(f"서킷 브레이커 CLOSED: {project} (쿨다운 종료)")
                return False
            return True

    def get_status(self) -> dict:
        """전체 서킷 브레이커 상태"""
        with self._lock:
            status = {}
            now = time.time()
            for project in set(list(self._failures.keys()) + list(self._open_until.keys())):
                is_open = project in self._open_until and self._open_until[project] > now
                remaining = 0
                if is_open:
                    remaining = int(self._open_until[project] - now)
                status[project] = {
                    "open": is_open,
                    "failures": len(self._failures.get(project, [])),
                    "remaining_seconds": remaining,
                }
            return status

    def reset(self, project: str = None):
        """서킷 브레이커 수동 리셋"""
        with self._lock:
            if project:
                self._failures.pop(project, None)
                self._open_until.pop(project, None)
            else:
                self._failures.clear()
                self._open_until.clear()


# ============================================================
# Exponential Backoff Tracker (지수 백오프)
# ============================================================

class BackoffTracker:
    """
    프로젝트별 지수 백오프 추적
    1차: 즉시, 2차: 30초 대기, 3차: 60초 대기, 4차 이상: 알림 후 서킷 브레이커
    """

    def __init__(self):
        self._attempts: dict[str, int] = {}
        self._last_attempt: dict[str, float] = {}
        self._lock = threading.Lock()
        # 백오프 시간 (초): 인덱스가 시도 횟수
        self.backoff_delays = [
            0,    # 1차: 즉시
            30,   # 2차: 30초
            60,   # 3차: 60초
        ]

    def can_attempt(self, project: str) -> bool:
        """백오프 대기 시간이 지났는지 확인"""
        with self._lock:
            attempts = self._attempts.get(project, 0)
            last = self._last_attempt.get(project, 0)

            if attempts >= len(self.backoff_delays):
                return False  # 최대 시도 초과 -> 사람에게 알림

            if attempts == 0:
                return True

            delay = self.backoff_delays[min(attempts, len(self.backoff_delays) - 1)]
            return time.time() - last >= delay

    def record_attempt(self, project: str):
        """시도 기록"""
        with self._lock:
            self._attempts[project] = self._attempts.get(project, 0) + 1
            self._last_attempt[project] = time.time()

    def get_attempt_count(self, project: str) -> int:
        with self._lock:
            return self._attempts.get(project, 0)

    def is_exhausted(self, project: str) -> bool:
        """최대 시도 횟수 초과 여부"""
        with self._lock:
            return self._attempts.get(project, 0) >= len(self.backoff_delays)

    def reset(self, project: str):
        """성공 시 리셋"""
        with self._lock:
            self._attempts.pop(project, None)
            self._last_attempt.pop(project, None)


# ============================================================
# Process Health Monitor (프로세스 건강 모니터)
# ============================================================

class ProcessHealthMonitor:
    """
    프로세스 수준 건강 모니터링:
    - 좀비/행 프로세스 감지 (CPU 0% 또는 100% 지속)
    - 메모리 누수 프로세스 감지
    """

    def __init__(self):
        self.cpu_stuck_threshold_seconds = HEALING_CONFIG.get("CPU_STUCK_THRESHOLD_SECONDS", 300)
        self.memory_growth_threshold_mb = HEALING_CONFIG.get("MEMORY_GROWTH_THRESHOLD_MB", 100)
        self.memory_check_window_minutes = HEALING_CONFIG.get("MEMORY_CHECK_WINDOW_MINUTES", 30)
        # 프로세스별 메모리 히스토리: {pid: [(timestamp, rss_mb), ...]}
        self._memory_history: dict[int, list] = {}
        self._cpu_history: dict[int, list] = {}
        self._lock = threading.Lock()

    def check_process_health(self, project_name: str, port: int) -> Optional[dict]:
        """
        프로세스 건강 체크.
        반환: None (정상) 또는 {"issue": ..., "details": ...}
        """
        pid = find_pid_by_port(port)
        if not pid:
            return None  # 프로세스 없음 -> 일반 헬스체크에서 처리

        try:
            proc = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return None

        now = time.time()
        issues = []

        # CPU 체크
        try:
            cpu_pct = proc.cpu_percent(interval=0.5)
            with self._lock:
                if pid not in self._cpu_history:
                    self._cpu_history[pid] = []
                self._cpu_history[pid].append((now, cpu_pct))
                # 최근 기록만 유지
                cutoff = now - self.cpu_stuck_threshold_seconds
                self._cpu_history[pid] = [
                    (t, c) for t, c in self._cpu_history[pid] if t > cutoff
                ]

                # CPU 0% 지속 체크 (좀비 프로세스)
                if len(self._cpu_history[pid]) >= 5:
                    all_zero = all(c < 0.1 for _, c in self._cpu_history[pid])
                    if all_zero:
                        duration = now - self._cpu_history[pid][0][0]
                        if duration >= self.cpu_stuck_threshold_seconds:
                            issues.append({
                                "issue": "zombie_process",
                                "message": f"CPU 0% 지속 ({int(duration)}초)",
                                "pid": pid,
                                "cpu": cpu_pct,
                            })

                    # CPU 100% 지속 체크 (행 프로세스)
                    all_max = all(c > 95 for _, c in self._cpu_history[pid])
                    if all_max:
                        duration = now - self._cpu_history[pid][0][0]
                        if duration >= self.cpu_stuck_threshold_seconds:
                            issues.append({
                                "issue": "hung_process",
                                "message": f"CPU 100% 지속 ({int(duration)}초)",
                                "pid": pid,
                                "cpu": cpu_pct,
                            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        # 메모리 체크
        try:
            mem_info = proc.memory_info()
            rss_mb = mem_info.rss / (1024 * 1024)
            with self._lock:
                if pid not in self._memory_history:
                    self._memory_history[pid] = []
                self._memory_history[pid].append((now, rss_mb))
                # 윈도우 내 기록만 유지
                cutoff = now - (self.memory_check_window_minutes * 60)
                self._memory_history[pid] = [
                    (t, m) for t, m in self._memory_history[pid] if t > cutoff
                ]

                # 메모리 지속 증가 체크
                if len(self._memory_history[pid]) >= 5:
                    first_mem = self._memory_history[pid][0][1]
                    growth = rss_mb - first_mem
                    if growth > self.memory_growth_threshold_mb:
                        # 단조 증가 확인
                        mems = [m for _, m in self._memory_history[pid]]
                        increasing = sum(
                            1 for i in range(1, len(mems)) if mems[i] >= mems[i - 1] - 1
                        )
                        if increasing >= len(mems) * 0.7:
                            issues.append({
                                "issue": "memory_leak",
                                "message": f"메모리 증가 +{growth:.0f}MB ({int(self.memory_check_window_minutes)}분)",
                                "pid": pid,
                                "rss_mb": round(rss_mb, 1),
                                "growth_mb": round(growth, 1),
                            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        if issues:
            return {
                "project": project_name,
                "pid": pid,
                "issues": issues,
            }
        return None

    def cleanup_stale(self, active_pids: set):
        """더 이상 추적하지 않는 PID 정리"""
        with self._lock:
            stale = set(self._cpu_history.keys()) - active_pids
            for pid in stale:
                self._cpu_history.pop(pid, None)
                self._memory_history.pop(pid, None)


# ============================================================
# Disk Pressure Auto-Cleanup (디스크 압력 자동 정리)
# ============================================================

class DiskCleaner:
    """
    디스크 사용량 초과 시 안전한 대상 자동 정리:
    - N일 이상 된 로그 파일
    - __pycache__ 디렉토리
    - .pyc 파일
    - 임시 파일
    - 로그 로테이션 (최근 5개 유지, 오래된 것 압축)
    """

    def __init__(self):
        self.disk_threshold = HEALING_CONFIG.get("DISK_CLEANUP_THRESHOLD", 90)
        self.log_retention_days = HEALING_CONFIG.get("LOG_RETENTION_DAYS", 7)
        self.max_log_files = HEALING_CONFIG.get("MAX_LOG_FILES_PER_PROJECT", 5)
        self.temp_patterns = HEALING_CONFIG.get("TEMP_FILE_PATTERNS", [
            "*.tmp", "*.temp", "*.bak", "*.swp",
        ])

    def check_and_clean(self) -> Optional[dict]:
        """
        디스크 사용량 확인 후 필요 시 자동 정리 실행
        반환: 정리 결과 또는 None (정리 불필요)
        """
        try:
            disk = psutil.disk_usage("C:\\")
        except Exception:
            return None

        if disk.percent < self.disk_threshold:
            return None

        logger.warning(f"디스크 사용률 {disk.percent:.1f}% - 자동 정리 시작")

        total_freed = 0
        cleaned_items = []

        # 1. 프로젝트별 로그 정리
        freed, items = self._clean_old_logs()
        total_freed += freed
        cleaned_items.extend(items)

        # 2. __pycache__ 디렉토리 정리
        freed, items = self._clean_pycache()
        total_freed += freed
        cleaned_items.extend(items)

        # 3. .pyc 파일 정리
        freed, items = self._clean_pyc_files()
        total_freed += freed
        cleaned_items.extend(items)

        # 4. 임시 파일 정리
        freed, items = self._clean_temp_files()
        total_freed += freed
        cleaned_items.extend(items)

        # 5. 로그 로테이션
        freed, items = self._rotate_logs()
        total_freed += freed
        cleaned_items.extend(items)

        freed_mb = total_freed / (1024 * 1024)

        result = {
            "disk_before": round(disk.percent, 1),
            "freed_bytes": total_freed,
            "freed_mb": round(freed_mb, 2),
            "cleaned_items": cleaned_items,
            "item_count": len(cleaned_items),
        }

        # 정리 후 디스크 재확인
        try:
            disk_after = psutil.disk_usage("C:\\")
            result["disk_after"] = round(disk_after.percent, 1)
        except Exception:
            result["disk_after"] = None

        if total_freed > 0:
            record_healing_action(
                trigger=f"디스크 사용률 {disk.percent:.1f}%",
                action="디스크 자동 정리",
                result=f"{freed_mb:.1f}MB 확보 ({len(cleaned_items)}개 항목)",
                details=result,
                severity="WARNING",
            )

        return result

    def _clean_old_logs(self) -> tuple[int, list]:
        """N일 이상 된 로그 파일 삭제"""
        freed = 0
        items = []
        cutoff = datetime.now() - timedelta(days=self.log_retention_days)
        cutoff_ts = cutoff.timestamp()

        for project_name in PROJECTS:
            log_dir = PROJECTS_DIR / project_name / "logs"
            if not log_dir.exists():
                continue
            for log_file in log_dir.glob("*.log"):
                try:
                    mtime = log_file.stat().st_mtime
                    if mtime < cutoff_ts:
                        size = log_file.stat().st_size
                        log_file.unlink()
                        freed += size
                        items.append({
                            "type": "old_log",
                            "path": str(log_file),
                            "size": size,
                            "project": project_name,
                        })
                except (OSError, PermissionError) as e:
                    logger.debug(f"로그 삭제 실패: {log_file} - {e}")

        # 서버 모니터 자체 로그도 정리
        monitor_log_dir = BASE_DIR / "logs"
        if monitor_log_dir.exists():
            for log_file in monitor_log_dir.glob("*.log"):
                try:
                    mtime = log_file.stat().st_mtime
                    if mtime < cutoff_ts:
                        size = log_file.stat().st_size
                        log_file.unlink()
                        freed += size
                        items.append({
                            "type": "old_log",
                            "path": str(log_file),
                            "size": size,
                            "project": "00-server-monitor",
                        })
                except (OSError, PermissionError):
                    pass

        return freed, items

    def _clean_pycache(self) -> tuple[int, list]:
        """__pycache__ 디렉토리 삭제"""
        freed = 0
        items = []
        for project_name in PROJECTS:
            project_dir = PROJECTS_DIR / project_name
            if not project_dir.exists():
                continue
            for pycache_dir in project_dir.rglob("__pycache__"):
                try:
                    size = sum(f.stat().st_size for f in pycache_dir.rglob("*") if f.is_file())
                    shutil.rmtree(str(pycache_dir), ignore_errors=True)
                    freed += size
                    items.append({
                        "type": "pycache",
                        "path": str(pycache_dir),
                        "size": size,
                        "project": project_name,
                    })
                except (OSError, PermissionError):
                    pass
        return freed, items

    def _clean_pyc_files(self) -> tuple[int, list]:
        """.pyc 파일 삭제"""
        freed = 0
        items = []
        for project_name in PROJECTS:
            project_dir = PROJECTS_DIR / project_name
            if not project_dir.exists():
                continue
            for pyc_file in project_dir.rglob("*.pyc"):
                try:
                    size = pyc_file.stat().st_size
                    pyc_file.unlink()
                    freed += size
                    items.append({
                        "type": "pyc",
                        "path": str(pyc_file),
                        "size": size,
                        "project": project_name,
                    })
                except (OSError, PermissionError):
                    pass
        return freed, items

    def _clean_temp_files(self) -> tuple[int, list]:
        """임시 파일 삭제"""
        freed = 0
        items = []
        for project_name in PROJECTS:
            project_dir = PROJECTS_DIR / project_name
            if not project_dir.exists():
                continue
            for pattern in self.temp_patterns:
                for temp_file in project_dir.rglob(pattern):
                    try:
                        size = temp_file.stat().st_size
                        temp_file.unlink()
                        freed += size
                        items.append({
                            "type": "temp",
                            "path": str(temp_file),
                            "size": size,
                            "project": project_name,
                        })
                    except (OSError, PermissionError):
                        pass
        return freed, items

    def _rotate_logs(self) -> tuple[int, list]:
        """프로젝트별 로그 로테이션: 최근 N개 유지, 나머지 gzip 압축"""
        freed = 0
        items = []
        for project_name in PROJECTS:
            log_dir = PROJECTS_DIR / project_name / "logs"
            if not log_dir.exists():
                continue

            log_files = sorted(
                log_dir.glob("*.log"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )

            # 최근 N개 제외한 나머지 압축
            for log_file in log_files[self.max_log_files:]:
                gz_path = log_file.with_suffix(".log.gz")
                try:
                    original_size = log_file.stat().st_size
                    with open(log_file, "rb") as f_in:
                        with gzip.open(gz_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    compressed_size = gz_path.stat().st_size
                    log_file.unlink()
                    saved = original_size - compressed_size
                    if saved > 0:
                        freed += saved
                    items.append({
                        "type": "log_rotation",
                        "path": str(log_file),
                        "original_size": original_size,
                        "compressed_size": compressed_size,
                        "project": project_name,
                    })
                except (OSError, PermissionError) as e:
                    logger.debug(f"로그 로테이션 실패: {log_file} - {e}")

        return freed, items


# ============================================================
# Port Conflict Resolver (포트 충돌 해결)
# ============================================================

class PortConflictResolver:
    """
    포트 충돌 감지 및 해결:
    - 프로젝트 시작 시 포트 사용 중이면 충돌 프로세스 식별
    - 선택적으로 충돌 프로세스 종료 후 재시도
    """

    def __init__(self):
        self.auto_kill = HEALING_CONFIG.get("PORT_CONFLICT_AUTO_KILL", True)

    def check_port_conflict(self, project_name: str, port: int) -> Optional[dict]:
        """
        포트 충돌 확인.
        반환: None (충돌 없음) 또는 충돌 정보 dict
        """
        pid = find_pid_by_port(port)
        if not pid:
            return None

        # 해당 프로젝트 자체의 프로세스인지 확인
        # (프로젝트가 이미 실행 중이면 충돌이 아님)
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            proc_cmdline = " ".join(proc.cmdline()[:5])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

        return {
            "port": port,
            "pid": pid,
            "process_name": proc_name,
            "cmdline": proc_cmdline,
            "project": project_name,
        }

    def resolve_conflict(self, project_name: str, port: int) -> dict:
        """
        포트 충돌 해결: 충돌 프로세스 종료 후 프로젝트 시작 재시도
        반환: {ok: bool, msg: str, details: dict}
        """
        conflict = self.check_port_conflict(project_name, port)
        if not conflict:
            return {"ok": True, "msg": "포트 충돌 없음"}

        result_details = {"conflict": conflict}

        if not self.auto_kill:
            return {
                "ok": False,
                "msg": f"포트 {port} 충돌 (PID {conflict['pid']}), 자동 종료 비활성",
                "details": result_details,
            }

        # 충돌 프로세스 종료
        try:
            proc = psutil.Process(conflict["pid"])
            proc_name = proc.name()
            children = proc.children(recursive=True)
            for child in children:
                child.terminate()
            proc.terminate()
            proc.wait(timeout=5)

            logger.info(f"포트 충돌 해결: PID {conflict['pid']} ({proc_name}) 종료")

            # 포트가 해제될 때까지 대기
            for _ in range(10):
                time.sleep(0.5)
                if not find_pid_by_port(port):
                    break

            # 프로젝트 재시작
            start_result = start_project(project_name)
            result_details["start_result"] = start_result

            if start_result.get("ok"):
                record_healing_action(
                    trigger=f"포트 {port} 충돌",
                    action=f"충돌 프로세스 종료 (PID {conflict['pid']}) 후 재시작",
                    result=start_result.get("msg", ""),
                    project=project_name,
                    details=result_details,
                    severity="WARNING",
                )
                return {"ok": True, "msg": f"포트 충돌 해결됨: {start_result['msg']}", "details": result_details}
            else:
                return {"ok": False, "msg": f"충돌 해결 후 시작 실패: {start_result['msg']}", "details": result_details}

        except psutil.NoSuchProcess:
            return {"ok": True, "msg": "충돌 프로세스 이미 종료됨"}
        except Exception as e:
            return {"ok": False, "msg": f"충돌 해결 실패: {e}", "details": result_details}


# ============================================================
# Cascading Failure Prevention (연쇄 장애 방지)
# ============================================================

class CascadePreventor:
    """
    연쇄 장애 방지:
    - 동시 다중 프로젝트 장애 감지
    - 우선순위 기반 시차 재시작
    - 의존성 인식 (DB 등 선행 서비스 확인)
    """

    def __init__(self):
        self.stagger_delay = HEALING_CONFIG.get("CASCADE_STAGGER_DELAY_SECONDS", 10)
        self.simultaneous_threshold = HEALING_CONFIG.get("CASCADE_SIMULTANEOUS_THRESHOLD", 2)
        self.project_priorities = HEALING_CONFIG.get("PROJECT_PRIORITIES", {})
        self.project_dependencies = HEALING_CONFIG.get("PROJECT_DEPENDENCIES", {})
        self._recent_failures: list[tuple[float, str]] = []
        self._lock = threading.Lock()

    def record_failure(self, project: str):
        """프로젝트 장애 기록"""
        with self._lock:
            now = time.time()
            self._recent_failures.append((now, project))
            # 최근 60초 내 기록만 유지
            cutoff = now - 60
            self._recent_failures = [(t, p) for t, p in self._recent_failures if t > cutoff]

    def is_cascade_detected(self) -> bool:
        """연쇄 장애 발생 여부"""
        with self._lock:
            now = time.time()
            recent = [(t, p) for t, p in self._recent_failures if now - t < 60]
            unique_projects = set(p for _, p in recent)
            return len(unique_projects) >= self.simultaneous_threshold

    def get_restart_order(self, failed_projects: list[str]) -> list[str]:
        """우선순위 기반 재시작 순서 결정"""
        def priority_key(name):
            return self.project_priorities.get(name, 50)

        return sorted(failed_projects, key=priority_key)

    def check_dependencies(self, project: str) -> tuple[bool, str]:
        """
        프로젝트 의존성 확인.
        반환: (all_ok, message)
        """
        deps = self.project_dependencies.get(project, [])
        if not deps:
            return True, ""

        missing = []
        for dep in deps:
            if dep in PROJECTS:
                if not check_port_sync(PROJECTS[dep]["port"]):
                    missing.append(dep)

        if missing:
            return False, f"의존성 미충족: {', '.join(missing)}"
        return True, ""

    def staggered_restart(self, failed_projects: list[str]) -> list[dict]:
        """
        시차 재시작 실행.
        반환: 각 프로젝트의 재시작 결과 리스트
        """
        ordered = self.get_restart_order(failed_projects)
        results = []

        record_healing_action(
            trigger="연쇄 장애 감지",
            action=f"시차 재시작 시작 ({len(ordered)}개 프로젝트)",
            result=f"순서: {', '.join(ordered)}",
            severity="CRITICAL",
        )

        for project in ordered:
            # 의존성 확인
            deps_ok, deps_msg = self.check_dependencies(project)
            if not deps_ok:
                results.append({
                    "project": project,
                    "ok": False,
                    "msg": f"시작 보류 - {deps_msg}",
                    "skipped": True,
                })
                record_healing_action(
                    trigger="의존성 미충족",
                    action=f"시작 보류",
                    result=deps_msg,
                    project=project,
                    severity="WARNING",
                )
                continue

            # 재시작
            try:
                result = restart_project(project)
                results.append({
                    "project": project,
                    "ok": result.get("ok", False),
                    "msg": result.get("msg", ""),
                })
                record_healing_action(
                    trigger="연쇄 장애 복구",
                    action="시차 재시작",
                    result=result.get("msg", ""),
                    project=project,
                    severity="INFO" if result.get("ok") else "WARNING",
                )
            except Exception as e:
                results.append({
                    "project": project,
                    "ok": False,
                    "msg": str(e),
                })

            # 시차 대기
            if project != ordered[-1]:
                time.sleep(self.stagger_delay)

        return results


# ============================================================
# Health Score System (건강 점수 시스템)
# ============================================================

class HealthScoreCalculator:
    """
    프로젝트별 건강 점수 (0-100):
    - 가동률 (40%) : 24시간 uptime
    - 재시작 빈도 (20%) : 적을수록 좋음
    - 응답 시간 추세 (20%) : 빠를수록 좋음
    - 리소스 사용 추세 (20%) : 낮을수록 좋음
    """

    def __init__(self):
        self.weights = HEALING_CONFIG.get("HEALTH_SCORE_WEIGHTS", {
            "uptime": 0.40,
            "restart_frequency": 0.20,
            "response_time": 0.20,
            "resource_usage": 0.20,
        })

    def calculate_project_score(self, project_name: str) -> dict:
        """프로젝트별 건강 점수 계산"""
        scores = {}

        # 1. 가동률 점수 (0-100)
        uptime_stats = get_uptime_stats()
        proj_stats = uptime_stats.get(project_name, {})
        uptime_pct = proj_stats.get("uptime_percent", 0.0)
        scores["uptime"] = min(uptime_pct, 100)

        # 2. 재시작 빈도 점수 (0-100): 24시간 내 재시작 횟수 기반
        events = _load_events()
        now = datetime.now()
        day_ago = (now - timedelta(hours=24)).isoformat()
        restart_count = sum(
            1 for e in events
            if e.get("project") == project_name
            and e.get("type") in ("restart", "auto_restart", "auto_heal")
            and e.get("timestamp", "") >= day_ago
        )
        # 0회 = 100점, 1회 = 80점, 2회 = 60점, 3회 = 40점, 4회 = 20점, 5+회 = 0점
        scores["restart_frequency"] = max(0, 100 - (restart_count * 20))

        # 3. 응답 시간 점수 (0-100): 현재 포트 응답 속도 기반
        port = PROJECTS.get(project_name, {}).get("port")
        if port:
            response_score = self._measure_response_score(port)
            scores["response_time"] = response_score
        else:
            scores["response_time"] = 0

        # 4. 리소스 사용 추세 점수 (0-100): 시스템 메트릭 기반
        resource_score = self._calculate_resource_score()
        scores["resource_usage"] = resource_score

        # 가중 평균 계산
        total = 0
        for key, weight in self.weights.items():
            total += scores.get(key, 0) * weight

        is_alive = check_port_sync(port) if port else False

        return {
            "project": project_name,
            "score": round(total, 1),
            "alive": is_alive,
            "components": {
                "uptime": round(scores.get("uptime", 0), 1),
                "restart_frequency": round(scores.get("restart_frequency", 0), 1),
                "response_time": round(scores.get("response_time", 0), 1),
                "resource_usage": round(scores.get("resource_usage", 0), 1),
            },
            "details": {
                "uptime_pct": round(uptime_pct, 1),
                "restart_count_24h": restart_count,
            },
            "timestamp": now.isoformat(),
        }

    def _measure_response_score(self, port: int) -> float:
        """포트 응답 시간 측정 -> 점수 변환"""
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            result = sock.connect_ex(("localhost", port))
            elapsed = time.time() - start
            sock.close()

            if result != 0:
                return 0  # 연결 실패

            # 응답 시간 기반 점수: <100ms=100, <500ms=80, <1000ms=60, <2000ms=40, <3000ms=20
            if elapsed < 0.1:
                return 100
            elif elapsed < 0.5:
                return 80
            elif elapsed < 1.0:
                return 60
            elif elapsed < 2.0:
                return 40
            elif elapsed < 3.0:
                return 20
            else:
                return 10
        except Exception:
            return 0

    def _calculate_resource_score(self) -> float:
        """시스템 리소스 사용량 기반 점수"""
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage("C:\\").percent

            # 각 리소스 점수: 0-50% = 100, 50-70% = 80, 70-85% = 60, 85-95% = 40, 95%+ = 20
            def resource_to_score(pct):
                if pct < 50:
                    return 100
                elif pct < 70:
                    return 80
                elif pct < 85:
                    return 60
                elif pct < 95:
                    return 40
                else:
                    return 20

            cpu_score = resource_to_score(cpu)
            mem_score = resource_to_score(mem)
            disk_score = resource_to_score(disk)

            return (cpu_score * 0.4 + mem_score * 0.35 + disk_score * 0.25)
        except Exception:
            return 50  # 기본값

    def calculate_all_scores(self) -> dict:
        """전체 프로젝트 + 시스템 건강 점수"""
        project_scores = {}
        total = 0
        count = 0

        for project_name in PROJECTS:
            score_data = self.calculate_project_score(project_name)
            project_scores[project_name] = score_data
            total += score_data["score"]
            count += 1

        system_score = round(total / count, 1) if count > 0 else 0

        # 시스템 수준 보정: 모든 프로젝트가 죽어있으면 0점
        alive_count = sum(1 for s in project_scores.values() if s.get("alive"))
        if alive_count == 0 and count > 0:
            system_score = 0

        result = {
            "system_score": system_score,
            "alive_count": alive_count,
            "total_count": count,
            "projects": project_scores,
            "timestamp": datetime.now().isoformat(),
        }

        # 점수 파일에 캐시 저장
        with _scores_lock:
            try:
                with open(HEALTH_SCORES_FILE, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            except IOError:
                pass

        return result

    def get_cached_scores(self) -> Optional[dict]:
        """캐시된 점수 반환 (5분 이내)"""
        with _scores_lock:
            if not HEALTH_SCORES_FILE.exists():
                return None
            try:
                with open(HEALTH_SCORES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ts = data.get("timestamp", "")
                if ts:
                    dt = datetime.fromisoformat(ts)
                    if datetime.now() - dt < timedelta(minutes=5):
                        return data
            except (json.JSONDecodeError, IOError, ValueError):
                pass
        return None


# ============================================================
# Auto-Healing Engine (메인 엔진)
# ============================================================

class AutoHealingEngine:
    """
    자동 복구 엔진 메인 클래스
    모든 자동 복구 컴포넌트를 통합하여 주기적으로 실행
    """

    def __init__(self):
        self.enabled = HEALING_CONFIG.get("HEALING_ENABLED", True)
        self.check_interval = HEALING_CONFIG.get("HEALING_CHECK_INTERVAL", 30)

        # 컴포넌트 초기화
        self.circuit_breaker = CircuitBreaker()
        self.backoff = BackoffTracker()
        self.process_monitor = ProcessHealthMonitor()
        self.disk_cleaner = DiskCleaner()
        self.port_resolver = PortConflictResolver()
        self.cascade_preventor = CascadePreventor()
        self.health_scorer = HealthScoreCalculator()

        self._running = False
        self._thread: Optional[threading.Thread] = None

    def run_healing_cycle(self):
        """단일 복구 사이클 실행"""
        if not self.enabled:
            return

        # 유지보수 윈도우 중이면 스킵
        mw = MaintenanceWindow()
        if mw.is_active():
            logger.debug("유지보수 윈도우 활성 - 자동 복구 스킵")
            return

        failed_projects = []
        active_pids = set()

        # === 1. 프로젝트별 헬스체크 ===
        for name, proj in PROJECTS.items():
            port = proj["port"]
            pid = find_pid_by_port(port)
            if pid:
                active_pids.add(pid)

            alive = check_port_sync(port)

            if alive:
                # 살아있으면 백오프/서킷 리셋
                self.backoff.reset(name)
                self.circuit_breaker.record_success(name)

                # 프로세스 수준 건강 체크
                health_result = self.process_monitor.check_process_health(name, port)
                if health_result:
                    for issue in health_result.get("issues", []):
                        issue_type = issue.get("issue", "")
                        if issue_type in ("zombie_process", "hung_process"):
                            logger.warning(f"프로세스 이상 감지: {name} - {issue.get('message')}")
                            self._handle_process_issue(name, port, issue)
                        elif issue_type == "memory_leak":
                            logger.warning(f"메모리 누수 감지: {name} - {issue.get('message')}")
                            record_healing_action(
                                trigger=f"메모리 누수 감지",
                                action=f"경고 알림 ({issue.get('message', '')})",
                                result=f"RSS: {issue.get('rss_mb', 0)}MB, 증가: +{issue.get('growth_mb', 0)}MB",
                                project=name,
                                severity="WARNING",
                            )
            else:
                # 죽었음
                failed_projects.append(name)
                self.cascade_preventor.record_failure(name)

        # 오래된 PID 정리
        self.process_monitor.cleanup_stale(active_pids)

        # === 2. 장애 프로젝트 복구 ===
        if failed_projects:
            if self.cascade_preventor.is_cascade_detected():
                # 연쇄 장애 감지 -> 시차 재시작
                logger.warning(f"연쇄 장애 감지: {failed_projects}")
                self._handle_cascade_failure(failed_projects)
            else:
                # 개별 복구
                for name in failed_projects:
                    self._handle_single_failure(name)

        # === 3. 디스크 정리 (매 10 사이클마다) ===
        if not hasattr(self, "_disk_check_counter"):
            self._disk_check_counter = 0
        self._disk_check_counter += 1
        if self._disk_check_counter >= 10:
            self._disk_check_counter = 0
            try:
                self.disk_cleaner.check_and_clean()
            except Exception as e:
                logger.error(f"디스크 정리 오류: {e}")

        # === 4. 건강 점수 업데이트 (매 5 사이클마다) ===
        if not hasattr(self, "_score_counter"):
            self._score_counter = 0
        self._score_counter += 1
        if self._score_counter >= 5:
            self._score_counter = 0
            try:
                self.health_scorer.calculate_all_scores()
            except Exception as e:
                logger.error(f"건강 점수 계산 오류: {e}")

    def _handle_single_failure(self, project_name: str):
        """단일 프로젝트 장애 처리"""
        proj = PROJECTS.get(project_name)
        if not proj:
            return

        port = proj["port"]

        # 서킷 브레이커 확인
        if self.circuit_breaker.is_open(project_name):
            logger.debug(f"서킷 브레이커 OPEN: {project_name} - 자동 재시작 스킵")
            return

        # 백오프 확인
        if self.backoff.is_exhausted(project_name):
            # 최대 시도 초과 -> 서킷 브레이커 활성화
            self.circuit_breaker.record_failure(project_name)
            record_healing_action(
                trigger="최대 재시작 시도 초과",
                action="자동 재시작 포기",
                result=f"{self.backoff.get_attempt_count(project_name)}회 시도 실패",
                project=project_name,
                severity="CRITICAL",
            )
            return

        if not self.backoff.can_attempt(project_name):
            return  # 백오프 대기 중

        # 포트 충돌 확인
        conflict = self.port_resolver.check_port_conflict(project_name, port)
        if conflict:
            resolve_result = self.port_resolver.resolve_conflict(project_name, port)
            if resolve_result.get("ok"):
                self.backoff.reset(project_name)
                return

        # 의존성 확인
        deps_ok, deps_msg = self.cascade_preventor.check_dependencies(project_name)
        if not deps_ok:
            logger.info(f"의존성 미충족으로 재시작 보류: {project_name} - {deps_msg}")
            return

        # 재시작 시도
        attempt = self.backoff.get_attempt_count(project_name) + 1
        self.backoff.record_attempt(project_name)

        logger.info(f"자동 복구 시도: {project_name} (시도 {attempt}/{len(self.backoff.backoff_delays)})")

        try:
            result = start_project(project_name)
            if result.get("ok"):
                self.backoff.reset(project_name)
                self.circuit_breaker.record_success(project_name)
                record_healing_action(
                    trigger="프로세스 다운 감지",
                    action=f"자동 시작 (시도 {attempt})",
                    result=result.get("msg", ""),
                    project=project_name,
                    severity="INFO",
                )
            else:
                self.circuit_breaker.record_failure(project_name)
                record_healing_action(
                    trigger="프로세스 다운 감지",
                    action=f"자동 시작 실패 (시도 {attempt})",
                    result=result.get("msg", ""),
                    project=project_name,
                    severity="WARNING",
                )
        except Exception as e:
            self.circuit_breaker.record_failure(project_name)
            record_healing_action(
                trigger="프로세스 다운 감지",
                action=f"자동 시작 예외 (시도 {attempt})",
                result=str(e),
                project=project_name,
                severity="WARNING",
            )

    def _handle_cascade_failure(self, failed_projects: list[str]):
        """연쇄 장애 처리: 우선순위 기반 시차 재시작"""
        # 서킷 브레이커가 열린 프로젝트 제외
        restartable = [
            p for p in failed_projects
            if not self.circuit_breaker.is_open(p) and not self.backoff.is_exhausted(p)
        ]

        if not restartable:
            logger.warning("연쇄 장애 발생했으나 모든 프로젝트 서킷 브레이커 OPEN")
            return

        results = self.cascade_preventor.staggered_restart(restartable)

        for r in results:
            project = r.get("project", "")
            if r.get("ok"):
                self.backoff.reset(project)
                self.circuit_breaker.record_success(project)
            elif not r.get("skipped"):
                self.circuit_breaker.record_failure(project)

    def _handle_process_issue(self, project_name: str, port: int, issue: dict):
        """프로세스 수준 이상 처리 (좀비/행 프로세스 재시작)"""
        issue_type = issue.get("issue", "")
        pid = issue.get("pid")

        record_healing_action(
            trigger=f"{issue_type} 감지",
            action="그레이스풀 재시작",
            result=f"PID {pid} - {issue.get('message', '')}",
            project=project_name,
            severity="WARNING",
        )

        try:
            result = restart_project(project_name)
            if result.get("ok"):
                record_healing_action(
                    trigger=f"{issue_type} 복구",
                    action="재시작 성공",
                    result=result.get("msg", ""),
                    project=project_name,
                    severity="INFO",
                )
            else:
                record_healing_action(
                    trigger=f"{issue_type} 복구",
                    action="재시작 실패",
                    result=result.get("msg", ""),
                    project=project_name,
                    severity="WARNING",
                )
        except Exception as e:
            logger.error(f"프로세스 이상 복구 실패: {project_name} - {e}")

    # === 수동 트리거 ===

    def manual_heal(self, project_name: str) -> dict:
        """수동 복구 트리거"""
        if project_name not in PROJECTS:
            return {"ok": False, "msg": f"알 수 없는 프로젝트: {project_name}"}

        proj = PROJECTS[project_name]
        port = proj["port"]
        alive = check_port_sync(port)

        actions_taken = []

        # 서킷 브레이커 리셋
        self.circuit_breaker.reset(project_name)
        self.backoff.reset(project_name)
        actions_taken.append("서킷 브레이커 리셋")

        if alive:
            # 프로세스 건강 체크
            health_result = self.process_monitor.check_process_health(project_name, port)
            if health_result and health_result.get("issues"):
                # 이상 감지 시 재시작
                result = restart_project(project_name)
                actions_taken.append(f"재시작: {result.get('msg', '')}")
                record_healing_action(
                    trigger="수동 복구",
                    action="프로세스 이상 감지 -> 재시작",
                    result=result.get("msg", ""),
                    project=project_name,
                    severity="INFO",
                )
                return {
                    "ok": result.get("ok", False),
                    "msg": f"이상 감지 -> 재시작: {result.get('msg', '')}",
                    "actions": actions_taken,
                }
            else:
                actions_taken.append("프로세스 정상")
                return {
                    "ok": True,
                    "msg": "프로젝트 정상 실행 중",
                    "actions": actions_taken,
                }
        else:
            # 포트 충돌 확인 및 해결
            conflict = self.port_resolver.check_port_conflict(project_name, port)
            if conflict:
                resolve_result = self.port_resolver.resolve_conflict(project_name, port)
                actions_taken.append(f"포트 충돌 해결: {resolve_result.get('msg', '')}")
                if resolve_result.get("ok"):
                    record_healing_action(
                        trigger="수동 복구",
                        action="포트 충돌 해결",
                        result=resolve_result.get("msg", ""),
                        project=project_name,
                        severity="INFO",
                    )
                    return {
                        "ok": True,
                        "msg": resolve_result.get("msg", ""),
                        "actions": actions_taken,
                    }

            # 시작 시도
            result = start_project(project_name)
            actions_taken.append(f"시작: {result.get('msg', '')}")
            record_healing_action(
                trigger="수동 복구",
                action="프로세스 시작",
                result=result.get("msg", ""),
                project=project_name,
                severity="INFO" if result.get("ok") else "WARNING",
            )
            return {
                "ok": result.get("ok", False),
                "msg": result.get("msg", ""),
                "actions": actions_taken,
            }

    def get_engine_status(self) -> dict:
        """엔진 상태 반환"""
        return {
            "enabled": self.enabled,
            "running": self._running,
            "check_interval": self.check_interval,
            "circuit_breaker": self.circuit_breaker.get_status(),
            "timestamp": datetime.now().isoformat(),
        }

    def get_healing_config(self) -> dict:
        """현재 설정 반환"""
        return dict(HEALING_CONFIG)

    def update_config(self, updates: dict) -> dict:
        """설정 업데이트 (런타임)"""
        updated = {}
        for key, value in updates.items():
            if key in HEALING_CONFIG:
                HEALING_CONFIG[key] = value
                updated[key] = value

        # 컴포넌트 설정 반영
        if "HEALING_ENABLED" in updated:
            self.enabled = updated["HEALING_ENABLED"]
        if "HEALING_CHECK_INTERVAL" in updated:
            self.check_interval = updated["HEALING_CHECK_INTERVAL"]

        return updated

    # === 백그라운드 스레드 ===

    def start(self):
        """백그라운드 복구 엔진 시작"""
        if self._running:
            logger.info("자동 복구 엔진 이미 실행 중")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._background_loop,
            daemon=True,
            name="auto-healer",
        )
        self._thread.start()
        logger.info(f"자동 복구 엔진 시작 (간격: {self.check_interval}초)")

    def stop(self):
        """엔진 정지"""
        self._running = False
        logger.info("자동 복구 엔진 정지")

    def _background_loop(self):
        """백그라운드 메인 루프"""
        # 초기 대기 (다른 서비스 부팅 대기)
        time.sleep(20)
        logger.info("자동 복구 엔진 메인 루프 시작")

        while self._running:
            try:
                self.run_healing_cycle()
            except Exception as e:
                logger.error(f"자동 복구 사이클 오류: {e}", exc_info=True)
            time.sleep(self.check_interval)


# ============================================================
# Singleton & Thread Start
# ============================================================

_engine: Optional[AutoHealingEngine] = None


def get_healing_engine() -> AutoHealingEngine:
    """AutoHealingEngine 싱글톤 반환"""
    global _engine
    if _engine is None:
        _engine = AutoHealingEngine()
    return _engine


def start_healing_thread() -> AutoHealingEngine:
    """자동 복구 엔진 백그라운드 스레드 시작"""
    engine = get_healing_engine()
    if not engine._running:
        engine.start()
    return engine


# ============================================================
# Bot Command Helpers (텔레그램 봇 커맨드)
# ============================================================

def bot_heal(args: list) -> str:
    """
    /heal [프로젝트명|all] - 수동 복구 트리거
    """
    engine = get_healing_engine()

    if not args or args[0].lower() == "all":
        # 전체 프로젝트 복구 시도
        results = []
        for name in PROJECTS:
            r = engine.manual_heal(name)
            icon = "\u2705" if r.get("ok") else "\u274c"
            results.append(f"{icon} {name}: {r.get('msg', '')}")
        return "\U0001f527 \uc804\uccb4 \ubcf5\uad6c \uacb0\uacfc\n\n" + "\n".join(results)

    project = args[0]
    if project not in PROJECTS:
        return f"\uc54c \uc218 \uc5c6\ub294 \ud504\ub85c\uc81d\ud2b8: {project}"

    r = engine.manual_heal(project)
    icon = "\u2705" if r.get("ok") else "\u274c"
    actions = "\n".join(f"  - {a}" for a in r.get("actions", []))
    return f"\U0001f527 \ubcf5\uad6c \uacb0\uacfc: {project}\n\n{icon} {r.get('msg', '')}\n\n\uc561\uc158:\n{actions}"


def bot_health(args: list) -> str:
    """
    /health [프로젝트명] - 건강 점수 조회
    """
    engine = get_healing_engine()
    scorer = engine.health_scorer

    if args:
        project = args[0]
        if project not in PROJECTS:
            return f"\uc54c \uc218 \uc5c6\ub294 \ud504\ub85c\uc81d\ud2b8: {project}"
        score_data = scorer.calculate_project_score(project)
        comp = score_data.get("components", {})
        details = score_data.get("details", {})
        alive_icon = "\U0001f7e2" if score_data.get("alive") else "\U0001f534"
        return (
            f"\U0001f4ca {project} \uac74\uac15 \uc810\uc218\n\n"
            f"{alive_icon} \uc885\ud569: {score_data['score']}\uc810/100\n\n"
            f"\uad6c\uc131 \uc694\uc18c:\n"
            f"  \uac00\ub3d9\ub960: {comp.get('uptime', 0)}\uc810 (24h {details.get('uptime_pct', 0)}%)\n"
            f"  \uc7ac\uc2dc\uc791 \ube48\ub3c4: {comp.get('restart_frequency', 0)}\uc810 (24h {details.get('restart_count_24h', 0)}\ud68c)\n"
            f"  \uc751\ub2f5 \uc2dc\uac04: {comp.get('response_time', 0)}\uc810\n"
            f"  \ub9ac\uc18c\uc2a4: {comp.get('resource_usage', 0)}\uc810"
        )

    # 전체 건강 점수
    all_scores = scorer.calculate_all_scores()
    lines = [
        f"\U0001f4ca \uc2dc\uc2a4\ud15c \uac74\uac15 \uc810\uc218: {all_scores['system_score']}\uc810/100",
        f"\uc2e4\ud589 \uc911: {all_scores['alive_count']}/{all_scores['total_count']}\n",
    ]
    for name, data in all_scores.get("projects", {}).items():
        alive_icon = "\U0001f7e2" if data.get("alive") else "\U0001f534"
        score = data.get("score", 0)
        if score >= 80:
            bar = "\u2588" * 4
        elif score >= 60:
            bar = "\u2588" * 3
        elif score >= 40:
            bar = "\u2588" * 2
        else:
            bar = "\u2588" * 1
        lines.append(f"{alive_icon} {name}: {score}\uc810 {bar}")

    return "\n".join(lines)
