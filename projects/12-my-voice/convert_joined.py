# -*- coding: utf-8 -*-
"""짧은 문장의 음색 흔들림을 줄인다.
문장들을 무음으로 이어붙여 '한 덩어리'로 변환한 뒤 다시 잘라낸다.
RVC가 참고할 음성 맥락이 길어져 짧은 문장의 품질이 올라간다."""
import glob, json, os, shutil, subprocess, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np, librosa, soundfile as sf
from pathlib import Path
ROOT = Path(__file__).resolve().parent
FFDIR = r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin"
os.environ["PATH"] = FFDIR + os.pathsep + os.environ.get("PATH", "")
FFMPEG = os.path.join(FFDIR, "ffmpeg.exe")
GAP = 0.6          # 문장 사이 무음(초). 되자를 때의 기준점이 된다
SR  = 44100

srcs = sorted(str(p) for p in (ROOT/"narration_to_convert").glob("*.mp3"))
if not srcs: sys.exit("narration_to_convert/ 가 비었습니다")

# 1) 이어붙이기 (각 문장의 시작 위치를 기록)
parts, marks, t = [], [], 0.0
sil = np.zeros(int(GAP*SR), dtype=np.float32)
for i, s in enumerate(srcs):
    y, _ = librosa.load(s, sr=SR, mono=True)
    if i: parts.append(sil); t += GAP
    marks.append((t, t+len(y)/SR)); parts.append(y); t += len(y)/SR
joined = ROOT/"_joined.wav"
sf.write(joined, np.concatenate(parts), SR)
print(f"이어붙임 {len(srcs)}문장 {t:.1f}초")

# 2) 통째로 변환
from infer_rvc_python import BaseLoader
conv = BaseLoader(only_cpu=True, hubert_path=None, rmvpe_path=None)
conv.apply_conf(tag="me", file_model=str(ROOT/"models/ajossi_v2_100e_3100s.pth"),
                pitch_algo="rmvpe", pitch_lvl=-1, file_index=str(ROOT/"models/ajossi_v2.index"),
                index_influence=1.0, respiration_median_filtering=3,
                envelope_ratio=1.0, consonant_breath_protection=0.0)
conv([str(joined)], tag_list=["me"], overwrite=False, parallel_workers=1,
     type_output="wav", show_progress=False)
out_joined = ROOT/"_joined_edited.wav"
if not out_joined.exists(): sys.exit("변환 실패")

# 3) 기록해둔 위치로 되자르기 (앞뒤 40ms 여유 + 페이드)
y, sr = librosa.load(str(out_joined), sr=SR, mono=True)
outdir = ROOT/"converted_joined"; shutil.rmtree(outdir, ignore_errors=True); outdir.mkdir()
pad, fade = 0.04, int(0.01*SR)
for (a, b), s in zip(marks, srcs):
    i0, i1 = max(0, int((a-pad)*sr)), min(len(y), int((b+pad)*sr))
    seg = y[i0:i1].copy()
    if len(seg) > 2*fade:
        seg[:fade] *= np.linspace(0, 1, fade); seg[-fade:] *= np.linspace(1, 0, fade)
    sf.write(outdir/(Path(s).stem + "_edited.wav"), seg, sr)
print(f"되자름 -> {outdir.name}/  ({len(srcs)}개)")
