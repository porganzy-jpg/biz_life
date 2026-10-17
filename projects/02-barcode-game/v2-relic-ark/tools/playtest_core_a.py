"""핵심 루프 A(S19) 플레이테스트 도우미 — 「어디로」 고르기, 매듭 답하기, 꾸밈, 떠날 때 카드, 세션 계약·같은 답 기록.

playtest_7day.py 의 단계로 불린다:
  loop:<물건,...>   찍고 → 「어디로」를 페르소나 정책으로 고르고 → 반응을 읽는다
  arcs              열린 매듭의 물음에 답한다(A: 고른다 / B: 넘긴다 = default)
  decor             선반 물건을 꼬리표가 붙을 방에 놓는다(A만, 세션당 최대 2)
  feast             잔치(비트 10일째 등, 가능할 때)
  leave             GET /api/leaving — 떠날 때 카드
  contract          이번 세션의 계약 다섯 + 같은 답 비율을 찍고 파일에 남긴다
세션 기록: scratchpad/pt_sessions_<uid>.jsonl (한 줄 = 한 세션)
"""
from __future__ import annotations

import collections
import json
import random
from pathlib import Path

from playtest_lib import ROOT, SCRATCH, get, post, ark, scan
from playtest_household import code, cat, name

TIER_A = {"chain_beat": 6, "memory": 6, "need": 5, "decor": 3, "like": 3, "warm": 2.2, "plain": 1, "not_for_me": 0}


def _data(fn):
    for p in (ROOT / "data" / fn, ROOT / "data" / "draft" / fn):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


DECOR_TAGS = _data("room_decor.json").get("tags") or []


class Session:
    """한 세션(= CLI 한 번의 open ~ leave)의 기록."""

    def __init__(self, persona, uid):
        self.persona, self.uid = persona, uid
        self.d = {"arrival": [], "new": [], "decisions": [], "unknown": [], "return": [],
                  "gives": [], "asks": [], "decor": [], "needs": [], "beat": None, "day": None}
        self.given_people = collections.Counter()

    # ── 도착 ──
    def on_open(self, st):
        self.d["day"] = st.get("day")
        ov = st.get("overnight") or {}
        # ── 6차: 첫 진입 패널 · 기억 벽 · 하루 소비(굶음) ──
        if ov.get("first_entry"):
            self.d["first_entry"] = {"title": ov.get("title"), "open": ov.get("open"), "n": ov.get("count")}
            print(f"  [첫 진입 패널] 「{ov.get('title')}」 「{ov.get('open')}」 항목 {ov.get('count')} 「{ov.get('close')}」")
        mw = st.get("memory_wall")
        if mw:
            self.d["memory_wall"] = {"filled": mw.get("filled"), "total": mw.get("total"), "complete": mw.get("complete")}
            print(f"  [기억 벽] {mw.get('filled')}/{mw.get('total')} 첫 칸 {(mw.get('slots') or [{}])[0]} 「{mw.get('open_ko') or ''}」 「{mw.get('prefilled_ko') or ''}」")
        res = st.get("resources") or {}
        self.d["res"] = {k: res.get(k) for k in ("food", "water", "morale", "power", "parts", "scrap")}
        self.d["consumed"] = st.get("consumed_while_away")
        print(f"  [하루 소비] {st.get('consumption')} 자리 비운 사이 {st.get('consumed_while_away')} · 식량 {res.get('food')} 물 {res.get('water')} 사기 {res.get('morale')}")
        if (res.get("food") or 0) <= 0 or (res.get("water") or 0) <= 0 or ((st.get("consumed_while_away") or {}).get("morale") or 0) < 0:
            print("  !! [굶음] 식량·물 0 또는 굶어서 사기 감소")
            self.d["hunger"] = True
        for it in ov.get("items") or []:
            k = it.get("kind")
            if k in ("octopus", "expedition_return", "visit", "knock", "night_judge", "overflow", "imprint", "wish", "depth"):
                self.d["arrival"].append(k)
            if k == "needs":
                for r in (it.get("data") or {}).get("rows") or []:
                    self.d["needs"].append(r.get("announce"))
        for n in st.get("needs_today") or []:
            if n.get("announce") and n["announce"] not in self.d["needs"]:
                self.d["needs"].append(n["announce"])
        if (st.get("octopus") or {}).get("gift_today"):
            self.d["arrival"].append("octopus_gift")
        for v in st.get("visits") or []:
            self.d["arrival"].append("visit:" + str(v.get("kind")))
            if v.get("first"):
                self.d["new"].append("visitor:" + str(v.get("ko")))
            self.d["unknown"].append("visit")
        b = st.get("beat_today") or {}
        if b:
            self.d["beat"] = {k: b.get(k) for k in ("play_day", "beat", "star", "teaser", "big", "new")}
            if b.get("new"):
                self.d["new"].append("beat:" + str(b.get("beat")))
        for e in st.get("arc_events") or []:
            self.d["new"].append("arc:" + str(e.get("arc_id")) + ":" + str(e.get("step")))
        if st.get("expedition_return"):
            self.d["unknown"].append("expedition_return")
        print("  [오늘 필요]", " / ".join(self.d["needs"]) or "-")
        print("  [비트]", json.dumps(self.d["beat"], ensure_ascii=False)[:400])
        if st.get("visits"):
            print("  [방문]", json.dumps(st["visits"], ensure_ascii=False)[:600])
        if st.get("arc_events"):
            print("  [매듭 사건]", json.dumps(st["arc_events"], ensure_ascii=False)[:900])
        if st.get("next_visit"):
            print("  [다음에 켜시면(열 때)]", (st["next_visit"] or {}).get("kind"), (st["next_visit"] or {}).get("line"))
        nov = st.get("novelty")
        for it in (st.get("overnight") or {}).get("items") or []:
            if it.get("kind") == "novelty" and not nov:
                nov = it.get("data")
        if nov:
            self.d["novelty"] = {k: nov.get(k) for k in ("kind", "line", "line_key", "resident_id")}
            self.d["new"].append("novelty:" + str(nov.get("kind")))
            print("  [실마리 novelty]", json.dumps(self.d["novelty"], ensure_ascii=False)[:400])
        tags_on = []
        for slot, room in (st.get("room_decor") or {}).items():
            for t in room.get("tags") or []:
                if t.get("on"):
                    tags_on.append(f"{room.get('room_id')}:{t.get('ko')}")
            prog = [f"{t.get('ko')} {t.get('have')}/{t.get('need')}" for t in room.get("tags") or [] if not t.get("on")]
            print(f"  [꾸밈 칸] {room.get('room_id')}({slot}) {len(room.get('items') or [])}/{room.get('cap')} 붙음 {[t.get('ko') for t in room.get('tags') or [] if t.get('on')]} 진척 {prog}")
        self.d["tags_on"] = tags_on
        if st.get("octopus_gift_where"):
            print("  [문어 조각 어디로]", json.dumps(st["octopus_gift_where"], ensure_ascii=False)[:600])
        # ── S22/S23 기록 ──
        day = st.get("day")
        tp = _tomorrow_file(self.uid)
        if tp.exists():
            ta = json.loads(tp.read_text(encoding="utf-8"))
            if ta.get("day") == day and "matched" not in ta:
                row = next((n for n in st.get("needs_today") or [] if n.get("resident_id") == ta.get("resident_id")), None)
                ta["matched"] = bool(row) and (row.get("need") or {}).get("category") == (ta.get("need") or {}).get("category") \
                    and sorted((row.get("need") or {}).get("subtype") or []) == sorted((ta.get("need") or {}).get("subtype") or [])
                ta["today_need"] = (row or {}).get("need")
                tp.write_text(json.dumps(ta, ensure_ascii=False), encoding="utf-8")
                print(f"  [내일의 부탁 확인] 어제 「{ta.get('line')}」 → 오늘 {ta.get('name')} 필요 {((row or {}).get('need') or {}).get('ko')} · 일치 {ta['matched']}")
                self.d["tomorrow_check"] = {"matched": ta["matched"], "need": ta.get("need"), "today": ta["today_need"]}
        forced = [v for v in st.get("visits") or [] if v.get("forced")]
        if forced:
            print("  [첫 손님(forced)]", json.dumps(forced, ensure_ascii=False)[:400])
            self.d["new"].append("forced_visitor")
        nv = [v for v in st.get("visits") or [] if v.get("kind") == "night_visitor"]
        if nv:
            print("  [밤 손님]", json.dumps(nv, ensure_ascii=False)[:300])
        self.d["decor_trace"] = [{k: t.get(k) for k in ("slot", "tag_ko", "ko", "line")} for t in st.get("decor_trace") or []]
        if self.d["decor_trace"]:
            print("  [꾸밈 흔적(예고)]", json.dumps(self.d["decor_trace"], ensure_ascii=False)[:400])
        vb = [(v.get("ko"), v.get("count"), (v.get("souvenir") or {}).get("name")) for v in st.get("visitors_book") or [] if v.get("count")]
        self.d["visitors_book"] = vb
        print(f"  [손님 책] {len(vb)}/{len(st.get('visitors_book') or [])} {vb}")
        if st.get("missed_chain"):
            print("  [놓친 매듭(열 때)]", json.dumps(st["missed_chain"], ensure_ascii=False)[:300])
        if st.get("notebook_tip"):
            self.d["notebook_tip"] = {k: st["notebook_tip"].get(k) for k in ("name", "kind", "ko", "line")}
            print("  [저녁 귀띔]", st["notebook_tip"].get("line"))
        self.d["notebook"] = {rid: ((r.get("notebook") or {}).get("known"), (r.get("notebook") or {}).get("total"))
                              for rid, r in ((st.get("core") or {}).get("residents") or {}).items()}
        print(f"  [수첩] 아는 칸 {sum(v[0] or 0 for v in self.d['notebook'].values())}/{sum(v[1] or 0 for v in self.d['notebook'].values())}")
        et = st.get("evening_table")
        self.d["evening"] = bool(et)
        # ── S25 해금 달력 ──
        ul = st.get("unlocked") or {}
        self.d["unlocked"] = {"play_day": ul.get("play_day"), "features": ul.get("features"),
                              "new": [n.get("feature") for n in ul.get("new") or []], "next": (ul.get("next") or {}).get("unlocks")}
        print(f"  [해금] 켠 날 {ul.get('play_day')} · 열린 것 {ul.get('features')} · 새로 {[(n.get('feature'), n.get('line')) for n in ul.get('new') or []]} · 다음 {(ul.get('next') or {}).get('unlocks')} 「{(ul.get('next') or {}).get('teaser')}」")
        for n in ul.get("new") or []:
            self.d["new"].append("unlock:" + str(n.get("feature")))
        # ── S24 안전: 필요·내일의 부탁·사슬 다음 조건에 담배·술·붕대 밖 의약이 있나 ──
        def unsafe(need):
            if not need:
                return False
            cg, sb = need.get("category"), need.get("subtype") or []
            sb = sb if isinstance(sb, list) else [sb]
            return cg == "tobacco" or (cg == "drink" and "alcohol" in sb) or (cg == "medical" and any(x != "bandage" for x in sb or ["?"]))
        bad = [("need", n.get("name"), n.get("need")) for n in st.get("needs_today") or [] if unsafe(n.get("need"))]
        if unsafe((st.get("tomorrow_ask") or {}).get("need")):
            bad.append(("tomorrow_ask", st["tomorrow_ask"].get("name"), st["tomorrow_ask"].get("need")))
        for rid, r in ((st.get("core") or {}).get("residents") or {}).items():
            for nd in r.get("needs_today") or []:
                if unsafe(nd):
                    bad.append(("core_need", rid, nd))
            for sl in (r.get("notebook") or {}).get("slots") or []:
                if sl.get("known") and sl.get("ko") and any(w in sl["ko"] for w in ("담배", "술", "맥주", "불붙이개", "알약", "연고", "소독", "화장품")):
                    bad.append(("notebook", rid, sl.get("ko")))
        self.d["safety"] = bad
        if bad:
            print("  !! [안전] 위반:", json.dumps(bad, ensure_ascii=False)[:400])
        if et:
            print(f"  [한 상] open={et.get('open')} done={et.get('done')} 「{et.get('open_ko')}」 돌아온 것 {len(et.get('returned') or [])}")

    def save(self):
        p = SCRATCH / f"pt_sessions_{self.uid}.jsonl"
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(self.d, ensure_ascii=False) + "\n")


