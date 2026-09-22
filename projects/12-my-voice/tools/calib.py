# -*- coding: utf-8 -*-
"""이동량을 실측 보정한다. 모델이 학습 범위 밖 음높이를 끌어내리므로 지정값과 결과가 다르다."""
import os, shutil, warnings
warnings.filterwarnings("ignore")
import numpy as np, librosa
from pathlib import Path
ROOT = Path(__file__).resolve().parent
MDIR = ROOT.parent/"02-barcode-game/media/song/rvc/models"
os.environ["PATH"] = r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin" + os.pathsep + os.environ.get("PATH","")
SRC = str(ROOT/"_cal.wav")
def med(p, fmin=60):
    y,sr = librosa.load(p, sr=16000, mono=True); y,_=librosa.effects.trim(y, top_db=35)
    f0 = librosa.yin(y, fmin=fmin, fmax=900, sr=sr, frame_length=1024)
    r = librosa.feature.rms(y=y, frame_length=1024)[0]; k=min(len(f0),len(r))
    v = f0[:k][r[:k] > np.percentile(r, 60)]
    return float(np.median(v))
src_med = med(SRC)
print(f"원곡 보컬 중앙값 {src_med:.0f}Hz   목표 130~150Hz (내 편안한 노래 음역)\n")
from infer_rvc_python import BaseLoader
conv = BaseLoader(only_cpu=True, hubert_path=None, rmvpe_path=None)
M, IDX = str(MDIR/"ajossi_v2_100e_3100s.pth"), str(MDIR/"ajossi_v2.index")
out = ROOT/"calib"; shutil.rmtree(out, ignore_errors=True); out.mkdir()
print(f"{'지정':>5}{'이론값':>8}{'실제결과':>9}{'차이':>7}")
for pt in (0, -4, -7, +3, +7):
    conv.apply_conf(tag="t", file_model=M, pitch_algo="rmvpe", pitch_lvl=pt, file_index=IDX,
                    index_influence=0.30, respiration_median_filtering=3,
                    envelope_ratio=1.0, consonant_breath_protection=0.33)
    conv([SRC], tag_list=["t"], overwrite=False, parallel_workers=1, type_output="wav", show_progress=False)
    p = SRC.replace(".wav","_edited.wav"); d = out/f"pitch{pt:+d}.wav"
    if os.path.exists(p): shutil.move(p, d)
    got = med(str(d)); theory = src_med*2**(pt/12)
    print(f"{pt:+5d}{theory:8.0f}{got:9.0f}{12*np.log2(got/theory):+7.1f}반음", flush=True)
