# -*- coding: utf-8 -*-
"""Blender 방 렌더(art_raw/rooms3d/*.png) → 톤 통일 후처리 → static/art/rooms3d/*.jpg
   python tools/post_rooms.py            # 전체
   python tools/post_rooms.py pantry     # 일부
채도 -20%, 종이색 6%, 종이 텍스처 18%, 비네트, 약한 샤픈. gen_art.py의 텍스처/비네트 함수를 재사용."""
import sys, pathlib, importlib.util
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.argv = [sys.argv[0], '--post-only', '__none__'] + sys.argv[1:]   # gen_art 모듈 로드 시 작업 실행 방지
spec = importlib.util.spec_from_file_location('gen_art', ROOT / 'tools' / 'gen_art.py'); g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
from PIL import Image, ImageChops, ImageEnhance, ImageFilter

SRC, DST = ROOT / 'art_raw' / 'rooms3d', ROOT / 'static' / 'art' / 'rooms3d'
DST.mkdir(parents=True, exist_ok=True)
only = [a for a in sys.argv[3:]]
for f in sorted(SRC.glob('*.png')):
    if only and not any(o in f.stem for o in only):
        continue
    img = Image.open(f).convert('RGB'); size = img.size
    img = ImageEnhance.Color(img).enhance(0.8)
    img = Image.blend(img, Image.new('RGB', size, (232, 223, 203)), 0.06)
    img = Image.blend(img, ImageChops.multiply(img, g.paper_texture(size)), 0.18)
    dark = ImageChops.multiply(img, Image.new('RGB', size, (70, 66, 60)))
    img = Image.composite(img, dark, g.vignette(size, 0.5))
    img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=30, threshold=3))
    img.save(DST / (f.stem + '.jpg'), 'JPEG', quality=88, optimize=True)
    print('post', f.stem)
