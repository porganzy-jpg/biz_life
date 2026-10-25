"""S37 서버 검증 — 주민 겉모습(appearance: 체형·머리·얼굴).

실행:  python tests/test_s37.py
"""
from __future__ import annotations

import collections
import os
import random
import sys
import tempfile
import traceback
from pathlib import Path

os.environ["RELIC_DEV"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import server as S  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

S.DB = Path(tempfile.mkdtemp()) / "t37.db"
S.DEV_MODE = True
S.NEW_STATE_SEED = "s37"
S.init_db()
C = TestClient(S.app)
RESULTS: list[tuple[bool, str]] = []
S.now_hour = lambda: 10


def ok(cond, msg):
    RESULTS.append((bool(cond), msg))
    print(("OK   " if cond else "FAIL ") + msg)


def t_fields_and_persist():
    """/api/ark core.residents[].appearance · residents_list 에도 · 한 번 정하면 그대로."""
    uid = "dev_s37_a"
    a = C.get(f"/api/ark?uid={uid}").json()
    aps = {rid: r["appearance"] for rid, r in a["core"]["residents"].items()}
    ok(all(ap["body"] in ("a", "b") and ap["hair"] in S.LOOK_HAIRS and ap["face"] in S.LOOK_FACES for ap in aps.values()), f"겉모습 {aps}")
    st = S.load_state(uid)
    ok(all(r.get("appearance") == aps[r["id"]] for r in st["residents_list"]), "residents_list 에 저장")
    again = C.get(f"/api/ark?uid={uid}").json()["core"]["residents"]
    ok(all(again[rid]["appearance"] == ap for rid, ap in aps.items()), "다시 열어도 같다")
    r0 = st["residents_list"][0]
    ok(S.appearance_of(uid, dict(r0, appearance=None)) == aps[r0["id"]], "같은 uid+id → 같은 겉모습(D6)")
    ok(all(aps[r["id"]]["sheet"] == r["role"] + ("_b" if aps[r["id"]]["body"] == "b" else "") for r in st["residents_list"]), "시트 이름 role[_b]")


def t_distribution_independent():
    """많은 사람: 체형 a·b, 머리 6, 얼굴 3이 고르게 · 역할(아이 포함)과 무관 · 18조합 모두 나온다."""
    by_role = collections.defaultdict(collections.Counter)
    bodies, hairs, faces, combos = collections.Counter(), collections.Counter(), collections.Counter(), set()
    for i in range(1200):
        role = S.ROLE_IDS[i % len(S.ROLE_IDS)]
        r = S.make_resident(role, random.Random(i), set(), "u")
        ap = S.appearance_of(f"u{i // 7}", r)
        bodies[ap["body"]] += 1
        hairs[ap["hair"]] += 1
        faces[ap["face"]] += 1
        combos.add((ap["hair"], ap["face"]))
        by_role[role][ap["body"]] += 1
    ok(min(bodies.values()) / sum(bodies.values()) > 0.4, f"체형 {dict(bodies)}")
    ok(len(hairs) == 6 and min(hairs.values()) > 120, f"머리 {dict(hairs)}")
    ok(len(faces) == 3 and min(faces.values()) > 300, f"얼굴 {dict(faces)}")
    ok(len(combos) == 18, f"머리×얼굴 {len(combos)}조합")
    ok(all(min(c.values()) / sum(c.values()) > 0.3 for c in by_role.values()), f"역할마다 체형 섞임(아이 {dict(by_role['kid'])})")


TESTS = [t_fields_and_persist, t_distribution_independent]

if __name__ == "__main__":
    for t in TESTS:
        print(f"\n## {t.__name__} — {(t.__doc__ or '').strip().splitlines()[0] if t.__doc__ else ''}")
        try:
            t()
        except Exception:
            traceback.print_exc()
            RESULTS.append((False, f"{t.__name__} 예외"))
    n = len(RESULTS)
    f = [m for c, m in RESULTS if not c]
    print(f"\n합계 {n} · 통과 {n - len(f)} · 실패 {len(f)}")
    for m in f:
        print("  FAIL", m)
    sys.exit(1 if f else 0)
