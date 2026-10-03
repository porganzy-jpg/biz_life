# -*- coding: utf-8 -*-
"""렌더한 컷(mv/board/S*.png)에 캡션을 붙여 스토리보드 한 장(storyboard.png)과
화자 후보 시트(characters.png)를 만든다."""
import json, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "shots.json").read_text(encoding="utf-8"))
F = lambda s: ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf" if s < 0 else "C:/Windows/Fonts/malgun.ttf", abs(s))
TW, TH, CAP, PAD, COLS = 640, 360, 210, 24, 2
SPEED = "○○○○○"

def mmss(x): return f"{int(x // 60)}:{x % 60:04.1f}"

def wrap(d, xy, text, font, width, fill, gap=4):
    x, y = xy
    for line in textwrap.wrap(text, width):
        d.text((x, y), line, font=font, fill=fill); y += font.size + gap
    return y

shots = CFG["shots"]; rows = (len(shots) + COLS - 1) // COLS
W = COLS * TW + (COLS + 1) * PAD; H = 150 + rows * (TH + CAP + PAD)
im = Image.new("RGB", (W, H), "#f4f2ee"); d = ImageDraw.Draw(im)
d.text((PAD, 28), "「동상이래요」 뮤직비디오 — 러프 스토리보드", font=F(-34), fill="#1d1d1f")
d.text((PAD, 80), f"원곡 {CFG['tempo']} BPM · 1마디 {CFG['bar_s']}초 · 영상 {mmss(CFG['video_end'])} (곡 끝 뒤 8.5초 무음 엔딩)   "
       "● 카메라 속도", font=F(19), fill="#666")
for k, sh in enumerate(shots):
    cx = PAD + (k % COLS) * (TW + PAD); cy = 140 + (k // COLS) * (TH + CAP + PAD)
    fr = Image.open(HERE / "board" / f"{sh['id']}.png").convert("RGB").resize((TW, TH))
    im.paste(fr, (cx, cy)); d.rectangle([cx, cy, cx + TW - 1, cy + TH - 1], outline="#bbb")
    d.rectangle([cx, cy, cx + 250, cy + 34], fill="#1d1d1f")
    d.text((cx + 10, cy + 4), f"{sh['id']}  {mmss(sh['start'])}–{mmss(sh['end'])}", font=F(-19), fill="white")
    y = cy + TH + 8
    sp = "●" * sh["speed"] + SPEED[sh["speed"]:]
    d.text((cx, y), sh["name"], font=F(-22), fill="#1d1d1f")
    d.text((cx + TW - 120, y + 2), sp, font=F(19), fill="#c2410c"); y += 34
    y = wrap(d, (cx, y), "♪ " + sh["music"], F(17), 36, "#555")
    y = wrap(d, (cx, y + 2), "연출  " + sh["action"], F(17), 36, "#222")
    wrap(d, (cx, y + 2), "카메라  " + sh["camera"], F(17), 36, "#1e40af")
im.save(HERE / "storyboard.png", optimize=True)

# 화자 후보 — 하단 워터마크(4.5%) 잘라냄
cands = [("A", "회색 니트 · 둥근 안경", "A_shy_ajossi"), ("B", "후드티 청년 (귀 장식은 오생성)", "B_hoodie"),
         ("C", "헐렁한 정장", "C_suit"), ("D", "카디건 · 수염 아저씨", "D_cardigan")]
cw, ch = 360, 480
sheet = Image.new("RGB", (4 * cw + 5 * PAD, ch + 140), "#f4f2ee"); d = ImageDraw.Draw(sheet)
d.text((PAD, 20), "화자 후보 (AI 컨셉 — Blender 모델링의 기준 그림)", font=F(-26), fill="#1d1d1f")
for k, (tag, label, fn) in enumerate(cands):
    c = Image.open(HERE / "char" / f"{fn}.jpg").convert("RGB")
    c = c.crop((0, 0, c.width, int(c.height * 0.955))).resize((cw, ch))
    x = PAD + k * (cw + PAD); sheet.paste(c, (x, 70))
    d.text((x, 70 + ch + 12), f"{tag}  {label}", font=F(-20), fill="#1d1d1f")
sheet.save(HERE / "characters.png", optimize=True)
print("ok")
