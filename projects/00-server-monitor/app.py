"""
통합 모니터링 대시보드 - 포트 9000
프로젝트 상태 확인 + 시작/중지/재시작 제어
"""
import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from config import PROJECTS
from services import (
    check_port,
    get_recent_logs,
    get_system_info,
    get_event_history,
    get_uptime_stats,
    start_project,
    stop_project,
    restart_project,
    search_events,
)
from deploy import deploy_router, get_deploy_manager
from anomaly import get_alert_manager, get_collector, MaintenanceWindow
from scheduler import get_schedules, add_schedule, remove_schedule, toggle_schedule, DAY_NAMES_KO
from auto_healer import get_healing_engine, get_healing_history

app = FastAPI(title="Server Monitor")
app.include_router(deploy_router)


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

@app.get("/api/events")
async def api_events(project: str = None, limit: int = 50):
    return JSONResponse(get_event_history(project_name=project, limit=limit))

@app.get("/api/events/search")
async def api_events_search(
    project: str = None,
    event_type: str = None,
    days: int = None,
    hours: int = None,
    limit: int = 100,
):
    """이벤트 검색 API - event_type은 쉼표 구분 (예: error,restart)"""
    type_list = None
    if event_type:
        type_list = [t.strip() for t in event_type.split(",") if t.strip()]
    results = search_events(
        project_name=project if project else None,
        event_types=type_list,
        days=days,
        hours=hours,
        limit=limit,
    )
    return JSONResponse(results)

@app.get("/api/uptime")
async def api_uptime():
    return JSONResponse(get_uptime_stats())


# === 알림 & 이상 탐지 API ===

@app.get("/api/alerts")
async def api_alerts(limit: int = 50):
    return JSONResponse(get_alert_manager().get_recent_alerts(limit))

@app.get("/api/alerts/stats")
async def api_alert_stats():
    return JSONResponse(get_alert_manager().get_alert_stats())

@app.get("/api/metrics/history")
async def api_metrics_history(minutes: int = None):
    history = get_collector().get_history(minutes=minutes)
    return JSONResponse(history)

@app.get("/api/alerts/thresholds")
async def api_alert_thresholds():
    return JSONResponse(get_alert_manager().get_thresholds())