# ── S22/S23 (5차 준비) ──────────────────────────────────────────────
# 「이게 뭐예요?」에서 사람이 고를 현실의 하위 종류(물어볼 때만 쓰인다 — 알려진 가문·책은 서버가 묻지 않는다)
REAL_SUB = {"jin": "noodle", "rice": "grain", "tofu": "canned", "kimchi": "canned", "milk": "milk",
            "cable": "cable", "tylenol": "pill", "vitamin": "pill", "socks": "small", "postit": "sticky",
            "chocopie": "snack", "pepero": "sweet", "granola": "sweet", "gim": "canned", "coke": "soda",
            "samdasoo": "water", "maxim": "coffee", "tea": "tea", "shampoo": "hygiene", "toothpaste": "hygiene",
            "battery": "battery", "lightbulb": "light", "monami": "pen", "soju": "liquor", "cass": "beer",
            "shin": "noodle", "chapa": "noodle", "saewoo": "snack"}
# 묻지 않는(서버가 정한) 바코드의 실제 하위 종류 — 4차 사전 조사 값. 내일의 부탁을 겨냥할 때 쓴다
SERVER_SUB = {"shin": "snack", "chapa": "snack", "saewoo": "snack", "pepero": "sweet", "chocopie": "snack",
              "gim": "sweet", "kimchi": "snack", "granola": "sweet", "coke": "juice", "samdasoo": "water",
              "maxim": "tea", "tea": "tea", "shampoo": "hygiene", "toothpaste": "pill", "battery": "battery",
              "lightbulb": "part", "monami": "pen", "soju": "liquor", "cass": "beer",
              "book1": "story", "book2": "field_guide", "book3": "map"}
# 기색(hint_ko)을 읽는 사람의 감 — 그 물건의 갈래·하위 종류를 떠올리게 하는 말
HINT_WORDS = {
    ("food", None): ["부엌", "꼬르륵", "배", "먹"], ("food", "noodle"): ["면", "국수", "꼬불", "국물", "실"],
    ("food", "snack"): ["과자", "바삭", "봉지"], ("food", "sweet"): ["단", "달", "사탕"],
    ("food", "canned"): ["통조림", "절임", "병"], ("food", "grain"): ["쌀", "밥", "곡물", "낟알"], ("food", "sauce"): ["양념", "간을"],
    ("drink", None): ["컵", "마실", "입술", "목이"], ("drink", "water"): ["물통", "물을", "마실 물"], ("drink", "soda"): ["거품", "톡"],
    ("drink", "coffee"): ["커피", "졸", "잠"], ("drink", "tea"): ["잎", "찻잔", "차 ", "김만"], ("drink", "milk"): ["우유", "하얀", "고소"],
    ("drink", "juice"): ["과일", "단물"],
    ("medical", None): ["의무실", "손등", "아프", "약"], ("medical", "pill"): ["알약", "약"], ("medical", "hygiene"): ["씻", "비누", "냄새"],
    ("medical", "bandage"): ["긁힌", "상처", "밴드"], ("medical", "disinfect"): ["소독", "상처"],
    ("electronics", None): ["기계", "작업대", "두드려"], ("electronics", "battery"): ["건전지", "꺼진", "배터리"],
    ("electronics", "cable"): ["줄", "충전"], ("electronics", "light"): ["불빛", "등", "어두"], ("electronics", "audio"): ["소리", "음악"],
    ("electronics", "part"): ["부품", "나사"], ("electronics", "device"): ["기계", "기기"],
    ("stationery", None): ["글씨", "적을", "쓰"], ("stationery", "pen"): ["펜", "글씨"], ("stationery", "paper"): ["종이", "공책"],
    ("stationery", "sticky"): ["메모", "붙"],
    ("book", None): ["책", "읽을"], ("apparel", None): ["소매", "옷", "춥", "움츠"], ("apparel", "small"): ["양말", "장갑", "모자", "발", "손"],
    ("apparel", "shoes"): ["신발", "발"], ("apparel", "bag"): ["가방", "짐"], ("tobacco", None): ["교역", "갑", "담배", "술", "맥주"],
}


