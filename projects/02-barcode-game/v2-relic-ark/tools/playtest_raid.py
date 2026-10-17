"""습격 단서 모드 — A(신중한 사람)의 판단(7차 도구 한계 보완).

사람이 하듯이:
  1) 버릇 한 줄을 읽고 떠오르는 대응을 점수로 줄 세운다(불 끄기·반대쪽 불·물 흐리기·전원·가만히·먹이·길 비키기·돌려보내기·올려 보내기·사람 모으기).
  2) 하나 해 보고 미리보기를 본다. 「막을 수 있습니다/지나갑니다」면 멈춘다.
  3) 관문은 통했는데 모자라다(short_of)면 그 갈래를 채운다 — 손: 사람 모으기, 도구: 맞는 도구 설치, 불: 불 켜기.
  4) 관문이 안 통하면(금·방 잃음) 되돌릴 수 있는 것(불·전원·자리)은 되돌리고 다음 후보로.
     행동(act)은 대가를 내고 되돌릴 수 없으니 버릇 문장과 맞을 때만, 낼 수 있을 때만 한다.
  5) 끝까지 안 되면 가장 나았던 배치로 돌아가고, 맞는 소모품이 있으면 접촉 때 쓴다.
기록: scratchpad/pt_raid_<uid>.jsonl
"""
from __future__ import annotations

import json
import re

from playtest_lib import SCRATCH, ark, get, post

GOOD = ("held", "passed")
RANK = {"held": 0, "passed": 0, "scarred": 1, "breached": 2}

# 버릇 문장에서 사람이 떠올릴 법한 대응. 각 항목은 (정규식 묶음 — 모두 맞아야 후보, 가중치)
READ = [
    ("lights_off",      [r"불빛|불을 보면|켜진 창|밝은 창|빛을 보면", r"꺼진|어두운|끄면|어둠"], 3),
    ("light_elsewhere", [r"비치|비친|더 밝게|밝은 쪽|밝게 비치는|불빛 쪽으로"], 3),
    ("cloud_water",     [r"흐린 물|맑은 물|물이 맑|흐려|맑아야"], 3),
    ("quiet",           [r"소리|웅웅|전기|기계음", r"조용|죽이|들리|나는 쪽|나는 방|따라|멈추|찾아옵|기웃"], 2),
    ("stand_still",     [r"움직|발소리|흔들|기척|떨림", r"않|느껴|눌러|가만"], 2),
    ("all_inside",      [r"바깥에 있는|밖에 있는|바깥에 나와|남은 사람|혼자 있는|밖의|문 안쪽"], 2),
    ("feed",            [r"배고|먹이|먹을|굶|먹고"], 2),
    ("make_way",        [r"길", r"걸리|비키|막히|가로막|지나"], 2),
    ("return_it",       [r"되찾|돌려|가져간|제 것|자기 것|잃어버린"], 2),
    ("guide_up",        [r"위로|올라가|위쪽|수면|올라갑", r"불빛|이어진|길"], 2),
    ("people",          [r"여럿|사람이 많|머릿수|떼로|많은 쪽|혼자는"], 2),
]
TOGGLE = {"lights_off", "quiet", "stand_still", "people"}
ACTS = {"light_elsewhere", "cloud_water", "feed", "make_way", "return_it", "guide_up"}
VERB = {"lights_off": "light", "quiet": "power", "stand_still": "station", "people": "station", "all_inside": "tool"}
KO = {"lights_off": "그 방 불 끄기", "light_elsewhere": "반대쪽에 불 켜기", "cloud_water": "물 흐리기", "quiet": "전원 내리기",
      "stand_still": "아무도 움직이지 않기", "all_inside": "밖의 사람 들이기", "feed": "먹이 내주기", "make_way": "길 비키기",
      "return_it": "돌려보내기", "guide_up": "위로 올려 보내기", "people": "그 방에 사람 모으기"}


def read_habit(habit: str) -> list:
    """버릇 → [(대응, 점수)] 높은 순. 하나도 안 맞으면 빈 목록."""
    out = []
    for mv, pats, w in READ:
        if all(re.search(p, habit or "") for p in pats):
            out.append((mv, w * len(pats)))
    out.sort(key=lambda x: -x[1])
    return out


