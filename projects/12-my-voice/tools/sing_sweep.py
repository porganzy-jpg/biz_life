# -*- coding: utf-8 -*-
"""노래 변환 설정 탐색. 음정 추적 정확도 + 음색을 함께 잰다.
음정 추적 오차 = (변환 결과의 음높이) 와 (원곡 음높이 + 이동량) 의 차이. 작을수록 음정이 안정적."""
import glob, os, shutil, warnings
warnings.filterwarnings("ignore")
import numpy as np, librosa
from pathlib import Path
ROOT = Path(__file__).resolve().parent
os.environ["PATH"] = r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin" + os.pathsep + os.environ.get("PATH","")
SRC = str(ROOT/"_voc30.wav")

def f0_track(path, sr=16000):
    y,_ = librosa.load(path, sr=sr, mono=True)
    f0 = librosa.yin(y, fmin=55, fmax=900, sr=sr, frame_length=1024, hop_length=256)
    r  = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
    k = min(len(f0), len(r))
    return f0[:k], r[:k]

def mfcc_vec(path):
    y,sr = librosa.load(path, sr=16000, mono=True); y,_=librosa.effects.trim(y, top_db=30)
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64, fmax=8000)
    m = librosa.feature.mfcc(S=librosa.power_to_db(S), n_mfcc=20)[1:]
    r = librosa.feature.rms(y=y)[0]; k=min(len(r), m.shape[1]); m=m[:,:k][:,r[:k]>np.percentile(r,45)]
    return m.mean(axis=1)

ref_voice = np.mean([mfcc_vec(p) for p in sorted(glob.glob(str(ROOT.parent/"02-barcode-game/media/song/rvc/_refchunks/*.wav")))], axis=0)
src_f0, src_r = f0_track(SRC)
voiced = src_r > np.percentile(src_r, 55)

from infer_rvc_python import BaseLoader
conv = BaseLoader(only_cpu=True, hubert_path=None, rmvpe_path=None)
MODEL = str(ROOT/"models/ajossi_v2_100e_3100s.pth")
IDX   = str(ROOT/"models/ajossi_v2.index")
# (pitch, index, protect, f0알고리즘)
CASES = [
    (-19, 1.00, 0.00, "rmvpe"),   # 현재 설정
    (-12, 0.30, 0.33, "rmvpe"),
    (-19, 0.30, 0.33, "rmvpe"),
    (-19, 0.30, 0.50, "rmvpe"),
    (-15, 0.30, 0.33, "rmvpe"),
]
print(f"{'pitch':>6}{'index':>7}{'protect':>8}{'f0':>8}{'음정오차':>10}{'음색':>7}")
rows=[]
for pt, ix, pr, alg in CASES:
    out = ROOT/"sing"/f"p{pt}_i{ix}_pr{pr}_{alg}"; shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    conv.apply_conf(tag="t", file_model=MODEL, pitch_algo=alg, pitch_lvl=pt, file_index=IDX,
                    index_influence=ix, respiration_median_filtering=3,
                    envelope_ratio=1.0, consonant_breath_protection=pr)
    conv([SRC], tag_list=["t"], overwrite=False, parallel_workers=1, type_output="wav", show_progress=False)
    prod = str(ROOT/"_voc30_edited.wav"); dst = out/"out.wav"
    if os.path.exists(prod): shutil.move(prod, dst)
    o_f0, o_r = f0_track(str(dst))
    n = min(len(src_f0), len(o_f0))
    m = voiced[:n] & (o_r[:n] > np.percentile(o_r, 40)) & (o_f0[:n] > 50) & (src_f0[:n] > 50)
    # 반음 단위 오차: 목표는 원곡 음높이를 pt 반음 이동한 값
    target = src_f0[:n][m] * (2 ** (pt/12))
    err = np.abs(12*np.log2(o_f0[:n][m] / target))
    pitch_err = float(np.median(err))
    tone = float(np.linalg.norm(mfcc_vec(str(dst)) - ref_voice))
    rows.append((pitch_err, tone, pt, ix, pr, alg))
    print(f"{pt:6d}{ix:7.2f}{pr:8.2f}{alg:>8}{pitch_err:10.2f}{tone:7.1f}", flush=True)
print("\n[음정이 안정적인 순]")
for pe,tn,pt,ix,pr,alg in sorted(rows): print(f"  pitch {pt:+3d} / index {ix:.2f} / protect {pr:.2f} / {alg:6s}  음정오차 {pe:.2f}반음  음색 {tn:.1f}")