def hint_match(hint: str, category, subtype) -> bool:
    if not hint:
        return False
    words = HINT_WORDS.get((category, subtype), []) + HINT_WORDS.get((category, None), [])
    return any(w in hint for w in words)


def choose(persona, where, ses: Session, rng: random.Random, card=None, want_rid=None):
    sug = where.get("suggest") or []
    if not sug:
        return "shelf", "제안 없음 → 선반", None
    if want_rid and persona.startswith("A"):            # 내일의 부탁을 겨냥해 찍은 물건 — 그 사람에게
        t = next((s for s in sug if isinstance(s.get("target"), dict) and s["target"].get("resident_id") == want_rid), None)
        if t:
            return t["target"], "어제 부탁받은 물건이라 그분께", t
    if persona.startswith("A") and where.get("labels") is False:
        # 3일째부터: 라벨이 없는 사람은 기색(hint_ko)을 읽고 고른다
        best, bs = None, -9
        for s in sug:
            rid = (s.get("target") or {}).get("resident_id") if isinstance(s.get("target"), dict) else None
            if s.get("known") is False:
                hm = hint_match(s.get("hint_ko"), (card or {}).get("category"), (card or {}).get("subtype"))
                sc = 2.8 + (2.2 if hm else 0)
                s["_hint_match"] = hm
            else:
                sc = TIER_A.get(s.get("tier"), 2) + (s.get("value") or 0.9)
                if s.get("tier") == "decor" and (s.get("tag_have", 0) + 1) >= (s.get("tag_need") or 99):
                    sc += 2.5
                if (s.get("mult") or 1) < 1 and s.get("tier") not in ("chain_beat", "memory"):
                    sc -= 1.2
            if rid and ses.given_people[rid] and s.get("tier") not in ("chain_beat", "memory"):
                sc -= 0.8
            if sc > bs:
                best, bs = s, sc
        if bs < 2:
            return "shelf", f"기색이 다 멀다(best {bs:.1f}) → 선반", None
        if best.get("known") is False:
            return best["target"], ("기색 읽기(맞는 말)" if best.get("_hint_match") else "기색 읽기(감)") + f": {best.get('hint_ko')}", best
        return best["target"], f"수첩에 아는 칸·{best.get('tier')}", best
    if persona.startswith("B"):
        # 4차 5일째부터: 무작위 대신 정확히 다섯 번에 한 번 닫는다(1~4일째 무작위가 12번 중 7번 닫아 페르소나 규칙 80%를 벗어났다)
        cf = SCRATCH / f"pt_bclose_{ses.uid}.txt"
        n = int(cf.read_text() or 0) + 1 if cf.exists() else 1
        cf.write_text(str(n))
        if n % 5 != 0:
            return sug[0]["target"], "첫 제안 그대로", sug[0]
        return "shelf", "그냥 닫음(선반)", None
    best, bs = None, -9
    for s in sug:
        sc = TIER_A.get(s.get("tier"), 1) + (s.get("value") or 0)
        if s.get("tier") == "decor" and (s.get("tag_have", 0) + 1) >= (s.get("tag_need") or 99):
            sc += 2.5                                        # 꼬리표가 붙는다 → 손님
        rid = (s.get("target") or {}).get("resident_id") if isinstance(s.get("target"), dict) else None
        story = s.get("tier") in ("chain_beat", "memory")   # 이야기는 깎여도 움직인다
        mult = s.get("mult") or 1
        if not story:
            if mult <= 0.5:
                sc -= 3                                      # 크게 깎임 → 선반이 낫다
            elif mult < 1:
                sc -= 1.2 if mult >= 0.75 else 1.6           # S21: 같은 세션 ×0.8 · 같은 물건 ×0.6
            if rid and ses.given_people[rid]:
                sc -= 0.8                                    # 이번 세션에 이미 준 사람 — 고르게 나누고 싶다
        if sc > bs:
            best, bs = s, sc
    if bs < 2:
        return "shelf", f"제안이 다 약함(best {bs:.1f}) → 선반", None
    return best["target"], f"{best.get('tier')}·{best.get('reason_ko')}", best


def pending_asks(uid):
    """답하지 못한 매듭 물음 중 물건이 필요한 것(place/give) — 선반·창고 상자에 맞는 물건이 없으면 목록에 남긴다."""
    st = ark(uid)
    out = []
    for rid, r in ((st.get("core") or {}).get("residents") or {}).items():
        ask = ((r.get("arc") or {}).get("next") or {}).get("ask")
        if ask and ask.get("kind") in ("place", "give"):
            if not [x for x in _items(st) if _match(x[2], ask.get("category"), ask.get("subtype"))]:
                out.append({"label": ask.get("label"), "category": ask.get("category"), "subtype": ask.get("subtype")})
    return out


def _tomorrow_file(uid):
    return SCRATCH / f"pt_tomorrow_{uid}.json"


def tomorrow_target(uid, day):
    """어제 떠날 때 받은 「내일의 부탁」 중 오늘 것 → 그 필요에 맞는 집 물건 키."""
    p = _tomorrow_file(uid)
    if not p.exists():
        return None
    ta = json.loads(p.read_text(encoding="utf-8"))
    if ta.get("day") != day or ta.get("tried"):
        return None
    need = ta.get("need") or {}
    subs = need.get("subtype") or []
    subs = subs if isinstance(subs, list) else [subs]
    for k in REAL_SUB.keys() | SERVER_SUB.keys():
        if cat(k) != need.get("category") and not (need.get("category") == "book" and k.startswith("book")):
            continue
        sub = SERVER_SUB.get(k) or REAL_SUB.get(k)
        if not subs or sub in subs:
            return {"key": k, "rid": ta.get("resident_id"), "name": ta.get("name"), "need": need}
    return {"key": None, "rid": ta.get("resident_id"), "name": ta.get("name"), "need": need}


