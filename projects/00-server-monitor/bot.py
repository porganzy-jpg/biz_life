"""
텔레그램 서버 관리 봇
핸드폰에서 프로젝트 상태 확인, 시작/중지/재시작 명령
"""
import asyncio
import logging
import os
import sys
import time

import psutil
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config import PROJECTS
from services import (
    find_pid_by_port,
    check_port_sync,
    start_project as _start_project,
    stop_project as _stop_project,
    get_recent_logs,
    get_event_history,
    get_uptime_stats,
    search_events,
)
from deploy import bot_deploy_trigger, bot_deploy_status
from anomaly import get_alert_manager, MaintenanceWindow
from scheduler import bot_schedule_list, bot_schedule_add, bot_schedule_remove, bot_schedule_toggle
from auto_healer import bot_heal, bot_health

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def is_authorized(update: Update) -> bool:
    if not ALLOWED_CHAT_ID:
        return True  # 제한 없음
    return str(update.effective_chat.id) == ALLOWED_CHAT_ID


def start_project(name: str) -> str:
    """services.start_project 래퍼 — 봇용 문자열 반환"""
    return _start_project(name)["msg"]


def stop_project(name: str) -> str:
    """services.stop_project 래퍼 — 봇용 문자열 반환"""
    return _stop_project(name)["msg"]


# === 텔레그램 핸들러 ===

async def cmd_start_bot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "🖥️ 서버 관리 봇\n\n"
        "/status - 전체 프로젝트 상태\n"
        "/system - 시스템 리소스 (CPU/RAM/Disk)\n"
        "/report - 서버 일일 리포트\n"
        "/history [프로젝트] [타입] [기간] - 이벤트 검색 (타입: start/stop/restart/error/deploy 등)\n"
        "/uptime - 가동률 통계\n"
        "/panel - 인라인 제어 패널\n\n"
        "프로젝트 제어:\n"
        "/begin <이름> - 시작\n"
        "/stop <이름> - 중지\n"
        "/restart <이름> - 재시작\n"
        "/logs <이름> - 최근 로그\n"
        "/startall - 전체 시작\n"
        "/stopall - 전체 중지\n\n"
        "배포:\n"
        "/deploy - 수동 배포 (git pull + 전체 재시작)\n"
        "/deploy <이름> - 특정 프로젝트만 배포\n"
        "/deploystatus - 마지막 배포 상태\n\n"
        "예약 재시작:\n"
        "/schedule - 예약 재시작 목록\n"
        "/schedule add <프로젝트> <daily|weekly> <HH:MM> [요일]\n"
        "/schedule remove <id> - 예약 삭제\n"
        "/schedule toggle <id> - 활성/비활성\n\n"
        "자동 복구:\n"
        "/heal [프로젝트명|all] - 수동 복구 트리거\n"
        "/health [프로젝트명] - 건강 점수 조회\n\n"
        "알림 & 이상 탐지:\n"
        "/alerts - 최근 알림 조회\n"
        "/maintenance start 2h - 유지보수 윈도우 시작\n"
        "/maintenance stop - 유지보수 윈도우 종료\n"
        "/thresholds - 알림 임계치 조회"
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    lines = ["📊 프로젝트 상태\n"]
    for name, proj in PROJECTS.items():
        alive = check_port_sync(proj["port"])
        icon = "🟢" if alive else "🔴"
        lines.append(f"{icon} {name} (:{proj['port']})")
    await update.message.reply_text("\n".join(lines))


