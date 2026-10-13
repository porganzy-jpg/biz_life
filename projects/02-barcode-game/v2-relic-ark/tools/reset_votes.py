"""★ 개발 전용 — 전역 투표·집계에서 시험·플레이테스트 방주의 표를 지운다(실제 사람 테스트 전에 한 번).

기본은 **미리 보기**(아무것도 지우지 않는다). 지우려면 --apply.
  python tools/reset_votes.py                      # 무엇이 지워질지 센다
  python tools/reset_votes.py --apply              # 지운다(지우기 전 DB 사본을 relic_ark.db.bak-<시각> 으로 남긴다)
  python tools/reset_votes.py --db path/to.db      # 다른 DB
  python tools/reset_votes.py --extra r6dry,qa_    # 더 뺄 uid 앞머리

지우는 곳: subtype_votes(다른 방주 이름), family_votes(가문 갈래 투표).
기준: server.vote_uid_excluded(uid)(시험 uid 꼴 — pt*, r4dry*, r5dry*, smoke*, s22check*, dev_*, devS*, test*, scn_*, … )
     + 개발 서버에서 만든 방주(arks.state 의 test_ark=true) + --extra 앞머리.
scans·arks·logs 는 건드리지 않는다(개인 놀이 기록은 그대로).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "relic_ark.db"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--extra", default="")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    import server as S                                  # 기준(앞머리 목록)을 서버와 같게 쓴다
    S.VOTES_EXCLUDE_TEST = True
    extra = tuple(x.strip().lower() for x in a.extra.split(",") if x.strip())
    con = sqlite3.connect(a.db)
    con.row_factory = sqlite3.Row
    test_arks = set()
    for r in con.execute("SELECT uid, state FROM arks"):
        try:
            if json.loads(r["state"]).get("test_ark"):
                test_arks.add(r["uid"])
        except (json.JSONDecodeError, TypeError):
            pass

    def drop(uid: str) -> bool:
        return S.vote_uid_excluded(uid) or uid in test_arks or str(uid).lower().startswith(extra or ("\0",))

    plan = {}
    for table in ("subtype_votes", "family_votes"):
        try:
            uids = [r["uid"] for r in con.execute(f"SELECT DISTINCT uid FROM {table}")]
        except sqlite3.OperationalError:
            continue
        bad = [u for u in uids if drop(u)]
        n = sum(con.execute(f"SELECT COUNT(*) FROM {table} WHERE uid=?", (u,)).fetchone()[0] for u in bad)
        plan[table] = {"uids": len(bad), "rows": n, "keep_uids": len(uids) - len(bad), "sample": sorted(bad)[:10]}
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if not a.apply:
        print("미리 보기만 했다. 지우려면 --apply")
        return 0
    bak = f"{a.db}.bak-{int(time.time())}"
    con.close()
    shutil.copy2(a.db, bak)
    con = sqlite3.connect(a.db)
    for table in plan:
        uids = [r[0] for r in con.execute(f"SELECT DISTINCT uid FROM {table}")]
        for u in uids:
            if drop(u):
                con.execute(f"DELETE FROM {table} WHERE uid=?", (u,))
    con.commit()
    con.close()
    print(f"지웠다. 사본: {bak}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