def do_loop(persona, uid, keys, ses: Session, rng: random.Random):
    pend = pending_asks(uid) if persona.startswith("A") else []
    if pend:
        print("  [물음에 쓸 물건 찾는 중]", pend)
    tt = tomorrow_target(uid, ses.d.get("day")) if persona.startswith("A") else None
    if tt:
        ses.d["tomorrow_try"] = {"rid": tt["rid"], "need": tt["need"], "key": tt["key"]}
        if tt["key"]:
            keys = [tt["key"]] + [x for x in keys if x != tt["key"]]
            print(f"  [내일의 부탁 → 오늘] {tt['name']} 님 「{(tt['need'] or {}).get('ko')}」 → 집에서 {name(tt['key'])} 를 찍어 드리기")
        else:
            print(f"  [내일의 부탁 → 오늘] {tt['name']} 님 「{(tt['need'] or {}).get('ko')}」 — 집에 맞는 물건이 없음")
        p = _tomorrow_file(uid); d0 = json.loads(p.read_text(encoding="utf-8")); d0["tried"] = True
        p.write_text(json.dumps(d0, ensure_ascii=False), encoding="utf-8")
    abf = SCRATCH / f"pt_abuse_{uid}.json"
    abused = json.loads(abf.read_text(encoding="utf-8")) if abf.exists() else {}
    for k in keys:
        ab = persona.startswith("A") and k not in abused and rng.random() < 0.10
        r = scan(uid, code(k), cat(k), sub=REAL_SUB.get(k), abuse=ab)
        if "_status" in r:
            continue
        qi = r.get("_qp")
        if qi:
            ses.d.setdefault("quick", []).append({"item": name(k), "hit": qi["hit"], "other": qi["other"], "abuse": qi["abuse"], "opts": len(qi["opts"])})
            if qi["abuse"]:
                abused[k] = {"real": REAL_SUB.get(k), "day": ses.d.get("day")}
                abf.write_text(json.dumps(abused, ensure_ascii=False), encoding="utf-8")
        c = r.get("card") or {}
        w0 = r.get("where") or {}
        # S27 ⑥ 이름 다시 붙이기: 전에 일부러 다르게 붙인 바코드면, 오늘 할 수 있을 때 바로잡는다(A)
        ro = w0.get("rename")
        if ro and persona.startswith("A") and k in abused and abused[k].get("day") != ses.d.get("day") and not abused[k].get("fixed"):
            real = abused[k].get("real")
            if ro.get("can_today") and real in [o.get("id") for o in ro.get("options") or []] and (ro.get("current") or {}).get("id") != real:
                rr = post("/api/scan/subtype", {"uid": uid, "barcode": code(k), "subtype": real, "rename": True})
                print(f"     ✎ 이름 다시 붙이기 「{ro.get('label_ko')}」 {(ro.get('current') or {}).get('ko')} → {real} | {rr.get('done_ko') or rr.get('detail')} (전: {rr.get('renamed_from')})")
                ses.d.setdefault("renames", []).append({"item": name(k), "to": real, "ok": "_status" not in rr})
                abused[k]["fixed"] = ses.d.get("day"); abf.write_text(json.dumps(abused, ensure_ascii=False), encoding="utf-8")
                if "_status" not in rr and rr.get("where"):
                    r["where"] = w0 = rr["where"]
                    c = rr.get("card") or c; r["card"] = c
            elif not ro.get("can_today"):
                print("     ✎ 이름 다시 붙이기: 오늘은 이미 한 번 함")
        sp = w0.get("subtype_pick")
        if sp and not sp.get("needed") and sp.get("later_ok"):
            print("     「이게 뭐예요?」 묻지 않음 — 「나중에 이름 붙이기」만")
            ses.d.setdefault("picks_later", []).append(name(k))
        if sp and sp.get("needed"):
            opts = [o["id"] for o in sp.get("options") or []]
            real = REAL_SUB.get(k)
            pick = real if real in opts else (opts[0] if opts else None)
            abuse = False
            if persona.startswith("A") and k not in abused and rng.random() < 0.10 and opts:
                st0 = ark(uid)
                wanted = {s for n in st0.get("needs_today") or [] if (n.get("need") or {}).get("category") == c.get("category")
                          for s in ((n.get("need") or {}).get("subtype") or [])}
                alt = [o for o in opts if o != pick and o in wanted] or [o for o in opts if o != pick]
                pick, abuse = alt[0], True
            rr = post("/api/scan/subtype", {"uid": uid, "scan_id": w0.get("scan_id"), "subtype": pick})
            if abuse and real:
                abused[k] = {"real": real, "day": ses.d.get("day")}; abf.write_text(json.dumps(abused, ensure_ascii=False), encoding="utf-8")
            print(f"     「이게 뭐예요?」 {sp.get('ask_ko')} 보기 {opts} 남들 {sp.get('suggest')} → {pick}{' (일부러 다르게 — 악용 점검)' if abuse else ''} | {rr.get('done_ko') or rr.get('detail')}")
            ses.d.setdefault("picks", []).append({"item": name(k), "real": real, "pick": pick, "abuse": abuse,
                                                  "suggest": (sp.get("suggest") or {}).get("id"), "status": rr.get("_status") or 200})
            if "_status" not in rr:
                r["where"] = rr.get("where") or w0
                c = rr.get("card") or c
                r["card"] = c
        if r.get("first_time") or c.get("rarity") in ("rare", "epic", "legendary") or (r.get("variant") or {}).get("shiny"):
            ses.d["unknown"].append("card:" + str(c.get("rarity")))
        if r.get("first_time") or r.get("first_meet"):
            ses.d["new"].append("relic:" + str(c.get("name")))
        if r.get("box_opened"):
            ses.d["unknown"].append("box")
        w = r.get("where")
        if not w:
            print("     !! where 없음(옛 서버?)"); continue
        sug = w.get("suggest") or []
        if w.get("labels") is False:
            print("     「어디로」(수첩·고정 순서):", " | ".join(
                (f"?:{s.get('name')}「{(s.get('hint_ko') or '')[:44]}」" if s.get("known") is False
                 else f"{s.get('icon')}:{s.get('name')}({s.get('tier')},{s.get('reason_ko')})") for s in sug) or "-", "| 선반")
        else:
          print("     「어디로」:", " | ".join(f"{s.get('icon')}:{s.get('name')}({s.get('tier')},{s.get('reason_ko')},v{s.get('value')}{',×'+str(s.get('mult')) if (s.get('mult') or 1) != 1 else ''}"
                                         + (f",꼬리표 {s.get('tag_ko')} {s.get('tag_have')}/{s.get('tag_need')}" if s.get('tag') else '') + ")" for s in sug) or "-", "| 선반", "| compact" if w.get("compact") else "")
        want = tt["rid"] if (tt and tt.get("key") == k) else None
        _tf = _tomorrow_file(uid)
        _ta = json.loads(_tf.read_text(encoding="utf-8")) if _tf.exists() else {}
        if _ta.get("day") == ses.d.get("day") and (_ta.get("need") or {}).get("category") == c.get("category"):
            _subs = (_ta.get("need") or {}).get("subtype") or []
            _subs = _subs if isinstance(_subs, list) else [_subs]
            if not _subs or c.get("subtype") in _subs:
                _in = any((s.get("target") or {}).get("resident_id") == _ta.get("resident_id") for s in sug if isinstance(s.get("target"), dict))
                ses.d.setdefault("asker_rows", []).append({"item": name(k), "who": _ta.get("name"), "in_row": _in,
                                                           "pos": next((i for i, s in enumerate(sug) if isinstance(s.get("target"), dict) and s["target"].get("resident_id") == _ta.get("resident_id")), None)})
                print(f"     [부탁한 사람 줄에?] {_ta.get('name')} (부탁 「{(_ta.get('need') or {}).get('ko')}」에 맞는 물건) → {'있음' if _in else '없음'}")
        if want:   # 6차: 어제 부탁한 사람이 이 물건의 「어디로」 줄에 있나(S27 줄 고정)
            in_row = any((s.get("target") or {}).get("resident_id") == want for s in sug if isinstance(s.get("target"), dict))
            ses.d["asker_in_row"] = in_row
            print(f"     [부탁한 사람 줄에?] {tt.get('name')} → {'있음' if in_row else '없음'}")
        tgt, why, picked = choose(persona, w, ses, rng, card=c, want_rid=want)
        hit = next((a for a in pend if _match(c, a["category"], a["subtype"])), None)
        if hit and not (picked and picked.get("tier") in ("chain_beat", "memory")):
            tgt, why, picked = "shelf", f"매듭 물음 「{hit['label']}」에 쓰려고 선반에", None
            pend.remove(hit)
        # ── S25 가보 칸: 귀함 이상이면 「누구의 가보로?」 ──
        hl = w.get("heirloom") or []
        if hl:
            print("     ◆ 가보 후보:", " | ".join(f"{h.get('name')}「{h.get('hint_ko')}」({h.get('label')},{h.get('tier')},swap={h.get('swap')},지금={(h.get('current') or {}).get('name') if isinstance(h.get('current'), dict) else h.get('current')})" for h in hl))
            ses.d.setdefault("heirloom_offers", []).append({"item": name(k), "rarity": c.get("rarity"), "n": len(hl),
                                                            "options": [(h.get("name"), h.get("tier"), bool(h.get("swap")), h.get("hint_ko")) for h in hl]})
            if persona.startswith("A") and not want:
                # 가보는 오래 남는다 — 이야기 등급(매듭·기억·필요·좋아함)이 붙은 사람이 있으면 그분, 없으면 아직 가보 없는 분
                rank = {"chain_beat": 5, "memory": 4, "need": 3, "like": 2}
                stier = {(x.get("target") or {}).get("resident_id"): x.get("tier") for x in sug if isinstance(x.get("target"), dict)}
                hpick = max(hl, key=lambda h: (rank.get(stier.get((h.get("target") or {}).get("resident_id")), 0), not h.get("swap"),
                                               -ses.given_people[(h.get("target") or {}).get("resident_id")]))
                tgt, why, picked = dict(hpick["target"]), f"가보로: {hpick.get('label')}", hpick
                ses.d["decisions"].append("가보:" + str(hpick.get("name")))
        g = post("/api/give", {"uid": uid, "scan_id": w["scan_id"], "target": tgt})
        if g.get("ok") is False and g.get("ask_swap"):
            asw = g["ask_swap"]
            # 바꾸기 물음: 새것이 더 높은 등급이고 지금 가보를 받은 지 사흘 넘었으면 바꾼다 — A의 판단
            cur, new = asw.get("current") or {}, asw.get("new") or {}
            order = ["common", "uncommon", "rare", "epic", "legendary"]
            swap = order.index(new.get("rarity", "rare")) > order.index(cur.get("rarity", "rare")) if new.get("rarity") in order and cur.get("rarity") in order else True
            print(f"     ◆ 바꾸기 물음: 「{asw.get('line')}」 지금 {cur.get('name')}({cur.get('rarity')}) → 새 {new.get('name')}({new.get('rarity')}) ⇒ {'바꾼다' if swap else '그대로 둔다'}")
            ses.d.setdefault("swap_asks", []).append({"line": asw.get("line"), "swap": swap})
            ses.d["decisions"].append("가보 바꾸기 물음")
            if swap:
                t2 = dict(tgt); t2["swap"] = True
                g = post("/api/give", {"uid": uid, "scan_id": w["scan_id"], "target": t2})
            else:
                tgt, why, picked = "shelf", "가보는 그대로 두고 선반에", None
                g = post("/api/give", {"uid": uid, "scan_id": w["scan_id"], "target": "shelf"})
        if g.get("heirloom"):
            hh = g["heirloom"]
            print(f"     ◆ 가보 놓음 tier={hh.get('tier')} swapped={hh.get('swapped')} 줄 {json.dumps(hh.get('lines'), ensure_ascii=False)[:400]}")
            ses.d["new"].append("heirloom")
            ses.d.setdefault("heirlooms", []).append({"item": name(k), "tier": hh.get("tier"), "swapped": hh.get("swapped"), "lines": hh.get("lines")})
        if "_status" in g:
            continue
        rid = (tgt or {}).get("resident_id") if isinstance(tgt, dict) else None
        if rid:
            ses.given_people[rid] += 1
        label = "선반" if tgt == "shelf" else (picked or {}).get("name") or json.dumps(tgt, ensure_ascii=False)
        distinct = len({json.dumps(s.get("target"), sort_keys=True) for s in sug})
        real = distinct >= 2 and persona.startswith("A")
        eff = [round((s.get("value") or 0) * (s.get("mult") or 1), 2) for s in sug]
        ses.d["gives"].append({"item": name(k), "options": [s.get("name") for s in sug], "chosen": label,
                               "first": (sug[0].get("name") if sug else "선반"), "first_tier": (sug[0].get("tier") if sug else None),
                               "tiers": [s.get("tier") for s in sug], "eff": eff, "mults": [s.get("mult") or 1 for s in sug],
                               "tier": g.get("tier"), "real": real, "why": why,
                               "weak_shelf": tgt == "shelf" and why.startswith("제안이 다 약함"),
                               "rescan_mult": r.get("rescan_multiplier"),
                               # S23: 라벨 없는 날의 기색 읽기 · 실제 결과 · 의도
                               "labels": w.get("labels"), "order": w.get("order"),
                               "picked_known": (picked or {}).get("known"), "hint": (picked or {}).get("hint_ko"),
                               "hint_match": (picked or {}).get("_hint_match"),
                               "first_known": (sug[0].get("known") if sug else None),
                               "revealed": {k2: (g.get("revealed") or {}).get(k2) for k2 in ("kind", "big", "slot", "new")} if g.get("revealed") else None,
                               "intent": g.get("intent"), "repeat": bool(g.get("repeat")),
                               "history": len((g.get("item") or {}).get("history") or (c.get("history") or [])),
                               "want": bool(want)})
        rv = g.get("revealed") or {}
        if rv:
            print(f"       수첩: revealed {rv.get('kind')} big={rv.get('big')} new={rv.get('new')} 「{rv.get('line')}」")
        if g.get("intent"):
            print(f"       ★ 의도 충족(intent) — 「{(g.get('reaction') or {}).get('announce')}」")
            ses.d["new"].append("intent")
        if g.get("repeat"):
            print(f"       같은 세션 두 번째: 「{(g.get('repeat') or {}).get('line')}」")
        if c.get("history"):
            print(f"       card.history: {json.dumps(c.get('history'), ensure_ascii=False)[:200]}")
        rx0 = g.get("reaction") or {}
        with (SCRATCH / f"pt_lines_{uid}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"day": ses.d.get("day"), "who": (g.get("who") or {}).get("name") or label, "rid": rid,
                                "tier": g.get("tier"), "announce": rx0.get("announce"), "line": rx0.get("line"),
                                "announce_key": rx0.get("announce_key"), "line_key": rx0.get("line_key")}, ensure_ascii=False) + chr(10))
        if real:
            ses.d["decisions"].append("어디로:" + label)
        rx = g.get("reaction") or {}
        ef = g.get("effects") or {}
        print(f"     → {label} ({why}) tier={g.get('tier')} v={g.get('value')} diminish={g.get('diminish')}")
        print(f"       「{rx.get('announce')}」 / 「{rx.get('line')}」")
        for key in ("keepsake", "memory", "arc", "decor"):
            if ef.get(key):
                print(f"       {key}: {json.dumps(ef[key], ensure_ascii=False)[:500]}")
                if key in ("memory", "arc"):
                    ses.d["new"].append(key)
                if key == "decor" and (ef[key].get("tag_added")):
                    ses.d["new"].append("tag:" + str(ef[key]["tag_added"].get("ko")))
        if ef.get("returned_to_shelf"):
            print("       (정중하게 돌려주셨습니다 → 선반)")


