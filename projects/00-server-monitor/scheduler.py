# -*- coding: utf-8 -*-
"""
예약 재시작 스케줄러
- data/schedules.json에 스케줄 저장
- 백그라운드 스레드에서 60초마다 스케줄 확인
- 재시작은 기존 services.restart_project 사용
- 유지보수 윈도우 활성 시 스킵
- 이벤트 로그 type="scheduled_restart"
"""
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import PROJECTS, SCHEDULE_CONFIG
from services import restart_project, log_event
from anomaly import MaintenanceWindow

logger = logging.getLogger("scheduler")

# === 파일 경로 ===
BASE_DIR = Path(__file__).parent
SCHEDULES_FILE = BASE_DIR / "data" / "schedules.json"
SCHEDULES_FILE.parent.mkdir(parents=True, exist_ok=True)

_schedules_lock = threading.Lock()

# 요일 매핑 (월=0 ~ 일=6)
DAY_NAMES_KO = {
    0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일",
}
DAY_NAMES_EN = {
    0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun",
}
DAY_LOOKUP = {}
for i, name_ko in DAY_NAMES_KO.items():
    DAY_LOOKUP[name_ko] = i
    DAY_LOOKUP[DAY_NAMES_EN[i]] = i
    DAY_LOOKUP[str(i)] = i


def _load_schedules() -> list:
    """스케줄 목록 로드"""
    if not SCHEDULES_FILE.exists():
        return []
    try:
        with open(SCHEDULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_schedules(schedules: list):
    """스케줄 목록 저장"""
    with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)


def get_schedules() -> list:
    """전체 스케줄 목록 반환 (API용)"""
    with _schedules_lock:
        schedules = _load_schedules()
    # 각 스케줄에 next_run 추가
    for s in schedules:
        s["next_run"] = _calc_next_run(s)
    return schedules


def add_schedule(
    project_name: str,
    schedule_type: str,
    time_str: str,
    day_of_week: Optional[str] = None,
    enabled: bool = True,
) -> dict:
    """
    새 스케줄 추가
    - project_name: PROJECTS에 있는 프로젝트 이름
    - schedule_type: "daily" | "weekly"
    - time_str: "HH:MM"
    - day_of_week: 주간 스케줄인 경우 요일 (0-6, mon-sun, 월-일)
    - enabled: 활성 여부
    반환: {"ok": bool, "msg": str, "schedule": dict}
    """
    if project_name not in PROJECTS:
        return {"ok": False, "msg": f"알 수 없는 프로젝트: {project_name}"}

    if schedule_type not in ("daily", "weekly"):
        return {"ok": False, "msg": f"잘못된 스케줄 타입: {schedule_type} (daily 또는 weekly)"}

    # 시간 형식 검증
    try:
        parts = time_str.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, IndexError):
        return {"ok": False, "msg": f"잘못된 시간 형식: {time_str} (HH:MM 형식 필요)"}

    # 요일 검증 (weekly인 경우)
    day_num = None
    if schedule_type == "weekly":
        if day_of_week is None:
            return {"ok": False, "msg": "weekly 스케줄은 day_of_week 필수"}
        day_key = str(day_of_week).lower().strip()
        if day_key not in DAY_LOOKUP:
            return {"ok": False, "msg": f"잘못된 요일: {day_of_week} (0-6, mon-sun, 월-일)"}
        day_num = DAY_LOOKUP[day_key]

    schedule = {
        "id": str(uuid.uuid4())[:8],
        "project_name": project_name,
        "schedule_type": schedule_type,
        "time": f"{hour:02d}:{minute:02d}",
        "day_of_week": day_num,
        "enabled": enabled,
        "created_at": datetime.now().isoformat(),
        "last_run": None,
    }

    with _schedules_lock:
        schedules = _load_schedules()
        schedules.append(schedule)
        _save_schedules(schedules)

    schedule["next_run"] = _calc_next_run(schedule)
    logger.info(f"스케줄 추가: {project_name} {schedule_type} {schedule['time']} (id={schedule['id']})")
    return {"ok": True, "msg": "스케줄 추가 완료", "schedule": schedule}


def remove_schedule(schedule_id: str) -> dict:
    """스케줄 삭제"""
    with _schedules_lock:
        schedules = _load_schedules()
        original_len = len(schedules)
        schedules = [s for s in schedules if s.get("id") != schedule_id]
        if len(schedules) == original_len:
            return {"ok": False, "msg": f"스케줄을 찾을 수 없음: {schedule_id}"}
        _save_schedules(schedules)

    logger.info(f"스케줄 삭제: {schedule_id}")
    return {"ok": True, "msg": "스케줄 삭제 완료"}


