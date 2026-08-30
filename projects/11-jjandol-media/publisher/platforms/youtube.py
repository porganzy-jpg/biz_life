"""유튜브 쇼츠 업로드 — YouTube Data API v3.

5개 채널 중 **유일하게 조건 없이 완전 자동화되는 곳**이다.
쿼터: 기본 10,000 units/day, 업로드 1건 = 1,600 units → 하루 6건까지.

최초 1회만 브라우저가 열려 계정 승인을 받고, 이후엔 token.json 으로 갱신된다.
"""
from __future__ import annotations

import os
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
HERE = Path(__file__).resolve().parent.parent
CLIENT_SECRET = HERE / "client_secret.json"
TOKEN = HERE / "token.json"


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET.exists():
                raise FileNotFoundError(
                    f"{CLIENT_SECRET} 가 없습니다.\n"
                    "Google Cloud Console → API 및 서비스 → 사용자 인증 정보에서\n"
                    "'데스크톱 앱' OAuth 클라이언트를 만들고 JSON을 이 경로에 저장하세요."
                )
            creds = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET), SCOPES).run_local_server(port=0)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def upload(video: Path, meta: dict, privacy: str = "private") -> str:
    """쇼츠 1건 업로드 후 video id 반환.

    privacy 기본값이 private 인 건 의도적이다. 자동 업로드가 바로 공개되면
    잘못 만든 편을 되돌릴 수 없다. 확인 후 수동 공개하거나 privacy='public' 으로 호출한다.
    """
    from googleapiclient.http import MediaFileUpload

    if not video.exists():
        raise FileNotFoundError(f"영상이 없습니다: {video}")

    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": meta["category_id"],
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video), chunksize=-1, resumable=True,
                            mimetype="video/mp4")
    req = _service().videos().insert(part="snippet,status", body=body, media_body=media)

    res = None
    while res is None:
        _, res = req.next_chunk()
    return res["id"]