def _preview(uid):
    r = (get(f"/api/raid/today?uid={uid}") or {}).get("raid") or {}
    rd = r.get("ready") or {}
    return {"would": rd.get("would"), "would_ko": rd.get("would_ko"), "ok": (rd.get("gate") or {}).get("ok"),
            "short": rd.get("short_of"), "hint": r.get("hint_action_ko"), "capped": rd.get("capped_week1")}


def _gather(uid, slot):
    st = ark(uid)
    n = 0
    for p in st["residents_list"]:
        if p["id"] in (st.get("outside") or []) or p.get("injured"):
            continue
        r = post("/api/ark/station", {"uid": uid, "resident_id": p["id"], "slot": slot}, quiet=True)
        n += "_status" not in r
    return n


def _apply(uid, mv, slot, opts):
    """대응 하나를 한다. (했는지, 설명)"""
    if mv in VERB:
        post("/api/raid/verb", {"uid": uid, "verb": VERB[mv]}, quiet=True)
    if mv == "lights_off":
        post("/api/ark/light", {"uid": uid, "slot": slot, "on": False}, quiet=True); return True, KO[mv]
    if mv == "quiet":
        post("/api/ark/power", {"uid": uid, "on": False}, quiet=True); return True, KO[mv]
    if mv == "stand_still":
        return True, KO[mv]                                # 하지 않는 것이 대응
    if mv == "people":
        return True, f"{KO[mv]}({_gather(uid, slot)}명)"
    if mv == "all_inside":
        st = ark(uid)
        r = post("/api/ark/recall", {"uid": uid}, quiet=True)
        how = f"밖의 사람 들이기({r.get('recalled') or '밖에 아무도 없음'})"
        if int((st.get("tools") or {}).get("beacon", 0)) > 0:
            opts["use"].append("beacon"); how += " + 귀환 신호기"
        return True, how
    if mv in ACTS:
        post("/api/raid/verb", {"uid": uid, "verb": "act"}, quiet=True)
        r = post("/api/ark/act", {"uid": uid, "action": mv}, quiet=True)
        if "_status" in r:
            return False, f"{KO[mv]} 못 함({r.get('detail')})"
        return True, f"{KO[mv]} (대가 {r.get('paid')})"
    return False, mv


def _revert(uid, mv, slot):
    if mv == "lights_off":
        post("/api/ark/light", {"uid": uid, "slot": slot, "on": True}, quiet=True)
    elif mv == "quiet":
        post("/api/ark/power", {"uid": uid, "on": True}, quiet=True)


def _fix_short(uid, short, slot, cre_id, cur_mv):
    """관문은 통했는데 모자란 갈래를 채운다."""
    if short == "손" and cur_mv != "stand_still":
        return f"손 → 사람 모으기({_gather(uid, slot)}명)"
    if short == "도구":
        st = ark(uid)
        for tid, n in (st.get("tools") or {}).items():
            if int(n) <= 0:
                continue
            r = post("/api/ark/install", {"uid": uid, "tool_id": tid, "slot": slot}, quiet=True)
            if "_status" not in r:
                return f"도구 → {tid} 설치"
        return "도구 → 가진 것 없음"
    if short == "불" and cur_mv != "lights_off":
        post("/api/ark/light", {"uid": uid, "slot": slot, "on": True}, quiet=True)
        return "불 → 그 방 불 켜기"
    return None


