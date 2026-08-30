"""인스타그램 릴스 업로드 — Instagram Graph API.

**제약 두 가지를 먼저 알아야 한다.**

1. 개인 계정으로는 불가능하다. 비즈니스/크리에이터 계정 + 페이스북 페이지 연결이 필요하다.
2. Graph API는 파일 바이트를 받지 않는다. **영상이 공개 URL에 올라가 있어야 한다.**
   즉 어딘가에 정적 호스팅이 있어야 자동화가 완성된다 (R2, S3, 아무 정적 호스트).
   호스팅이 없으면 이 채널은 수동 업로드로 두는 게 맞다 — 억지로 뚫을 값어치가 없다.

일일 게시 한도 25건.
"""
from __future__ import annotations

import os
import time

API = "https://graph.facebook.com/v21.0"


def _cfg() -> tuple[str, str]:
    uid = os.getenv("IG_USER_ID")
    token = os.getenv("IG_ACCESS_TOKEN")
    if not (uid and token):
        raise RuntimeError(
            "IG_USER_ID / IG_ACCESS_TOKEN 이 설정되지 않았습니다. .env 를 확인하세요."
        )
    return uid, token


def upload_reel(video_url: str, caption: str, timeout_sec: int = 300) -> str:
    """공개 URL의 영상을 릴스로 게시하고 media id 반환."""
    import requests

    uid, token = _cfg()

    r = requests.post(f"{API}/{uid}/media", data={
        "media_type": "REELS", "video_url": video_url,
        "caption": caption, "access_token": token,
    }, timeout=60)
    r.raise_for_status()
    container = r.json()["id"]

    # 인스타가 영상을 내려받아 처리할 때까지 기다린다. 바로 publish 하면 실패한다.
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        s = requests.get(f"{API}/{container}", params={
            "fields": "status_code", "access_token": token}, timeout=30).json()
        status = s.get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError(f"인스타 미디어 처리 실패: {s}")
        time.sleep(5)
    else:
        raise TimeoutError(f"{timeout_sec}초 안에 처리가 끝나지 않았습니다: {container}")

    p = requests.post(f"{API}/{uid}/media_publish", data={
        "creation_id": container, "access_token": token}, timeout=60)
    p.raise_for_status()
    return p.json()["id"]