def _items(st):
    out = []
    for it in st.get("shelf") or []:
        out.append(("shelf", it.get("card_id"), it))
    for it in st.get("stored") or []:
        out.append(("stored", it.get("id"), it))
    return out


def _match(it, cat_, sub):
    if cat_ and it.get("category") != cat_:
        return False
    if sub:
        subs = sub if isinstance(sub, list) else [sub]
        return it.get("subtype") in subs
    return True


def do_arcs(persona, uid, ses: Session):
    st = ark(uid)
    asks = []
    for rid, r in ((st.get("core") or {}).get("residents") or {}).items():
        arc = r.get("arc") or {}
        nx = arc.get("next") or {}
        if nx.get("ask"):
            asks.append((rid, arc.get("id"), nx["ask"], arc.get("title")))
        if arc and not arc.get("done"):
            print(f"  [매듭] {rid} 「{arc.get('title')}」 {arc.get('step')}/{arc.get('steps')} 다음: {nx.get('hint_ko')} open={nx.get('open')} opens_day={nx.get('opens_day')}")
    seen_arc = {a[1] for a in asks}
    for e in st.get("arc_events") or []:
        if e.get("ask") and e.get("arc_id") not in seen_arc and e["ask"].get("step") is not None:
            asks.append((None, e.get("arc_id"), e["ask"], e.get("title")))
    if not asks:
        print("  [매듭 물음] 없음"); return
    for rid, aid, ask, title in asks:
        print(f"  [매듭 물음] 「{title}」 {json.dumps(ask, ensure_ascii=False)[:400]}")
        if persona.startswith("B"):
            print("     B: 답하지 않음(default)"); continue
        body = {"uid": uid, "arc_id": aid, "step": ask.get("step")}
        kind = ask.get("kind")
        if kind == "choice":
            opts = ask.get("options") or []
            body["choice"] = next((o for o in opts if o != ask.get("default")), opts[0] if opts else None)
        elif kind in ("place", "give"):
            cand = [x for x in _items(st) if _match(x[2], ask.get("category"), ask.get("subtype"))]
            cand.sort(key=lambda x: -(x[2].get("polish") or 0))
            if not cand:
                print("     맞는 물건이 선반·창고 상자에 없음 → 다음에"); continue
            body["relic_id"] = cand[0][1]
        elif kind == "pick_residents":
            ids = [p["id"] for p in st["residents_list"]]
            gp = ses.given_people
            ids.sort(key=lambda i: gp[i])
            body["resident_ids"] = ids[:ask.get("n") or 2]
        r = post("/api/arc/ask", body)
        if "_status" not in r:
            ses.d["asks"].append({"arc": aid, "kind": kind, "answer": body.get("choice") or body.get("relic_id") or body.get("resident_ids")})
            ses.d["decisions"].append("매듭물음:" + str(kind))
            print(f"     → 답 {body.get('choice') or body.get('relic_id') or body.get('resident_ids')}: 「{r.get('after_ask_ko')}」 {json.dumps(r.get('applied'), ensure_ascii=False)[:300]}")


