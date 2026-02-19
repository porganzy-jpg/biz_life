"""
공유 서비스 모듈 - app.py, bot.py, monitor.py 공통 함수
프로젝트 제어(시작/중지/재시작), 상태 확인, 로그 조회, 시스템 정보
"""
import os
import subprocess
import time

import httpx
import psutil

from config import PROJECTS, PROJECTS_DIR


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
                return {"ok": True, "msg": f"시작 확인됨 (포트 {proj['port']})"}
        return {"ok": False, "msg": f"시작 실패 — 포트 {proj['port']} 응답 없음"}

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
        return {"ok": True, "msg": f"중지됨 (PID {pid})"}
    except psutil.NoSuchProcess:
        return {"ok": True, "msg": f"이미 종료됨"}
    except Exception as e:
        return {"ok": False, "msg": f"중지 실패: {e}"}


def restart_project(name: str) -> dict:
    """프로젝트 재시작 (중지 후 시작). 결과를 {"ok": bool, "msg": str}로 반환"""
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
