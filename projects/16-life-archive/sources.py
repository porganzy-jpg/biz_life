"""
검색 어댑터 — 소스마다 함수 하나, 모두 같은 모양의 dict 목록을 돌려준다.

  {source, source_id, kind, title, subtitle, year, image, url, links}

kind: movie tv anime manga book game music place event person thing
키가 없는 소스(TMDB·RAWG)는 조용히 건너뛴다.
"""
import asyncio
import os
import re

import httpx

UA = "LifeArchive/0.1 (personal use; shs.yeon local app)"

# ── Wikidata ────────────────────────────────────────────────
# P31(무엇의 일종인가) → kind. 못 맞추면 설명문 키워드로 한 번 더 본다.
WD_KIND = {
    "Q11424": "movie", "Q202866": "movie", "Q24869": "movie",
    "Q5398426": "tv", "Q581714": "tv", "Q15416": "tv",
    "Q63952888": "anime", "Q20650540": "anime", "Q1107": "anime",
    "Q21198342": "manga", "Q8274": "manga", "Q74262765": "manga",
    "Q7889": "game", "Q7058673": "game", "Q865493": "game",
    "Q7725634": "book", "Q571": "book", "Q8261": "book",
    "Q47461344": "book", "Q277759": "book", "Q1667921": "book",
    "Q482994": "music", "Q208569": "music", "Q134556": "music",
    "Q7366": "music", "Q105543609": "music", "Q215380": "music",
    "Q5741069": "music", "Q2088357": "music",
    "Q5": "person",
    "Q1190554": "event", "Q1656682": "event", "Q178561": "event",
    "Q3839081": "event", "Q8065": "event", "Q18608583": "event",
    "Q515": "place", "Q486972": "place", "Q41176": "place",
    "Q33506": "place", "Q22698": "place", "Q570116": "place",
    "Q8502": "place", "Q23397": "place", "Q3918": "place",
    "Q11422": "thing", "Q1194970": "thing",
}
DESC_KIND = [
    ("애니메이션", "anime"), ("웹툰", "manga"), ("만화", "manga"),
    ("드라마", "tv"), ("텔레비전", "tv"), ("영화", "movie"),
    ("게임", "game"), ("소설", "book"), ("책", "book"),
    ("앨범", "music"), ("노래", "music"), ("가수", "music"), ("밴드", "music"),
    ("사건", "event"), ("사고", "event"), ("대회", "event"), ("올림픽", "event"),
    ("anime", "anime"), ("manga", "manga"), ("film", "movie"),
    ("television series", "tv"), ("video game", "game"), ("novel", "book"),
    ("album", "music"), ("song", "music"),
]
# 다른 DB와 같은 작품을 묶는 외부 ID들 (나중에 카드 합치기에 쓴다)
WD_LINKS = {
    "P4947": "tmdb_movie", "P4983": "tmdb_tv", "P8729": "anilist_anime",
    "P8731": "anilist_manga", "P5794": "igdb", "P436": "musicbrainz_rg",
    "P345": "imdb",
}


def _claim_ids(claims, prop):
    out = []
    for c in claims.get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and "id" in v:
            out.append(v["id"])
        elif isinstance(v, str):
            out.append(v)
    return out


def _claim_year(claims):
    for prop in ("P577", "P580", "P571", "P585"):
        for c in claims.get(prop, []):
            t = c.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            m = re.match(r"[+-]?(\d{4})", t.get("time", "") if isinstance(t, dict) else "")
            if m:
                return int(m.group(1))
    return None


def _wd_kind(claims, desc):
    for q in _claim_ids(claims, "P31"):
        if q in WD_KIND:
            return WD_KIND[q]
    d = (desc or "").lower()
    for word, kind in DESC_KIND:
        if word in d:
            return kind
    return "thing"


