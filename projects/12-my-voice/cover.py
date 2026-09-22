# -*- coding: utf-8 -*-
"""노래 파일의 보컬만 내 목소리로 바꾼다.

  python cover.py 노래.mp3                 # 자동 (음역 분석해 반음 조정까지)
  python cover.py 노래.mp3 --pitch -12     # 여성 보컬 -> 남성 (한 옥타브 내림)
  python cover.py 노래.mp3 --keep-parts    # 분리된 보컬/반주 파일도 남김
  python cover.py 노래.mp3 --vocal-gain 1.2 --inst-gain 0.9

처리 순서
  1) Demucs 로 보컬 / 반주 분리
  2) 보컬만 RVC 로 내 목소리로 변환 (필요하면 음높이 이동)
  3) 변환 보컬 + 원래 반주 재믹스

주의: RVC 는 음색만 바꾼다. 원곡의 음정·박자·창법은 그대로 남는다.
"""
import argparse, os, shutil, subprocess, sys, tempfile, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, soundfile as sf, librosa

ROOT = Path(__file__).resolve().parent
FFMPEG_DIR = r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin"
os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
MODEL_NAME = "ajossi_v2_100e_3100s"
MY_F0_MEDIAN = 110.0          # 내 목소리 중앙값(Hz). 측정값 99~121 의 중간
SR = 44100

ap = argparse.ArgumentParser()
ap.add_argument("song", help="노래 파일 (mp3/wav/m4a 등)")
ap.add_argument("-o", "--out", default=None)
ap.add_argument("--pitch", type=int, default=None, help="반음 조정. 생략하면 자동 계산")
ap.add_argument("--index", type=float, default=0.3, help="노래는 낮게. 인덱스는 말소리로 만들어져 노래에 강하게 걸면 음색이 흔들린다")
ap.add_argument("--protect", type=float, default=0.33, help="노래는 0.33 권장")
ap.add_argument("--vocal-gain", type=float, default=1.0)
ap.add_argument("--inst-gain", type=float, default=1.0)
ap.add_argument("--keep-parts", action="store_true", help="분리된 보컬/반주도 남김")
ap.add_argument("--model", default="htdemucs", help="분리 모델 (htdemucs / htdemucs_ft)")
a = ap.parse_args()

song = Path(a.song).resolve()
if not song.exists(): sys.exit(f"파일이 없습니다: {song}")
out = Path(a.out) if a.out else song.with_name(song.stem + "_내목소리.wav")
work = Path(tempfile.mkdtemp(prefix="cover_"))

# ── 1) 보컬 / 반주 분리 ──────────────────────────────────────
print("1/3  보컬 분리 중... (곡 길이의 2~4배 걸립니다)", flush=True)
subprocess.run([sys.executable, "-m", "demucs", "--two-stems", "vocals",
                "-n", a.model, "-o", str(work), "--float32", str(song)],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
sep = next(work.rglob("vocals.wav"), None)
inst = next(work.rglob("no_vocals.wav"), None)
if not sep or not inst: sys.exit("분리 실패 — demucs 출력이 없습니다")

# ── 2) 음높이 차이 계산 ─────────────────────────────────────
pitch = a.pitch
if pitch is None:
    y, _ = librosa.load(str(sep), sr=16000, mono=True)
    y, _ = librosa.effects.trim(y, top_db=30)
    f0 = librosa.yin(y[:16000*60], fmin=60, fmax=800, sr=16000, frame_length=1024)
    rms = librosa.feature.rms(y=y[:16000*60], frame_length=1024)[0]
    k = min(len(f0), len(rms)); v = f0[:k][rms[:k] > np.percentile(rms, 55)]
    med = float(np.median(v)) if len(v) else MY_F0_MEDIAN
    pitch = int(round(12 * np.log2(MY_F0_MEDIAN / med)))
    pitch = max(-24, min(24, pitch))
    print(f"     원곡 보컬 중앙값 {med:.0f}Hz / 내 목소리 {MY_F0_MEDIAN:.0f}Hz  ->  {pitch:+d} 반음", flush=True)

# ── 3) 보컬 변환 ────────────────────────────────────────────
print(f"2/3  보컬을 내 목소리로 변환 중 (pitch {pitch:+d})...", flush=True)
model = str(ROOT / "models" / (MODEL_NAME + ".pth"))
index = str(ROOT / "models" / "ajossi_v2.index")
if not os.path.exists(model): sys.exit(f"모델이 없습니다: {model}")
from infer_rvc_python import BaseLoader
conv = BaseLoader(only_cpu=True, hubert_path=None, rmvpe_path=None)
conv.apply_conf(tag="me", file_model=model, pitch_algo="rmvpe", pitch_lvl=pitch,
                file_index=index, index_influence=a.index, respiration_median_filtering=3,
                envelope_ratio=1.0, consonant_breath_protection=a.protect)
conv([str(sep)], tag_list=["me"], overwrite=False, parallel_workers=1,
     type_output="wav", show_progress=False)
conv_vocal = sep.with_name("vocals_edited.wav")
if not conv_vocal.exists(): sys.exit("보컬 변환 실패")

# ── 4) 재믹스 ───────────────────────────────────────────────
print("3/3  반주와 재믹스 중...", flush=True)
v, _ = librosa.load(str(conv_vocal), sr=SR, mono=False)
i, _ = librosa.load(str(inst), sr=SR, mono=False)
if v.ndim == 1: v = np.stack([v, v])
if i.ndim == 1: i = np.stack([i, i])
n = min(v.shape[1], i.shape[1])
mix = v[:, :n] * a.vocal_gain + i[:, :n] * a.inst_gain
peak = np.abs(mix).max()
if peak > 0.99: mix = mix / peak * 0.99
sf.write(out, mix.T, SR)

if a.keep_parts:
    d = out.with_name(out.stem + "_파트")
    d.mkdir(exist_ok=True)
    shutil.copy(sep, d / "01_원본보컬.wav")
    shutil.copy(conv_vocal, d / "02_변환보컬.wav")
    shutil.copy(inst, d / "03_반주.wav")
    print(f"     파트 저장: {d}")
shutil.rmtree(work, ignore_errors=True)
print(f"\n완성: {out}  ({n/SR:.0f}초)")
