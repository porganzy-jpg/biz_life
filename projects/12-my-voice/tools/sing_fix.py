# -*- coding: utf-8 -*-
"""노래 녹음 없이 음색 안정성을 올리는 방법들을 비교한다.
흔들림 지표 = 긴 음 구간에서 MFCC 가 프레임마다 얼마나 요동치는가. 낮을수록 안정적."""
import os, shutil, warnings
warnings.filterwarnings("ignore")
import numpy as np, librosa, soundfile as sf, pyworld as pw
from pathlib import Path
ROOT = Path(__file__).resolve().parent
os.environ["PATH"] = r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin" + os.pathsep + os.environ.get("PATH","")
SRC, SR = str(ROOT/"_voc30.wav"), 44100

def shift_keep_formant(inp, outp, semitones):
    """성도 공명(포먼트)은 그대로 두고 음높이만 바꾼다. 극단적 이동에서도 목소리가 얇아지지 않는다."""
    y, sr = librosa.load(inp, sr=SR, mono=True)
    y = y.astype(np.float64)
    f0, t = pw.harvest(y, sr, f0_floor=55.0, f0_ceil=900.0)
    sp = pw.cheaptrick(y, f0, t, sr)          # 스펙트럼 포락선 = 포먼트 (건드리지 않음)
    ap = pw.d4c(y, f0, t, sr)
    out = pw.synthesize(f0 * (2 ** (semitones/12)), sp, ap, sr)
    sf.write(outp, np.clip(out, -0.99, 0.99).astype(np.float32), sr)

def mfcc_frames(p):
    y, sr = librosa.load(p, sr=16000, mono=True)
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64, fmax=8000)
    m = librosa.feature.mfcc(S=librosa.power_to_db(S), n_mfcc=20)[1:]
    r = librosa.feature.rms(y=y)[0]; k = min(len(r), m.shape[1])
    keep = r[:k] > np.percentile(r, 55)
    return m[:, :k][:, keep]
def tone_and_wobble(p, ref):
    m = mfcc_frames(p)
    tone = float(np.linalg.norm(m.mean(axis=1) - ref))
    wob  = float(np.mean(np.abs(np.diff(m, axis=1))))    # 프레임 간 변화량 = 흔들림
    return tone, wob

import glob
refp = sorted(glob.glob(str(ROOT.parent/"02-barcode-game/media/song/rvc/_refchunks/*.wav")))
ref = np.mean([mfcc_frames(p).mean(axis=1) for p in refp], axis=0)
ref_wob = float(np.mean([np.mean(np.abs(np.diff(mfcc_frames(p), axis=1))) for p in refp]))
orig_tone, orig_wob = tone_and_wobble(SRC, ref)
print(f"실제 내 목소리   흔들림 {ref_wob:5.2f}")
print(f"원곡 보컬        음색 {orig_tone:5.1f}  흔들림 {orig_wob:5.2f}\n")

from infer_rvc_python import BaseLoader
conv = BaseLoader(only_cpu=True, hubert_path=None, rmvpe_path=None)
MODEL, IDX = str(ROOT/"models/ajossi_v2_100e_3100s.pth"), str(ROOT/"models/ajossi_v2.index")
def run(src, pitch, idx, prot, resp=3):
    conv.apply_conf(tag="t", file_model=MODEL, pitch_algo="rmvpe", pitch_lvl=pitch, file_index=IDX,
                    index_influence=idx, respiration_median_filtering=resp,
                    envelope_ratio=1.0, consonant_breath_protection=prot)
    conv([src], tag_list=["t"], overwrite=False, parallel_workers=1, type_output="wav", show_progress=False)
    p = src.replace(".wav", "_edited.wav")
    return p if os.path.exists(p) else None

out = ROOT/"singfix"; shutil.rmtree(out, ignore_errors=True); out.mkdir()
rows = []
def record(name, path):
    dst = out/(name + ".wav"); shutil.move(path, dst)
    t, w = tone_and_wobble(str(dst), ref)
    rows.append((w, t, name)); print(f"  {name:<34} 음색 {t:5.1f}   흔들림 {w:5.2f}", flush=True)

print("[비교]")
record("A_현재_RVC만_-19", run(SRC, -19, 0.30, 0.33))
record("B_숨필터강화_resp7", run(SRC, -19, 0.30, 0.33, resp=7))
pre = str(ROOT/"_pre19.wav"); shift_keep_formant(SRC, pre, -19)
record("C_포먼트유지_사전이동19_RVC0", run(pre, 0, 0.30, 0.33))
pre12 = str(ROOT/"_pre12.wav"); shift_keep_formant(SRC, pre12, -12)
record("D_사전이동12_RVC-7", run(pre12, -7, 0.30, 0.33))
print("\n[흔들림 적은 순]")
for w, t, n in sorted(rows): print(f"  {n:<34} 흔들림 {w:5.2f}  음색 {t:5.1f}")
