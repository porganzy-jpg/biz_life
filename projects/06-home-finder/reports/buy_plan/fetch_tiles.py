"""매물·땅 좌표 범위의 OpenStreetMap 타일을 받아 WebP로 줄여 tiles/ 에 저장한다.

아티팩트 페이지는 외부 이미지를 불러올 수 없어서 타일을 페이지 안에 넣어야 한다.
  z11: 전체 후보 범위 · z12: 수도권 · z13: 서울 핵심부 (약 260장, WebP 3MB)
OSM 타일 정책에 맞춰 식별 가능한 User-Agent와 0.2초 간격을 쓴다. CARTO는 키 없이 받으면
'API KEY REQUIRED' 이미지만 돌려주니 쓰지 않는다.
"""
import io
import json
import math
import sys
import time
from pathlib import Path

import requests
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
SP = Path(__file__).parent
OUT = SP / "tiles"
OUT.mkdir(exist_ok=True)

A = json.loads((SP / "apts.json").read_text(encoding="utf-8"))
L = json.loads((SP / "land.json").read_text(encoding="utf-8"))
xs = [o["x"] for o in A + L]
ys = [o["y"] for o in A + L]


def tile(lon, lat, z):
    n = 2 ** z
    r = math.radians(lat)
    return int((lon + 180) / 360 * n), int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n)


PLAN = [  # (zoom, (서, 북, 동, 남))
    (11, (min(xs) - .05, max(ys) + .05, max(xs) + .05, min(ys) - .05)),
    (12, (126.60, 37.80, 127.35, 37.22)),
    (13, (126.76, 37.70, 127.20, 37.43)),
]
jobs = []
for z, (w, n, e, s) in PLAN:
    x0, y0 = tile(w, n, z)
    x1, y1 = tile(e, s, z)
    jobs += [(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]

S = requests.Session()
S.headers["User-Agent"] = "HomeFinder-personal-report/1.0 (one-off static map for private page)"
for i, (z, x, y) in enumerate(jobs, 1):
    p = OUT / f"{z}_{x}_{y}.webp"
    if p.exists():
        continue
    r = S.get(f"https://tile.openstreetmap.org/{z}/{x}/{y}.png", timeout=20)
    r.raise_for_status()
    buf = io.BytesIO()
    Image.open(io.BytesIO(r.content)).convert("RGB").save(buf, "WEBP", quality=62, method=6)
    p.write_bytes(buf.getvalue())
    time.sleep(0.2)
print(len(jobs), "tiles,", round(sum(f.stat().st_size for f in OUT.glob("*.webp")) / 1e6, 2), "MB")
