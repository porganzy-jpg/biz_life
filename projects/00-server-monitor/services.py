"""
공유 서비스 모듈 - app.py, bot.py, monitor.py 공통 함수
프로젝트 제어(시작/중지/재시작), 상태 확인, 로그 조회, 시스템 정보, 이벤트 로깅
"""
import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx
import psutil

from config import PROJECTS, PROJECTS_DIR

# === 이벤트 로깅 ===

EVENTS_FILE = Path(__file__).parent / "events.json"
_events_lock = threading.Lock()


def _load_events() -> list:
    """이벤트 로그 파일에서 이벤트 목록 로드"""
    if not EVENTS_FILE.exists():
        return []
    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_events(events: list):
    """이벤트 목록을 로그 파일에 저장 (최대 500개 유지)"""
    events = events[-500:]
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)


def log_event(project_name: str, event_type: str, details: str = ""):
    """이벤트 기록 (start, stop, restart, auto_restart, resource_alert, error)"""
    event = {
        "timestamp": datetime.now().isoformat(),
        "project": project_name,
        "type": event_type,
        "details": details,
    }
    with _events_lock:
        events = _load_events()
        events.append(event)
        _save_events(events)


def get_event_history(project_name: str = None, limit: int = 50) -> list:
    """최근 이벤트 목록 반환 (project_name 필터 가능)"""
    with _events_lock:
        events = _load_events()
    if project_name:
        events = [e for e in events if e["project"] == project_name]
    return events[-limit:][::-1]  # 최신순


def get_uptime_stats() -> dict:
    """프로젝트별 가동률(%) 및 마지막 재시작 시간 계산"""
    with _events_lock:
        events = _load_events()

    stats = {}
    for name in PROJECTS:
        proj_events = [e for e in events if e["project"] == name]
        stats[name] = {
            "uptime_percent": _calc_uptime_percent(proj_events),
            "last_restart": _find_last_event(proj_events, ["restart", "auto_restart"]),
            "total_starts": sum(1 for e in proj_events if e["type"] in ("start", "restart", "auto_restart")),
            "total_stops": sum(1 for e in proj_events if e["type"] == "stop"),
            "total_errors": sum(1 for e in proj_events if e["type"] == "error"),
        }
    return stats


def _calc_uptime_percent(proj_events: list) -> float:
    """이벤트 기반 가동률 계산 (24시간 기준)"""
    if not proj_events:
        return 0.0

    now = datetime.now()
    window_hours = 24
    window_start = now.timestamp() - (window_hours * 3600)

    # 윈도우 내 이벤트만 필터링
    window_events = []
    for e in proj_events:
        try:
            ts = datetime.fromisoformat(e["timestamp"]).timestamp()
            if ts >= window_start:
                window_events.append((ts, e["type"]))
        except (ValueError, KeyError):
            continue

    if not window_events:
        # 윈도우 내 이벤트 없으면 마지막 이벤트 타입으로 추정
        last = proj_events[-1]
        if last["type"] in ("start", "restart", "auto_restart"):
            return 100.0
        return 0.0

    window_events.sort(key=lambda x: x[0])

    # 구간별 up/down 시간 계산
    up_time = 0.0
    total_time = now.timestamp() - window_start

    is_up = False
    last_ts = window_start

    for ts, etype in window_events:
        duration = ts - last_ts
        if is_up:
            up_time += duration
        if etype in ("start", "restart", "auto_restart"):
            is_up = True
        elif etype == "stop":
            is_up = False
        last_ts = ts

    # 마지막 이벤트부터 현재까지
    if is_up:
        up_time += now.timestamp() - last_ts

    if total_time <= 0:
        return 0.0
    return round((up_time / total_time) * 100, 1)


def _find_last_event(proj_events: list, event_types: list) -> str:
    """특정 타입의 마지막 이벤트 시간 반환 (없으면 빈 문자열)"""
    for e in reversed(proj_events):
        if e["type"] in event_types:
            return e["timestamp"]
    return ""


# === 상태 확인 ===

def find_pid_by_port(port: int):
    """포트를 리슨 중인 프로세스의 PID 반환 (없으면 None)"""
    for conn in psutil.net_connections(kind="tcp"):
        if conn.laddr.port == port and conn.status == "LISTEN":
            return conn.pid
    return None


async def check_port(port: int) -> bool:
    """HTTP 요청으로 포트 생존 확인 (async)"""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"http://localhost:{port}/")
            return resp.status_code < 500
    except Exception:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"http://localhost:{port}/health")
                return resp.status_code < 500
        except Exception:
            return False