async def cmd_system(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    cpu = psutil.cpu_percent(interval=1)
    text = (
        f"💻 시스템 리소스\n\n"
        f"CPU: {cpu}% ({psutil.cpu_count()} cores)\n"
        f"RAM: {mem.used // (1024**3)}/{mem.total // (1024**3)} GB ({mem.percent}%)\n"
        f"Disk: {disk.used // (1024**3)}/{disk.total // (1024**3)} GB ({round(disk.percent, 1)}%)"
    )
    await update.message.reply_text(text)


async def cmd_project_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    if not ctx.args:
        await update.message.reply_text("사용법: /start <프로젝트명>\n예: /start 01-promo-map")
        return
    name = ctx.args[0]
    result = start_project(name)
    await update.message.reply_text(f"▶️ {name}: {result}")


async def cmd_project_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    if not ctx.args:
        await update.message.reply_text("사용법: /stop <프로젝트명>\n예: /stop 01-promo-map")
        return
    name = ctx.args[0]
    result = stop_project(name)
    await update.message.reply_text(f"⏹️ {name}: {result}")


async def cmd_project_restart(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    if not ctx.args:
        await update.message.reply_text("사용법: /restart <프로젝트명>\n예: /restart 04-crypto-trader")
        return
    name = ctx.args[0]
    stop_msg = stop_project(name)
    proj = PROJECTS.get(name)
    if proj:
        for _ in range(20):
            await asyncio.sleep(0.5)
            if not find_pid_by_port(proj["port"]):
                break
    start_msg = start_project(name)
    await update.message.reply_text(f"🔄 {name}\n중지: {stop_msg}\n시작: {start_msg}")


async def cmd_logs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    if not ctx.args:
        await update.message.reply_text("사용법: /logs <프로젝트명>")
        return
    name = ctx.args[0]
    if name not in PROJECTS:
        await update.message.reply_text(f"알 수 없는 프로젝트: {name}")
        return
    logs = get_recent_logs(name)
    await update.message.reply_text(f"📋 {name} 로그:\n\n{logs[:3500]}")


async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """일일 서버 리포트"""
    if not is_authorized(update):
        return
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    cpu = psutil.cpu_percent(interval=1)

    alive_count = 0
    dead_list = []
    for name, proj in PROJECTS.items():
        if check_port_sync(proj["port"]):
            alive_count += 1
        else:
            dead_list.append(name)

    total = len(PROJECTS)
    uptime_sec = time.time() - psutil.boot_time()
    days = int(uptime_sec // 86400)
    hours = int((uptime_sec % 86400) // 3600)

    text = (
        f"📊 서버 일일 리포트\n\n"
        f"프로젝트: {alive_count}/{total} 실행 중\n"
    )
    if dead_list:
        text += f"중지됨: {', '.join(dead_list)}\n"
    text += (
        f"\nCPU: {cpu}% ({psutil.cpu_count()} cores)\n"
        f"RAM: {mem.used // (1024**3)}/{mem.total // (1024**3)} GB ({mem.percent}%)\n"
        f"Disk: {disk.used // (1024**3)}/{disk.total // (1024**3)} GB ({round(disk.percent, 1)}%)\n"
        f"Uptime: {days}일 {hours}시간"
    )
    await update.message.reply_text(text)


async def cmd_events(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """최근 이벤트 히스토리 (필터 지원)
    사용법: /history [프로젝트명] [이벤트타입] [기간]
    예: /history
        /history 04-crypto-trader
        /history 04-crypto-trader error
        /history 04-crypto-trader error 7d
        /history error 24h
        /history all restart 30d
    기간 형식: 1h, 24h, 7d, 30d 등
    """
    if not is_authorized(update):
        return

    # 인자 파싱: [project] [event_type] [duration]
    args = ctx.args or []
    project_filter = None
    type_filter = None
    days_filter = None
    hours_filter = None

    valid_types = {"start", "stop", "restart", "auto_restart", "scheduled_restart", "error", "resource_alert", "deploy"}

    for arg in args:
        arg_lower = arg.lower()
        # 기간 파싱 (예: 7d, 24h, 1h, 30d)
        if arg_lower.endswith("d") and arg_lower[:-1].isdigit():
            days_filter = int(arg_lower[:-1])
        elif arg_lower.endswith("h") and arg_lower[:-1].isdigit():
            hours_filter = int(arg_lower[:-1])
        # 이벤트 타입
        elif arg_lower in valid_types:
            type_filter = [arg_lower]
        # 프로젝트명 ('all'이면 전체)
        elif arg_lower != "all":
            project_filter = arg

    events = search_events(
        project_name=project_filter,
        event_types=type_filter,
        days=days_filter,
        hours=hours_filter,
        limit=15,
    )

    if not events:
        await update.message.reply_text("📋 조건에 맞는 이벤트가 없습니다.")
        return

    event_icons = {
        "start": "▶️",
        "stop": "⏹️",
        "restart": "🔄",
        "auto_restart": "🤖",
        "scheduled_restart": "⏰",
        "resource_alert": "⚠️",
        "error": "❌",
        "deploy": "🚀",
    }

    # 필터 요약 생성
    summary_parts = [f"{len(events)}개"]
    if project_filter:
        summary_parts.append(f"프로젝트: {project_filter}")
    if type_filter:
        summary_parts.append(f"타입: {', '.join(type_filter)}")
    if days_filter:
        summary_parts.append(f"기간: {days_filter}일")
    elif hours_filter:
        summary_parts.append(f"기간: {hours_filter}시간")
    summary = " | ".join(summary_parts)

    lines = [f"📋 이벤트 ({summary})\n"]
    for ev in events:
        icon = event_icons.get(ev.get("type", ""), "📋")
        ts = ev.get("timestamp", "")[:19].replace("T", " ")
        project = ev.get("project", "")
        details = ev.get("details", ev.get("type", ""))
        lines.append(f"{icon} [{ts}] {project}: {details}")

    await update.message.reply_text("\n".join(lines))


async def cmd_uptime(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """프로젝트별 가동률 통계"""
    if not is_authorized(update):
        return

    stats = get_uptime_stats()
    if not stats:
        await update.message.reply_text("📊 가동률 데이터가 없습니다.")
        return

    lines = ["📊 가동률 통계 (24시간 기준)\n"]
    for name, s in stats.items():
        pct = s.get("uptime_percent", 0.0)
        starts = s.get("total_starts", 0)
        errors = s.get("total_errors", 0)
        if pct >= 99:
            icon = "🟢"
        elif pct >= 90:
            icon = "🟡"
        else:
            icon = "🔴"
        lines.append(f"{icon} {name}: {pct}% (시작 {starts}회, 오류 {errors}회)")

    await update.message.reply_text("\n".join(lines))


async def cmd_startall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """전체 프로젝트 시작"""
    if not is_authorized(update):
        return
    results = []
    for name, proj in PROJECTS.items():
        if not find_pid_by_port(proj["port"]):
            result = start_project(name)
            results.append(f"▶️ {name}: {result}")
        else:
            results.append(f"✅ {name}: 이미 실행 중")
    await update.message.reply_text("\n".join(results))


async def cmd_stopall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """전체 프로젝트 중지"""
    if not is_authorized(update):
        return
    results = []
    for name in PROJECTS:
        result = stop_project(name)
        results.append(f"⏹️ {name}: {result}")
    await update.message.reply_text("\n".join(results))


async def cmd_deploy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """수동 배포 트리거: /deploy [프로젝트명|all]"""
    if not is_authorized(update):
        return
    project = ctx.args[0] if ctx.args else "all"
    await update.message.reply_text(f"🚀 배포 시작 중... (대상: {project})")
    try:
        result = bot_deploy_trigger(project)
        await update.message.reply_text(f"🚀 배포 결과\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"❌ 배포 실패: {e}")


async def cmd_deploy_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """마지막 배포 상태 조회: /deploystatus"""
    if not is_authorized(update):
        return
    try:
        result = bot_deploy_status()
        await update.message.reply_text(f"📦 배포 상태\n\n{result}")
    except Exception as e:
        await update.message.reply_text(f"❌ 배포 상태 조회 실패: {e}")


async def cmd_alerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """최근 알림 조회: /alerts"""
    if not is_authorized(update):
        return
    alert_mgr = get_alert_manager()
    alerts = alert_mgr.get_recent_alerts(10)
    if not alerts:
        await update.message.reply_text("🔔 최근 알림이 없습니다.")
        return

    level_icons = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️"}
    lines = ["🔔 최근 알림 (10개)\n"]
    for al in alerts:
        icon = level_icons.get(al.get("level", "INFO"), "📢")
        ts = al.get("timestamp", "")[:19].replace("T", " ")
        msg = al.get("message", "")
        lines.append(f"{icon} [{ts}] {msg}")

    stats = alert_mgr.get_alert_stats()
    unresolved = stats.get("unresolved_critical", 0)
    if unresolved > 0:
        lines.append(f"\n🚨 미해결 CRITICAL: {unresolved}건")

    await update.message.reply_text("\n".join(lines))


async def cmd_maintenance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """유지보수 윈도우 제어: /maintenance start 2h | /maintenance stop"""
    if not is_authorized(update):
        return
    args = ctx.args or []
    mw = MaintenanceWindow()

    if not args:
        status = mw.get_status()
        if status.get("active"):
            end = status.get("end", "")[:19].replace("T", " ")
            await update.message.reply_text(f"🔧 유지보수 윈도우: 활성\n종료 예정: {end}")
        else:
            await update.message.reply_text(
                "🔧 유지보수 윈도우: 비활성\n\n"
                "사용법:\n/maintenance start 2h\n/maintenance stop"
            )
        return

    action = args[0].lower()
    if action == "start":
        hours = 2.0
        if len(args) > 1:
            duration = args[1].lower()
            if duration.endswith("h") and duration[:-1].replace(".", "").isdigit():
                hours = float(duration[:-1])
            elif duration.replace(".", "").isdigit():
                hours = float(duration)
        mw.start(hours=hours)
        await update.message.reply_text(f"🔧 유지보수 윈도우 시작 ({hours}시간)\n알림이 억제됩니다.")
    elif action == "stop":
        mw.stop()
        await update.message.reply_text("🔧 유지보수 윈도우 종료\n알림이 다시 활성화됩니다.")
    else:
        await update.message.reply_text("사용법: /maintenance start 2h | /maintenance stop")


async def cmd_thresholds(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """현재 알림 임계치 조회: /thresholds"""
    if not is_authorized(update):
        return
    thresholds = get_alert_manager().get_thresholds()
    lines = [
        "📊 알림 임계치\n",
        f"CPU 임계치: {thresholds.get('cpu_threshold')}%",
        f"Memory 임계치: {thresholds.get('memory_threshold')}%",
        f"Disk 임계치: {thresholds.get('disk_threshold')}%",
        f"Disk 포화 예측: {thresholds.get('disk_predict_target')}%",
        f"CPU 표준편차 배수: {thresholds.get('cpu_std_multiplier')}",
        f"CPU 연속 이상 최소: {thresholds.get('cpu_consecutive_min')}회",
        f"메모리 누수 판단: {thresholds.get('memory_leak_minutes')}분",
        f"디스크 증가율: {thresholds.get('disk_growth_rate_threshold')}%/h",
        f"재시작 폭풍: {thresholds.get('restart_storm_count')}회/{thresholds.get('restart_storm_window_minutes')}분",
        f"알림 쿨다운: {thresholds.get('alert_cooldown_minutes')}분",
        f"알림 활성: {'예' if thresholds.get('alert_enabled') else '아니오'}",
    ]
    await update.message.reply_text("\n".join(lines))


async def cmd_schedule(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """예약 재시작 관리: /schedule [add|remove|toggle] [args...]
    사용법:
      /schedule - 목록 조회
      /schedule add 04-crypto-trader daily 03:00
      /schedule add 01-promo-map weekly 04:00 mon
      /schedule remove <id>
      /schedule toggle <id>
    """
    if not is_authorized(update):
        return

    args = ctx.args or []
    if not args:
        # 목록 조회
        result = bot_schedule_list()
        await update.message.reply_text(f"⏰ {result}")
        return

    action = args[0].lower()
    sub_args = args[1:]

    if action == "add":
        result = bot_schedule_add(sub_args)
        await update.message.reply_text(f"⏰ {result}")
    elif action == "remove" or action == "delete" or action == "del":
        result = bot_schedule_remove(sub_args)
        await update.message.reply_text(f"⏰ {result}")
    elif action == "toggle":
        result = bot_schedule_toggle(sub_args)
        await update.message.reply_text(f"⏰ {result}")
    elif action == "list":
        result = bot_schedule_list()
        await update.message.reply_text(f"⏰ {result}")
    else:
        await update.message.reply_text(
            "⏰ 사용법:\n"
            "/schedule - 목록 조회\n"
            "/schedule add <프로젝트> <daily|weekly> <HH:MM> [요일]\n"
            "/schedule remove <id>\n"
            "/schedule toggle <id>"
        )


async def cmd_heal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """수동 복구 트리거: /heal [프로젝트명|all]"""
    if not is_authorized(update):
        return
    args = ctx.args or []
    await update.message.reply_text("🔧 복구 실행 중...")
    try:
        result = bot_heal(args)
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"❌ 복구 실패: {e}")


async def cmd_health(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """건강 점수 조회: /health [프로젝트명]"""
    if not is_authorized(update):
        return
    args = ctx.args or []
    try:
        result = bot_health(args)
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"❌ 건강 점수 조회 실패: {e}")


async def cmd_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    keyboard = []
    for name, proj in PROJECTS.items():
        alive = check_port_sync(proj["port"])
        icon = "🟢" if alive else "🔴"
        short = name.split("-", 1)[1] if "-" in name else name
        keyboard.append([
            InlineKeyboardButton(f"{icon} {short}", callback_data=f"noop_{name}"),
            InlineKeyboardButton("▶️", callback_data=f"start_{name}"),
            InlineKeyboardButton("⏹️", callback_data=f"stop_{name}"),
            InlineKeyboardButton("🔄", callback_data=f"restart_{name}"),
        ])
    keyboard.append([InlineKeyboardButton("🔄 새로고침", callback_data="refresh_panel")])
    await update.message.reply_text("🎛️ 제어 패널", reply_markup=InlineKeyboardMarkup(keyboard))


async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not ALLOWED_CHAT_ID or str(query.message.chat.id) == ALLOWED_CHAT_ID:
        data = query.data

        if data == "refresh_panel":
            keyboard = []
            for name, proj in PROJECTS.items():
                alive = check_port_sync(proj["port"])
                icon = "🟢" if alive else "🔴"
                short = name.split("-", 1)[1] if "-" in name else name
                keyboard.append([
                    InlineKeyboardButton(f"{icon} {short}", callback_data=f"noop_{name}"),
                    InlineKeyboardButton("▶️", callback_data=f"start_{name}"),
                    InlineKeyboardButton("⏹️", callback_data=f"stop_{name}"),
                    InlineKeyboardButton("🔄", callback_data=f"restart_{name}"),
                ])
            keyboard.append([InlineKeyboardButton("🔄 새로고침", callback_data="refresh_panel")])
            await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
            await query.answer("새로고침 완료")
            return

        if data.startswith("noop_"):
            await query.answer()
            return

        action, name = data.split("_", 1)
        if action == "start":
            result = start_project(name)
            await query.answer(f"▶️ {result}", show_alert=True)
        elif action == "stop":
            result = stop_project(name)
            await query.answer(f"⏹️ {result}", show_alert=True)
        elif action == "restart":
            stop_msg = stop_project(name)
            await asyncio.sleep(2)
            start_msg = start_project(name)
            await query.answer(f"🔄 {stop_msg} → {start_msg}", show_alert=True)

        # 패널 자동 새로고침
        keyboard = []
        for n, p in PROJECTS.items():
            alive = check_port_sync(p["port"])
            icon = "🟢" if alive else "🔴"
            short = n.split("-", 1)[1] if "-" in n else n
            keyboard.append([
                InlineKeyboardButton(f"{icon} {short}", callback_data=f"noop_{n}"),
                InlineKeyboardButton("▶️", callback_data=f"start_{n}"),
                InlineKeyboardButton("⏹️", callback_data=f"stop_{n}"),
                InlineKeyboardButton("🔄", callback_data=f"restart_{n}"),
            ])
        keyboard.append([InlineKeyboardButton("🔄 새로고침", callback_data="refresh_panel")])
        try:
            await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
        except Exception:
            pass
    else:
        await query.answer("권한 없음")


def main():
    if not BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
        print(".env 파일에 TELEGRAM_BOT_TOKEN=your_token_here 를 추가하세요.")
        sys.exit(1)

    print(f"텔레그램 봇 시작 중...")
    if ALLOWED_CHAT_ID:
        print(f"허용된 Chat ID: {ALLOWED_CHAT_ID}")
    else:
        print("경고: TELEGRAM_CHAT_ID 미설정 - 모든 사용자가 접근 가능")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start_bot))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("system", cmd_system))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("begin", cmd_project_start))  # /start은 봇 시작에 예약됨
    app.add_handler(CommandHandler("stop", cmd_project_stop))
    app.add_handler(CommandHandler("restart", cmd_project_restart))
    app.add_handler(CommandHandler("logs", cmd_logs))
    app.add_handler(CommandHandler("startall", cmd_startall))
    app.add_handler(CommandHandler("stopall", cmd_stopall))
    app.add_handler(CommandHandler("history", cmd_events))
    app.add_handler(CommandHandler("events", cmd_events))
    app.add_handler(CommandHandler("uptime", cmd_uptime))
    app.add_handler(CommandHandler("deploy", cmd_deploy))
    app.add_handler(CommandHandler("deploystatus", cmd_deploy_status))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("maintenance", cmd_maintenance))
    app.add_handler(CommandHandler("thresholds", cmd_thresholds))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("heal", cmd_heal))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("panel", cmd_panel))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
