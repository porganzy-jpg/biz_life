# -*- coding: utf-8 -*-
"""과하게 매끄러워진 변환 보컬에 '표현 디테일'을 되살린다.
1) 원본 보컬을 포먼트 유지한 채 내 음역으로 내려 소량 섞기
2) 자음보호(protect) 를 올려 숨·마찰음 디테일 보존
목표: 흔들림(표현 변화량)을 실제 목소리 수준(5.2)에 가깝게, 음색은 유지"""
import os, shutil, glob, warnings
warnings.filterwarnings("ignore")
import numpy as np, librosa, soundfile as sf, pyworld as pw
from pathlib import Path
ROOT = Path(__file__).resolve().parent
os.environ["PATH"] = r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin" + os.pathsep + os.environ.get("PATH","")
SRC, SR = str(ROOT/"_voc30.wav"), 44100

def mfcc_frames(p):
    y, sr = librosa.load(p, sr=16000, mono=True)
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64, fmax=8000)
    m = librosa.feature.mfcc(S=librosa.power_to_db(S), n_mfcc=20)[1:]
    r = librosa.feature.rms(y=y)[0]; k=min(len(r), m.shape[1])
    return m[:, :k][:, r[:k] > np.percentile(r, 55)]
refp = sorted(glob.glob(str(ROOT.parent/"02-barcode-game/media/song/rvc/_refchunks/*.wav")))
ref = np.mean([mfcc_frames(p).mean(axis=1) for p in refp], axis=0)
ref_wob = float(np.mean([np.mean(np.abs(np.diff(mfcc_frames(p), axis=1))) for p in refp]))
def score(p):
    m = mfcc_frames(p)
    return float(np.linalg.norm(m.mean(axis=1)-ref)), float(np.mean(np.abs(np.diff(m, axis=1))))

# 원본 보컬을 포먼트 유지한 채 -19 반음 내린다 (섞을 재료)
shifted = str(ROOT/"_orig_shift19.wav")
if not os.path.exists(shifted):
    y, sr = librosa.load(SRC, sr=SR, mono=True); y = y.astype(np.float64)
    f0, t = pw.harvest(y, sr, f0_floor=55.0, f0_ceil=900.0)
    sp = pw.cheaptrick(y, f0, t, sr); ap = pw.d4c(y, f0, t, sr)
    o = pw.synthesize(f0*(2**(-19/12)), sp, ap, sr)
    sf.write(shifted, np.clip(o,-0.99,0.99).astype(np.float32), sr)

from infer_rvc_python import BaseLoader
conv = BaseLoader(only_cpu=True, hubert_path=None, rmvpe_path=None)
MODEL, IDX = str(ROOT/"models/ajossi_v2_100e_3100s.pth"), str(ROOT/"models/ajossi_v2.index")
out = ROOT/"blend"; shutil.rmtree(out, ignore_errors=True); out.mkdir()
print(f"목표 흔들림(실제 목소리) {ref_wob:.2f}\n[비교]")
rows=[]
for prot in (0.33, 0.60):
    conv.apply_conf(tag="t", file_model=MODEL, pitch_algo="rmvpe", pitch_lvl=-19, file_index=IDX,
                    index_influence=0.30, respiration_median_filtering=3,
                    envelope_ratio=1.0, consonant_breath_protection=prot)
    conv([SRC], tag_list=["t"], overwrite=False, parallel_workers=1, type_output="wav", show_progress=False)
    base = out/f"conv_p{prot}.wav"; shutil.move(SRC.replace(".wav","_edited.wav"), base)
    cv, _ = librosa.load(str(base), sr=SR, mono=True)
    ov, _ = librosa.load(shifted, sr=SR, mono=True)
    n = min(len(cv), len(ov))
    for mix in (0.0, 0.12, 0.22, 0.35):
        z = cv[:n]*(1-mix*0.5) + ov[:n]*mix
        pk = np.abs(z).max()
        if pk > 0.99: z = z/pk*0.99
        p = out/f"protect{prot}_원본{int(mix*100)}%.wav"
        sf.write(p, z, SR)
        t, w = score(str(p))
        rows.append((abs(w-ref_wob), w, t, f"protect {prot} / 원본 {int(mix*100)}%"))
        print(f"  protect {prot:.2f} / 원본 {int(mix*100):>2}%   음색 {t:5.1f}   흔들림 {w:5.2f}", flush=True)
print("\n[실제 목소리의 표현 변화량에 가까운 순]")
for d,w,t,n in sorted(rows)[:5]: print(f"  {n:<28} 흔들림 {w:5.2f} (목표 {ref_wob:.2f})   음색 {t:5.1f}")
