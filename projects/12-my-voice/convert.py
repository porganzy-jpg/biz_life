# -*- coding: utf-8 -*-
"""edge-tts 나레이션을 학습된 내 목소리로 변환한다 (CPU).
사용: .venv/Scripts/python.exe convert.py [파일...] [--pitch N] [--index 0.6]"""
import argparse, glob, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent

ap = argparse.ArgumentParser()
ap.add_argument("files", nargs="*")
ap.add_argument("--pitch", type=int, default=0, help="반음 조정")
ap.add_argument("--index", type=float, default=1.0, help="학습 음색 반영도 0~1 (금속성이면 낮춘다)")
ap.add_argument("--out", default="converted")
a = ap.parse_args()

MODEL_NAME = "ajossi_v2_100e_3100s"
model = str(ROOT/"models"/(MODEL_NAME+".pth"))
index = str(ROOT/"models"/"ajossi_v2.index")
if not model: sys.exit("models/ 에 .pth 가 없습니다")
files = [str(Path(f).resolve()) for f in a.files] or sorted(str(p) for p in (ROOT/"narration_to_convert").glob("*.mp3"))
if not files: sys.exit("변환할 파일이 없습니다")

outdir = ROOT / a.out; outdir.mkdir(exist_ok=True)
print(f"모델 {os.path.basename(model)} / 인덱스 {os.path.basename(index) if index else '없음'}")
print(f"대상 {len(files)}개, pitch={a.pitch}, index={a.index}\n", flush=True)

from infer_rvc_python import BaseLoader
conv = BaseLoader(only_cpu=True, hubert_path=None, rmvpe_path=None)
# 파라미터 스윕(sweep.py) 결과 최적값: 음색 거리 33.3 -> 31.6
conv.apply_conf(tag="me", file_model=model, pitch_algo="rmvpe", pitch_lvl=a.pitch,
                file_index=index or "", index_influence=a.index,
                respiration_median_filtering=3, envelope_ratio=1.0,
                consonant_breath_protection=0.0)
res = conv(files, tag_list=["me"]*len(files), overwrite=False, parallel_workers=1, type_output="wav")

import shutil
for src in (res if isinstance(res, (list, tuple)) else [res]):
    p = src[0] if isinstance(src, (list, tuple)) else src
    if p and os.path.exists(p):
        shutil.move(p, outdir / os.path.basename(p)); print("  ->", os.path.basename(p), flush=True)
print(f"\n완료: {outdir}")
