# -*- coding: utf-8 -*-
"""아이소 타일 후처리(알파 유지): art_raw/iso/*.png → static/art/iso/*.png + tile_meta.json 복사"""
import sys, pathlib, shutil, importlib.util
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.argv = [sys.argv[0], '--post-only', '__none__'] + sys.argv[1:]
spec = importlib.util.spec_from_file_location('gen_art', ROOT / 'tools' / 'gen_art.py'); g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
from PIL import Image, ImageChops, ImageEnhance, ImageFilter
SRC, DST = ROOT / 'art_raw' / 'iso', ROOT / 'static' / 'art' / 'iso'; DST.mkdir(parents=True, exist_ok=True)
only = sys.argv[3:]
for f in sorted(SRC.glob('*.png')):
    if only and not any(o in f.stem for o in only): continue
    im = Image.open(f).convert('RGBA'); a = im.getchannel('A'); rgb = im.convert('RGB'); size = rgb.size
    rgb = ImageEnhance.Color(rgb).enhance(0.82)
    rgb = Image.blend(rgb, Image.new('RGB', size, (232, 223, 203)), 0.05)
    rgb = Image.blend(rgb, ImageChops.multiply(rgb, g.paper_texture(size)), 0.16)
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.0, percent=35, threshold=3))
    out = rgb.convert('RGBA'); out.putalpha(a); out.save(DST / f.name, 'PNG', optimize=True); print('post', f.stem)
shutil.copy(SRC / 'tile_meta.json', DST / 'tile_meta.json'); print('meta copied')
