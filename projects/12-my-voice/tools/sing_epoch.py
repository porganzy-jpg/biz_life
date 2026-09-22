# -*- coding: utf-8 -*-
"""노래에는 어느 에폭이 맞는지 본다. 과학습된 모델이 디테일을 더 간직할 수 있다."""
import os, shutil, glob, warnings
warnings.filterwarnings("ignore")
import numpy as np, librosa
from pathlib import Path
ROOT = Path(__file__).resolve().parent
MDIR = ROOT.parent/"02-barcode-game/media/song/rvc/models"
os.environ["PATH"] = r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin" + os.pathsep + os.environ.get("PATH","")
SRC = str(ROOT/"_voc30.wav")
def mf(p):
    y, sr = librosa.load(p, sr=16000, mono=True)
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64, fmax=8000)
    m = librosa.feature.mfcc(S=librosa.power_to_db(S), n_mfcc=20)[1:]
    r = librosa.feature.rms(y=y)[0]; k=min(len(r), m.shape[1])
    return m[:, :k][:, r[:k] > np.percentile(r, 55)]
refp = sorted(glob.glob(str(ROOT.parent/"02-barcode-game/media/song/rvc/_refchunks/*.wav")))
ref = np.mean([mf(p).mean(axis=1) for p in refp], axis=0)
ref_wob = float(np.mean([np.mean(np.abs(np.diff(mf(p), axis=1))) for p in refp]))
from infer_rvc_python import BaseLoader
conv = BaseLoader(only_cpu=True, hubert_path=None, rmvpe_path=None)
IDX = str(MDIR/"ajossi_v2.index")
out = ROOT/"sing_ep"; shutil.rmtree(out, ignore_errors=True); out.mkdir()
print(f"목표 표현 변화량(실제 목소리) {ref_wob:.2f}\n")
rows=[]
for pth in sorted(glob.glob(str(MDIR/"ajossi_v2_*e_*.pth"))):
    name = Path(pth).stem
    conv.apply_conf(tag="t", file_model=pth, pitch_algo="rmvpe", pitch_lvl=-19, file_index=IDX,
                    index_influence=0.30, respiration_median_filtering=3,
                    envelope_ratio=1.0, consonant_breath_protection=0.33)
    conv([SRC], tag_list=["t"], overwrite=False, parallel_workers=1, type_output="wav", show_progress=False)
    p = SRC.replace(".wav","_edited.wav"); dst = out/(name+".wav")
    if os.path.exists(p): shutil.move(p, dst)
    m = mf(str(dst)); t = float(np.linalg.norm(m.mean(axis=1)-ref)); w = float(np.mean(np.abs(np.diff(m, axis=1))))
    rows.append((t, w, name)); print(f"  {name:<26} 음색 {t:5.1f}   표현변화량 {w:5.2f}", flush=True)
print("\n[음색 가까운 순]")
for t,w,n in sorted(rows): print(f"  {n:<26} 음색 {t:5.1f}  표현변화량 {w:5.2f}")
