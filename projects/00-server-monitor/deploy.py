"""
GitHub Webhook 기반 자동 배포 모듈
- GitHub push webhook 수신 및 검증
- 변경된 프로젝트 자동 식별 및 재시작
- 수동 배포 트리거, 배포 이력 관리
- 텔레그램 배포 알림

FastAPI APIRouter 패턴으로 app.py에서 include_router로 통합
"""
import hashlib
import hmac
import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

from config import PROJECTS, PROJECTS_DIR, DEPLOY_CONFIG
from services import start_project, stop_project, restart_project, log_event

logger = logging.getLogger("deploy")

# === Deploy Log ===

DEPLOY_LOG_FILE = Path(__file__).parent / "deploy_log.json"
_deploy_lock = threading.Lock()


def _load_deploy_log() -> list:
    """배포 로그 파일에서 이력 로드"""
    if not DEPLOY_LOG_FILE.exists():
        return []
    try:
        with open(DEPLOY_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_deploy_log(entries: list):
    """배포 로그 저장 (최대 200개 유지)"""
    entries = entries[-200:]
    with open(DEPLOY_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def _append_deploy_log(entry: dict):
    """배포 로그에 항목 추가"""
    with _deploy_lock:
        logs = _load_deploy_log()
        logs.append(entry)
        _save_deploy_log(logs)


# === Telegram Notification ===

async def _send_telegram_notification(message: str):
    """배포 관련 텔레그램 알림 전송"""
    import httpx

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        logger.warning("텔레그램 토큰/채팅ID 미설정, 배포 알림 스킵")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"chat_id": chat_id, "text": message})
    except Exception as e:
        logger.error(f"텔레그램 배포 알림 전송 실패: {e}")


def _send_telegram_sync(message: str):
    """동기 텔레그램 알림 (봇 커맨드 등에서 사용)"""
    import httpx

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        with httpx.Client(timeout=10) as client:
            client.post(url, json={"chat_id": chat_id, "text": message})
    except Exception as e:
        logger.error(f"텔레그램 동기 알림 실패: {e}")


# === Deploy Manager ===