def check_port_sync(port: int) -> bool:
    """PID 기반 포트 생존 확인 (sync)"""
    return find_pid_by_port(port) is not None


# === 프로젝트 제어 ===

def start_project(name: str, verify: bool = True) -> dict:
    """프로젝트 시작. 결과를 {"ok": bool, "msg": str}로 반환"""
    if name not in PROJECTS:
        return {"ok": False, "msg": f"알 수 없는 프로젝트: {name}"}

    proj = PROJECTS[name]
    pid = find_pid_by_port(proj["port"])
    if pid:
        return {"ok": False, "msg": f"이미 실행 중 (포트 {proj['port']})"}

    project_dir = PROJECTS_DIR / name
    work_dir = project_dir / proj["cwd"]

    cmd = list(proj["cmd"])
    cmd[0] = str(project_dir / cmd[0])

    log_dir = project_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "server.log"

    with open(log_file, "a", encoding="utf-8") as lf:
        subprocess.Popen(
            cmd,
            cwd=str(work_dir),
            stdout=lf,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    if verify:
        for _ in range(6):
            time.sleep(0.5)
            if find_pid_by_port(proj["port"]):
                log_event(name, "start", f"시작 확인됨 (포트 {proj['port']})")
                return {"ok": True, "msg": f"시작 확인됨 (포트 {proj['port']})"}
        log_event(name, "error", f"시작 실패 — 포트 {proj['port']} 응답 없음")
        return {"ok": False, "msg": f"시작 실패 — 포트 {proj['port']} 응답 없음"}

    log_event(name, "start", f"시작됨 (포트 {proj['port']})")
    return {"ok": True, "msg": f"시작됨 (포트 {proj['port']})"}


def stop_project(name: str) -> dict:
    """프로젝트 중지. 결과를 {"ok": bool, "msg": str}로 반환"""
    if name not in PROJECTS:
        return {"ok": False, "msg": f"알 수 없는 프로젝트: {name}"}

    proj = PROJECTS[name]
    pid = find_pid_by_port(proj["port"])
    if not pid:
        return {"ok": False, "msg": f"실행 중이 아님"}

    try:
        proc = psutil.Process(pid)
        children = proc.children(recursive=True)
        for child in children:
            child.terminate()
        proc.terminate()
        proc.wait(timeout=5)
        log_event(name, "stop", f"중지됨 (PID {pid})")
        return {"ok": True, "msg": f"중지됨 (PID {pid})"}
    except psutil.NoSuchProcess:
        log_event(name, "stop", "이미 종료됨")
        return {"ok": True, "msg": f"이미 종료됨"}
    except Exception as e:
        log_event(name, "error", f"중지 실패: {e}")
        return {"ok": False, "msg": f"중지 실패: {e}"}


def restart_project(name: str) -> dict:
    """프로젝트 재시작 (중지 후 시작). 결과를 {"ok": bool, "msg": str}로 반환"""
    log_event(name, "restart", "재시작 시작")
    stop_result = stop_project(name)
    proj = PROJECTS.get(name)
    if proj:
        for _ in range(20):
            time.sleep(0.5)
            if not find_pid_by_port(proj["port"]):
                break
    start_result = start_project(name)
    return {
        "ok": start_result["ok"],
        "msg": f"중지: {stop_result['msg']} → 시작: {start_result['msg']}",
    }


# === 로그 조회 ===

def get_recent_logs(project_name: str, lines: int = 15) -> str:
    """프로젝트의 최근 로그 반환"""
    log_dir = PROJECTS_DIR / project_name / "logs"
    if not log_dir.exists():
        return "(로그 폴더 없음)"
    log_files = sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
    if not log_files:
        return "(로그 파일 없음)"
    try:
        with open(log_files[0], "r", encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:]) or "(빈 로그)"
    except Exception as e:
        return f"(읽기 실패: {e})"


# === 시스템 정보 ===

def get_system_info() -> dict:
    """CPU, 메모리, 디스크 사용량 반환"""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "cpu_count": psutil.cpu_count(),
        "mem_total_gb": round(mem.total / (1024**3), 1),
        "mem_used_gb": round(mem.used / (1024**3), 1),
        "mem_percent": mem.percent,
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "disk_used_gb": round(disk.used / (1024**3), 1),
        "disk_percent": round(disk.percent, 1),
    }