def do_decor(persona, uid, ses: Session, max_n=2):
    if persona.startswith("B"):
        return
    st = ark(uid)
    rd = st.get("room_decor") or {}
    n = 0
    for slot, room in rd.items():
        free = (room.get("cap") or 0) - len(room.get("items") or [])
        if free <= 0:
            continue
        have_tags = {t["id"]: t for t in room.get("tags") or []}
        started = [t for t in DECOR_TAGS if (have_tags.get(t["id"]) or {}).get("have", 0) >= 1 and not (have_tags.get(t["id"]) or {}).get("on")]
        order = started + [t for t in DECOR_TAGS if t not in started and room.get("room_id") in (t.get("best_rooms") or [])]
        for tag in order:
            if (have_tags.get(tag["id"]) or {}).get("on"):
                continue
            cand = [x for x in _items(st) if any(_match(x[2], f.get("category"), f.get("subtype")) for f in tag.get("feeds") or [])]
            for src, rid, it in cand[:free]:
                g = post("/api/give", {"uid": uid, "relic_id": rid, "target": {"slot": int(slot)}})
                if "_status" in g:
                    continue
                ef = (g.get("effects") or {}).get("decor") or {}
                print(f"  [꾸밈] {it.get('name') or it.get('relic_name')} → {room.get('room_id')}({slot}) 꼬리표 목표 {tag['ko']} | {json.dumps(ef, ensure_ascii=False)[:300]}")
                ses.d["decor"].append({"slot": slot, "tag": tag["ko"], "added": bool(ef.get("tag_added"))})
                ses.d["decisions"].append("꾸밈")
                n += 1
                if ef.get("tag_added"):
                    ses.d["new"].append("tag:" + tag["ko"]); print(f"     꼬리표 붙음: {ef['tag_added'].get('announce')}")
                if n >= max_n:
                    return
            break


def do_leave(uid, ses: Session):
    lv = get(f"/api/leaving?uid={uid}")
    print(f"  [떠날 때] {lv.get('title')}: " + " / ".join(lv.get("changed") or []))
    nv = lv.get("next_visit") or {}
    print(f"  [다음에 켜시면] ({nv.get('kind')}) {nv.get('line')}")
    if nv.get("kind") and nv.get("kind") != "nothing":
        ses.d["return"].append(nv.get("kind"))
    if lv.get("missed_chain"):
        print(f"  [놓친 매듭] {json.dumps(lv['missed_chain'], ensure_ascii=False)[:300]}")
        ses.d["missed_chain"] = lv["missed_chain"]
    if lv.get("unlock_teaser"):
        ut = lv["unlock_teaser"]
        print(f"  [해금 예고] {ut.get('play_day')}일째 {ut.get('unlocks')} 「{ut.get('line')}」")
        ses.d["unlock_teaser"] = {k: ut.get(k) for k in ("play_day", "unlocks", "line")}
    ta = lv.get("tomorrow_ask")
    if ta:
        print(f"  [내일의 부탁] {ta.get('name')} 「{(ta.get('need') or {}).get('ko')}」 — 「{ta.get('line')}」")
        ses.d["tomorrow_ask"] = {k: ta.get(k) for k in ("resident_id", "name", "day", "need", "line")}
        p = _tomorrow_file(ses.uid)
        old = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        if old.get("day") != ta.get("day"):
            p.write_text(json.dumps(ses.d["tomorrow_ask"], ensure_ascii=False), encoding="utf-8")
        ses.d["return"].append("tomorrow_ask")
    st = ark(uid)
    for r in ((st.get("core") or {}).get("residents") or {}).values():
        nx = (r.get("arc") or {}).get("next") or {}
        if nx.get("open"):
            ses.d["return"].append("open_arc"); break


def do_contract(ses: Session):
    d = ses.d
    gives = d["gives"]
    chosen = collections.Counter(g["chosen"] for g in gives)
    modal = chosen.most_common(1)[0][1] / len(gives) if gives else 0
    follow_first = sum(1 for g in gives if g["chosen"] == g["first"]) / len(gives) if gives else 0
    ns = collections.Counter(g["chosen"] for g in gives if g["chosen"] != "선반")
    modal_ns = ns.most_common(1)[0][1] / sum(ns.values()) if ns else 0
    c = {"도착 선물": sorted(set(d["arrival"])) or None, "새것": sorted(set(d["new"]))[:8] or None,
         "진짜 결정": d["decisions"] or None, "모르는 결과": sorted(set(d["unknown"])) or None,
         "다시 올 이유": sorted(set(d["return"])) or None}
    ok = sum(1 for v in c.values() if v)
    print(f"\n  ===== 세션 계약 {ok}/5 (Day {d['day']}) =====")
    for k, v in c.items():
        print(f"   {'O' if v else 'X'} {k}: {json.dumps(v, ensure_ascii=False)[:300] if v else '-'}")
    print(f"   「어디로」 {len(gives)}번 · 같은 답(가장 많이 고른 곳) {modal:.0%} · 선반 뺀 같은 답 {modal_ns:.0%} · 첫 제안 그대로 {follow_first:.0%} · 고른 곳 {dict(chosen)}")
    d["contract"] = {k: bool(v) for k, v in c.items()}
    d["same_answer"] = round(modal, 3)
    d["same_answer_no_shelf"] = round(modal_ns, 3)
    d["follow_first"] = round(follow_first, 3)
    ses.save()