class DeployManager:
    """GitHub webhook 기반 배포 관리자"""

    def __init__(self, repo_dir: str = None, webhook_secret: str = None):
        self.repo_dir = Path(repo_dir) if repo_dir else Path(DEPLOY_CONFIG["DEPLOY_REPO_DIR"])
        self.webhook_secret = webhook_secret or DEPLOY_CONFIG["DEPLOY_WEBHOOK_SECRET"]

    def validate_signature(self, payload: bytes, signature: str) -> bool:
        """
        GitHub webhook HMAC-SHA256 서명 검증
        signature 형식: sha256=<hex_digest>
        """
        if not self.webhook_secret:
            logger.warning("DEPLOY_WEBHOOK_SECRET 미설정 -- 서명 검증 스킵")
            return True

        if not signature or not signature.startswith("sha256="):
            return False

        expected = "sha256=" + hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def parse_push_event(self, payload: dict) -> dict:
        """
        GitHub push 이벤트 파싱
        반환: {branch, commits, commit_messages, changed_files, pusher, repo_name}
        """
        ref = payload.get("ref", "")
        branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref

        commits = payload.get("commits", [])
        commit_messages = [c.get("message", "") for c in commits]

        # 변경된 파일 목록 수집 (added + modified + removed)
        changed_files = set()
        for commit in commits:
            changed_files.update(commit.get("added", []))
            changed_files.update(commit.get("modified", []))
            changed_files.update(commit.get("removed", []))

        pusher = payload.get("pusher", {}).get("name", "unknown")
        repo_name = payload.get("repository", {}).get("full_name", "unknown")

        return {
            "branch": branch,
            "commits": len(commits),
            "commit_messages": commit_messages,
            "changed_files": list(changed_files),
            "pusher": pusher,
            "repo_name": repo_name,
        }

    def identify_affected_projects(self, changed_files: list) -> list:
        """
        변경된 파일 경로를 분석하여 영향받는 프로젝트 이름 리스트 반환
        예: projects/01-promo-map/backend/main.py -> "01-promo-map"
            projects/00-server-monitor/config.py  -> "00-server-monitor"
        """
        affected = set()
        for filepath in changed_files:
            # 경로가 projects/<project-name>/... 형태인지 확인
            parts = filepath.replace("\\", "/").split("/")
            if len(parts) >= 2 and parts[0] == "projects":
                project_name = parts[1]
                # PROJECTS dict에 있거나, server-monitor 자체인 경우
                if project_name in PROJECTS or project_name == "00-server-monitor":
                    affected.add(project_name)
            # biz_life 루트 파일 변경 시 (docker-compose 등) -- 특정 프로젝트가 아니므로 스킵
        return sorted(affected)

    def git_pull(self) -> dict:
        """
        git pull 실행
        반환: {ok: bool, output: str}
        """
        try:
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                error_output = result.stderr.strip()
                logger.error(f"git pull 실패: {error_output}")
                return {"ok": False, "output": f"git pull 실패: {error_output}"}

            logger.info(f"git pull 성공: {output}")
            return {"ok": True, "output": output}

        except subprocess.TimeoutExpired:
            logger.error("git pull 타임아웃 (60초)")
            return {"ok": False, "output": "git pull 타임아웃 (60초)"}
        except FileNotFoundError:
            logger.error("git 명령어를 찾을 수 없습니다")
            return {"ok": False, "output": "git 명령어를 찾을 수 없습니다"}
        except Exception as e:
            logger.error(f"git pull 오류: {e}")
            return {"ok": False, "output": f"git pull 오류: {e}"}

    def execute_deploy(self, projects: list) -> dict:
        """
        배포 실행: git pull 후 영향받는 프로젝트 재시작
        반환: {ok: bool, git_result: str, restart_results: dict, timestamp: str}
        """
        timestamp = datetime.now().isoformat()
        deploy_entry = {
            "timestamp": timestamp,
            "projects": projects,
            "trigger": "auto",
            "git_result": "",
            "restart_results": {},
            "success": False,
        }

        # 1. git pull
        git_result = self.git_pull()
        deploy_entry["git_result"] = git_result["output"]

        if not git_result["ok"]:
            deploy_entry["success"] = False
            _append_deploy_log(deploy_entry)
            return {
                "ok": False,
                "git_result": git_result["output"],
                "restart_results": {},
                "timestamp": timestamp,
            }

        # 2. 프로젝트 재시작 (server-monitor 자체는 재시작하지 않음 -- 자기 자신을 죽이면 안 됨)
        restart_results = {}
        restartable = [p for p in projects if p != "00-server-monitor" and p in PROJECTS]

        if DEPLOY_CONFIG.get("DEPLOY_AUTO_RESTART", True):
            for project_name in restartable:
                try:
                    result = restart_project(project_name)
                    restart_results[project_name] = result
                    log_event(project_name, "restart", f"자동 배포 재시작: {result['msg']}")
                except Exception as e:
                    restart_results[project_name] = {"ok": False, "msg": str(e)}
                    log_event(project_name, "error", f"배포 재시작 실패: {e}")

        if "00-server-monitor" in projects:
            restart_results["00-server-monitor"] = {
                "ok": True,
                "msg": "서버 모니터는 자동 재시작 대상에서 제외 (수동 재시작 필요)",
            }

        all_ok = git_result["ok"] and all(r.get("ok", False) for r in restart_results.values())
        deploy_entry["restart_results"] = {k: v.get("msg", str(v)) for k, v in restart_results.items()}
        deploy_entry["success"] = all_ok
        _append_deploy_log(deploy_entry)

        return {
            "ok": all_ok,
            "git_result": git_result["output"],
            "restart_results": restart_results,
            "timestamp": timestamp,
        }

    def get_deploy_history(self, limit: int = 20) -> list:
        """최근 배포 이력 반환"""
        with _deploy_lock:
            logs = _load_deploy_log()
        return logs[-limit:][::-1]  # 최신순

    def get_last_deploy(self) -> Optional[dict]:
        """마지막 배포 정보 반환"""
        with _deploy_lock:
            logs = _load_deploy_log()
        return logs[-1] if logs else None


# === Singleton ===

_deploy_manager: Optional[DeployManager] = None


def get_deploy_manager() -> DeployManager:
    """DeployManager 싱글톤 반환"""
    global _deploy_manager
    if _deploy_manager is None:
        _deploy_manager = DeployManager()
    return _deploy_manager


# === FastAPI Router ===

deploy_router = APIRouter(prefix="/api/deploy", tags=["deploy"])


