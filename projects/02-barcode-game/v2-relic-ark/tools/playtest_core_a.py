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

TIER_A = {"chain_beat": 6, "memory": 6, "need": 5, "decor": 3, "like": 3, "plain": 1, "not_for_me": 0}


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
            print("  [다음에 켜시면(열 때)]", (st["next_visit"] or {}).get("line"))

    def save(self):
        p = SCRATCH / f"pt_sessions_{self.uid}.jsonl"
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(self.d, ensure_ascii=False) + "\n")


def choose(persona, where, ses: Session, rng: random.Random):
    sug = where.get("suggest") or []
    if not sug:
        return "shelf", "제안 없음 → 선반", None
    if persona.startswith("B"):
        if rng.random() < 0.8:
            return sug[0]["target"], "첫 제안 그대로", sug[0]
        return "shelf", "그냥 닫음(선반)", None
    best, bs = None, -9
    for s in sug:
        sc = TIER_A.get(s.get("tier"), 1) + (s.get("value") or 0)
        if s.get("tier") == "decor" and (s.get("tag_have", 0) + 1) >= (s.get("tag_need") or 99):
            sc += 2.5                                        # 꼬리표가 붙는다 → 손님
        rid = (s.get("target") or {}).get("resident_id") if isinstance(s.get("target"), dict) else None
        if rid and ses.given_people[rid]:
            sc -= 3                                          # 오늘 이미 준 사람(×0.5)
        if (s.get("mult") or 1) < 1:
            sc -= 3                                          # 깎인 값(×0.5·×0.3)이면 선반이 낫다
        if sc > bs:
            best, bs = s, sc
    if bs < 2:
        return "shelf", f"제안이 다 약함(best {bs:.1f}) → 선반", None
    return best["target"], f"{best.get('tier')}·{best.get('reason_ko')}", best


def do_loop(persona, uid, keys, ses: Session, rng: random.Random):
    for k in keys:
        r = scan(uid, code(k), cat(k))
        if "_status" in r:
            continue
        c = r.get("card") or {}
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
        print("     「어디로」:", " | ".join(f"{s.get('icon')}:{s.get('name')}({s.get('tier')},{s.get('reason_ko')},v{s.get('value')}{',×'+str(s.get('mult')) if (s.get('mult') or 1) != 1 else ''}"
                                         + (f",꼬리표 {s.get('tag_ko')} {s.get('tag_have')}/{s.get('tag_need')}" if s.get('tag') else '') + ")" for s in sug) or "-", "| 선반", "| compact" if w.get("compact") else "")
        tgt, why, picked = choose(persona, w, ses, rng)
        g = post("/api/give", {"uid": uid, "scan_id": w["scan_id"], "target": tgt})
        if "_status" in g:
            continue
        rid = (tgt or {}).get("resident_id") if isinstance(tgt, dict) else None
        if rid:
            ses.given_people[rid] += 1
        label = "선반" if tgt == "shelf" else (picked or {}).get("name") or json.dumps(tgt, ensure_ascii=False)
        distinct = len({json.dumps(s.get("target"), sort_keys=True) for s in sug})
        real = distinct >= 2 and persona.startswith("A")
        ses.d["gives"].append({"item": name(k), "options": [s.get("name") for s in sug], "chosen": label,
                               "first": (sug[0].get("name") if sug else "선반"), "tier": g.get("tier"), "real": real})
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
    for e in st.get("arc_events") or []:
        if e.get("ask"):
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
        for tag in DECOR_TAGS:
            if room.get("room_id") not in (tag.get("best_rooms") or []) or (have_tags.get(tag["id"]) or {}).get("on"):
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