def careful_clue(uid, raid):
    """단서 모드 습격을 사람처럼 푼다. 접촉 결과를 돌려준다."""
    slot = raid.get("target_slot")
    cre = raid.get("creature") or {}
    habit = raid.get("habit") or ""
    st = ark(uid)
    acts_have = {o["id"]: o for v in raid.get("verbs") or [] if v.get("id") == "act" for o in v.get("options") or []}
    read = read_habit(habit)
    cand = [mv for mv, _ in read]
    for mv in ("lights_off", "people", "quiet"):          # 글에서 안 떠올라도 공짜로 해 볼 수 있는 것
        if mv not in cand:
            cand.append(mv)
    opts = {"use": []}
    trace, best, seen = [], None, []
    print(f"   [버릇 읽기] 「{habit}」 → 떠오른 대응 {[(KO.get(m, m), s) for m, s in read] or '없음'}")
    hints, hint_moves = [], []
    i = 0
    while i < len(cand):
        mv = cand[i]; i += 1
        if mv in ACTS:
            o = acts_have.get(mv) or {}
            lack = {k: v - int((st.get("resources") or {}).get(k, 0)) for k, v in (o.get("cost") or {}).items() if int((st.get("resources") or {}).get(k, 0)) < v}
            if lack:
                trace.append((KO[mv], "대가 모자람", lack))
                print(f"     생각: {KO[mv]} — 대가 {o.get('cost')} 중 {lack} 모자람, 못 함"); continue
        done, how = _apply(uid, mv, slot, opts)
        if not done:
            trace.append((how, "못 함", None)); continue
        pv = _preview(uid)
        note = None
        if pv["ok"] and pv["would"] not in GOOD and pv["short"]:
            note = _fix_short(uid, pv["short"], slot, cre.get("id"), mv)
            pv = _preview(uid)
        trace.append((how + (f" + {note}" if note else ""), pv["would_ko"], pv["short"]))
        print(f"     시도: {how}{' + ' + note if note else ''} → 미리보기 「{pv['would_ko']}」 관문={'통함' if pv['ok'] else '안 통함'} 모자람={pv['short']}")
        seen.append(RANK.get(pv["would"], 1.5))
        if best is None or RANK.get(pv["would"], 1.5) < RANK.get(best[1], 1.5):
            best = (mv, pv["would"])
        if pv["would"] in GOOD:
            break
        if mv in TOGGLE and not pv["ok"]:
            _revert(uid, mv, slot)                       # 안 통한 토글은 되돌리고 다음으로
        if pv.get("hint") and pv["hint"] not in hints:  # S30 귀띔: 읽고 떠오른 대응을 다음 시도 맨 앞에
            hints.append(pv["hint"])
            hm = [m for m, _ in read_habit(pv["hint"]) if m != mv]
            hint_moves += hm
            print(f"     귀띔: 「{pv['hint']}」 → 떠오른 대응 {[KO.get(m, m) for m in hm] or '없음'}")
            cand = cand[:i] + hm + [m for m in cand[i:] if m not in hm]
    else:
        if best and best[0] in TOGGLE and best[0] not in ("people", "stand_still") and seen and RANK.get(best[1], 1.5) < max(seen):
            _apply(uid, best[0], slot, opts)             # 가장 나았던 배치로 돌아간다
            print(f"     → 가장 나았던 「{KO[best[0]]}」로 돌아감")
    st = ark(uid)
    for tid, n in (st.get("tools") or {}).items():       # 맞는 소모품(봉합 패치·귀환 신호기)은 접촉 때 쓴다
        if int(n) > 0 and tid in ("patch", "beacon") and tid not in opts["use"]:
            opts["use"].append(tid)
    pv = _preview(uid)
    a = post("/api/raid/advance", {"uid": uid, "use": opts["use"] or None})
    res = {k: a.get(k) for k in ("result", "result_ko", "line", "gained")}
    print(f"   최종 미리보기 「{pv['would_ko']}」 · 소모품 {opts['use']} → [접촉 결과] {json.dumps(res, ensure_ascii=False)[:300]}")
    post("/api/ark/light", {"uid": uid, "slot": slot, "on": True}, quiet=True)
    post("/api/ark/power", {"uid": uid, "on": True}, quiet=True)
    with (SCRATCH / f"pt_raid_{uid}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"day": st.get("day"), "creature": cre.get("id"), "habit": habit, "read": read,
                            "hints": hints, "hint_moves": hint_moves, "hint_led": bool(best and best[0] in hint_moves and best[1] in GOOD),
                            "capped": pv.get("capped"),
                            "trace": trace, "final_preview": pv.get("would"), "result": a.get("result")},
                           ensure_ascii=False) + "\n")
    return a