@deploy_router.post("/webhook")
async def webhook_handler(request: Request):
    """
    GitHub push webhook 수신 엔드포인트
    - HMAC-SHA256 서명 검증
    - main/master 브랜치 push만 처리
    - 변경된 프로젝트 자동 식별 및 재시작
    """
    if not DEPLOY_CONFIG.get("DEPLOY_ENABLED", True):
        return JSONResponse({"ok": False, "msg": "배포 기능 비활성화 상태"}, status_code=503)

    manager = get_deploy_manager()

    # 1. 서명 검증
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if manager.webhook_secret and not manager.validate_signature(body, signature):
        logger.warning("Webhook 서명 검증 실패")
        return JSONResponse({"ok": False, "msg": "서명 검증 실패"}, status_code=403)

    # 2. 페이로드 파싱
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "msg": "잘못된 JSON"}, status_code=400)

    # ping 이벤트 처리
    if request.headers.get("X-GitHub-Event") == "ping":
        return JSONResponse({"ok": True, "msg": "pong"})

    # push 이벤트만 처리
    if request.headers.get("X-GitHub-Event") != "push":
        return JSONResponse({"ok": True, "msg": f"이벤트 무시: {request.headers.get('X-GitHub-Event')}"})

    # 3. push 이벤트 파싱
    push_info = manager.parse_push_event(payload)

    # main/master 브랜치만 처리
    if push_info["branch"] not in ("main", "master"):
        return JSONResponse({
            "ok": True,
            "msg": f"브랜치 무시: {push_info['branch']} (main/master만 배포)",
        })

    # 4. 영향받는 프로젝트 식별
    affected = manager.identify_affected_projects(push_info["changed_files"])

    if not affected:
        # 변경된 프로젝트 없음 (루트 파일만 변경)
        git_result = manager.git_pull()
        entry = {
            "timestamp": datetime.now().isoformat(),
            "projects": [],
            "trigger": "webhook",
            "git_result": git_result["output"],
            "restart_results": {},
            "success": git_result["ok"],
            "push_info": {
                "branch": push_info["branch"],
                "commits": push_info["commits"],
                "pusher": push_info["pusher"],
            },
        }
        _append_deploy_log(entry)

        msg = (
            f"git pull 완료 (재시작 대상 없음)\n"
            f"Branch: {push_info['branch']}\n"
            f"Commits: {push_info['commits']}\n"
            f"Pusher: {push_info['pusher']}"
        )
        await _send_telegram_notification(msg)
        return JSONResponse({"ok": True, "msg": msg, "affected": []})

    # 5. 배포 실행
    deploy_result = manager.execute_deploy(affected)

    # 배포 로그 엔트리 업데이트 (push_info 추가)
    with _deploy_lock:
        logs = _load_deploy_log()
        if logs:
            logs[-1]["trigger"] = "webhook"
            logs[-1]["push_info"] = {
                "branch": push_info["branch"],
                "commits": push_info["commits"],
                "pusher": push_info["pusher"],
                "commit_messages": push_info["commit_messages"][:5],
            }
            _save_deploy_log(logs)

    # 6. 텔레그램 알림
    status_icon = "+" if deploy_result["ok"] else "X"
    restart_summary = ""
    for proj, result in deploy_result["restart_results"].items():
        r_icon = "+" if result.get("ok") else "X"
        r_msg = result.get("msg", str(result))
        restart_summary += f"  [{r_icon}] {proj}: {r_msg}\n"

    commit_summary = ""
    for msg in push_info["commit_messages"][:3]:
        first_line = msg.split("\n")[0][:80]
        commit_summary += f"  - {first_line}\n"

    telegram_msg = (
        f"[{status_icon}] 자동 배포 {'성공' if deploy_result['ok'] else '실패'}\n\n"
        f"Branch: {push_info['branch']}\n"
        f"Pusher: {push_info['pusher']}\n"
        f"Commits: {push_info['commits']}개\n"
        f"{commit_summary}\n"
        f"영향 프로젝트: {', '.join(affected)}\n"
        f"\n재시작 결과:\n{restart_summary}"
        f"\ngit: {deploy_result['git_result'][:200]}"
    )
    await _send_telegram_notification(telegram_msg)

    return JSONResponse({
        "ok": deploy_result["ok"],
        "msg": f"배포 {'성공' if deploy_result['ok'] else '실패'}",
        "affected": affected,
        "git_result": deploy_result["git_result"],
        "restart_results": {k: v.get("msg", str(v)) for k, v in deploy_result["restart_results"].items()},
        "timestamp": deploy_result["timestamp"],
    })