def toggle_schedule(schedule_id: str) -> dict:
    """스케줄 활성/비활성 토글"""
    with _schedules_lock:
        schedules = _load_schedules()
        target = None
        for s in schedules:
            if s.get("id") == schedule_id:
                target = s
                break
        if not target:
            return {"ok": False, "msg": f"스케줄을 찾을 수 없음: {schedule_id}"}
        target["enabled"] = not target.get("enabled", True)
        _save_schedules(schedules)

    new_state = "활성" if target["enabled"] else "비활성"
    logger.info(f"스케줄 토글: {schedule_id} -> {new_state}")
    target["next_run"] = _calc_next_run(target)
    return {"ok": True, "msg": f"스케줄 {new_state}화 완료", "schedule": target}


def _calc_next_run(schedule: dict) -> Optional[str]:
    """다음 실행 시간 계산 (ISO 문자열 반환)"""
    if not schedule.get("enabled", True):
        return None

    try:
        hour, minute = map(int, schedule["time"].split(":"))
    except (ValueError, KeyError):
        return None

    now = datetime.now()
    schedule_type = schedule.get("schedule_type", "daily")

    if schedule_type == "daily":
        # 오늘 해당 시간이 아직 안 지났으면 오늘, 지났으면 내일
        next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_dt <= now:
            next_dt += timedelta(days=1)
        return next_dt.isoformat()

    elif schedule_type == "weekly":
        day_num = schedule.get("day_of_week")
        if day_num is None:
            return None
        # 이번 주 해당 요일의 해당 시간
        days_ahead = day_num - now.weekday()
        if days_ahead < 0:
            days_ahead += 7
        next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
        if next_dt <= now:
            next_dt += timedelta(days=7)
        return next_dt.isoformat()

    return None


def _is_due(schedule: dict) -> bool:
    """스케줄 실행 시간이 되었는지 확인 (60초 윈도우)"""
    if not schedule.get("enabled", True):
        return False

    try:
        hour, minute = map(int, schedule["time"].split(":"))
    except (ValueError, KeyError):
        return False

    now = datetime.now()
    schedule_type = schedule.get("schedule_type", "daily")

    # weekly인 경우 요일 확인
    if schedule_type == "weekly":
        day_num = schedule.get("day_of_week")
        if day_num is None or now.weekday() != day_num:
            return False

    # 시간 확인 (현재 시간이 스케줄 시간의 60초 윈도우 안인지)
    scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    diff = (now - scheduled_time).total_seconds()

    # 0~59초 사이면 실행 대상
    if not (0 <= diff < 60):
        return False

    # 중복 실행 방지: last_run이 오늘 같은 시간대에 이미 실행되었는지
    last_run = schedule.get("last_run")
    if last_run:
        try:
            last_dt = datetime.fromisoformat(last_run)
            # 같은 날 같은 시간에 이미 실행됨
            if last_dt.date() == now.date() and last_dt.hour == hour and last_dt.minute == minute:
                return False
            # weekly인 경우: 이번 주 같은 요일에 이미 실행됨
            if schedule_type == "weekly":
                days_diff = (now.date() - last_dt.date()).days
                if days_diff < 7 and last_dt.weekday() == now.weekday():
                    return False
        except (ValueError, TypeError):
            pass

    return True


def _execute_schedule(schedule: dict):
    """스케줄 실행 - 프로젝트 재시작"""
    project_name = schedule.get("project_name", "")
    schedule_id = schedule.get("id", "?")

    # 유지보수 윈도우 확인
    mw = MaintenanceWindow()
    if mw.is_active():
        logger.info(f"예약 재시작 스킵 (유지보수 윈도우 활성): {project_name} (id={schedule_id})")
        log_event(
            project_name,
            "scheduled_restart",
            f"예약 재시작 스킵 - 유지보수 윈도우 활성 (스케줄 id={schedule_id})",
        )
        return

    if project_name not in PROJECTS:
        logger.warning(f"예약 재시작 실패 - 알 수 없는 프로젝트: {project_name} (id={schedule_id})")
        return

    logger.info(f"예약 재시작 실행: {project_name} (id={schedule_id})")
    log_event(
        project_name,
        "scheduled_restart",
        f"예약 재시작 시작 (스케줄: {schedule.get('schedule_type')} {schedule.get('time')})",
    )

    try:
        result = restart_project(project_name)
        log_event(
            project_name,
            "scheduled_restart",
            f"예약 재시작 완료: {result.get('msg', '')} (id={schedule_id})",
        )
        logger.info(f"예약 재시작 완료: {project_name} -> {result.get('msg', '')}")

        # 텔레그램 알림
        _send_schedule_telegram(project_name, schedule, result)

    except Exception as e:
        log_event(project_name, "error", f"예약 재시작 실패: {e}")
        logger.error(f"예약 재시작 실패: {project_name} -> {e}")