async def wikidata(client, q):
    r = await client.get("https://www.wikidata.org/w/api.php", params={
        "action": "wbsearchentities", "search": q, "language": "ko",
        "uselang": "ko", "type": "item", "limit": 15, "format": "json",
    })
    hits = r.json().get("search", [])
    if not hits:
        return []
    ids = [h["id"] for h in hits]
    r = await client.get("https://www.wikidata.org/w/api.php", params={
        "action": "wbgetentities", "ids": "|".join(ids),
        "props": "claims|labels|descriptions", "languages": "ko|en", "format": "json",
    })
    ents = r.json().get("entities", {})
    out = []
    for qid in ids:
        e = ents.get(qid, {})
        claims = e.get("claims", {})
        labels, descs = e.get("labels", {}), e.get("descriptions", {})
        title = (labels.get("ko") or labels.get("en") or {}).get("value")
        if not title:
            continue
        desc = (descs.get("ko") or descs.get("en") or {}).get("value", "")
        # 포스터(P3383) > 대표 이미지(P18). 로고(P154)는 표지로 잘라 놓으면 글자만 남아 뺀다
        img = _claim_ids(claims, "P3383") or _claim_ids(claims, "P18")
        out.append({
            "source": "wikidata", "source_id": qid,
            "kind": _wd_kind(claims, desc), "title": title, "subtitle": desc,
            "year": _claim_year(claims),
            "image": ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                      + img[0].replace(" ", "_") + "?width=320") if img else None,
            "url": f"https://www.wikidata.org/wiki/{qid}",
            "links": {name: v[0] for p, name in WD_LINKS.items()
                      if (v := _claim_ids(claims, p))},
        })
    return out


# ── 카카오 (책·장소) ───────────────────────────────────────
def _kakao_headers():
    # home-finder와 같은 키(JS 플랫폼 키)라서 등록된 origin(localhost:8006)을 KA 헤더로 밝혀야 한다
    key = os.getenv("KAKAO_REST_API_KEY")
    origin = os.getenv("KAKAO_ORIGIN", "http://localhost:8006")
    return {"Authorization": f"KakaoAK {key}", "Origin": origin,
            "KA": f"sdk/1.0 os/javascript origin/{origin}"} if key else None


async def kakao_book(client, q):
    h = _kakao_headers()
    if not h:
        return []
    r = await client.get("https://dapi.kakao.com/v3/search/book",
                         params={"query": q, "size": 10}, headers=h)
    r.raise_for_status()
    out = []
    for d in r.json().get("documents", []):
        year = int(d["datetime"][:4]) if d.get("datetime") else None
        out.append({
            "source": "kakao_book", "source_id": d.get("isbn", "").split(" ")[-1],
            "kind": "book", "title": d["title"],
            "subtitle": " · ".join(filter(None, [", ".join(d.get("authors", [])),
                                                 d.get("publisher")])),
            "year": year, "image": d.get("thumbnail") or None,
            "url": d.get("url"), "links": {},
        })
    return out


async def kakao_place(client, q):
    h = _kakao_headers()
    if not h:
        return []
    r = await client.get("https://dapi.kakao.com/v2/local/search/keyword.json",
                         params={"query": q, "size": 8}, headers=h)
    r.raise_for_status()
    return [{
        "source": "kakao_place", "source_id": d["id"], "kind": "place",
        "title": d["place_name"], "subtitle": d.get("road_address_name") or d.get("address_name"),
        "year": None, "image": None, "url": d.get("place_url"),
        "links": {"lat": d.get("y"), "lng": d.get("x")},
    } for d in r.json().get("documents", [])]


# ── AniList (애니·만화) ────────────────────────────────────
ANILIST_Q = """
query ($q: String) { Page(perPage: 10) { media(search: $q, sort: SEARCH_MATCH) {
  id type format title { native english romaji } synonyms
  startDate { year } coverImage { large } siteUrl } } }"""


async def anilist(client, q):
    r = await client.post("https://graphql.anilist.co",
                          json={"query": ANILIST_Q, "variables": {"q": q}})
    out = []
    for m in r.json().get("data", {}).get("Page", {}).get("media", []):
        t = m["title"]
        korean = next((s for s in m.get("synonyms") or []
                       if re.search("[가-힣]", s)), None)
        title = korean or t.get("english") or t.get("romaji") or t.get("native")
        out.append({
            "source": "anilist", "source_id": str(m["id"]),
            "kind": "anime" if m["type"] == "ANIME" else "manga",
            "title": title,
            "subtitle": " · ".join(filter(None, [t.get("native"), m.get("format")])),
            "year": (m.get("startDate") or {}).get("year"),
            "image": (m.get("coverImage") or {}).get("large"),
            "url": m.get("siteUrl"), "links": {},
        })
    return out


