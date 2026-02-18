"""
텔레그램 서버 관리 봇
핸드폰에서 프로젝트 상태 확인, 시작/중지/재시작 명령
"""
import asyncio
import logging
import os
import subprocess
import sys
import time

import psutil
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config import PROJECTS, PROJECTS_DIR

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def is_authorized(update: Update) -> bool:
    if not ALLOWED_CHAT_ID:
        return True  # 제한 없음
    return str(update.effective_chat.id) == ALLOWED_CHAT_ID


def find_pid_by_port(port: int):
    for conn in psutil.net_connections(kind="tcp"):
        if conn.laddr.port == port and conn.status == "LISTEN":
            return conn.pid
    return None


def check_port_sync(port: int) -> bool:
    return find_pid_by_port(port) is not None


def start_project(name: str) -> str:
    if name not in PROJECTS:
        return f"알 수 없는 프로젝트: {name}"
    proj = PROJECTS[name]
    if find_pid_by_port(proj["port"]):
        return f"이미 실행 중 (포트 {proj['port']})"

    project_dir = PROJECTS_DIR / name
    work_dir = project_dir / proj["cwd"]
    cmd = list(proj["cmd"])
    cmd[0] = str(project_dir / cmd[0])

    log_dir = project_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    with open(log_dir / "server.log", "a", encoding="utf-8") as lf:
        subprocess.Popen(
            cmd, cwd=str(work_dir), stdout=lf, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    for _ in range(6):
        time.sleep(0.5)
        if find_pid_by_port(proj["port"]):
            return f"시작 확인됨 (포트 {proj['port']})"
    return f"시작 실패 — 포트 {proj['port']} 응답 없음"


def stop_project(name: str) -> str:
    if name not in PROJECTS:
        return f"알 수 없는 프로젝트: {name}"
    proj = PROJECTS[name]
    pid = find_pid_by_port(proj["port"])
    if not pid:
        return "실행 중이 아님"
    try:
        proc = psutil.Process(pid)
        for child in proc.children(recursive=True):
            child.terminate()
        proc.terminate()
        proc.wait(timeout=5)
        return f"중지됨 (PID {pid})"
    except Exception as e:
        return f"중지 실패: {e}"


def get_recent_logs(name: str, lines: int = 10) -> str:
    log_dir = PROJECTS_DIR / name / "logs"
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


# === 텔레그램 핸들러 ===

async def cmd_start_bot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "🖥️ 서버 관리 봇\n\n"
        "/status - 전체 프로젝트 상태\n"
        "/system - 시스템 리소스 (CPU/RAM/Disk)\n"
        "/report - 서버 일일 리포트\n"
        "/panel - 인라인 제어 패널\n\n"
        "프로젝트 제어:\n"
        "/begin <이름> - 시작\n"
        "/stop <이름> - 중지\n"
        "/restart <이름> - 재시작\n"
        "/logs <이름> - 최근 로그\n"
        "/startall - 전체 시작\n"
        "/stopall - 전체 중지"
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
    app.add_handler(CommandHandler("panel", cmd_panel))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