def same_answer_report(uid):
    """세션 기록 전체에서 날마다 같은 답 비율·계약 충족을 모은다."""
    p = SCRATCH / f"pt_sessions_{uid}.jsonl"
    if not p.exists():
        return
    by = collections.defaultdict(list)
    for line in p.read_text(encoding="utf-8").splitlines():
        s = json.loads(line); by[s.get("day")].append(s)
    for day, ss in sorted(by.items(), key=lambda x: x[0] or 0):
        gives = [g for s in ss for g in s["gives"]]
        ch = collections.Counter(g["chosen"] for g in gives)
        modal = ch.most_common(1)[0][1] / len(gives) if gives else 0
        ns = collections.Counter(g["chosen"] for g in gives if g["chosen"] != "선반")
        mns = ns.most_common(1)[0][1] / sum(ns.values()) if ns else 0
        cs = [sum((s.get("contract") or {}).values()) for s in ss]
        print(f"  Day {day}: 세션 {len(ss)} · 계약 {cs} · 「어디로」 {len(gives)} · 같은 답 {modal:.0%}(선반 빼면 {mns:.0%}) · 고른 곳 {dict(ch)}")


def do_octogift(persona, uid, ses: Session, rng: random.Random):
    """5일째 비트: 문어가 물어 온 색 조각을 「어디로」로 건넨다(S21 octopus_gift_where)."""
    st = ark(uid)
    w = st.get("octopus_gift_where")
    if not w:
        print("  [문어 조각] octopus_gift_where 없음"); return
    sug = w.get("suggest") or []
    print("  [문어 조각 「어디로」]", w.get("name"), " | ".join(f"{s.get('tier')}:{s.get('name')}({s.get('reason_ko')})" for s in sug))
    tgt, why, picked = choose(persona, w, ses, rng)
    g = post("/api/give", {"uid": uid, "relic_id": w.get("relic_id"), "target": tgt})
    if "_status" in g:
        return
    rx = g.get("reaction") or {}
    ef = g.get("effects") or {}
    label = "선반" if tgt == "shelf" else (picked or {}).get("name")
    print(f"     → {label} ({why}) tier={g.get('tier')} 「{rx.get('announce')}」 / 「{rx.get('line')}」")
    for key in ("memory", "arc", "decor"):
        if ef.get(key):
            print(f"       {key}: {json.dumps(ef[key], ensure_ascii=False)[:400]}")
            ses.d["new"].append("octogift:" + key)
    ses.d["decisions"].append("문어조각:" + str(label))
    ses.d["gives"].append({"item": "문어 색 조각", "options": [s.get("name") for s in sug], "chosen": label,
                           "first": (sug[0].get("name") if sug else "선반"), "first_tier": (sug[0].get("tier") if sug else None),
                           "tiers": [s.get("tier") for s in sug], "tier": g.get("tier"), "real": len(sug) >= 2, "why": why,
                           "weak_shelf": False, "eff": [], "mults": []})


def do_bug1(persona, uid, key, ses: Session):
    """버그 1 재현: 선반이 찬 뒤 찍은 물건(창고 상자로 간 스캔)을 scan_id 로 사람에게 준다."""
    st = ark(uid)
    cap = (st.get("shelf_room") or {}).get("capacity")
    print(f"  [버그1] 선반 {len(st.get('shelf') or [])} / 칸 {cap}, 창고 상자 {len(st.get('stored') or [])}")
    r = scan(uid, code(key), cat(key), show=False)
    w = r.get("where") or {}
    print(f"  [버그1] 찍음 {name(key)}: shelf_slot={r.get('shelf_slot')} swap_offer={'있음' if r.get('swap_offer') else '없음'} stored={len(r.get('stored') or []) if isinstance(r.get('stored'), list) else r.get('stored')}")
    sug = [s for s in w.get("suggest") or [] if isinstance(s.get("target"), dict) and s["target"].get("resident_id")]
    if not sug:
        print("  [버그1] 사람 제안이 없음 → 재현 불가"); return
    g = post("/api/give", {"uid": uid, "scan_id": w["scan_id"], "target": sug[0]["target"]})
    print(f"  [버그1] give → {g.get('_status') or 200} {g.get('detail') or (g.get('reaction') or {}).get('announce')}")
    ses.d["bug1"] = {"shelf_slot": r.get("shelf_slot"), "swap": bool(r.get("swap_offer")),
                     "status": g.get("_status") or 200, "detail": g.get("detail")}


def lines_report(uid):
    """반응 문장 반복: 같은 사람·같은 문장이 몇 번 나왔나, announce == line 은 몇 번인가."""
    p = SCRATCH / f"pt_lines_{uid}.jsonl"
    if not p.exists():
        print("  (문장 기록 없음)"); return
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    same = sum(1 for r in rows if r.get("announce") and r.get("announce") == r.get("line"))
    print(f"  반응 {len(rows)}번 · announce==line {same}번 · line 없음 {sum(1 for r in rows if not r.get('line'))}번")
    by = collections.defaultdict(list)
    for r in rows:
        if r.get("line"):
            by[(r.get("who"), r.get("tier"))].append((r.get("day"), r.get("line")))
    rep = 0
    for (who, tier), ls in sorted(by.items(), key=lambda x: str(x[0])):
        cnt = collections.Counter(l for _, l in ls)
        for l, c in cnt.items():
            if c > 1:
                rep += c - 1
                days = [d for d, x in ls if x == l]
                print(f"   반복 {who}/{tier} ×{c} (날 {days}): 「{l[:60]}」")
    ann = collections.Counter(r.get("announce") for r in rows if r.get("announce"))
    top = [(a[:50], c) for a, c in ann.most_common(6) if c > 1]
    print(f"  같은 사람·같은 줄 반복 합계 {rep} · 관리실 줄 자주 나온 것 {top}")


def first_report(uid):
    """세션마다 첫 제안이 누구였나(같은 사람이 1순위에 몰리나), 약해서 선반으로 밀린 횟수."""
    p = SCRATCH / f"pt_sessions_{uid}.jsonl"
    if not p.exists():
        return
    by = collections.defaultdict(list)
    for line in p.read_text(encoding="utf-8").splitlines():
        s = json.loads(line); by[s.get("day")].append(s)
    for day, ss in sorted(by.items(), key=lambda x: x[0] or 0):
        for i, s in enumerate(ss):
            gv = s["gives"]
            firsts = collections.Counter(g.get("first") for g in gv)
            ff = sum(1 for g in gv if g["chosen"] == g["first"]) / len(gv) if gv else 0
            weak = sum(1 for g in gv if g.get("weak_shelf"))
            top = firsts.most_common(1)[0] if firsts else ("-", 0)
            tiers = dict(collections.Counter(g.get("first_tier") for g in gv))
            print(f"  Day {day} 세션{i + 1}: 「어디로」 {len(gv)} · 첫 제안 그대로 {ff:.0%} · 1순위 최다 {top[0]} {top[1]}/{len(gv)} · 약해서 선반 {weak} · 1순위 등급 {tiers}")


def do_table(persona, uid, ses: Session):
    """받는 저녁·한 상(S23): 저녁 세션이면 물건 하나와 짝 하나를 골라 상을 차린다(A만)."""
    st = ark(uid)
    et = st.get("evening_table")
    if not et:
        print("  [한 상] 저녁이 아님(evening_table null)"); return
    if not et.get("open"):
        print(f"  [한 상] 이미 차림: {json.dumps(et.get('result'), ensure_ascii=False)[:200]}"); return
    items = (et.get("candidates") or {}).get("items") or []
    people = (et.get("candidates") or {}).get("residents") or []
    print(f"  [한 상] {'낮' if et.get('daytime') else '저녁'} 「{et.get('open_ko')}」 「{et.get('table_prompt')}」")
    if not items or len(people) < 2:
        print(f"  [한 상] 후보 부족 items={len(items)} people={len(people)}"); return
    item = items[0] if persona.startswith("B") else next((i for i in items if i.get("today") and i.get("category") == "food"), None) or \
        next((i for i in items if i.get("today")), None) or items[0]
    pf = SCRATCH / f"pt_pairs_{uid}.json"
    used = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else []
    ids = [p["id"] for p in people]
    pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]]
    if not persona.startswith("B"):
        pairs.sort(key=lambda pr: used.count("|".join(sorted(pr))))
    pair = list(pairs[0])
    r = post("/api/table", {"uid": uid, "relic_id": item.get("relic_id"), "seats": [pair]})
    if "_status" in r:
        return
    used.append("|".join(sorted(pair))); pf.write_text(json.dumps(used, ensure_ascii=False), encoding="utf-8")
    talk = [f"{t.get('name')}: {t.get('line')}" for t in r.get("talk") or []]
    print(f"  [한 상] 「{item.get('name')}」 · {r.get('names')} · 신뢰 +{r.get('trust_delta')} 좋아함 {r.get('liked_by')} 같은 짝 {r.get('repeat_pair')} 식량 {r.get('food_paid')}/{r.get('table_store_paid')}")
    for t in talk:
        print(f"     {t}")
    if r.get("promise"):
        print(f"     약속: {r.get('promise')}")
    ses.d["table"] = {"daytime": et.get("daytime"), "item": item.get("name"), "names": r.get("names"), "trust_delta": r.get("trust_delta"),
                      "liked_by": r.get("liked_by"), "repeat_pair": r.get("repeat_pair"), "talk": talk, "talk_key": r.get("talk_key")}
    ses.d["decisions"].append("한 상")
    ses.d["new"].append("table_talk")