# ── MusicBrainz (음반·노래) ────────────────────────────────
async def musicbrainz(client, q):
    r = await client.get("https://musicbrainz.org/ws/2/release-group/",
                         params={"query": q, "limit": 8, "fmt": "json"})
    out = []
    for g in r.json().get("release-groups", []):
        artist = " ".join(a.get("name", "") + a.get("joinphrase", "")
                          for a in g.get("artist-credit", []))
        date = g.get("first-release-date") or ""
        out.append({
            "source": "musicbrainz", "source_id": g["id"], "kind": "music",
            "title": g["title"],
            "subtitle": " · ".join(filter(None, [artist.strip(), g.get("primary-type")])),
            "year": int(date[:4]) if date[:4].isdigit() else None,
            "image": f"https://coverartarchive.org/release-group/{g['id']}/front-250",
            "url": f"https://musicbrainz.org/release-group/{g['id']}", "links": {},
        })
    return out


# ── 키가 있을 때만: TMDB, RAWG ────────────────────────────
async def tmdb(client, q):
    key = os.getenv("TMDB_API_KEY")
    if not key:
        return []
    r = await client.get("https://api.themoviedb.org/3/search/multi",
                         params={"api_key": key, "query": q, "language": "ko-KR"})
    out = []
    for m in r.json().get("results", []):
        if m.get("media_type") not in ("movie", "tv"):
            continue
        date = m.get("release_date") or m.get("first_air_date") or ""
        is_anime = 16 in m.get("genre_ids", []) and m.get("original_language") == "ja"
        out.append({
            "source": "tmdb", "source_id": f"{m['media_type']}/{m['id']}",
            "kind": "anime" if is_anime else m["media_type"],
            "title": m.get("title") or m.get("name"),
            "subtitle": m.get("original_title") or m.get("original_name"),
            "year": int(date[:4]) if date[:4].isdigit() else None,
            "image": f"https://image.tmdb.org/t/p/w342{m['poster_path']}" if m.get("poster_path") else None,
            "url": f"https://www.themoviedb.org/{m['media_type']}/{m['id']}", "links": {},
        })
    return out


async def rawg(client, q):
    key = os.getenv("RAWG_API_KEY")
    if not key:
        return []
    r = await client.get("https://api.rawg.io/api/games",
                         params={"key": key, "search": q, "page_size": 8})
    return [{
        "source": "rawg", "source_id": str(g["id"]), "kind": "game",
        "title": g["name"],
        "subtitle": ", ".join(p["platform"]["name"] for p in (g.get("platforms") or [])[:3]),
        "year": int(g["released"][:4]) if g.get("released") else None,
        "image": g.get("background_image"),
        "url": f"https://rawg.io/games/{g['slug']}", "links": {},
    } for g in r.json().get("results", [])]


SOURCES = {
    "wikidata": wikidata, "kakao_book": kakao_book, "kakao_place": kakao_place,
    "anilist": anilist, "musicbrainz": musicbrainz, "tmdb": tmdb, "rawg": rawg,
}


async def search_all(q):
    """모든 소스를 동시에 부르고, 실패한 소스는 errors에 이름만 남긴다."""
    async with httpx.AsyncClient(timeout=8, headers={"User-Agent": UA},
                                 follow_redirects=True) as client:
        names = list(SOURCES)
        res = await asyncio.gather(*(SOURCES[n](client, q) for n in names),
                                   return_exceptions=True)
    results, errors = [], {}
    for name, r in zip(names, res):
        if isinstance(r, Exception):
            errors[name] = f"{type(r).__name__}: {r}"[:200]
        else:
            results.extend(r)
    return results, errors