@app.post("/api/maintenance/start")
async def api_maintenance_start(request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    hours = body.get("hours", 2)
    mw = MaintenanceWindow()
    mw.start(hours=hours)
    return JSONResponse({"ok": True, "msg": f"유지보수 윈도우 시작 ({hours}시간)"})

@app.post("/api/maintenance/stop")
async def api_maintenance_stop():
    mw = MaintenanceWindow()
    mw.stop()
    return JSONResponse({"ok": True, "msg": "유지보수 윈도우 종료"})


# === 예약 재시작 API ===

@app.get("/api/schedules")
async def api_schedules():
    """전체 스케줄 목록 반환"""
    return JSONResponse(get_schedules())

@app.post("/api/schedules")
async def api_schedule_create(request: Request):
    """스케줄 생성"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "msg": "잘못된 요청"}, status_code=400)
    result = add_schedule(
        project_name=body.get("project_name", ""),
        schedule_type=body.get("schedule_type", ""),
        time_str=body.get("time", ""),
        day_of_week=body.get("day_of_week"),
        enabled=body.get("enabled", True),
    )
    return JSONResponse(result)

@app.delete("/api/schedules/{schedule_id}")
async def api_schedule_delete(schedule_id: str):
    """스케줄 삭제"""
    return JSONResponse(remove_schedule(schedule_id))

@app.put("/api/schedules/{schedule_id}/toggle")
async def api_schedule_toggle(schedule_id: str):
    """스케줄 활성/비활성 토글"""
    return JSONResponse(toggle_schedule(schedule_id))


# === 자동 복구 API ===

@app.get("/api/health-scores")
async def api_health_scores():
    """프로젝트별 건강 점수 반환 (캐시 5분)"""
    engine = get_healing_engine()
    scorer = engine.health_scorer
    cached = scorer.get_cached_scores()
    if cached:
        return JSONResponse(cached)
    return JSONResponse(scorer.calculate_all_scores())

@app.get("/api/healing-history")
async def api_healing_history(limit: int = 50, project: str = None):
    """복구 이력 반환"""
    return JSONResponse(get_healing_history(limit=limit, project=project))

@app.post("/api/healing/trigger/{project}")
async def api_healing_trigger(project: str):
    """수동 복구 트리거"""
    engine = get_healing_engine()
    result = engine.manual_heal(project)
    return JSONResponse(result)

@app.get("/api/healing/status")
async def api_healing_status():
    """자동 복구 엔진 상태"""
    engine = get_healing_engine()
    return JSONResponse(engine.get_engine_status())


# === 대시보드 UI ===

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    from datetime import datetime

    tasks = [check_port(p["port"]) for p in PROJECTS.values()]
    results = await asyncio.gather(*tasks)
    sys_info = get_system_info()
    uptime_stats = get_uptime_stats()
    recent_events = get_event_history(limit=30)

    # 알림 데이터
    alert_mgr = get_alert_manager()
    recent_alerts = alert_mgr.get_recent_alerts(20)
    alert_stats = alert_mgr.get_alert_stats()
    maintenance_status = MaintenanceWindow().get_status()
    unresolved_critical = alert_stats.get("unresolved_critical", 0)

    # 자동 복구 데이터
    healing_engine = get_healing_engine()
    healing_scorer = healing_engine.health_scorer
    health_scores = healing_scorer.get_cached_scores()
    if not health_scores:
        try:
            health_scores = healing_scorer.calculate_all_scores()
        except Exception:
            health_scores = {"system_score": 0, "alive_count": 0, "total_count": 0, "projects": {}}
    healing_history = get_healing_history(limit=20)
    healing_status = healing_engine.get_engine_status()

    def _time_ago(iso_str: str) -> str:
        """ISO 시간 문자열을 '~전' 형식으로 변환"""
        if not iso_str:
            return "기록 없음"
        try:
            dt = datetime.fromisoformat(iso_str)
            diff = datetime.now() - dt
            secs = int(diff.total_seconds())
            if secs < 60:
                return f"{secs}초 전"
            elif secs < 3600:
                return f"{secs // 60}분 전"
            elif secs < 86400:
                return f"{secs // 3600}시간 전"
            else:
                return f"{secs // 86400}일 전"
        except (ValueError, TypeError):
            return "기록 없음"

    project_cards = ""
    for (name, proj), alive in zip(PROJECTS.items(), results):
        status_class = "alive" if alive else "dead"
        status_text = "실행 중" if alive else "중지됨"
        status_dot = "🟢" if alive else "🔴"
        logs = get_recent_logs(name)
        logs_escaped = logs.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        stats = uptime_stats.get(name, {})
        uptime_pct = stats.get("uptime_percent", 0.0)
        last_restart = stats.get("last_restart", "")
        last_restart_ago = _time_ago(last_restart)

        if uptime_pct >= 99:
            uptime_color = "#4caf50"
        elif uptime_pct >= 90:
            uptime_color = "#ff9800"
        else:
            uptime_color = "#f44336"

        project_cards += f"""
        <div class="card {status_class}" id="card-{name}">
            <div class="card-header">
                <span class="status-dot">{status_dot}</span>
                <h3>{name}</h3>
                <span class="badge">{status_text}</span>
                <span class="badge uptime-badge" style="background:{uptime_color}22;color:{uptime_color}">가동률 {uptime_pct}%</span>
            </div>
            <p class="desc">{proj['desc']} &mdash; 포트 {proj['port']}</p>
            <p class="desc">마지막 재시작: {last_restart_ago}</p>
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

    # 이벤트 타임라인 HTML 생성
    event_icons = {
        "start": "▶️",
        "stop": "⏹️",
        "restart": "🔄",
        "auto_restart": "🤖",
        "scheduled_restart": "⏰",
        "resource_alert": "⚠️",
        "error": "❌",
    }
    event_timeline_html = ""
    if recent_events:
        for ev in recent_events:
            icon = event_icons.get(ev.get("type", ""), "📋")
            ev_time = _time_ago(ev.get("timestamp", ""))
            ev_ts = ev.get("timestamp", "")[:19].replace("T", " ")
            ev_project = ev.get("project", "")
            ev_details = ev.get("details", ev.get("type", ""))
            ev_details_escaped = ev_details.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            event_timeline_html += f"""<div class="event-item">
              <span class="event-icon">{icon}</span>
              <span class="event-time" title="{ev_ts}">{ev_time}</span>
              <span class="event-project">{ev_project}</span>
              <span class="event-details">{ev_details_escaped}</span>
            </div>\n"""
    else:
        event_timeline_html = '<div style="color:#666;font-size:0.8rem;padding:8px 0;">이벤트 기록이 없습니다.</div>'

    # 알림 타임라인 HTML 생성
    alert_level_icons = {"CRITICAL": "\U0001f6a8", "WARNING": "\u26a0\ufe0f", "INFO": "\u2139\ufe0f"}
    alert_timeline_html = ""
    if recent_alerts:
        for al in recent_alerts[:20]:
            al_level = al.get("level", "INFO")
            al_icon = alert_level_icons.get(al_level, "\U0001f4e2")
            al_time = _time_ago(al.get("timestamp", ""))
            al_ts = al.get("timestamp", "")[:19].replace("T", " ")
            al_type = al.get("type", "")
            al_msg = al.get("message", "")
            al_msg_escaped = al_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            alert_timeline_html += f"""<div class="alert-item {al_level}">
              <span class="alert-level">{al_icon}</span>
              <span class="alert-time" title="{al_ts}">{al_time}</span>
              <span class="alert-type">{al_type}</span>
              <span class="alert-msg">{al_msg_escaped}</span>
            </div>\n"""
    else:
        alert_timeline_html = '<div style="color:#666;font-size:0.8rem;padding:8px 0;">알림 기록이 없습니다.</div>'

    maint_active = maintenance_status.get("active", False)
    maint_end = maintenance_status.get("end", "")
    maint_end_display = _time_ago(maint_end) if maint_end else ""

    # 배포 상태 카드 생성
    deploy_mgr = get_deploy_manager()
    last_deploy = deploy_mgr.get_last_deploy()
    if last_deploy:
        deploy_time = _time_ago(last_deploy.get("timestamp", ""))
        deploy_ts = last_deploy.get("timestamp", "")[:19].replace("T", " ")
        deploy_success = last_deploy.get("success", False)
        deploy_trigger = last_deploy.get("trigger", "unknown")
        deploy_projects = ", ".join(last_deploy.get("projects", [])) or "없음"
        deploy_color = "#4caf50" if deploy_success else "#f44336"
        deploy_status_text = "성공" if deploy_success else "실패"
        deploy_card_html = f"""
        <div class="sys-card" style="border-left:3px solid {deploy_color}">
          <h4>마지막 배포</h4>
          <div class="value" style="font-size:1rem;color:{deploy_color}">{deploy_status_text}</div>
          <div style="color:#888;font-size:0.72rem;margin-top:4px">{deploy_time} ({deploy_trigger})</div>
          <div style="color:#666;font-size:0.7rem;margin-top:2px" title="{deploy_ts}">프로젝트: {deploy_projects}</div>
          <div style="margin-top:6px">
            <button class="btn btn-restart" onclick="manualDeploy('all')" style="padding:4px 10px;font-size:0.7rem">수동 배포</button>
            <button class="btn btn-link" onclick="gitPull()" style="padding:4px 10px;font-size:0.7rem">git pull</button>
          </div>
          <div class="action-msg" id="deploy-msg" style="margin-top:4px"></div>
        </div>"""
    else:
        deploy_card_html = f"""
        <div class="sys-card" style="border-left:3px solid #666">
          <h4>배포</h4>
          <div class="value" style="font-size:1rem;color:#666">이력 없음</div>
          <div style="margin-top:6px">
            <button class="btn btn-restart" onclick="manualDeploy('all')" style="padding:4px 10px;font-size:0.7rem">수동 배포</button>
            <button class="btn btn-link" onclick="gitPull()" style="padding:4px 10px;font-size:0.7rem">git pull</button>
          </div>
          <div class="action-msg" id="deploy-msg" style="margin-top:4px"></div>
        </div>"""

    # 자동 복구 - 건강 점수 게이지 HTML 생성
    system_score = health_scores.get("system_score", 0)
    project_scores = health_scores.get("projects", {})

    def _score_color(score):
        if score >= 80:
            return "#4caf50"
        elif score >= 60:
            return "#ff9800"
        elif score >= 40:
            return "#f44336"
        else:
            return "#d32f2f"

    # SVG 게이지 둘레 계산 (반지름 32, 둘레 = 2*pi*32 ~= 201)
    gauge_circumference = 201

    # 시스템 전체 게이지
    sys_score_offset = gauge_circumference - (gauge_circumference * system_score / 100)
    sys_score_color = _score_color(system_score)
    health_gauges_html = f"""
    <div class="health-gauge">
      <div class="gauge-name">시스템 전체</div>
      <div class="gauge-ring">
        <svg viewBox="0 0 70 70">
          <circle class="bg" cx="35" cy="35" r="32"/>
          <circle class="fg" cx="35" cy="35" r="32" stroke="{sys_score_color}" stroke-dasharray="{gauge_circumference}" stroke-dashoffset="{sys_score_offset:.1f}"/>
        </svg>
        <div class="gauge-score" style="color:{sys_score_color}">{system_score}</div>
      </div>
      <div class="gauge-status">{health_scores.get('alive_count', 0)}/{health_scores.get('total_count', 0)} 실행 중</div>
    </div>"""

    for pname, pdata in project_scores.items():
        pscore = pdata.get("score", 0)
        palive = pdata.get("alive", False)
        pcolor = _score_color(pscore)
        poffset = gauge_circumference - (gauge_circumference * pscore / 100)
        alive_cls = "gauge-alive" if palive else "gauge-dead"
        alive_txt = "실행 중" if palive else "중지됨"
        health_gauges_html += f"""
    <div class="health-gauge">
      <div class="gauge-name">{pname}</div>
      <div class="gauge-ring">
        <svg viewBox="0 0 70 70">
          <circle class="bg" cx="35" cy="35" r="32"/>
          <circle class="fg" cx="35" cy="35" r="32" stroke="{pcolor}" stroke-dasharray="{gauge_circumference}" stroke-dashoffset="{poffset:.1f}"/>
        </svg>
        <div class="gauge-score" style="color:{pcolor}">{pscore}</div>
      </div>
      <div class="gauge-status {alive_cls}">{alive_txt}</div>
    </div>"""

    # 복구 이력 HTML
    heal_severity_icons = {"CRITICAL": "\U0001f6a8", "WARNING": "\u26a0\ufe0f", "INFO": "\u2139\ufe0f"}
    healing_history_html = ""
    if healing_history:
        for hh in healing_history[:20]:
            hh_sev = hh.get("severity", "INFO")
            hh_icon = heal_severity_icons.get(hh_sev, "\U0001f527")
            hh_time = _time_ago(hh.get("timestamp", ""))
            hh_ts = hh.get("timestamp", "")[:19].replace("T", " ")
            hh_project = hh.get("project", "")
            hh_action = hh.get("action", "")
            hh_result = hh.get("result", "")
            hh_action_escaped = hh_action.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            hh_result_escaped = hh_result.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            healing_history_html += f"""<div class="heal-item {hh_sev}">
              <span class="heal-severity">{hh_icon}</span>
              <span class="heal-time" title="{hh_ts}">{hh_time}</span>
              <span class="heal-project">{hh_project}</span>
              <span class="heal-action">{hh_action_escaped}</span>
              <span class="heal-result">{hh_result_escaped}</span>
            </div>\n"""
    else:
        healing_history_html = '<div style="color:#666;font-size:0.8rem;padding:8px 0;">복구 이력이 없습니다.</div>'

    # 엔진 상태
    engine_running = healing_status.get("running", False)
    engine_enabled = healing_status.get("enabled", False)
    engine_interval = healing_status.get("check_interval", 30)
    circuit_breakers = healing_status.get("circuit_breaker", {})

    cb_badges_html = ""
    for cb_proj, cb_info in circuit_breakers.items():
        if cb_info.get("open"):
            remaining = cb_info.get("remaining_seconds", 0)
            cb_badges_html += f'<span class="cb-badge">{cb_proj}: OPEN ({remaining}s)</span>'

    cpu_color = "#4caf50" if sys_info["cpu_percent"] < 60 else "#ff9800" if sys_info["cpu_percent"] < 85 else "#f44336"
    mem_color = "#4caf50" if sys_info["mem_percent"] < 60 else "#ff9800" if sys_info["mem_percent"] < 85 else "#f44336"
    disk_color = "#4caf50" if sys_info["disk_percent"] < 75 else "#ff9800" if sys_info["disk_percent"] < 90 else "#f44336"

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{"🚨 (" + str(unresolved_critical) + ") " if unresolved_critical > 0 else ""}Server Monitor</title>
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
  .uptime-badge {{ margin-left: 4px; }}
  .refresh {{ text-align: center; margin-top: 16px; color: #555; font-size: 0.75rem; }}
  .all-controls {{ text-align: center; margin-bottom: 16px; }}
  .all-controls .btn {{ padding: 8px 20px; font-size: 0.85rem; }}
  .events-section {{ margin-top: 24px; background: #1a1d27; border-radius: 12px; padding: 16px; }}
  .events-section h2 {{ font-size: 1.1rem; margin-bottom: 12px; display: flex; align-items: center; gap: 10px; }}
  .event-item {{ display: flex; align-items: flex-start; gap: 10px; padding: 8px 0; border-bottom: 1px solid #2a2d37; font-size: 0.8rem; }}
  .event-item:last-child {{ border-bottom: none; }}
  .event-icon {{ font-size: 1rem; min-width: 24px; text-align: center; }}
  .event-time {{ color: #666; min-width: 130px; font-size: 0.72rem; }}
  .event-project {{ color: #64b5f6; min-width: 110px; font-weight: 600; font-size: 0.75rem; }}
  .event-details {{ color: #aaa; flex: 1; }}

  /* 필터 패널 */
  .filter-toggle {{ background: #2a2d37; color: #aaa; border: none; padding: 4px 12px; border-radius: 8px; font-size: 0.75rem; cursor: pointer; }}
  .filter-toggle:hover {{ background: #3a3d47; color: #e0e0e0; }}
  .filter-panel {{ background: #15171e; border-radius: 10px; padding: 14px; margin-bottom: 14px; display: none; }}
  .filter-panel.open {{ display: block; }}
  .filter-row {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 10px; }}
  .filter-row:last-child {{ margin-bottom: 0; }}
  .filter-label {{ color: #888; font-size: 0.72rem; min-width: 60px; text-transform: uppercase; font-weight: 600; }}
  .filter-row select {{ background: #1a1d27; color: #e0e0e0; border: 1px solid #2a2d37; border-radius: 6px; padding: 4px 8px; font-size: 0.75rem; }}
  .filter-row label {{ display: flex; align-items: center; gap: 4px; color: #ccc; font-size: 0.72rem; cursor: pointer; }}
  .filter-row input[type="checkbox"] {{ accent-color: #64b5f6; }}
  .time-btn {{ background: #2a2d37; color: #aaa; border: none; padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; cursor: pointer; transition: all 0.15s; }}
  .time-btn:hover {{ background: #3a3d47; color: #e0e0e0; }}
  .time-btn.active {{ background: #1b2a3a; color: #64b5f6; border: 1px solid #64b5f6; }}
  .filter-summary {{ color: #888; font-size: 0.72rem; padding: 6px 0 4px; }}
  .filter-actions {{ display: flex; gap: 8px; align-items: center; }}
  .filter-apply {{ background: #1b2a3a; color: #64b5f6; border: 1px solid #64b5f6; padding: 4px 14px; border-radius: 6px; font-size: 0.72rem; cursor: pointer; font-weight: 600; }}
  .filter-apply:hover {{ background: #264a6a; }}
  .filter-reset {{ background: none; color: #888; border: 1px solid #2a2d37; padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; cursor: pointer; }}
  .filter-reset:hover {{ color: #e0e0e0; border-color: #555; }}

  /* 자동 새로고침 토글 */
  .refresh-toggle {{ display: inline-flex; align-items: center; gap: 6px; background: #1a1d27; border: 1px solid #2a2d37; padding: 4px 12px; border-radius: 8px; font-size: 0.72rem; cursor: pointer; color: #aaa; }}
  .refresh-toggle:hover {{ border-color: #555; color: #e0e0e0; }}
  .refresh-toggle.paused {{ border-color: #f44336; color: #f44336; }}
  .refresh-toggle .indicator {{ width: 8px; height: 8px; border-radius: 50%; background: #4caf50; }}
  .refresh-toggle.paused .indicator {{ background: #f44336; }}

  /* 알림 섹션 */
  .alerts-section {{ margin-top: 24px; background: #1a1d27; border-radius: 12px; padding: 16px; }}
  .alerts-section h2 {{ font-size: 1.1rem; margin-bottom: 12px; display: flex; align-items: center; gap: 10px; }}
  .critical-badge {{ background: #f44336; color: #fff; font-size: 0.7rem; padding: 2px 8px; border-radius: 12px; font-weight: 700; }}
  .alert-item {{ display: flex; align-items: flex-start; gap: 10px; padding: 8px 0; border-bottom: 1px solid #2a2d37; font-size: 0.8rem; }}
  .alert-item:last-child {{ border-bottom: none; }}
  .alert-item.CRITICAL {{ border-left: 3px solid #f44336; padding-left: 8px; }}
  .alert-item.WARNING {{ border-left: 3px solid #ff9800; padding-left: 8px; }}
  .alert-item.INFO {{ border-left: 3px solid #64b5f6; padding-left: 8px; }}
  .alert-level {{ font-size: 1rem; min-width: 24px; text-align: center; }}
  .alert-time {{ color: #666; min-width: 130px; font-size: 0.72rem; }}
  .alert-type {{ color: #64b5f6; min-width: 110px; font-weight: 600; font-size: 0.75rem; }}
  .alert-msg {{ color: #aaa; flex: 1; }}
  .sparkline-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-bottom: 16px; }}
  .sparkline-card {{ background: #15171e; border-radius: 10px; padding: 12px; }}
  .sparkline-card h4 {{ color: #aaa; font-size: 0.72rem; margin-bottom: 6px; text-transform: uppercase; }}
  .sparkline-card canvas {{ width: 100%; height: 60px; }}
  .maint-toggle {{ display: flex; align-items: center; gap: 12px; margin-bottom: 16px; padding: 10px; background: #15171e; border-radius: 10px; }}
  .maint-toggle .maint-status {{ font-size: 0.8rem; flex: 1; }}
  .maint-btn {{ padding: 6px 14px; border: none; border-radius: 8px; font-size: 0.78rem; cursor: pointer; font-weight: 600; }}
  .maint-btn.start {{ background: #2a2a1b; color: #ff9800; }}
  .maint-btn.stop {{ background: #3a1b1b; color: #f44336; }}
  .maint-msg {{ font-size: 0.72rem; color: #aaa; min-height: 16px; }}

  /* 예약 재시작 섹션 */
  .schedule-section {{ margin-top: 24px; background: #1a1d27; border-radius: 12px; padding: 16px; }}
  .schedule-section h2 {{ font-size: 1.1rem; margin-bottom: 12px; display: flex; align-items: center; gap: 10px; }}
  .schedule-table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
  .schedule-table th {{ text-align: left; color: #888; font-size: 0.72rem; text-transform: uppercase; padding: 8px 10px; border-bottom: 2px solid #2a2d37; font-weight: 600; }}
  .schedule-table td {{ padding: 8px 10px; border-bottom: 1px solid #2a2d37; vertical-align: middle; }}
  .schedule-table tr:last-child td {{ border-bottom: none; }}
  .schedule-table .sched-enabled {{ color: #4caf50; font-weight: 600; }}
  .schedule-table .sched-disabled {{ color: #888; }}
  .sched-toggle {{ background: none; border: 1px solid #2a2d37; color: #aaa; padding: 3px 10px; border-radius: 6px; font-size: 0.72rem; cursor: pointer; }}
  .sched-toggle:hover {{ border-color: #555; color: #e0e0e0; }}
  .sched-toggle.on {{ border-color: #4caf50; color: #4caf50; }}
  .sched-delete {{ background: none; border: 1px solid #3a1b1b; color: #f44336; padding: 3px 10px; border-radius: 6px; font-size: 0.72rem; cursor: pointer; }}
  .sched-delete:hover {{ background: #3a1b1b; }}
  .schedule-form {{ background: #15171e; border-radius: 10px; padding: 14px; margin-top: 14px; }}
  .schedule-form h4 {{ color: #aaa; font-size: 0.8rem; margin-bottom: 10px; }}
  .sched-form-row {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 10px; }}
  .sched-form-row:last-child {{ margin-bottom: 0; }}
  .sched-form-row label {{ color: #888; font-size: 0.72rem; min-width: 60px; }}
  .sched-form-row select, .sched-form-row input {{ background: #1a1d27; color: #e0e0e0; border: 1px solid #2a2d37; border-radius: 6px; padding: 5px 8px; font-size: 0.75rem; }}
  .sched-form-row input[type="time"] {{ width: 100px; }}
  .sched-add-btn {{ background: #1b2a3a; color: #64b5f6; border: 1px solid #64b5f6; padding: 5px 16px; border-radius: 6px; font-size: 0.75rem; cursor: pointer; font-weight: 600; }}
  .sched-add-btn:hover {{ background: #264a6a; }}
  .sched-msg {{ font-size: 0.72rem; color: #aaa; min-height: 16px; margin-top: 6px; }}
  .sched-msg.ok {{ color: #4caf50; }}
  .sched-msg.err {{ color: #f44336; }}
  .sched-empty {{ color: #666; font-size: 0.8rem; padding: 12px 0; }}

  /* 자동 복구 섹션 */
  .healing-section {{ margin-top: 24px; background: #1a1d27; border-radius: 12px; padding: 16px; }}
  .healing-section h2 {{ font-size: 1.1rem; margin-bottom: 12px; display: flex; align-items: center; gap: 10px; }}
  .health-overview {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 16px; }}
  .health-gauge {{ background: #15171e; border-radius: 10px; padding: 14px; text-align: center; position: relative; }}
  .health-gauge .gauge-name {{ color: #aaa; font-size: 0.72rem; margin-bottom: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .health-gauge .gauge-ring {{ position: relative; width: 70px; height: 70px; margin: 0 auto 6px; }}
  .health-gauge .gauge-ring svg {{ width: 70px; height: 70px; transform: rotate(-90deg); }}
  .health-gauge .gauge-ring .bg {{ fill: none; stroke: #2a2d37; stroke-width: 6; }}
  .health-gauge .gauge-ring .fg {{ fill: none; stroke-width: 6; stroke-linecap: round; transition: stroke-dashoffset 0.6s ease; }}
  .health-gauge .gauge-score {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 1.1rem; font-weight: 700; }}
  .health-gauge .gauge-status {{ font-size: 0.7rem; margin-top: 2px; }}
  .health-gauge .gauge-alive {{ color: #4caf50; }}
  .health-gauge .gauge-dead {{ color: #f44336; }}
  .healing-engine-status {{ display: flex; align-items: center; gap: 12px; margin-bottom: 16px; padding: 10px; background: #15171e; border-radius: 10px; font-size: 0.8rem; flex-wrap: wrap; }}
  .healing-engine-status .status-label {{ color: #888; }}
  .healing-engine-status .status-on {{ color: #4caf50; font-weight: 600; }}
  .healing-engine-status .status-off {{ color: #f44336; font-weight: 600; }}
  .heal-btn {{ background: #1b2a3a; color: #64b5f6; border: 1px solid #64b5f6; padding: 4px 12px; border-radius: 6px; font-size: 0.72rem; cursor: pointer; font-weight: 600; }}
  .heal-btn:hover {{ background: #264a6a; }}
  .heal-msg {{ font-size: 0.72rem; color: #aaa; min-height: 16px; margin-top: 4px; }}
  .heal-msg.ok {{ color: #4caf50; }}
  .heal-msg.err {{ color: #f44336; }}
  .healing-history {{ max-height: 300px; overflow-y: auto; }}
  .heal-item {{ display: flex; align-items: flex-start; gap: 10px; padding: 8px 0; border-bottom: 1px solid #2a2d37; font-size: 0.8rem; }}
  .heal-item:last-child {{ border-bottom: none; }}
  .heal-item.CRITICAL {{ border-left: 3px solid #f44336; padding-left: 8px; }}
  .heal-item.WARNING {{ border-left: 3px solid #ff9800; padding-left: 8px; }}
  .heal-item.INFO {{ border-left: 3px solid #64b5f6; padding-left: 8px; }}
  .heal-severity {{ font-size: 1rem; min-width: 24px; text-align: center; }}
  .heal-time {{ color: #666; min-width: 130px; font-size: 0.72rem; }}
  .heal-project {{ color: #64b5f6; min-width: 100px; font-weight: 600; font-size: 0.75rem; }}
  .heal-action {{ color: #e0e0e0; min-width: 140px; font-size: 0.75rem; }}
  .heal-result {{ color: #aaa; flex: 1; }}
  .circuit-breaker-info {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 6px; }}
  .cb-badge {{ font-size: 0.68rem; padding: 2px 8px; border-radius: 8px; background: #3a1b1b; color: #f44336; }}
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
  {deploy_card_html}
</div>

<div class="all-controls">
  <button class="btn btn-start" onclick="ctrlAll('start')">전체 시작</button>
  <button class="btn btn-stop" onclick="ctrlAll('stop')">전체 중지</button>
  <button class="btn btn-restart" onclick="ctrlAll('restart')">전체 재시작</button>
</div>

<div class="grid">
{project_cards}
</div>

<div class="events-section">
  <h2>
    이벤트 히스토리
    <button class="filter-toggle" onclick="toggleFilterPanel()">필터</button>
  </h2>
  <div class="filter-panel" id="filterPanel">
    <div class="filter-row">
      <span class="filter-label">프로젝트</span>
      <select id="filterProject">
        <option value="">전체</option>
        {"".join(f'<option value="{n}">{n}</option>' for n in PROJECTS.keys())}
      </select>
    </div>
    <div class="filter-row">
      <span class="filter-label">이벤트</span>
      <label><input type="checkbox" class="evt-type-cb" value="start" checked> start</label>
      <label><input type="checkbox" class="evt-type-cb" value="stop" checked> stop</label>
      <label><input type="checkbox" class="evt-type-cb" value="restart" checked> restart</label>
      <label><input type="checkbox" class="evt-type-cb" value="auto_restart" checked> auto_restart</label>
      <label><input type="checkbox" class="evt-type-cb" value="error" checked> error</label>
      <label><input type="checkbox" class="evt-type-cb" value="resource_alert" checked> resource_alert</label>
      <label><input type="checkbox" class="evt-type-cb" value="scheduled_restart" checked> scheduled_restart</label>
      <label><input type="checkbox" class="evt-type-cb" value="deploy" checked> deploy</label>
    </div>
    <div class="filter-row">
      <span class="filter-label">기간</span>
      <button class="time-btn" data-hours="1" onclick="setTimeFilter(this)">1h</button>
      <button class="time-btn" data-hours="24" onclick="setTimeFilter(this)">24h</button>
      <button class="time-btn active" data-days="7" onclick="setTimeFilter(this)">7d</button>
      <button class="time-btn" data-days="30" onclick="setTimeFilter(this)">30d</button>
    </div>
    <div class="filter-row">
      <span class="filter-label"></span>
      <div class="filter-actions">
        <button class="filter-apply" onclick="applyFilter()">검색</button>
        <button class="filter-reset" onclick="resetFilter()">초기화</button>
      </div>
    </div>
  </div>
  <div class="filter-summary" id="filterSummary"></div>
  <div id="eventTimeline">
    {event_timeline_html}
  </div>
</div>

<div class="alerts-section">
  <h2>
    \U0001f6a8 Alerts
    {"<span class='critical-badge'>" + str(unresolved_critical) + " CRITICAL</span>" if unresolved_critical > 0 else ""}
  </h2>

  <!-- 유지보수 윈도우 토글 -->
  <div class="maint-toggle">
    <div class="maint-status">
      \U0001f527 유지보수 윈도우: <strong>{"활성 (종료: " + maint_end[:19].replace("T"," ") + ")" if maint_active else "비활성"}</strong>
    </div>
    {"<button class='maint-btn stop' onclick='maintStop()'>윈도우 종료</button>" if maint_active else "<button class='maint-btn start' onclick='maintStart()'>윈도우 시작 (2h)</button>"}
    <span class="maint-msg" id="maintMsg"></span>
  </div>

  <!-- 메트릭 스파크라인 -->
  <div class="sparkline-row">
    <div class="sparkline-card">
      <h4>CPU %</h4>
      <canvas id="sparkCpu"></canvas>
    </div>
    <div class="sparkline-card">
      <h4>Memory %</h4>
      <canvas id="sparkMem"></canvas>
    </div>
    <div class="sparkline-card">
      <h4>Disk %</h4>
      <canvas id="sparkDisk"></canvas>
    </div>
  </div>

  <!-- 알림 타임라인 -->
  <div id="alertTimeline">
    {alert_timeline_html}
  </div>
</div>

<!-- 예약 재시작 섹션 -->
<div class="schedule-section">
  <h2>예약 재시작</h2>
  <div id="scheduleTable">
    <div class="sched-empty">스케줄 로딩 중...</div>
  </div>

  <div class="schedule-form">
    <h4>새 예약 추가</h4>
    <div class="sched-form-row">
      <label>프로젝트</label>
      <select id="schedProject">
        {"".join(f'<option value="{n}">{n}</option>' for n in PROJECTS.keys())}
      </select>
    </div>
    <div class="sched-form-row">
      <label>유형</label>
      <select id="schedType" onchange="schedTypeChanged()">
        <option value="daily">매일 (daily)</option>
        <option value="weekly">매주 (weekly)</option>
      </select>
    </div>
    <div class="sched-form-row">
      <label>시간</label>
      <input type="time" id="schedTime" value="04:00">
    </div>
    <div class="sched-form-row" id="schedDayRow" style="display:none">
      <label>요일</label>
      <select id="schedDay">
        <option value="0">월요일</option>
        <option value="1">화요일</option>
        <option value="2">수요일</option>
        <option value="3">목요일</option>
        <option value="4">금요일</option>
        <option value="5">토요일</option>
        <option value="6">일요일</option>
      </select>
    </div>
    <div class="sched-form-row">
      <label></label>
      <button class="sched-add-btn" onclick="addSchedule()">추가</button>
    </div>
    <div class="sched-msg" id="schedMsg"></div>
  </div>
</div>

<!-- 자동 복구 섹션 -->
<div class="healing-section">
  <h2>\U0001fa79 자동 복구</h2>

  <!-- 엔진 상태 -->
  <div class="healing-engine-status">
    <span class="status-label">엔진:</span>
    <span class="{"status-on" if engine_running else "status-off"}">{"실행 중" if engine_running else "중지됨"}</span>
    <span class="status-label">간격: {engine_interval}초</span>
    {f'<span class="status-label">서킷 브레이커:</span>' + cb_badges_html if cb_badges_html else ''}
    <button class="heal-btn" onclick="healAll()">전체 복구</button>
    <span class="heal-msg" id="healAllMsg"></span>
  </div>

  <!-- 건강 점수 게이지 -->
  <div class="health-overview">
    {health_gauges_html}
  </div>

  <!-- 프로젝트별 수동 복구 -->
  <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px">
    {"".join('<button class="heal-btn" onclick="healProject(' + chr(39) + n + chr(39) + ')">' + n + '</button>' for n in PROJECTS.keys())}
  </div>
  <div class="heal-msg" id="healProjectMsg"></div>

  <!-- 복구 이력 -->
  <details open>
    <summary style="cursor:pointer;color:#aaa;font-size:0.8rem;margin-bottom:8px">복구 이력 (최근 20건)</summary>
    <div class="healing-history" id="healingHistory">
      {healing_history_html}
    </div>
  </details>
</div>

<p class="refresh">
  <button class="refresh-toggle" id="refreshToggle" onclick="toggleAutoRefresh()">
    <span class="indicator"></span>
    <span id="refreshLabel">자동 새로고침 켜짐 (30초)</span>
  </button>
  &middot; <a href="/" style="color:#64b5f6">수동 새로고침</a>
</p>

<script>
/* === 프로젝트 제어 === */
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
async function manualDeploy(project) {{
  const msg = document.getElementById('deploy-msg');
  msg.textContent = '배포 중...';
  msg.className = 'action-msg';
  try {{
    const res = await fetch('/api/deploy/manual?project=' + project, {{method: 'POST'}});
    const data = await res.json();
    msg.textContent = data.msg;
    msg.className = 'action-msg ' + (data.ok ? 'ok' : 'err');
    setTimeout(() => location.reload(), 3000);
  }} catch(e) {{
    msg.textContent = '배포 실패: ' + e;
    msg.className = 'action-msg err';
  }}
}}
async function gitPull() {{
  const msg = document.getElementById('deploy-msg');
  msg.textContent = 'git pull 중...';
  msg.className = 'action-msg';
  try {{
    const res = await fetch('/api/deploy/pull', {{method: 'POST'}});
    const data = await res.json();
    msg.textContent = data.msg;
    msg.className = 'action-msg ' + (data.ok ? 'ok' : 'err');
    setTimeout(() => location.reload(), 2000);
  }} catch(e) {{
    msg.textContent = 'git pull 실패: ' + e;
    msg.className = 'action-msg err';
  }}
}}

/* === 이벤트 필터 === */
const eventIcons = {{
  start: "\\u25b6\\ufe0f", stop: "\\u23f9\\ufe0f", restart: "\\ud83d\\udd04",
  auto_restart: "\\ud83e\\udd16", scheduled_restart: "\\u23f0", resource_alert: "\\u26a0\\ufe0f", error: "\\u274c", deploy: "\\ud83d\\ude80"
}};
let activeTimeBtn = document.querySelector('.time-btn.active');

function toggleFilterPanel() {{
  document.getElementById('filterPanel').classList.toggle('open');
}}

function setTimeFilter(btn) {{
  document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  activeTimeBtn = btn;
}}

function resetFilter() {{
  document.getElementById('filterProject').value = '';
  document.querySelectorAll('.evt-type-cb').forEach(cb => cb.checked = true);
  document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
  const def = document.querySelector('.time-btn[data-days="7"]');
  if (def) {{ def.classList.add('active'); activeTimeBtn = def; }}
  document.getElementById('filterSummary').textContent = '';
  applyFilter();
}}

function timeAgo(isoStr) {{
  if (!isoStr) return "기록 없음";
  try {{
    const dt = new Date(isoStr);
    const secs = Math.floor((Date.now() - dt.getTime()) / 1000);
    if (secs < 60) return secs + "초 전";
    if (secs < 3600) return Math.floor(secs / 60) + "분 전";
    if (secs < 86400) return Math.floor(secs / 3600) + "시간 전";
    return Math.floor(secs / 86400) + "일 전";
  }} catch(e) {{ return "기록 없음"; }}
}}

function escapeHtml(str) {{
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}}

async function applyFilter() {{
  const project = document.getElementById('filterProject').value;
  const types = Array.from(document.querySelectorAll('.evt-type-cb:checked')).map(cb => cb.value);
  const btn = document.querySelector('.time-btn.active');

  let params = new URLSearchParams();
  if (project) params.set('project', project);
  if (types.length > 0 && types.length < 7) params.set('event_type', types.join(','));
  if (btn) {{
    if (btn.dataset.days) params.set('days', btn.dataset.days);
    else if (btn.dataset.hours) params.set('hours', btn.dataset.hours);
  }}
  params.set('limit', '100');

  try {{
    const res = await fetch('/api/events/search?' + params.toString());
    const events = await res.json();
    renderTimeline(events);

    // 필터 요약
    const parts = [events.length + '개 이벤트'];
    if (project) parts.push('프로젝트: ' + project);
    if (types.length < 7) parts.push('타입: ' + types.join(', '));
    if (btn) parts.push('기간: ' + btn.textContent);
    document.getElementById('filterSummary').textContent = parts.join(' | ');
  }} catch(e) {{
    document.getElementById('eventTimeline').innerHTML = '<div style="color:#f44336;font-size:0.8rem">검색 실패: ' + e + '</div>';
  }}
}}

function renderTimeline(events) {{
  const container = document.getElementById('eventTimeline');
  if (!events || events.length === 0) {{
    container.innerHTML = '<div style="color:#666;font-size:0.8rem;padding:8px 0;">조건에 맞는 이벤트가 없습니다.</div>';
    return;
  }}
  let html = '';
  events.forEach(ev => {{
    const icon = eventIcons[ev.type] || "\\ud83d\\udccb";
    const evTime = timeAgo(ev.timestamp);
    const evTs = (ev.timestamp || '').substring(0, 19).replace('T', ' ');
    const evProject = ev.project || '';
    const evDetails = escapeHtml(ev.details || ev.type || '');
    html += '<div class="event-item">' +
      '<span class="event-icon">' + icon + '</span>' +
      '<span class="event-time" title="' + evTs + '">' + evTime + '</span>' +
      '<span class="event-project">' + evProject + '</span>' +
      '<span class="event-details">' + evDetails + '</span>' +
      '</div>';
  }});
  container.innerHTML = html;
}}

/* === 자동 새로고침 토글 === */
let autoRefreshPaused = localStorage.getItem('autoRefreshPaused') === 'true';
let refreshTimer = null;

function updateRefreshUI() {{
  const btn = document.getElementById('refreshToggle');
  const label = document.getElementById('refreshLabel');
  if (autoRefreshPaused) {{
    btn.classList.add('paused');
    label.textContent = '자동 새로고침 꺼짐';
  }} else {{
    btn.classList.remove('paused');
    label.textContent = '자동 새로고침 켜짐 (30초)';
  }}
}}

function toggleAutoRefresh() {{
  autoRefreshPaused = !autoRefreshPaused;
  localStorage.setItem('autoRefreshPaused', autoRefreshPaused);
  updateRefreshUI();
  if (autoRefreshPaused) {{
    if (refreshTimer) {{ clearInterval(refreshTimer); refreshTimer = null; }}
  }} else {{
    startAutoRefresh();
  }}
}}

function startAutoRefresh() {{
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(() => {{
    if (!autoRefreshPaused) location.reload();
  }}, 30000);
}}

// 초기화
updateRefreshUI();
if (!autoRefreshPaused) startAutoRefresh();

/* === 유지보수 윈도우 토글 === */
async function maintStart() {{
  const msg = document.getElementById('maintMsg');
  msg.textContent = '시작 중...';
  try {{
    const res = await fetch('/api/maintenance/start', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{hours:2}})}});
    const data = await res.json();
    msg.textContent = data.msg;
    setTimeout(() => location.reload(), 1500);
  }} catch(e) {{ msg.textContent = '실패: ' + e; }}
}}
async function maintStop() {{
  const msg = document.getElementById('maintMsg');
  msg.textContent = '종료 중...';
  try {{
    const res = await fetch('/api/maintenance/stop', {{method:'POST'}});
    const data = await res.json();
    msg.textContent = data.msg;
    setTimeout(() => location.reload(), 1500);
  }} catch(e) {{ msg.textContent = '실패: ' + e; }}
}}

/* === 메트릭 스파크라인 === */
function drawSparkline(canvasId, data, color) {{
  const canvas = document.getElementById(canvasId);
  if (!canvas || !data.length) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  const w = rect.width, h = rect.height;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const step = w / (data.length - 1 || 1);
  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  data.forEach((v, i) => {{
    const x = i * step;
    const y = h - ((v - min) / range) * (h - 4) - 2;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }});
  ctx.stroke();
  // 마지막 값 표시
  if (data.length > 0) {{
    const last = data[data.length - 1];
    ctx.fillStyle = color;
    ctx.font = '11px sans-serif';
    ctx.fillText(last.toFixed(1) + '%', w - 45, 12);
  }}
}}
// 메트릭 데이터 로드 및 스파크라인 렌더링
(async function() {{
  try {{
    const res = await fetch('/api/metrics/history?minutes=120');
    const metrics = await res.json();
    if (metrics && metrics.length > 0) {{
      const cpuData = metrics.map(m => m.cpu_percent || 0);
      const memData = metrics.map(m => m.memory_percent || 0);
      const diskData = metrics.map(m => m.disk_percent || 0);
      drawSparkline('sparkCpu', cpuData, '#64b5f6');
      drawSparkline('sparkMem', memData, '#4caf50');
      drawSparkline('sparkDisk', diskData, '#ff9800');
    }}
  }} catch(e) {{ console.log('sparkline error:', e); }}
}})();

/* === 예약 재시작 === */
const dayNames = {{0:'월',1:'화',2:'수',3:'목',4:'금',5:'토',6:'일'}};

function schedTypeChanged() {{
  const t = document.getElementById('schedType').value;
  document.getElementById('schedDayRow').style.display = t === 'weekly' ? 'flex' : 'none';
}}

function formatNextRun(isoStr) {{
  if (!isoStr) return '-';
  try {{
    const dt = new Date(isoStr);
    const mm = String(dt.getMonth()+1).padStart(2,'0');
    const dd = String(dt.getDate()).padStart(2,'0');
    const hh = String(dt.getHours()).padStart(2,'0');
    const mi = String(dt.getMinutes()).padStart(2,'0');
    const dayKo = dayNames[dt.getDay() === 0 ? 6 : dt.getDay()-1] || '';
    return mm+'/'+dd+' ('+dayKo+') '+hh+':'+mi;
  }} catch(e) {{ return '-'; }}
}}

function renderSchedules(schedules) {{
  const container = document.getElementById('scheduleTable');
  if (!schedules || schedules.length === 0) {{
    container.innerHTML = '<div class="sched-empty">등록된 예약 재시작이 없습니다.</div>';
    return;
  }}
  let html = '<table class="schedule-table"><thead><tr>';
  html += '<th>상태</th><th>프로젝트</th><th>유형</th><th>시간</th><th>요일</th><th>다음 실행</th><th>제어</th>';
  html += '</tr></thead><tbody>';
  schedules.forEach(s => {{
    const enabled = s.enabled !== false;
    const statusCls = enabled ? 'sched-enabled' : 'sched-disabled';
    const statusTxt = enabled ? 'ON' : 'OFF';
    const stype = s.schedule_type === 'daily' ? '매일' : '매주';
    const dayStr = s.day_of_week !== null && s.day_of_week !== undefined ? (dayNames[s.day_of_week] || '-') : '-';
    const nextRun = formatNextRun(s.next_run);
    const toggleCls = enabled ? 'sched-toggle on' : 'sched-toggle';
    const toggleTxt = enabled ? '비활성' : '활성';
    html += '<tr>';
    html += '<td class="'+statusCls+'">'+statusTxt+'</td>';
    html += '<td>'+escapeHtml(s.project_name)+'</td>';
    html += '<td>'+stype+'</td>';
    html += '<td>'+(s.time||'')+'</td>';
    html += '<td>'+dayStr+'</td>';
    html += '<td>'+nextRun+'</td>';
    html += '<td>';
    html += '<button class="'+toggleCls+'" onclick="toggleSched(\''+s.id+'\')">'+toggleTxt+'</button> ';
    html += '<button class="sched-delete" onclick="deleteSched(\''+s.id+'\')">삭제</button>';
    html += '</td>';
    html += '</tr>';
  }});
  html += '</tbody></table>';
  container.innerHTML = html;
}}

async function loadSchedules() {{
  try {{
    const res = await fetch('/api/schedules');
    const data = await res.json();
    renderSchedules(data);
  }} catch(e) {{
    document.getElementById('scheduleTable').innerHTML = '<div class="sched-empty" style="color:#f44336">스케줄 로딩 실패</div>';
  }}
}}

async function addSchedule() {{
  const msg = document.getElementById('schedMsg');
  const project = document.getElementById('schedProject').value;
  const stype = document.getElementById('schedType').value;
  const time = document.getElementById('schedTime').value;
  const day = document.getElementById('schedDay').value;

  if (!time) {{ msg.textContent = '시간을 입력하세요'; msg.className = 'sched-msg err'; return; }}

  const body = {{ project_name: project, schedule_type: stype, time: time }};
  if (stype === 'weekly') body.day_of_week = day;

  msg.textContent = '추가 중...';
  msg.className = 'sched-msg';
  try {{
    const res = await fetch('/api/schedules', {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify(body)
    }});
    const data = await res.json();
    msg.textContent = data.msg;
    msg.className = 'sched-msg ' + (data.ok ? 'ok' : 'err');
    if (data.ok) loadSchedules();
  }} catch(e) {{
    msg.textContent = '추가 실패: ' + e;
    msg.className = 'sched-msg err';
  }}
}}

async function toggleSched(id) {{
  try {{
    const res = await fetch('/api/schedules/' + id + '/toggle', {{method: 'PUT'}});
    const data = await res.json();
    if (data.ok) loadSchedules();
  }} catch(e) {{ console.error('toggle error:', e); }}
}}

async function deleteSched(id) {{
  if (!confirm('이 스케줄을 삭제하시겠습니까?')) return;
  try {{
    const res = await fetch('/api/schedules/' + id, {{method: 'DELETE'}});
    const data = await res.json();
    if (data.ok) loadSchedules();
  }} catch(e) {{ console.error('delete error:', e); }}
}}

// 페이지 로드 시 스케줄 목록 로딩
loadSchedules();

/* === 자동 복구 === */
async function healProject(name) {{
  const msg = document.getElementById('healProjectMsg');
  msg.textContent = name + ' 복구 중...';
  msg.className = 'heal-msg';
  try {{
    const res = await fetch('/api/healing/trigger/' + name, {{method: 'POST'}});
    const data = await res.json();
    msg.textContent = name + ': ' + (data.msg || '');
    msg.className = 'heal-msg ' + (data.ok ? 'ok' : 'err');
    setTimeout(() => location.reload(), 3000);
  }} catch(e) {{
    msg.textContent = '복구 실패: ' + e;
    msg.className = 'heal-msg err';
  }}
}}

async function healAll() {{
  const msg = document.getElementById('healAllMsg');
  msg.textContent = '전체 복구 중...';
  msg.className = 'heal-msg';
  const names = {list(PROJECTS.keys())};
  const results = [];
  for (const name of names) {{
    try {{
      const res = await fetch('/api/healing/trigger/' + name, {{method: 'POST'}});
      const data = await res.json();
      results.push((data.ok ? '\\u2705' : '\\u274c') + ' ' + name);
    }} catch(e) {{
      results.push('\\u274c ' + name + ': ' + e);
    }}
  }}
  msg.textContent = results.join(' | ');
  msg.className = 'heal-msg';
  setTimeout(() => location.reload(), 3000);
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
