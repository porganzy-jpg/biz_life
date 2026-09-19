# -*- coding: utf-8 -*-
"""4개 테마 폴더의 PNG를 한 장의 컨택트 시트로. python make_sheet.py"""
from PIL import Image, ImageDraw, ImageFont
import glob, os
themes = sorted(d for d in glob.glob("*/") if [f for f in glob.glob(d+"*.png") if "_alt" not in f])
cell, pad, label_h = 300, 12, 40
cols = max(len([f for f in glob.glob(t+"*.png") if "_alt" not in f]) for t in themes)
W = pad + cols*(cell+pad); H = pad + len(themes)*(cell+label_h+pad)
sheet = Image.new("RGB",(W,H),(24,26,34)); d = ImageDraw.Draw(sheet)
try: font = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 22); small = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 15)
except: font = small = ImageFont.load_default()
for r,t in enumerate(themes):
    y = pad + r*(cell+label_h+pad); d.text((pad, y), t.strip("/\\"), fill=(255,220,120), font=font)
    for c,f in enumerate(sorted([f for f in glob.glob(t+"*.png") if "_alt" not in f])):
        im = Image.open(f).convert("RGB"); im.thumbnail((cell,cell)); x = pad + c*(cell+pad)
        sheet.paste(im,(x, y+label_h)); d.text((x, y+label_h+cell-20), os.path.basename(f)[:30], fill=(230,230,230), font=small)
sheet.save("CONTACT_SHEET.jpg", quality=90); print("CONTACT_SHEET.jpg", sheet.size, themes)
