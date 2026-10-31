"""
내 인생 아카이브 — 개인용 0단계
  python app.py  →  http://localhost:8016
"""
import csv
import io
import json
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv(Path(__file__).parent / ".env")

import db  # noqa: E402
from sources import search_all  # noqa: E402

ROOT = Path(__file__).parent
app = FastAPI(title="Life Archive")

# DNS 재바인딩 막기: 남의 도메인 이름으로 들어온 요청은 받지 않는다.
# 폰 등에서 IP로 접속하려면 .env에 ALLOWED_HOSTS=192.168.0.10 처럼 쉼표로 추가.
ALLOWED_HOSTS = ["localhost", "127.0.0.1",
                 *filter(None, os.getenv("ALLOWED_HOSTS", "").split(","))]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

MAX_UPLOAD = 20 * 1024 * 1024


@app.middleware("http")
async def same_origin_writes(request: Request, call_next):
    """CSRF 막기: 바꾸는 요청은 이 앱 화면에서 온 것만 받는다.
    브라우저는 다른 사이트가 보낸 POST에 Origin을 붙이므로, 그 호스트가 우리와 다르면 거절."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "다른 사이트에서 온 요청은 받지 않습니다"}, status_code=403)
    return await call_next(request)


@app.get("/api/search")
async def search(q: str):
    q = q.strip()
    if not q:
        return {"results": [], "errors": {}}
    results, errors = await search_all(q)
    return {"results": results, "errors": errors}


@app.get("/api/cards")
def cards():
    return db.list_cards()


PHOTO_NAME = re.compile(r"^\d+-[0-9a-f]{8}\.(jpg|jpeg|png|webp|gif|heic)$")


def remove_photo(name):
    """업로드 핸들러가 지은 이름만 지운다 — 경로를 섞은 이름은 무시."""
    if name and PHOTO_NAME.match(name):
        (db.DATA / "photos" / name).unlink(missing_ok=True)


@app.post("/api/cards")
def create(card: dict):
    card.pop("photo", None)  # 사진 이름은 업로드 핸들러만 정한다
    if not (card.get("title") or "").strip():
        raise HTTPException(400, "제목이 필요합니다")
    return db.create_card(card)


@app.put("/api/cards/{cid}")
def update(cid: int, card: dict):
    card.pop("photo", None)
    if not db.get_card(cid):
        raise HTTPException(404)
    return db.update_card(cid, card)


@app.delete("/api/cards/{cid}")
def delete(cid: int):
    c = db.get_card(cid)
    if c:
        remove_photo(c.get("photo"))
    db.delete_card(cid)
    return {"ok": True}


@app.post("/api/cards/{cid}/photo")
async def photo(cid: int, file: UploadFile):
    c = db.get_card(cid)
    if not c:
        raise HTTPException(404)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"):
        raise HTTPException(400, "이미지 파일만 올릴 수 있습니다")
    body = await file.read(MAX_UPLOAD + 1)
    if len(body) > MAX_UPLOAD:
        raise HTTPException(413, "사진은 20MB까지 올릴 수 있습니다")
    name = f"{cid}-{uuid.uuid4().hex[:8]}{ext}"
    (db.DATA / "photos" / name).write_bytes(body)
    remove_photo(c.get("photo"))
    return db.update_card(cid, {"photo": name})


@app.get("/api/settings")
def settings():
    return db.get_settings()


@app.put("/api/settings")
def put_settings(data: dict):
    return db.set_settings(data)


@app.get("/api/export.json")
def export_json():
    body = {"settings": db.get_settings(), "cards": db.list_cards()}
    return JSONResponse(body, headers={"Content-Disposition": "attachment; filename=life-archive.json"})


@app.get("/api/export.csv")
def export_csv():
    def cell(v):
        # 외부 DB 제목이 =·+·-·@로 시작하면 엑셀이 수식으로 실행하므로 ' 를 앞에 붙인다
        return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v

    rows = [{k: cell(v) for k, v in {**c, "links": json.dumps(c["links"], ensure_ascii=False)}.items()}
            for c in db.list_cards()]
    buf = io.StringIO()
    buf.write("﻿")  # 엑셀에서 한글이 깨지지 않게
    w = csv.DictWriter(buf, fieldnames=["id", *db.CARD_FIELDS, "created_at", "updated_at"],
                       extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=life-archive.csv"})


db.connect().close()  # 첫 실행 때 data/·photos/·테이블을 만든다
app.mount("/photos", StaticFiles(directory=db.DATA / "photos"), name="photos")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


if __name__ == "__main__":
    # 인증이 없으니 기본은 이 PC에서만. 폰에서 쓰려면 .env에 HOST=0.0.0.0
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", 8016)))
