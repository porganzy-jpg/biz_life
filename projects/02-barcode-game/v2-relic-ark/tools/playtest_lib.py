"""플레이테스트 도우미 (2026-10-04, 7일 플레이 일지용). 프로젝트 파일을 고치지 않는다.

- api(): 서버 호출 + 4xx/5xx 기록
- Base: 헤드리스 Playwright 로 /base 를 페르소나별 영구 프로필(localStorage 유지)로 연다.
  토스트(관리실 방송)·패널·만남 카드 문장을 시간 순으로 모으고, 콘솔 오류·실패 응답을 기록한다.
- 화면 글자에서 날 id·{자리표시}를 찾는다.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import warnings
warnings.filterwarnings("ignore")
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8002"
SHOTS = ROOT / "docs" / "reports" / "shots"
SCRATCH = Path(r"C:\Users\user\AppData\Local\Temp\claude\c--Users-user-Desktop-biz-life\696d4b7b-943c-4c45-873f-85f382ee6064\scratchpad")
ERRLOG = SCRATCH / "playtest_errors.jsonl"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RAW_ID = re.compile(r"\{[a-z_]+\}|\b(?:cook|engineer|scout|medic|farmer|scholar|trader|kid|g)-\d+\b|\b(?:spot|oct|wish|box|exp)[_-][a-z0-9_-]+\b|undefined|NaN|null\b|\[object")


def note_err(kind: str, detail: dict):
    detail = dict(detail, kind=kind, t=time.strftime("%H:%M:%S"))
    with ERRLOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(detail, ensure_ascii=False) + "\n")


def api(method: str, path: str, body: dict | None = None, quiet=False):
    url = BASE + path
    r = requests.request(method, url, json=body if method == "POST" else None, timeout=60)
    try:
        j = r.json()
    except Exception:
        j = {"_text": r.text[:300]}
    if r.status_code >= 400:
        if not quiet:
            print(f"  !! {r.status_code} {method} {path} {json.dumps(body, ensure_ascii=False)[:160] if body else ''} -> {json.dumps(j, ensure_ascii=False)[:300]}")
        note_err("http", {"status": r.status_code, "method": method, "path": path, "body": body, "resp": j})
        j = dict(j) if isinstance(j, dict) else {"_resp": j}
        j["_status"] = r.status_code
    return j


def get(path, quiet=False):
    return api("GET", path, quiet=quiet)


def post(path, body, quiet=False):
    return api("POST", path, body, quiet=quiet)


def scan(uid, code, cat=None, show=True):
    pk = get(f"/api/peek?barcode={code}&uid={uid}")
    use = cat if pk.get("needs_category") else None
    r = post("/api/scan", {"uid": uid, "barcode": code, "user_category": use})
    if show and "_status" not in r:
        c = r.get("card") or {}
        g = ", ".join(f"{k}+{v}" for k, v in (r.get("gained") or {}).items()) or "(얻은 것 없음)"
        print(f"  [찍기] {code} → 「{c.get('name')}」 {c.get('rarity')} {c.get('category')} {('가문:' + c.get('family_name')) if c.get('family_name') else ''} | {g} ×{r.get('rescan_multiplier')} | 선반 {r.get('shelf_slot')} new={r.get('shelf_new')} first={r.get('first_time')}")
        if r.get("polish") and r["polish"].get("ko"):
            print(f"     닦기: {r['polish']['ko']} ({r['polish'].get('label')})")
        for m in r.get("first_meet") or []:
            print(f"     첫만남: {m.get('line')}")
        if (r.get("family_set") or {}).get("ko"):
            print(f"     가문: {r['family_set']['ko']}")
        if (r.get("variant") or {}).get("shiny"):
            print(f"     변형: {r['variant'].get('ko')}")
        for w in r.get("wishes_done") or []:
            print(f"     바람이룸: {w.get('line')}")
        if r.get("box_opened"):
            print(f"     상자열림: {json.dumps(r['box_opened'], ensure_ascii=False)}")
        if (r.get("voice") or {}).get("text"):
            print(f"     목소리({r['voice'].get('who_ko')}): {r['voice']['text']}")
    return r


def advance(uid, minutes):
    return post("/api/dev/advance", {"uid": uid, "minutes": minutes})


def ark(uid):
    return get(f"/api/ark?uid={uid}")


def res_line(st):
    r = st.get("resources") or {}
    ko = {"food": "식량", "water": "물", "power": "전력", "parts": "부품", "med": "의약", "morale": "사기", "cloth": "직물",
          "trade": "교역", "knowledge": "지식", "scrap": "잔해", "chem": "화학"}
    return " ".join(f"{ko.get(k, k)}{v}" for k, v in r.items())


class Base:
    """한 페르소나의 브라우저(영구 프로필)."""

    def __init__(self, persona: str, uid: str):
        from playwright.sync_api import sync_playwright
        self.uid = uid
        self.pw = sync_playwright().start()
        prof = SCRATCH / f"pw_profile_{persona}"
        prof.mkdir(parents=True, exist_ok=True)
        self.ctx = self.pw.chromium.launch_persistent_context(
            str(prof), headless=True, viewport={"width": 1280, "height": 800}, locale="ko-KR",
            args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
        self.ctx.add_init_script(f"try{{localStorage.setItem('ark_uid', {json.dumps(uid)});}}catch(e){{}}")
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.errors: list[str] = []
        self.bad: list[str] = []
        self.payloads: dict[str, list] = {}
        p = self.page
        p.on("console", lambda m: self.errors.append(f"console.{m.type}: {m.text[:300]}") if m.type == "error" else None)
        p.on("pageerror", lambda e: self.errors.append(f"pageerror: {str(e)[:300]}"))
        p.on("response", self._resp)

    def _resp(self, resp):
        u = resp.url
        if resp.status >= 400:
            self.bad.append(f"{resp.status} {u.replace(BASE, '')}")
        if "/api/" in u:
            key = u.replace(BASE, "").split("?")[0]
            try:
                if "json" in (resp.headers.get("content-type") or ""):
                    self.payloads.setdefault(key, []).append(resp.json())
            except Exception:
                pass

    def open(self, path="/base", wait=14.0, shot: str | None = None, shot_at: float | None = None):
        self.errors.clear(); self.bad.clear(); self.payloads.clear()
        self.page.goto(BASE + path, wait_until="domcontentloaded")
        seen = []
        t0 = time.time()
        shot_done = False
        while time.time() - t0 < wait:
            for sel in ("#toast", ".meet", "#panel:not([hidden])", "#rstrip:not([hidden])", "#evbtn:not([hidden])", "#xpbtn:not([hidden])"):
                try:
                    els = self.page.query_selector_all(sel)
                    for el in els:
                        if el.is_visible():
                            t = (el.inner_text() or "").strip()
                            if t and (sel, t) not in seen:
                                seen.append((sel, t))
                except Exception:
                    pass
            if shot and shot_at is not None and not shot_done and time.time() - t0 >= shot_at:
                self.page.screenshot(path=str(SHOTS / shot)); shot_done = True
            time.sleep(0.35)
        if shot and not shot_done:
            self.page.screenshot(path=str(SHOTS / shot))
        return seen

    def text(self, sel="body"):
        try:
            return self.page.inner_text(sel)
        except Exception:
            return ""

    def shot(self, name):
        self.page.screenshot(path=str(SHOTS / name))

    def report(self, seen, label=""):
        print(f"--- 화면({label}) ---")
        for sel, t in seen:
            print(f"  <{sel}> {t[:400]}")
        top = self.text("#topbar")
        print(f"  [위 줄] {top.replace(chr(10), ' | ')[:300]}")
        allt = self.text("body")
        hits = sorted(set(m.group(0) for m in RAW_ID.finditer(allt + " " + " ".join(t for _, t in seen))))
        if hits:
            print(f"  ?? 화면에 날 id/자리표시 의심: {hits}")
            note_err("raw_text", {"uid": self.uid, "hits": hits, "label": label})
        if self.errors:
            print(f"  !! 콘솔 오류 {len(self.errors)}: {self.errors[:5]}")
            note_err("console", {"uid": self.uid, "errors": self.errors[:10], "label": label})
        if self.bad:
            print(f"  !! 실패 응답: {self.bad[:8]}")
            note_err("ui_http", {"uid": self.uid, "bad": self.bad[:10], "label": label})

    def close(self):
        try:
            self.ctx.close()
        finally:
            self.pw.stop()


def show_raid(r):
    raid = r.get("raid") or {}
    if not raid or raid.get("none"):
        print("  [습격] 오늘 오는 것 없음", json.dumps(r.get("next_raid_hint"), ensure_ascii=False)[:200])
        return raid
    keys = ["id", "creature", "name", "stage", "target_room", "target_slot", "grade", "strength", "resolved", "result"]
    print("  [습격]", json.dumps({k: raid.get(k) for k in keys if k in raid}, ensure_ascii=False))
    for k in ("text", "sound_ko", "line", "how", "how_ko", "gate_ko", "flip", "reveal_ko"):
        if raid.get(k):
            print(f"     {k}: {json.dumps(raid[k], ensure_ascii=False)[:500]}")
    if raid.get("ready"):
        print("     ready:", json.dumps(raid["ready"], ensure_ascii=False)[:700])
    return raid


CAT_BTN = {"food": "식품", "drink": "음료", "medical": "의약·화학", "electronics": "전자", "stationery": "문구",
           "apparel": "의류", "tobacco": "담배·주류", None: "모름"}


def ui_scan(b: "Base", code: str, cat: str | None, shot: str | None = None):
    """UI 로 찍기: 찍기 → 숫자 적기 → (물으면) 카테고리 → 카드 → 선반에 두기."""
    p = b.page
    p.click("#scanbtn"); time.sleep(0.6)
    p.fill("#manual", code); p.click("#manualBtn"); time.sleep(1.2)
    picked = None
    if p.is_visible("#picker"):
        q = p.inner_text("#picker").split("\n")[0]
        picked = CAT_BTN.get(cat, "모름")
        p.click(f"#picker button:text-is('{picked}')"); time.sleep(1.2)
    time.sleep(1.5)
    front = p.inner_text("#rcFront") if p.is_visible("#scanCard") else ""
    gain = p.inner_text("#rgain") if p.is_visible("#scanCard") else ""
    toast = p.inner_text("#toast")
    print(f"  [UI찍기] {code} 고름={picked} | 카드: {front.replace(chr(10), ' / ')[:200]}")
    print(f"           {gain.replace(chr(10), ' / ')[:600]}")
    if not front:
        print(f"           (카드 안 뜸) toast={toast[:200]}")
    if shot:
        b.shot(shot)
    try:
        if p.is_visible("#shelfBtn"):
            p.click("#shelfBtn"); time.sleep(1.0)
        if p.is_visible("#scan"):
            p.click("#scanClose")
    except Exception:
        pass
    time.sleep(0.4)
    return front, gain


def follow_expedition(b: "Base", exp_id: str, pick_choice=None, shot_mid=None, shot_ret=None, max_s=150):
    """3D 따라 나가기: 반짝이를 화면 좌표로 누르고, 고르기 카드는 pick_choice(text, buttons)->index 로 고른다."""
    p = b.page
    b.errors.clear(); b.bad.clear()
    p.goto(f"{BASE}/static/expedition.html?uid={b.uid}&exp={exp_id}", wait_until="domcontentloaded")
    t0 = time.time(); seen = []; shot_mid_done = False; clicked_follow = False; last_try = 0
    def rec(tag, t):
        t = (t or "").strip()
        if t and (tag, t) not in seen:
            seen.append((tag, t)); print(f"   <{tag}> {t[:500]}")
    while time.time() - t0 < max_s:
        for sel, tag in (("#pa", "방송"), ("#narr", "서술"), ("#discT", "발견"), ("#discP", "발견글")):
            try:
                if p.is_visible(sel): rec(tag, p.inner_text(sel))
            except Exception: pass
        try:
            if p.is_visible("#ret") and p.inner_text("#retCard").strip():
                time.sleep(4.0)
                rec("귀환카드", p.inner_text("#retCard"))
                if shot_ret: b.shot(shot_ret)
                btns = p.query_selector_all("#retCard button")
                print("   귀환카드 버튼:", [x.inner_text() for x in btns])
                return seen, btns
            if p.is_visible("#disc") and p.is_visible("#discOk"):
                time.sleep(2.5); rec("발견", p.inner_text("#disc")); p.click("#discOk"); time.sleep(1)
            ch = p.query_selector("#choice.show")
            if ch:
                txt = ch.inner_text(); btns = ch.query_selector_all("button")
                labels = [x.inner_text().replace("\n", " ") for x in btns]
                rec("고르기", txt + " || " + " | ".join(labels))
                if not clicked_follow and p.query_selector("#cFollow"):
                    if shot_mid and not shot_mid_done and "threshold" in (shot_mid or ""):
                        b.shot(shot_mid); shot_mid_done = True
                    p.click("#cFollow"); clicked_follow = True; time.sleep(1.5); continue
                idx = pick_choice(txt, labels) if pick_choice else 0
                if idx is not None and 0 <= idx < len(btns):
                    print(f"   → 고름: {labels[idx]}")
                    btns[idx].click(); time.sleep(2.0)
                    # 손이 넘침(drop) 카드에는 확인 버튼이 따로 있을 수 있다
                    continue
            mode = p.evaluate("window.EXPED && window.EXPED.mode")
            nxv = p.evaluate("window.EXPED && window.EXPED.scene && window.EXPED.scene.next")
            if nxv != getattr(follow_expedition, '_nx', None):
                follow_expedition._nx = nxv; last_try = 0
            if mode == "follow" and time.time() - last_try > 25:
                info = p.evaluate("""() => { const E = window.EXPED; const sc = E.scene || {}; const nx = sc.next || '';
                    const g = E.glints.find(g => g.state === 'sparkle' && ('pick:' + g.i) === nx);
                    if (!g) return {nx};
                    const s = E.screenOf(g.x, g.z, 0.5); return {nx, x: s.x, y: s.y}; }""")
                if info and info.get("x") is not None:
                    x, y = info["x"], info["y"]
                    if 0 < x < 1280 and 0 < y < 800:
                        p.mouse.click(x, y)
                    else:
                        p.evaluate("([x,y]) => window.EXPED.tap(x,y)", [x, y])
                    last_try = time.time(); print(f"   (반짝이 {info['nx']} 누름, 걸어가는 중)")
                    if shot_mid and not shot_mid_done and info["nx"] == "pick:1":
                        time.sleep(2.5); b.shot(shot_mid); shot_mid_done = True
        except Exception as e:
            print("   (루프 예외)", str(e)[:200])
        time.sleep(0.4)
    print("   !! 시간 초과 — mode:", p.evaluate("window.EXPED && window.EXPED.mode"))
    return seen, []