def do_wall(persona, uid, ses: Session):
    """6차 기억 벽: 빈 고리가 있으면 선반 물건 하나를 건다(A: 가장 귀한 것, B: 맨 앞 것)."""
    st = ark(uid)
    mw = st.get("memory_wall")
    if not mw:
        print("  [기억 벽] 아직 안 열림"); return
    if mw.get("complete"):
        print("  [기억 벽] 다 참"); return
    shelf = [x for x in st.get("shelf") or [] if x.get("card_id")]
    if not shelf:
        print("  [기억 벽] 걸 물건 없음"); return
    order = ["common", "uncommon", "rare", "epic", "legendary"]
    it = shelf[0] if persona.startswith("B") else max(shelf, key=lambda x: order.index(x.get("rarity")) if x.get("rarity") in order else 0)
    r = post("/api/memory_wall/hang", {"uid": uid, "relic_id": it["card_id"]})
    if "_status" in r:
        return
    print(f"  [기억 벽 걸기] 「{it.get('name') or it.get('relic_name')}」 → 「{r.get('line')}」 complete={r.get('complete')} {r.get('complete_ko') or ''}")
    if r.get("story"):
        print("     뒷이야기:", " / ".join(r["story"])[:500])
    ses.d.setdefault("wall", []).append({"item": it.get("name"), "line": r.get("line"), "complete": r.get("complete")})
    ses.d["decisions"].append("기억 벽")
    ses.d["new"].append("wall_hang")


def s23_report(uid):
    """5차 지표: 하위 종류 고르기, 기색 읽기 적중(날별 수첩 곡선), 첫 제안의 실제 결과, 한 상, 내일의 부탁·의도."""
    p = SCRATCH / f"pt_sessions_{uid}.jsonl"
    if not p.exists():
        return
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    picks = [pk for s in rows for pk in s.get("picks") or []]
    if picks:
        ab = [pk for pk in picks if pk.get("abuse")]
        print(f"  하위 종류 고르기 {len(picks)}번 · 일부러 다르게 {len(ab)}번 {[(pk['item'], pk['pick']) for pk in ab]} · 남들 이름 제안 {sum(1 for pk in picks if pk.get('suggest'))}번")
    good = ("need", "like", "memory", "chain_beat")
    by = collections.defaultdict(list)
    for s in rows:
        by[s.get("day")].append(s)
    print("  날 | 라벨 | 기색 읽기 n · 맞음(필요·좋아함·기억·매듭) · big | 첫 제안 결과 좋음 | 수첩 아는 칸 | 한 상 신뢰 | 내일의 부탁 일치·의도")
    for day, ss in sorted(by.items(), key=lambda x: x[0] or 0):
        gv = [g for s in ss for g in s.get("gives") or []]
        lab = sorted({str(g.get("labels")) for g in gv})
        hint = [g for g in gv if g.get("picked_known") is False]
        hok = sum(1 for g in hint if (g.get("revealed") or {}).get("kind") in good)
        big = sum(1 for g in hint if (g.get("revealed") or {}).get("big"))
        first = [g for g in gv if g["chosen"] == g["first"] and g.get("revealed")]
        fok = sum(1 for g in first if (g.get("revealed") or {}).get("kind") in good)
        nb = ss[-1].get("notebook") or {}
        nbk = f"{sum(v[0] or 0 for v in nb.values())}/{sum(v[1] or 0 for v in nb.values())}" if nb else "-"
        tb = [s.get("table") for s in ss if s.get("table")]
        tc = [s.get("tomorrow_check") for s in ss if s.get("tomorrow_check")]
        it = [g for g in gv if g.get("want")]
        print(f"  {day} | {lab} | {len(hint)} · {hok} · {big} | {fok}/{len(first)} | {nbk} | {[t.get('trust_delta') for t in tb]} | "
              f"{[c.get('matched') for c in tc]} · {[g.get('intent') for g in it]}")


def r6_report(uid):
    """6차 지표: 한 번에 고르기, 이름 다시 붙이기, 부탁한 사람 줄, 낮 한 상, 기억 벽, 굶음, 물 빼기 막힘, 안전, 첫 진입."""
    p = SCRATCH / f"pt_sessions_{uid}.jsonl"
    if not p.exists():
        return
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    q = [x for s in rows for x in s.get("quick") or []]
    print(f"  한 번에 고르기 {len(q)}번 · 보기에 있음 {sum(1 for x in q if x['hit'])} · 기타 {sum(1 for x in q if x['other'])} · 일부러 다르게 {sum(1 for x in q if x['abuse'])}")
    print(f"  이름 다시 붙이기 {[(s.get('day'), x) for s in rows for x in s.get('renames') or []]}")
    print(f"  첫 진입 {[s.get('first_entry') for s in rows if s.get('first_entry')]}")
    good = ("need", "like", "memory", "chain_beat")
    by = collections.defaultdict(list)
    for s in rows:
        by[s.get("day")].append(s)
    drain = []
    dp = SCRATCH / f"pt_drain_{uid}.jsonl"
    if dp.exists():
        drain = [json.loads(x) for x in dp.read_text(encoding="utf-8").splitlines() if x.strip()]
    print("  날 | 기색 n·맞음 | 부탁한 사람 줄에 | 한 상(낮?) | 기억 벽 | 식량·물·사기 | 굶음 | 물 빼기 막힘 | 안전 | 해금 새로")
    for day, ss in sorted(by.items(), key=lambda x: x[0] or 0):
        gv = [g for s in ss for g in s.get("gives") or []]
        hint = [g for g in gv if g.get("picked_known") is False]
        hok = sum(1 for g in hint if (g.get("revealed") or {}).get("kind") in good)
        ar = [a["in_row"] for s in ss for a in s.get("asker_rows") or []]
        tb = [(t.get("trust_delta"), t.get("daytime")) for s in ss for t in [s.get("table")] if t]
        wl = [len(s.get("wall") or []) for s in ss]
        mw = ss[-1].get("memory_wall")
        rs = [(s.get("res") or {}) for s in ss]
        dr = [d for d in drain if d.get("day") == day]
        print(f"  {day} | {len(hint)}·{hok} | {ar} | {tb} | 걸기{sum(wl)} {mw and str(mw.get('filled')) + '/' + str(mw.get('total'))} | "
              f"{[(r.get('food'), r.get('water'), r.get('morale')) for r in rs]} | {any(s.get('hunger') for s in ss)} | {[(d['room'], d['missing']) for d in dr]} | "
              f"{sum(len(s.get('safety') or []) for s in ss)} | {[u for s in ss for u in (s.get('unlocked') or {}).get('new') or []]}")
