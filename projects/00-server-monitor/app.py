"""
통합 모니터링 대시보드 - 포트 9000
프로젝트 상태 확인 + 시작/중지/재시작 제어
"""
import asyncio
import os
import subprocess
import signal
from pathlib import Path

import httpx
import psutil
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from config import PROJECTS, PROJECTS_DIR

app = FastAPI(title="Server Monitor")


# === 유틸리티 ===

async def check_port(port: int) -> bool:
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


def find_pid_by_port(port: int):
    for conn in psutil.net_connections(kind="tcp"):
        if conn.laddr.port == port and conn.status == "LISTEN":
            return conn.pid
    return None


def get_recent_logs(project_name: str, lines: int = 15) -> str:
    log_dir = PROJECTS_DIR / project_name / "logs"
    if not log_dir.exists():
        return "(로그 폴더 없음)"
    log_files = sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
    if not log_files:
        return "(로그 파일 없음)"
    try:
        with open(log_files[0], "r", encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except Exception as e:
        return f"(로그 읽기 실패: {e})"


def get_system_info() -> dict:
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


# === 프로젝트 제어 ===

def start_project(name: str, verify: bool = True) -> dict:
    if name not in PROJECTS:
        return {"ok": False, "msg": f"알 수 없는 프로젝트: {name}"}

    proj = PROJECTS[name]
    pid = find_pid_by_port(proj["port"])
    if pid:
        return {"ok": False, "msg": f"{name} 이미 실행 중 (PID {pid})"}

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
        import time
        for _ in range(6):
            time.sleep(0.5)
            if find_pid_by_port(proj["port"]):
                return {"ok": True, "msg": f"{name} 시작 확인됨 (포트 {proj['port']})"}
        return {"ok": False, "msg": f"{name} 시작 실패 — 포트 {proj['port']} 응답 없음"}

    return {"ok": True, "msg": f"{name} 시작됨 (포트 {proj['port']})"}


def stop_project(name: str) -> dict:
    if name not in PROJECTS:
        return {"ok": False, "msg": f"알 수 없는 프로젝트: {name}"}

    proj = PROJECTS[name]
    pid = find_pid_by_port(proj["port"])
    if not pid:
        return {"ok": False, "msg": f"{name} 실행 중이 아님"}

    try:
        proc = psutil.Process(pid)
        children = proc.children(recursive=True)
        for child in children:
            child.terminate()
        proc.terminate()
        proc.wait(timeout=5)
        return {"ok": True, "msg": f"{name} 중지됨 (PID {pid})"}
    except psutil.NoSuchProcess:
        return {"ok": True, "msg": f"{name} 이미 종료됨"}
    except Exception as e:
        return {"ok": False, "msg": f"중지 실패: {e}"}


def restart_project(name: str) -> dict:
    import time
    stop_result = stop_project(name)
    proj = PROJECTS.get(name)
    if proj:
        for _ in range(20):
            time.sleep(0.5)
            if not find_pid_by_port(proj["port"]):
                break
    start_result = start_project(name)
    return {"ok": start_result["ok"], "msg": f"중지: {stop_result['msg']} → 시작: {start_result['msg']}"}


# === API 엔드포인트 ===

@app.post("/api/start/{name}")
async def api_start(name: str):
    return JSONResponse(start_project(name))

@app.post("/api/stop/{name}")
async def api_stop(name: str):
    return JSONResponse(stop_project(name))

@app.post("/api/restart/{name}")
async def api_restart(name: str):
    return JSONResponse(restart_project(name))

@app.get("/api/status")
async def api_status():
    project_list = []
    tasks = [check_port(p["port"]) for p in PROJECTS.values()]
    results = await asyncio.gather(*tasks)
    for (name, proj), alive in zip(PROJECTS.items(), results):
        project_list.append({"name": name, "port": proj["port"], "desc": proj["desc"], "alive": alive})
    return {"system": get_system_info(), "projects": project_list}


# === 대시보드 UI ===

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    tasks = [check_port(p["port"]) for p in PROJECTS.values()]
    results = await asyncio.gather(*tasks)
    sys_info = get_system_info()

    project_cards = ""
    for (name, proj), alive in zip(PROJECTS.items(), results):
        status_class = "alive" if alive else "dead"
        status_text = "실행 중" if alive else "중지됨"
        status_dot = "🟢" if alive else "🔴"
        logs = get_recent_logs(name)
        logs_escaped = logs.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        project_cards += f"""
        <div class="card {status_class}" id="card-{name}">
            <div class="card-header">
                <span class="status-dot">{status_dot}</span>
                <h3>{name}</h3>
                <span class="badge">{status_text}</span>
            </div>
            <p class="desc">{proj['desc']} &mdash; 포트 {proj['port']}</p>
            <div class="controls">
                <button class="btn btn-start" onclick="ctrl('{name}','start')" {'disabled' if alive else ''}>시작</button>
                <button class="btn btn-stop" onclick="ctrl('{name}','stop')" {'disabled' if not alive else ''}>중지</button>
                <button class="btn btn-restart" onclick="ctrl('{name}','restart')">재시작</button>
                <a href="http://{{{{host}}}}:{proj['port']}/" target="_blank" class="btn btn-link">열기</a>
            </div>
            <div class="action-msg" id="msg-{name}"></div>
            <details>
                <summary>최근 로그</summary>
                <pre class="log">{logs_escaped}</pre>
            </details>
        </div>
        """

    cpu_color = "#4caf50" if sys_info["cpu_percent"] < 60 else "#ff9800" if sys_info["cpu_percent"] < 85 else "#f44336"
    mem_color = "#4caf50" if sys_info["mem_percent"] < 60 else "#ff9800" if sys_info["mem_percent"] < 85 else "#f44336"
    disk_color = "#4caf50" if sys_info["disk_percent"] < 75 else "#ff9800" if sys_info["disk_percent"] < 90 else "#f44336"

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Server Monitor</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0; padding: 16px; }}
  h1 {{ text-align: center; margin-bottom: 8px; font-size: 1.5rem; }}
  .subtitle {{ text-align: center; color: #888; margin-bottom: 20px; font-size: 0.85rem; }}
  .system {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .sys-card {{ background: #1a1d27; border-radius: 12px; padding: 14px; }}
  .sys-card h4 {{ color: #aaa; font-size: 0.75rem; margin-bottom: 6px; text-transform: uppercase; }}
  .sys-card .value {{ font-size: 1.6rem; font-weight: 700; }}
  .bar {{ height: 5px; border-radius: 3px; background: #2a2d37; margin-top: 6px; }}
  .bar-fill {{ height: 100%; border-radius: 3px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }}
  .card {{ background: #1a1d27; border-radius: 12px; padding: 16px; border-left: 4px solid #666; }}
  .card.alive {{ border-left-color: #4caf50; }}
  .card.dead {{ border-left-color: #f44336; }}
  .card-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }}
  .card-header h3 {{ flex: 1; font-size: 0.95rem; }}
  .badge {{ font-size: 0.7rem; padding: 2px 8px; border-radius: 12px; background: #2a2d37; }}
  .alive .badge {{ background: #1b3a1b; color: #4caf50; }}
  .dead .badge {{ background: #3a1b1b; color: #f44336; }}
  .desc {{ color: #888; font-size: 0.8rem; margin-bottom: 10px; }}
  .controls {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }}
  .btn {{ padding: 6px 14px; border: none; border-radius: 8px; font-size: 0.78rem; cursor: pointer; font-weight: 600; transition: opacity 0.2s; }}
  .btn:disabled {{ opacity: 0.3; cursor: not-allowed; }}
  .btn-start {{ background: #1b3a1b; color: #4caf50; }}
  .btn-start:hover:not(:disabled) {{ background: #264a26; }}
  .btn-stop {{ background: #3a1b1b; color: #f44336; }}
  .btn-stop:hover:not(:disabled) {{ background: #4a2626; }}
  .btn-restart {{ background: #2a2a1b; color: #ff9800; }}
  .btn-restart:hover {{ background: #3a3a26; }}
  .btn-link {{ background: #1b2a3a; color: #64b5f6; text-decoration: none; display: inline-block; }}
  .btn-link:hover {{ background: #263a4a; }}
  .action-msg {{ font-size: 0.75rem; color: #aaa; min-height: 18px; margin-bottom: 4px; }}
  .action-msg.ok {{ color: #4caf50; }}
  .action-msg.err {{ color: #f44336; }}
  details {{ margin-top: 8px; }}
  summary {{ cursor: pointer; color: #888; font-size: 0.75rem; }}
  .log {{ background: #111318; padding: 8px; border-radius: 8px; font-size: 0.7rem; max-height: 180px; overflow-y: auto; margin-top: 6px; white-space: pre-wrap; word-break: break-all; color: #aaa; }}
  .refresh {{ text-align: center; margin-top: 16px; color: #555; font-size: 0.75rem; }}
  .all-controls {{ text-align: center; margin-bottom: 16px; }}
  .all-controls .btn {{ padding: 8px 20px; font-size: 0.85rem; }}
</style>
</head>
<body>
<h1>Server Monitor</h1>
<p class="subtitle">biz_life 프로젝트 통합 모니터링 + 제어</p>

<div class="system">
  <div class="sys-card">
    <h4>CPU</h4>
    <div class="value">{sys_info['cpu_percent']}%</div>
    <div class="bar"><div class="bar-fill" style="width:{sys_info['cpu_percent']}%;background:{cpu_color}"></div></div>
    <div style="color:#666;font-size:0.7rem;margin-top:3px">{sys_info['cpu_count']} cores</div>
  </div>
  <div class="sys-card">
    <h4>Memory</h4>
    <div class="value">{sys_info['mem_used_gb']} / {sys_info['mem_total_gb']} GB</div>
    <div class="bar"><div class="bar-fill" style="width:{sys_info['mem_percent']}%;background:{mem_color}"></div></div>
  </div>
  <div class="sys-card">
    <h4>Disk (C:)</h4>
    <div class="value">{sys_info['disk_used_gb']} / {sys_info['disk_total_gb']} GB</div>
    <div class="bar"><div class="bar-fill" style="width:{sys_info['disk_percent']}%;background:{disk_color}"></div></div>
  </div>
</div>

<div class="all-controls">
  <button class="btn btn-start" onclick="ctrlAll('start')">전체 시작</button>
  <button class="btn btn-stop" onclick="ctrlAll('stop')">전체 중지</button>
  <button class="btn btn-restart" onclick="ctrlAll('restart')">전체 재시작</button>
</div>

<div class="grid">
{project_cards}
</div>

<p class="refresh">30초마다 자동 새로고침 &middot; <a href="/" style="color:#64b5f6">수동 새로고침</a></p>

<script>
async function ctrl(name, action) {{
  const msg = document.getElementById('msg-' + name);
  msg.textContent = action + ' 중...';
  msg.className = 'action-msg';
  try {{
    const res = await fetch('/api/' + action + '/' + name, {{method: 'POST'}});
    const data = await res.json();
    msg.textContent = data.msg;
    msg.className = 'action-msg ' + (data.ok ? 'ok' : 'err');
    setTimeout(() => location.reload(), 2000);
  }} catch(e) {{
    msg.textContent = '요청 실패: ' + e;
    msg.className = 'action-msg err';
  }}
}}
async function ctrlAll(action) {{
  const names = {list(PROJECTS.keys())};
  for (const name of names) {{
    ctrl(name, action);
    await new Promise(r => setTimeout(r, 1000));
  }}
}}
</script>
</body>
</html>"""

    req_host = request.headers.get("host", "localhost:9000")
    host_only = req_host.split(":")[0]
    html = html.replace("{{host}}", host_only)
    return HTMLResponse(html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=9000)
