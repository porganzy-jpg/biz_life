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

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv(Path(__file__).parent / ".env")

import db  # noqa: E402
from sources import search_all  # noqa: E402

ROOT = Path(__file__).parent
app = FastAPI(title="Life Archive")


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
    name = f"{cid}-{uuid.uuid4().hex[:8]}{ext}"
    (db.DATA / "photos" / name).write_bytes(await file.read())
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
    rows = [{**c, "links": json.dumps(c["links"], ensure_ascii=False)} for c in db.list_cards()]
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