def _send_schedule_telegram(project_name: str, schedule: dict, result: dict):
    """예약 재시작 결과 텔레그램 알림"""
    import os

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        return

    import httpx

    ok = result.get("ok", False)
    icon = "+" if ok else "X"
    stype = "매일" if schedule.get("schedule_type") == "daily" else "매주"
    day_str = ""
    if schedule.get("schedule_type") == "weekly" and schedule.get("day_of_week") is not None:
        day_str = f" ({DAY_NAMES_KO.get(schedule['day_of_week'], '')})"

    message = (
        f"[{icon}] 예약 재시작\n\n"
        f"프로젝트: {project_name}\n"
        f"스케줄: {stype} {schedule.get('time', '')}{day_str}\n"
        f"결과: {result.get('msg', '')}\n"
        f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        with httpx.Client(timeout=10) as client:
            client.post(url, json={"chat_id": chat_id, "text": message})
    except Exception as e:
        logger.error(f"스케줄 텔레그램 알림 실패: {e}")


# ============================================================
# Background Scheduler Thread
# ============================================================

def scheduler_loop():
    """
    백그라운드 스케줄 루프
    - SCHEDULE_CHECK_INTERVAL 초마다 스케줄 확인
    - 실행 시간이 된 스케줄 실행
    """
    interval = SCHEDULE_CONFIG.get("SCHEDULE_CHECK_INTERVAL", 60)
    logger.info(f"예약 재시작 스케줄러 시작 (확인 간격: {interval}초)")

    # 초기 대기
    time.sleep(15)

    while True:
        try:
            with _schedules_lock:
                schedules = _load_schedules()

            for schedule in schedules:
                if _is_due(schedule):
                    # 실행 전 last_run 즉시 업데이트 (중복 실행 방지)
                    with _schedules_lock:
                        current = _load_schedules()
                        for s in current:
                            if s.get("id") == schedule.get("id"):
                                s["last_run"] = datetime.now().isoformat()
                                break
                        _save_schedules(current)

                    # 별도 스레드에서 재시작 실행 (블로킹 방지)
                    exec_thread = threading.Thread(
                        target=_execute_schedule,
                        args=(schedule,),
                        daemon=True,
                        name=f"sched-exec-{schedule.get('id', '?')}",
                    )
                    exec_thread.start()

        except Exception as e:
            logger.error(f"스케줄러 루프 오류: {e}")

        time.sleep(interval)


_scheduler_thread: Optional[threading.Thread] = None


def start_scheduler_thread() -> threading.Thread:
    """스케줄러 백그라운드 스레드 시작 (daemon)"""
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        logger.info("스케줄러 스레드 이미 실행 중")
        return _scheduler_thread
    _scheduler_thread = threading.Thread(
        target=scheduler_loop,
        daemon=True,
        name="scheduler",
    )
    _scheduler_thread.start()
    logger.info("예약 재시작 스케줄러 스레드 시작됨")
    return _scheduler_thread


# ============================================================
# Bot Helper
# ============================================================

def bot_schedule_list() -> str:
    """봇용: 스케줄 목록 문자열 반환"""
    schedules = get_schedules()
    if not schedules:
        return "등록된 예약 재시작이 없습니다."

    lines = ["예약 재시작 목록\n"]
    for s in schedules:
        enabled = "ON" if s.get("enabled") else "OFF"
        stype = "매일" if s.get("schedule_type") == "daily" else "매주"
        day_str = ""
        if s.get("schedule_type") == "weekly" and s.get("day_of_week") is not None:
            day_str = f" {DAY_NAMES_KO.get(s['day_of_week'], '')}"

        next_run = ""
        if s.get("next_run"):
            try:
                nr_dt = datetime.fromisoformat(s["next_run"])
                next_run = nr_dt.strftime("%m/%d %H:%M")
            except (ValueError, TypeError):
                pass

        lines.append(
            f"[{enabled}] {s['project_name']} - {stype} {s.get('time', '')}{day_str}"
            f" (다음: {next_run}) id={s.get('id', '?')}"
        )
    return "\n".join(lines)


def bot_schedule_add(args: list) -> str:
    """
    봇용: 스케줄 추가
    형식: <프로젝트> <daily|weekly> <HH:MM> [요일]
    예: 04-crypto-trader daily 03:00
        01-promo-map weekly 04:00 mon
    """
    if len(args) < 3:
        return (
            "사용법: /schedule add <프로젝트> <daily|weekly> <HH:MM> [요일]\n"
            "예: /schedule add 04-crypto-trader daily 03:00\n"
            "    /schedule add 01-promo-map weekly 04:00 mon"
        )

    project_name = args[0]
    schedule_type = args[1].lower()
    time_str = args[2]
    day_of_week = args[3] if len(args) > 3 else None

    result = add_schedule(project_name, schedule_type, time_str, day_of_week)
    if result["ok"]:
        s = result["schedule"]
        return f"스케줄 추가 완료: {s['project_name']} {s['schedule_type']} {s['time']} (id={s['id']})"
    return f"스케줄 추가 실패: {result['msg']}"


def bot_schedule_remove(args: list) -> str:
    """봇용: 스케줄 삭제"""
    if not args:
        return "사용법: /schedule remove <id>"
    result = remove_schedule(args[0])
    return result["msg"]


def bot_schedule_toggle(args: list) -> str:
    """봇용: 스케줄 토글"""
    if not args:
        return "사용법: /schedule toggle <id>"
    result = toggle_schedule(args[0])
    return result["msg"]
