# -*- coding: utf-8 -*-
"""내 말소리에서 '내가 높은 음을 내면 날 소리'를 합성해 학습 데이터에 보탠다.

원리: 목소리의 음높이(성대 진동수)와 음색(성도 공명 = 포먼트)은 따로 움직인다.
      pyworld 로 음높이만 올리고 포먼트는 그대로 두면, 같은 사람이 높은 음을 낸 소리가 된다.
      이 합성본을 학습에 넣으면 모델이 높은 음에서도 내 음색을 유지하는 법을 배운다.

한계: 실제 고음 발성은 숨과 성대 긴장이 달라 완전히 같지는 않다. 다만 지금처럼
      '높은 음을 아예 모르는' 상태보다는 훨씬 낫다.
"""
import os, glob, shutil, sys, warnings, zipfile
warnings.filterwarnings("ignore")
import numpy as np, librosa, soundfile as sf, pyworld as pw
from pathlib import Path
ROOT = Path(__file__).resolve().parent
SRCDIR = ROOT.parent/"02-barcode-game/media/song/rvc/dataset_v2"
OUT = ROOT.parent/"02-barcode-game/media/song/rvc/dataset_v3"
SR = 44100
SHIFTS = [4, 8, 12]          # +4 반음(약 140Hz), +8(약 175Hz), +12(약 220Hz)

if not SRCDIR.exists(): sys.exit(f"원본 데이터셋 없음: {SRCDIR}")
shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir(parents=True)

def shift_keep_formant(y, sr, semitones):
    y = y.astype(np.float64)
    f0, t = pw.harvest(y, sr, f0_floor=55.0, f0_ceil=600.0)
    sp = pw.cheaptrick(y, f0, t, sr)     # 포먼트 = 내 목소리 지문. 그대로 둔다
    ap = pw.d4c(y, f0, t, sr)
    o = pw.synthesize(f0 * (2 ** (semitones/12)), sp, ap, sr)
    return np.clip(o, -0.99, 0.99).astype(np.float32)

# 1) 원본 그대로 복사
orig = sorted(glob.glob(str(SRCDIR/"*.wav")))
tot = 0.0
for f in orig:
    shutil.copy(f, OUT/os.path.basename(f)); tot += librosa.get_duration(filename=f)
print(f"원본 {len(orig)}개 {tot/60:.1f}분 복사")

# 2) 직접 녹음분(rec_*)만 음높이를 올려 합성. 유튜브 음원은 잡음이 있어 제외
rec = sorted(glob.glob(str(SRCDIR/"rec_*.wav")))
made = 0.0; n = 0
for f in rec:
    y, sr = librosa.load(f, sr=SR, mono=True)
    if len(y) < sr*1.0: continue
    for s in SHIFTS:
        try:
            o = shift_keep_formant(y, sr, s)
        except Exception as e:
            print("건너뜀", os.path.basename(f), s, e); continue
        sf.write(OUT/f"hi{s}_{os.path.basename(f)}", o, sr)
        made += len(o)/sr; n += 1
    print(f"  {os.path.basename(f)} -> +{'/+'.join(map(str,SHIFTS))}반음", flush=True)
print(f"\n고음 합성 {n}개 {made/60:.1f}분 추가")

zp = ROOT.parent/"02-barcode-game/media/song/rvc/ajossi_v3_dataset.zip"
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(glob.glob(str(OUT/"*.wav"))): z.write(f, "ajossi_v3/"+os.path.basename(f))
print(f"합계 {(tot+made)/60:.1f}분, {len(glob.glob(str(OUT/'*.wav')))}클립")
print(f"zip {os.path.getsize(zp)//1024//1024}MB  ->  {zp}")
