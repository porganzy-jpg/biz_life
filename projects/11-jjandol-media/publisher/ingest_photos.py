# -*- coding: utf-8 -*-
"""폰 사진 덤프 → 날짜별 정리 → 가계부 photos 칸 자동 채우기.

    python ingest_photos.py "D:/phone_dump"          # 실행
    python ingest_photos.py "D:/phone_dump" --dry    # 뭘 할지만 출력
    python ingest_photos.py                          # 기본 입력 폴더 photos/inbox/

하는 일
  1. 입력 폴더의 사진을 전부 읽어 촬영일을 알아낸다 (EXIF → 파일명 → 수정시각 순).
  2. photos/YYYY-MM-DD/NN.jpg 로 복사한다. EXIF 회전을 픽셀에 적용하고 긴 변 1440px로 줄인다.
     (ffmpeg 는 EXIF 회전을 무시하므로 폰 세로 사진을 그대로 넣으면 옆으로 눕는다.)
  3. 같은 사진을 두 번 넣지 않는다 (내용 해시로 판단). 몇 번 다시 돌려도 결과가 같다.
  4. data/ledger.csv 의 해당 날짜 photos 칸을 채운다. 이미 채워진 날은 건드리지 않는다 (--overwrite 로 강제).
  5. 사진은 있는데 가계부 행이 없는 날은 data/photos_unmatched.csv 에 적어 둔다.
     지출·한 끼는 사람이 써야 하는 값이라 0원으로 지어내지 않는다.

photos/manifest.csv 에 원본 경로·해시·날짜 출처가 남는다. 날짜 출처가 mtime 인 사진은
카톡으로 받았거나 편집된 것일 수 있으니 한 번 눈으로 확인하는 게 좋다.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageOps

from config import LEDGER_CSV, ROOT

PHOTOS_DIR = ROOT / "photos"
INBOX_DIR = PHOTOS_DIR / "inbox"
MANIFEST = PHOTOS_DIR / "manifest.csv"
UNMATCHED = ROOT / "data" / "photos_unmatched.csv"

# 쇼츠 8컷 구성이 쓰는 사진은 최대 5장. 그보다 많으면 하루에 걸쳐 고르게 뽑는다.
MAX_PER_DAY = 5
# 켄번스 줌이 1.08이라 이 이상은 화질 이득이 없고 ffmpeg zoompan 만 느려진다.
MAX_EDGE = 1440
JPEG_QUALITY = 88

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
EXIF_DATETIME_ORIGINAL = 0x9003
EXIF_DATETIME = 0x0132
# 삼성 20260830_123456.jpg / 아이폰·안드로이드 IMG_20260830_123456 / 카톡 KakaoTalk_20260830_...
_FILENAME_DATE = re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")


@dataclass
class Shot:
    src: Path
    taken: datetime
    date_source: str        # exif | filename | mtime
    sha1: str


# ── 날짜 알아내기 ─────────────────────────────────────────────

def _exif_datetime(im: Image.Image) -> datetime | None:
    try:
        exif = im.getexif()
        raw = exif.get_ifd(0x8769).get(EXIF_DATETIME_ORIGINAL) or exif.get(EXIF_DATETIME)
    except Exception:
        return None
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip()[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _filename_datetime(p: Path) -> datetime | None:
    m = _FILENAME_DATE.search(p.stem)
    if not m:
        return None
    try:
        d = datetime(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None
    # 시각까지 있으면 하루 안 순서를 맞추는 데 쓴다 (20260830_183012)
    t = re.search(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)", p.stem[m.end():])
    if t and int(t[1]) < 24 and int(t[2]) < 60 and int(t[3]) < 60:
        d = d.replace(hour=int(t[1]), minute=int(t[2]), second=int(t[3]))
    return d


def _open(p: Path) -> Image.Image:
    if p.suffix.lower() in (".heic", ".heif"):
        try:
            import pillow_heif  # noqa: F401  (등록만 하면 Image.open 이 HEIC 를 읽는다)
            pillow_heif.register_heif_opener()
        except ImportError:
            raise RuntimeError(
                f"{p.name}: HEIC 를 읽으려면 `pip install pillow-heif` 가 필요합니다. "
                "아이폰이면 설정 > 카메라 > 포맷을 '높은 호환성'으로 바꾸면 JPG 로 찍힙니다."
            )
    return Image.open(p)


def inspect(p: Path) -> Shot:
    sha1 = hashlib.sha1(p.read_bytes()).hexdigest()
    with _open(p) as im:
        taken = _exif_datetime(im)
    if taken:
        return Shot(p, taken, "exif", sha1)
    taken = _filename_datetime(p)
    if taken:
        return Shot(p, taken, "filename", sha1)
    return Shot(p, datetime.fromtimestamp(p.stat().st_mtime), "mtime", sha1)


# ── 하루 안에서 고르기 ────────────────────────────────────────

def choose(shots: list[Shot], k: int = MAX_PER_DAY) -> list[Shot]:
    """시간순으로 정렬한 뒤 k장을 하루에 걸쳐 고르게 뽑는다.

    앞에서 k장을 자르면 아침 사진만 남는다. 첫 장과 마지막 장은 반드시 포함해서
    마지막 컷(시그니처)이 그날 가장 늦은 사진 — 보통 다 먹고 난 자리 — 이 되게 한다.
    """
    shots = sorted(shots, key=lambda s: s.taken)
    n = len(shots)
    if n <= k:
        return shots
    idx = sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})
    return [shots[i] for i in idx]


# ── 복사 ─────────────────────────────────────────────────────

def _load_manifest() -> dict[str, dict]:
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open(encoding="utf-8-sig", newline="") as f:
        return {r["sha1"]: r for r in csv.DictReader(f)}


def _append_manifest(rows: list[dict]) -> None:
    new = not MANIFEST.exists()
    with MANIFEST.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sha1", "date", "date_source", "src", "dest"])
        if new:
            w.writeheader()
        w.writerows(rows)


def copy_normalized(shot: Shot, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _open(shot.src) as im:
        im = ImageOps.exif_transpose(im)          # 회전을 픽셀에 굽는다
        im.thumbnail((MAX_EDGE, MAX_EDGE))        # 비율 유지, 긴 변 기준
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        im.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)


# ── 가계부 갱신 ──────────────────────────────────────────────

def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def update_ledger(by_day: dict[date, list[Path]], overwrite: bool, dry: bool) -> tuple[list[date], list[date], list[date]]:
    """photos 칸을 채운다. (채운 날, 이미 있어서 건너뛴 날, 가계부에 행이 없는 날) 을 돌려준다."""
    with LEDGER_CSV.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if "photos" not in fields:
        fields.append("photos")

    # 이번 배치가 아니라 photos/ 의 날짜 폴더 전체를 본다.
    # 그래야 (1) 가계부 행을 나중에 추가한 날도 채워지고 (2) 미매칭 목록이 다음 실행 때 안 사라진다.
    on_disk: dict[date, list[Path]] = {}
    for day_dir in PHOTOS_DIR.iterdir() if PHOTOS_DIR.exists() else []:
        try:
            dd = date.fromisoformat(day_dir.name)
        except ValueError:
            continue
        shots_here = sorted(day_dir.glob("*.jpg"))
        if shots_here:
            on_disk[dd] = shots_here
    on_disk.update(by_day)

    filled, skipped, missing = [], [], []
    seen: set[date] = set()
    for r in rows:
        try:
            d = date.fromisoformat((r.get("date") or "").strip())
        except ValueError:
            continue
        seen.add(d)
        if d not in on_disk:
            continue
        if (r.get("photos") or "").strip() and not (overwrite and d in by_day):
            if d in by_day:
                skipped.append(d)
            continue
        r["photos"] = ";".join(_rel(p) for p in on_disk[d])
        filled.append(d)
    missing = sorted(d for d in on_disk if d not in seen)

    if not dry and filled:
        with LEDGER_CSV.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fields})

    if not dry:
        UNMATCHED.parent.mkdir(exist_ok=True)
        with UNMATCHED.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "photos", "todo"])
            for d in missing:
                w.writerow([d.isoformat(), ";".join(_rel(p) for p in on_disk[d]),
                            "ledger.csv 에 이 날짜 행을 추가하고 spend/meal/meal_cost/note 를 채운 뒤 다시 실행"])
    return filled, skipped, missing


# ── 메인 ─────────────────────────────────────────────────────

def run(source: Path, dry: bool, overwrite: bool) -> int:
    if not source.exists():
        print(f"입력 폴더가 없습니다: {source}")
        print("폰 사진을 PC 폴더로 먼저 복사한 뒤 그 경로를 넘기거나, photos/inbox/ 에 넣으세요.")
        return 1

    files = sorted(p for p in source.rglob("*") if p.suffix.lower() in IMAGE_EXTS and p.is_file())
    if not files:
        print(f"사진이 없습니다: {source}")
        return 1
    print(f"입력 {len(files)}장 · {source}")

    known = _load_manifest()
    shots: list[Shot] = []
    errors = 0
    for p in files:
        try:
            s = inspect(p)
        except Exception as e:  # 깨진 파일 하나 때문에 전체를 멈추지 않는다
            print(f"  [건너뜀] {p.name}: {e}")
            errors += 1
            continue
        if s.sha1 in known:
            continue
        known[s.sha1] = {}          # 같은 덤프 안의 복사본(카톡 재전송 등)도 한 장으로
        shots.append(s)
    dup = len(files) - len(shots) - errors
    if dup:
        print(f"이미 들어온 사진 {dup}장 건너뜀 (manifest)")

    grouped: dict[date, list[Shot]] = defaultdict(list)
    for s in shots:
        grouped[s.taken.date()].append(s)

    by_day: dict[date, list[Path]] = {}
    manifest_rows: list[dict] = []
    for d in sorted(grouped):
        day_dir = PHOTOS_DIR / d.isoformat()
        existing = sorted(day_dir.glob("*.jpg")) if day_dir.exists() else []
        slots = MAX_PER_DAY - len(existing)
        picked = choose(grouped[d], slots) if slots > 0 else []
        chosen = {s.sha1 for s in picked}
        # 안 뽑힌 사진도 manifest 에 남긴다 (dest 빈칸). 안 그러면 다음 실행 때 '새 사진'으로 다시 들어온다.
        for s in grouped[d]:
            if s.sha1 not in chosen:
                manifest_rows.append({"sha1": s.sha1, "date": d.isoformat(), "date_source": s.date_source,
                                      "src": str(s.src), "dest": ""})
        if not picked:
            print(f"{d}  {len(grouped[d])}장 — 이미 {len(existing)}장 있어 건너뜀")
            continue
        srcs = ", ".join(s.date_source for s in picked)
        print(f"{d}  {len(grouped[d])}장 중 {len(picked)}장 선택  ({srcs})")
        dests: list[Path] = list(existing)
        for i, s in enumerate(picked, start=len(existing) + 1):
            dest = day_dir / f"{i:02d}.jpg"
            print(f"    {s.src.name} → {_rel(dest)}")
            if not dry:
                copy_normalized(s, dest)
            dests.append(dest)
            manifest_rows.append({"sha1": s.sha1, "date": d.isoformat(), "date_source": s.date_source,
                                  "src": str(s.src), "dest": _rel(dest)})
        by_day[d] = dests

    if not dry and manifest_rows:
        _append_manifest(manifest_rows)
    if not by_day:
        print("새로 넣을 사진이 없습니다.")
        if not dry:
            update_ledger({}, overwrite, dry)   # 미매칭 목록은 매번 다시 계산
        return 0

    filled, skipped, missing = update_ledger(by_day, overwrite, dry)
    print()
    print(f"가계부 photos 칸 채움: {len(filled)}일" + (f"  {', '.join(map(str, filled))}" if filled else ""))
    if skipped:
        print(f"이미 채워져 있어 건너뜀: {len(skipped)}일 (--overwrite 로 덮어쓸 수 있음)")
    if missing:
        print(f"사진은 있는데 가계부 행이 없는 날: {len(missing)}일 → {_rel(UNMATCHED)}")
        for d in missing:
            print(f"    {d}")
    mtime_days = sorted({s.taken.date() for s in shots if s.date_source == "mtime"})
    if mtime_days:
        print(f"[확인 필요] 촬영일을 파일 수정시각으로 추정한 날 {len(mtime_days)}일: "
              f"{', '.join(map(str, mtime_days))} — 카톡 전달본이면 날짜가 틀릴 수 있음")
    if dry:
        print("\n(--dry: 아무것도 쓰지 않았습니다)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", default=str(INBOX_DIR), help="폰 사진을 복사해 둔 폴더 (기본 photos/inbox/)")
    ap.add_argument("--dry", action="store_true", help="복사·가계부 수정 없이 계획만 출력")
    ap.add_argument("--overwrite", action="store_true", help="이미 photos 가 채워진 날도 덮어쓴다")
    a = ap.parse_args(argv)
    return run(Path(a.source), a.dry, a.overwrite)


if __name__ == "__main__":
    sys.exit(main())