@deploy_router.post("/manual")
async def manual_deploy(project: str = Query(default="all", description="프로젝트명 또는 'all'")):
    """
    수동 배포 트리거
    - project=all: git pull 후 전체 프로젝트 재시작
    - project=<name>: git pull 후 해당 프로젝트만 재시작
    """
    if not DEPLOY_CONFIG.get("DEPLOY_ENABLED", True):
        return JSONResponse({"ok": False, "msg": "배포 기능 비활성화 상태"}, status_code=503)

    manager = get_deploy_manager()

    if project == "all":
        projects = list(PROJECTS.keys())
    elif project in PROJECTS:
        projects = [project]
    else:
        return JSONResponse({"ok": False, "msg": f"알 수 없는 프로젝트: {project}"}, status_code=400)

    deploy_result = manager.execute_deploy(projects)

    # 배포 로그에 trigger=manual 설정
    with _deploy_lock:
        logs = _load_deploy_log()
        if logs:
            logs[-1]["trigger"] = "manual"
            _save_deploy_log(logs)

    # 텔레그램 알림
    status_icon = "+" if deploy_result["ok"] else "X"
    restart_summary = ""
    for proj, result in deploy_result["restart_results"].items():
        r_msg = result.get("msg", str(result))
        restart_summary += f"  {proj}: {r_msg}\n"

    telegram_msg = (
        f"[{status_icon}] 수동 배포 {'성공' if deploy_result['ok'] else '실패'}\n\n"
        f"대상: {', '.join(projects)}\n"
        f"\n재시작 결과:\n{restart_summary}"
        f"\ngit: {deploy_result['git_result'][:200]}"
    )
    await _send_telegram_notification(telegram_msg)

    return JSONResponse({
        "ok": deploy_result["ok"],
        "msg": f"수동 배포 {'성공' if deploy_result['ok'] else '실패'}",
        "projects": projects,
        "git_result": deploy_result["git_result"],
        "restart_results": {k: v.get("msg", str(v)) for k, v in deploy_result["restart_results"].items()},
        "timestamp": deploy_result["timestamp"],
    })


@deploy_router.post("/pull")
async def git_pull_only():
    """git pull만 실행 (재시작 없음)"""
    if not DEPLOY_CONFIG.get("DEPLOY_ENABLED", True):
        return JSONResponse({"ok": False, "msg": "배포 기능 비활성화 상태"}, status_code=503)

    manager = get_deploy_manager()
    result = manager.git_pull()

    entry = {
        "timestamp": datetime.now().isoformat(),
        "projects": [],
        "trigger": "manual_pull",
        "git_result": result["output"],
        "restart_results": {},
        "success": result["ok"],
    }
    _append_deploy_log(entry)

    return JSONResponse({
        "ok": result["ok"],
        "msg": result["output"],
    })


@deploy_router.get("/status")
async def deploy_status():
    """마지막 배포 상태 조회"""
    manager = get_deploy_manager()
    last = manager.get_last_deploy()

    if not last:
        return JSONResponse({
            "ok": True,
            "last_deploy": None,
            "msg": "배포 이력 없음",
        })

    return JSONResponse({
        "ok": True,
        "last_deploy": last,
    })


@deploy_router.get("/history")
async def deploy_history(limit: int = Query(default=20, ge=1, le=100)):
    """배포 이력 조회"""
    manager = get_deploy_manager()
    history = manager.get_deploy_history(limit=limit)

    return JSONResponse({
        "ok": True,
        "count": len(history),
        "history": history,
    })


# === Bot Command Helpers (bot.py에서 사용) ===

def bot_deploy_trigger(project: str = "all") -> str:
    """
    봇에서 배포 트리거 (동기)
    반환: 결과 메시지 문자열
    """
    manager = get_deploy_manager()

    if project == "all":
        projects = list(PROJECTS.keys())
    elif project in PROJECTS:
        projects = [project]
    else:
        return f"알 수 없는 프로젝트: {project}"

    deploy_result = manager.execute_deploy(projects)

    with _deploy_lock:
        logs = _load_deploy_log()
        if logs:
            logs[-1]["trigger"] = "telegram_bot"
            _save_deploy_log(logs)

    lines = []
    status = "성공" if deploy_result["ok"] else "실패"
    lines.append(f"배포 {status}")
    lines.append(f"git: {deploy_result['git_result'][:200]}")
    lines.append("")

    for proj, result in deploy_result["restart_results"].items():
        icon = "+" if result.get("ok") else "X"
        lines.append(f"[{icon}] {proj}: {result.get('msg', '')}")

    return "\n".join(lines)


def bot_deploy_status() -> str:
    """
    봇에서 배포 상태 조회 (동기)
    반환: 상태 메시지 문자열
    """
    manager = get_deploy_manager()
    last = manager.get_last_deploy()

    if not last:
        return "배포 이력이 없습니다."

    ts = last.get("timestamp", "")[:19].replace("T", " ")
    success = last.get("success", False)
    trigger = last.get("trigger", "unknown")
    projects = last.get("projects", [])
    git_result = last.get("git_result", "")[:150]

    status_icon = "+" if success else "X"
    lines = [
        f"[{status_icon}] 마지막 배포",
        f"시간: {ts}",
        f"트리거: {trigger}",
        f"결과: {'성공' if success else '실패'}",
        f"프로젝트: {', '.join(projects) if projects else '없음'}",
        f"git: {git_result}",
    ]

    restart_results = last.get("restart_results", {})
    if restart_results:
        lines.append("\n재시작 결과:")
        for proj, msg in restart_results.items():
            lines.append(f"  {proj}: {msg}")

    return "\n".join(lines)
