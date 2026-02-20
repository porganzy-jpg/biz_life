"""
Smart Alerting & Anomaly Detection Engine
- MetricsCollector: 시스템 메트릭 수집 및 저장 (rolling 24h)
- AnomalyDetector: CPU/Memory/Disk 이상 탐지 + 재시작 폭풍 감지
- AlertManager: 알림 레벨, 쿨다운, 유지보수 윈도우, 텔레그램 알림
- 백그라운드 스레드: 2분마다 이상 탐지 실행
"""
import json
import logging
import math
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import psutil

from config import ALERT_CONFIG

logger = logging.getLogger(__name__)

# === 파일 경로 ===
BASE_DIR = Path(__file__).parent
METRICS_FILE = BASE_DIR / "metrics_history.json"
ALERT_HISTORY_FILE = BASE_DIR / "alert_history.json"
MAINTENANCE_FILE = BASE_DIR / "maintenance_window.json"

_metrics_lock = threading.Lock()
_alert_lock = threading.Lock()
_maintenance_lock = threading.Lock()


# ============================================================
# AlertLevel
# ============================================================

class AlertLevel:
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# ============================================================
# MetricsCollector
# ============================================================

class MetricsCollector:
    """시스템 메트릭(CPU/Memory/Disk)을 주기적으로 수집하여 rolling 24h window에 저장"""

    def __init__(self, max_entries: int = None):
        self.max_entries = max_entries or ALERT_CONFIG.get("METRICS_MAX_ENTRIES", 1440)

    def collect(self) -> dict:
        """현재 시스템 메트릭 수집"""
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("C:\\")
            entry = {
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": cpu,
                "memory_percent": mem.percent,
                "memory_used_gb": round(mem.used / (1024 ** 3), 2),
                "memory_total_gb": round(mem.total / (1024 ** 3), 2),
                "disk_percent": round(disk.percent, 2),
                "disk_used_gb": round(disk.used / (1024 ** 3), 2),
                "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            }
            return entry
        except Exception as e:
            logger.error(f"메트릭 수집 오류: {e}")
            return {}

    def store(self, entry: dict):
        """메트릭을 파일에 저장 (rolling window)"""
        if not entry:
            return
        with _metrics_lock:
            history = self._load()
            history.append(entry)
            # rolling 24h window: 최대 항목 수 제한
            if len(history) > self.max_entries:
                history = history[-self.max_entries:]
            self._save(history)

    def collect_and_store(self) -> dict:
        """수집 + 저장을 한 번에"""
        entry = self.collect()
        self.store(entry)
        return entry

    def get_history(self, minutes: int = None) -> list:
        """메트릭 이력 반환. minutes 지정 시 해당 시간 내 데이터만."""
        with _metrics_lock:
            history = self._load()
        if minutes is not None:
            cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
            history = [h for h in history if h.get("timestamp", "") >= cutoff]
        return history

    def get_full_history(self) -> list:
        """전체 이력 반환 (API용)"""
        with _metrics_lock:
            return self._load()

    def _load(self) -> list:
        if not METRICS_FILE.exists():
            return []
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save(self, data: list):
        with open(METRICS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)


# ============================================================
# AnomalyDetector
# ============================================================

class AnomalyDetector:
    """시스템 메트릭 이력 기반 이상 탐지"""

    def __init__(self):
        self.cpu_std_multiplier = ALERT_CONFIG.get("CPU_STD_MULTIPLIER", 2.0)
        self.cpu_consecutive_min = ALERT_CONFIG.get("CPU_CONSECUTIVE_MIN", 3)
        self.memory_leak_minutes = ALERT_CONFIG.get("MEMORY_LEAK_MINUTES", 30)
        self.disk_threshold = ALERT_CONFIG.get("DISK_THRESHOLD", 90)
        self.disk_growth_threshold = ALERT_CONFIG.get("DISK_GROWTH_RATE_THRESHOLD", 1.0)
        self.disk_predict_target = ALERT_CONFIG.get("DISK_PREDICT_TARGET", 95)
        self.restart_storm_count = ALERT_CONFIG.get("RESTART_STORM_COUNT", 3)
        self.restart_storm_window = ALERT_CONFIG.get("RESTART_STORM_WINDOW_MINUTES", 10)

    def detect_cpu_anomaly(self, history: list) -> Optional[dict]:
        """
        CPU 이상 탐지: rolling 1h 평균 대비 2 표준편차 초과가 3회 연속 시 알림
        반환: {"level": ..., "message": ..., "details": ...} or None
        """
        if len(history) < 10:
            return None

        # 최근 1시간 데이터
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        recent = [h for h in history if h.get("timestamp", "") >= one_hour_ago]
        if len(recent) < 5:
            return None

        cpu_values = [h["cpu_percent"] for h in recent if "cpu_percent" in h]
        if len(cpu_values) < 5:
            return None

        mean = sum(cpu_values) / len(cpu_values)
        variance = sum((x - mean) ** 2 for x in cpu_values) / len(cpu_values)
        std_dev = math.sqrt(variance) if variance > 0 else 0

        if std_dev == 0:
            return None

        threshold = mean + (self.cpu_std_multiplier * std_dev)

        # 마지막 N개 readings가 모두 threshold 초과인지 확인
        tail = cpu_values[-self.cpu_consecutive_min:]
        if len(tail) < self.cpu_consecutive_min:
            return None

        if all(v > threshold for v in tail):
            current = tail[-1]
            level = AlertLevel.CRITICAL if current > 95 else AlertLevel.WARNING
            return {
                "type": "cpu_anomaly",
                "level": level,
                "message": f"CPU 이상 감지: {current:.1f}% (1h 평균 {mean:.1f}%, 임계 {threshold:.1f}%)",
                "details": {
                    "current": current,
                    "mean_1h": round(mean, 1),
                    "std_dev": round(std_dev, 1),
                    "threshold": round(threshold, 1),
                    "consecutive": self.cpu_consecutive_min,
                },
            }
        return None

    def detect_memory_leak(self, history: list) -> Optional[dict]:
        """
        메모리 누수 탐지: 30분 이상 메모리가 단조 증가하면 알림
        반환: {"level": ..., "message": ..., "details": ...} or None
        """
        window_ago = (datetime.now() - timedelta(minutes=self.memory_leak_minutes)).isoformat()
        recent = [h for h in history if h.get("timestamp", "") >= window_ago]
        if len(recent) < 5:
            return None

        mem_values = [h["memory_percent"] for h in recent if "memory_percent" in h]
        if len(mem_values) < 5:
            return None

        # 단조 증가 확인 (약간의 허용 오차: -0.1%)
        monotonic_count = 0
        for i in range(1, len(mem_values)):
            if mem_values[i] >= mem_values[i - 1] - 0.1:
                monotonic_count += 1
            else:
                monotonic_count = 0

        # 전체 기간의 80% 이상이 단조 증가이면 누수로 판단
        if monotonic_count >= len(mem_values) * 0.8:
            increase = mem_values[-1] - mem_values[0]
            if increase > 0.5:  # 최소 0.5% 증가
                level = AlertLevel.CRITICAL if mem_values[-1] > 90 else AlertLevel.WARNING
                return {
                    "type": "memory_leak",
                    "level": level,
                    "message": f"메모리 누수 의심: {mem_values[-1]:.1f}% (최근 {self.memory_leak_minutes}분간 +{increase:.1f}%)",
                    "details": {
                        "current": round(mem_values[-1], 1),
                        "start": round(mem_values[0], 1),
                        "increase": round(increase, 1),
                        "window_minutes": self.memory_leak_minutes,
                    },
                }
        return None

    def detect_disk_pressure(self, history: list) -> Optional[dict]:
        """
        디스크 압력 탐지:
        - 현재 디스크 사용률 > 90%
        - 또는 시간당 증가율 > 1%
        """
        if not history:
            return None

        current = history[-1]
        disk_pct = current.get("disk_percent", 0)

        # 절대 임계치
        if disk_pct > self.disk_threshold:
            level = AlertLevel.CRITICAL if disk_pct > 95 else AlertLevel.WARNING
            return {
                "type": "disk_pressure",
                "level": level,
                "message": f"디스크 사용률 위험: {disk_pct:.1f}% (임계 {self.disk_threshold}%)",
                "details": {
                    "current": disk_pct,
                    "threshold": self.disk_threshold,
                },
            }

        # 시간당 증가율 확인
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        old_readings = [h for h in history if h.get("timestamp", "") <= one_hour_ago]
        if old_readings:
            old_disk = old_readings[-1].get("disk_percent", 0)
            growth_rate = disk_pct - old_disk  # %/hour
            if growth_rate > self.disk_growth_threshold:
                return {
                    "type": "disk_pressure",
                    "level": AlertLevel.WARNING,
                    "message": f"디스크 증가 속도 경고: +{growth_rate:.2f}%/h (현재 {disk_pct:.1f}%)",
                    "details": {
                        "current": disk_pct,
                        "growth_rate_per_hour": round(growth_rate, 2),
                        "threshold_rate": self.disk_growth_threshold,
                    },
                }
        return None

    def detect_restart_storm(self, events: list) -> Optional[dict]:
        """
        재시작 폭풍 탐지: 동일 프로젝트가 10분 이내에 3회 이상 재시작
        events: services.py의 이벤트 목록 형식
        """
        window_ago = (datetime.now() - timedelta(minutes=self.restart_storm_window)).isoformat()
        recent = [
            e for e in events
            if e.get("timestamp", "") >= window_ago
            and e.get("type") in ("restart", "auto_restart")
        ]

        # 프로젝트별 재시작 횟수
        restart_counts = {}
        for e in recent:
            proj = e.get("project", "")
            if proj:
                restart_counts[proj] = restart_counts.get(proj, 0) + 1

        storms = []
        for proj, count in restart_counts.items():
            if count >= self.restart_storm_count:
                storms.append((proj, count))

        if storms:
            storm_details = ", ".join(f"{p}: {c}회" for p, c in storms)
            return {
                "type": "restart_storm",
                "level": AlertLevel.CRITICAL,
                "message": f"재시작 폭풍 감지: {storm_details} ({self.restart_storm_window}분 이내)",
                "details": {
                    "projects": {p: c for p, c in storms},
                    "window_minutes": self.restart_storm_window,
                    "threshold": self.restart_storm_count,
                },
            }
        return None

    def predict_disk_full(self, history: list) -> Optional[dict]:
        """
        디스크 만료 예측: 선형 회귀로 disk_percent가 95%에 도달하는 시간 예측
        반환: {"level": ..., "message": ..., "details": {"hours_until_full": ...}} or None
        """
        if len(history) < 10:
            return None

        # 타임스탬프를 시간 단위로 변환하고 disk_percent와 쌍으로 추출
        points = []
        for h in history:
            try:
                ts = datetime.fromisoformat(h["timestamp"])
                points.append((ts.timestamp(), h["disk_percent"]))
            except (ValueError, KeyError):
                continue

        if len(points) < 10:
            return None

        # 선형 회귀 (최소제곱법)
        n = len(points)
        t0 = points[0][0]  # 기준 시간
        xs = [(p[0] - t0) / 3600 for p in points]  # 시간 단위
        ys = [p[1] for p in points]

        sum_x = sum(xs)
        sum_y = sum(ys)
        sum_xy = sum(x * y for x, y in zip(xs, ys))
        sum_x2 = sum(x * x for x in xs)

        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return None

        slope = (n * sum_xy - sum_x * sum_y) / denominator  # %/hour

        if slope <= 0.001:
            # 디스크가 줄거나 거의 변화 없음
            return None

        # 현재 값에서 target까지 남은 시간
        current = ys[-1]
        current_time_h = xs[-1]

        if current >= self.disk_predict_target:
            return {
                "type": "disk_full_prediction",
                "level": AlertLevel.CRITICAL,
                "message": f"디스크 이미 {current:.1f}% 사용 (목표 임계 {self.disk_predict_target}% 초과)",
                "details": {
                    "current": round(current, 1),
                    "target": self.disk_predict_target,
                    "hours_until_full": 0,
                    "growth_rate_per_hour": round(slope, 4),
                },
            }

        hours_until = (self.disk_predict_target - current) / slope

        if hours_until < 48:  # 48시간 내 예측만 알림
            level = AlertLevel.CRITICAL if hours_until < 12 else AlertLevel.WARNING
            return {
                "type": "disk_full_prediction",
                "level": level,
                "message": f"디스크 포화 예측: 약 {hours_until:.1f}시간 후 {self.disk_predict_target}% 도달 (현재 {current:.1f}%, +{slope:.3f}%/h)",
                "details": {
                    "current": round(current, 1),
                    "target": self.disk_predict_target,
                    "hours_until_full": round(hours_until, 1),
                    "growth_rate_per_hour": round(slope, 4),
                },
            }
        return None


# ============================================================
# MaintenanceWindow
# ============================================================

class MaintenanceWindow:
    """유지보수 윈도우: 설정된 시간 범위 동안 알림 억제"""

    def _load(self) -> dict:
        with _maintenance_lock:
            if not MAINTENANCE_FILE.exists():
                return {}
            try:
                with open(MAINTENANCE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}

    def _save(self, data: dict):
        with _maintenance_lock:
            with open(MAINTENANCE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def start(self, hours: float = None):
        """유지보수 윈도우 시작"""
        if hours is None:
            hours = ALERT_CONFIG.get("MAINTENANCE_WINDOW_DEFAULT_HOURS", 2)
        end_time = (datetime.now() + timedelta(hours=hours)).isoformat()
        self._save({
            "active": True,
            "start": datetime.now().isoformat(),
            "end": end_time,
            "hours": hours,
        })
        logger.info(f"유지보수 윈도우 시작: {hours}시간")

    def stop(self):
        """유지보수 윈도우 즉시 종료"""
        self._save({"active": False})
        logger.info("유지보수 윈도우 종료")

    def is_active(self) -> bool:
        """현재 유지보수 윈도우가 활성 상태인지"""
        data = self._load()
        if not data.get("active"):
            return False
        end_str = data.get("end", "")
        if not end_str:
            return False
        try:
            end_time = datetime.fromisoformat(end_str)
            if datetime.now() > end_time:
                # 자동 만료
                self.stop()
                return False
            return True
        except (ValueError, TypeError):
            return False

    def get_status(self) -> dict:
        """유지보수 윈도우 상태 반환"""
        data = self._load()
        active = self.is_active()
        return {
            "active": active,
            "start": data.get("start", ""),
            "end": data.get("end", ""),
            "hours": data.get("hours", 0),
        }


# ============================================================
# AlertManager
# ============================================================

class AlertManager:
    """알림 관리: 레벨, 쿨다운, 유지보수 윈도우, 텔레그램 전송, 이력 저장"""

    def __init__(self):
        self.cooldown_minutes = ALERT_CONFIG.get("ALERT_COOLDOWN_MINUTES", 30)
        self.maintenance = MaintenanceWindow()
        self._cooldown_cache: dict[str, str] = {}  # key -> last_alerted_iso

    def _load_alert_history(self) -> list:
        with _alert_lock:
            if not ALERT_HISTORY_FILE.exists():
                return []
            try:
                with open(ALERT_HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []

    def _save_alert_history(self, alerts: list):
        with _alert_lock:
            # 최대 500개 유지
            alerts = alerts[-500:]
            with open(ALERT_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(alerts, f, ensure_ascii=False, indent=2)

    def _is_in_cooldown(self, alert_key: str) -> bool:
        """동일 알림이 쿨다운 시간 내에 이미 전송되었는지 확인"""
        last = self._cooldown_cache.get(alert_key)
        if not last:
            return False
        try:
            last_dt = datetime.fromisoformat(last)
            if datetime.now() - last_dt < timedelta(minutes=self.cooldown_minutes):
                return True
        except (ValueError, TypeError):
            pass
        return False

    def _set_cooldown(self, alert_key: str):
        self._cooldown_cache[alert_key] = datetime.now().isoformat()

    def process_alert(self, anomaly: dict) -> bool:
        """
        이상 탐지 결과를 처리: 쿨다운/유지보수 확인 후 알림 전송 및 저장.
        반환: 알림이 실제로 전송되었는지
        """
        if not anomaly:
            return False

        if not ALERT_CONFIG.get("ALERT_ENABLED", True):
            return False

        # 유지보수 윈도우 중이면 억제
        if self.maintenance.is_active():
            logger.debug(f"유지보수 윈도우 활성 - 알림 억제: {anomaly.get('type')}")
            return False

        alert_key = anomaly.get("type", "unknown")
        # 디테일에 프로젝트 정보가 있으면 key에 포함
        details = anomaly.get("details", {})
        if "projects" in details:
            for p in details["projects"]:
                alert_key += f"_{p}"

        if self._is_in_cooldown(alert_key):
            logger.debug(f"쿨다운 중 - 알림 억제: {alert_key}")
            return False

        # 알림 기록 저장
        alert_record = {
            "timestamp": datetime.now().isoformat(),
            "type": anomaly.get("type", "unknown"),
            "level": anomaly.get("level", AlertLevel.INFO),
            "message": anomaly.get("message", ""),
            "details": anomaly.get("details", {}),
            "resolved": False,
        }
        history = self._load_alert_history()
        history.append(alert_record)
        self._save_alert_history(history)

        # 쿨다운 설정
        self._set_cooldown(alert_key)

        # 텔레그램 알림 전송
        self._send_telegram_alert(anomaly)

        logger.warning(f"알림 발생: [{anomaly.get('level')}] {anomaly.get('message')}")
        return True

    def _send_telegram_alert(self, anomaly: dict):
        """텔레그램으로 알림 전송 (동기)"""
        import httpx

        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        if not bot_token or not chat_id:
            return

        level = anomaly.get("level", AlertLevel.INFO)
        level_icon = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨",
        }.get(level, "📢")

        message = (
            f"{level_icon} [{level}] 스마트 알림\n\n"
            f"{anomaly.get('message', '')}\n\n"
            f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        try:
            with httpx.Client(timeout=10) as client:
                client.post(url, json={"chat_id": chat_id, "text": message})
        except Exception as e:
            logger.error(f"텔레그램 알림 전송 실패: {e}")

    def get_recent_alerts(self, limit: int = 50) -> list:
        """최근 알림 이력 반환 (최신순)"""
        history = self._load_alert_history()
        return history[-limit:][::-1]

    def get_alert_stats(self) -> dict:
        """알림 통계: 오늘 알림 수, 가장 많은 알림 타입 등"""
        history = self._load_alert_history()
        today = datetime.now().date().isoformat()
        today_alerts = [a for a in history if a.get("timestamp", "").startswith(today)]

        # 타입별 카운트
        type_counts = {}
        for a in today_alerts:
            t = a.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        # 가장 많은 알림 타입
        most_alerted_type = max(type_counts, key=type_counts.get) if type_counts else None

        # 레벨별 카운트
        level_counts = {}
        for a in today_alerts:
            lvl = a.get("level", "INFO")
            level_counts[lvl] = level_counts.get(lvl, 0) + 1

        critical_count = sum(
            1 for a in history
            if a.get("level") == AlertLevel.CRITICAL and not a.get("resolved", False)
        )

        return {
            "today_total": len(today_alerts),
            "today_by_type": type_counts,
            "today_by_level": level_counts,
            "most_alerted_type": most_alerted_type,
            "unresolved_critical": critical_count,
        }

    def get_thresholds(self) -> dict:
        """현재 알림 임계치 반환"""
        return {
            "cpu_threshold": ALERT_CONFIG.get("CPU_THRESHOLD", 85),
            "memory_threshold": ALERT_CONFIG.get("MEMORY_THRESHOLD", 80),
            "disk_threshold": ALERT_CONFIG.get("DISK_THRESHOLD", 90),
            "disk_predict_target": ALERT_CONFIG.get("DISK_PREDICT_TARGET", 95),
            "cpu_std_multiplier": ALERT_CONFIG.get("CPU_STD_MULTIPLIER", 2.0),
            "cpu_consecutive_min": ALERT_CONFIG.get("CPU_CONSECUTIVE_MIN", 3),
            "memory_leak_minutes": ALERT_CONFIG.get("MEMORY_LEAK_MINUTES", 30),
            "disk_growth_rate_threshold": ALERT_CONFIG.get("DISK_GROWTH_RATE_THRESHOLD", 1.0),
            "restart_storm_count": ALERT_CONFIG.get("RESTART_STORM_COUNT", 3),
            "restart_storm_window_minutes": ALERT_CONFIG.get("RESTART_STORM_WINDOW_MINUTES", 10),
            "alert_cooldown_minutes": ALERT_CONFIG.get("ALERT_COOLDOWN_MINUTES", 30),
            "alert_enabled": ALERT_CONFIG.get("ALERT_ENABLED", True),
        }

    def update_thresholds(self, updates: dict) -> dict:
        """알림 임계치 업데이트 (런타임에서만, 재시작 시 config.py 기본값)"""
        field_map = {
            "cpu_threshold": "CPU_THRESHOLD",
            "memory_threshold": "MEMORY_THRESHOLD",
            "disk_threshold": "DISK_THRESHOLD",
            "disk_predict_target": "DISK_PREDICT_TARGET",
            "cpu_std_multiplier": "CPU_STD_MULTIPLIER",
            "cpu_consecutive_min": "CPU_CONSECUTIVE_MIN",
            "memory_leak_minutes": "MEMORY_LEAK_MINUTES",
            "disk_growth_rate_threshold": "DISK_GROWTH_RATE_THRESHOLD",
            "restart_storm_count": "RESTART_STORM_COUNT",
            "restart_storm_window_minutes": "RESTART_STORM_WINDOW_MINUTES",
            "alert_cooldown_minutes": "ALERT_COOLDOWN_MINUTES",
            "alert_enabled": "ALERT_ENABLED",
        }
        updated = {}
        for key, value in updates.items():
            if key in field_map:
                config_key = field_map[key]
                ALERT_CONFIG[config_key] = value
                updated[key] = value
        # Reload detector thresholds
        self.cooldown_minutes = ALERT_CONFIG.get("ALERT_COOLDOWN_MINUTES", 30)
        return updated


# ============================================================
# Singleton instances
# ============================================================

_collector: Optional[MetricsCollector] = None
_detector: Optional[AnomalyDetector] = None
_alert_manager: Optional[AlertManager] = None


def get_collector() -> MetricsCollector:
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector


def get_detector() -> AnomalyDetector:
    global _detector
    if _detector is None:
        _detector = AnomalyDetector()
    return _detector


def get_alert_manager() -> AlertManager:
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


# ============================================================
# Background anomaly check loop
# ============================================================

def run_anomaly_check():
    """이상 탐지 1회 실행: 모든 탐지기를 돌리고 알림 처리"""
    collector = get_collector()
    detector = get_detector()
    alert_mgr = get_alert_manager()

    history = collector.get_history()
    if not history:
        return

    anomalies = []

    # 1. CPU 이상
    result = detector.detect_cpu_anomaly(history)
    if result:
        anomalies.append(result)

    # 2. 메모리 누수
    result = detector.detect_memory_leak(history)
    if result:
        anomalies.append(result)

    # 3. 디스크 압력
    result = detector.detect_disk_pressure(history)
    if result:
        anomalies.append(result)

    # 4. 디스크 포화 예측
    result = detector.predict_disk_full(history)
    if result:
        anomalies.append(result)

    # 5. 재시작 폭풍 (이벤트 데이터 필요)
    try:
        from services import _load_events
        events = _load_events()
        result = detector.detect_restart_storm(events)
        if result:
            anomalies.append(result)
    except ImportError:
        pass

    for anomaly in anomalies:
        alert_mgr.process_alert(anomaly)


def anomaly_background_loop():
    """백그라운드 스레드: 주기적으로 이상 탐지 실행"""
    interval = ALERT_CONFIG.get("ANOMALY_CHECK_INTERVAL", 120)
    logger.info(f"이상 탐지 백그라운드 루프 시작 (간격: {interval}초)")

    # 초기 대기
    time.sleep(30)

    while True:
        try:
            run_anomaly_check()
        except Exception as e:
            logger.error(f"이상 탐지 루프 오류: {e}")
        time.sleep(interval)


def start_anomaly_thread():
    """이상 탐지 백그라운드 스레드 시작 (daemon)"""
    thread = threading.Thread(target=anomaly_background_loop, daemon=True, name="anomaly-detector")
    thread.start()
    logger.info("이상 탐지 백그라운드 스레드 시작됨")
    return thread
