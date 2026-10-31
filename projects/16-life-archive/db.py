"""SQLite 저장소 — 카드 한 장 = 작품(외부 ID) + 그때의 나(기억)."""
import json
import sqlite3
from pathlib import Path

DATA = Path(__file__).parent / "data"
DB_PATH = DATA / "archive.db"

CARD_FIELDS = [
    # 작품 쪽 (검색 결과에서 채워짐)
    "kind", "title", "subtitle", "year", "image", "source", "source_id", "url", "links",
    # 나 쪽 (내가 적음)
    "met_year", "place", "people", "memory", "influence", "photo", "pinned",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL DEFAULT 'thing',
  title TEXT NOT NULL,
  subtitle TEXT, year INTEGER, image TEXT,
  source TEXT, source_id TEXT, url TEXT, links TEXT,
  met_year INTEGER, place TEXT, people TEXT, memory TEXT, influence TEXT,
  photo TEXT, pinned INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""


def connect():
    DATA.mkdir(exist_ok=True)
    (DATA / "photos").mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _row(r):
    d = dict(r)
    d["links"] = json.loads(d["links"]) if d.get("links") else {}
    d["pinned"] = bool(d["pinned"])
    return d


KINDS = {"movie", "tv", "anime", "manga", "book", "game", "music",
         "place", "event", "person", "thing", "memo"}


def _clean(data):
    out = {k: data[k] for k in CARD_FIELDS if k in data}
    if "kind" in out and out["kind"] not in KINDS:
        out["kind"] = "thing"
    if "links" in out and not isinstance(out["links"], str):
        out["links"] = json.dumps(out["links"] or {}, ensure_ascii=False)
    if "pinned" in out:
        out["pinned"] = 1 if out["pinned"] else 0
    for k in ("year", "met_year"):
        if k in out and out[k] in ("", None):
            out[k] = None
    return out


def list_cards():
    with connect() as con:
        return [_row(r) for r in con.execute("SELECT * FROM cards ORDER BY met_year IS NULL, met_year, id")]


def get_card(cid):
    with connect() as con:
        r = con.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
        return _row(r) if r else None


def create_card(data):
    d = _clean(data)
    cols = ", ".join(d)
    with connect() as con:
        cur = con.execute(f"INSERT INTO cards ({cols}) VALUES ({', '.join('?' * len(d))})",
                          list(d.values()))
    return get_card(cur.lastrowid)  # with 블록이 끝나야 커밋되므로 밖에서 읽는다


def update_card(cid, data):
    d = _clean(data)
    if d:
        sets = ", ".join(f"{k}=?" for k in d)
        with connect() as con:
            con.execute(f"UPDATE cards SET {sets}, updated_at=datetime('now','localtime') WHERE id=?",
                        [*d.values(), cid])
    return get_card(cid)


def delete_card(cid):
    with connect() as con:
        con.execute("DELETE FROM cards WHERE id=?", (cid,))


def get_settings():
    with connect() as con:
        return {r["key"]: r["value"] for r in con.execute("SELECT * FROM settings")}


def set_settings(data):
    with connect() as con:
        con.executemany("INSERT OR REPLACE INTO settings VALUES (?, ?)",
                        [(k, str(v)) for k, v in data.items()])
    return get_settings()
