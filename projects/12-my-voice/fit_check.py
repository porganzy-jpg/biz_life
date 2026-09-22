# -*- coding: utf-8 -*-
"""노래가 내 목소리에 얼마나 맞는지 측정한다. (보컬 분리 → 음역·창법 분석)
  python fit_check.py 노래.mp3 [--sec 60]"""
import argparse, os, subprocess, sys, tempfile, shutil, warnings
warnings.filterwarnings("ignore")
import numpy as np, librosa
from pathlib import Path
ROOT = Path(__file__).resolve().parent
os.environ["PATH"] = r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin" + os.pathsep + os.environ.get("PATH","")
FFMPEG = r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"
MY_MED, MY_SING_CENTER = 111.0, 167.0     # 내 말소리 중앙값 / 편안한 노래 중심

ap = argparse.ArgumentParser()
ap.add_argument("song"); ap.add_argument("--sec", type=int, default=60, help="분석 구간 길이(초)")
ap.add_argument("--start", type=int, default=None, help="시작 지점(초). 생략하면 곡 중간")
a = ap.parse_args()
song = Path(a.song).resolve()
if not song.exists(): sys.exit(f"없음: {song}")

work = Path(tempfile.mkdtemp(prefix="fit_"))
dur = float(subprocess.run([FFMPEG.replace("ffmpeg.exe","ffprobe.exe"),"-v","error",
      "-show_entries","format=duration","-of","csv=p=0",str(song)],capture_output=True,text=True).stdout.strip())
start = a.start if a.start is not None else max(0, int(dur/2 - a.sec/2))
clip = work/"clip.wav"
subprocess.run([FFMPEG,"-y","-loglevel","error","-ss",str(start),"-t",str(a.sec),
                "-i",str(song),"-ar","44100","-ac","2",str(clip)], check=True)
print(f"분석 구간 {start}s ~ {start+a.sec}s (전체 {dur:.0f}s)", flush=True)
print("보컬 분리 중...", flush=True)
subprocess.run([sys.executable,"-m","demucs","--two-stems","vocals","-n","htdemucs",
                "-o",str(work),"--float32",str(clip)], check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
voc = next(work.rglob("vocals.wav"), None)
if not voc: sys.exit("분리 실패")

y, sr = librosa.load(str(voc), sr=16000, mono=True)
f0 = librosa.yin(y, fmin=55, fmax=900, sr=sr, frame_length=1024, hop_length=256)
r  = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
k = min(len(f0), len(r)); m = r[:k] > np.percentile(r, 60)
v = f0[:k][m]
if len(v) < 50: sys.exit("보컬이 거의 없습니다")
med, p10, p90 = np.median(v), np.percentile(v,10), np.percentile(v,90)
shift = 12*np.log2(MY_SING_CENTER/med)
span  = 12*np.log2(p90/p10)
# 비브라토·기교: 유성 구간에서 음높이가 얼마나 빠르게 흔들리는가 (반음/프레임)
d = np.abs(np.diff(12*np.log2(np.clip(f0[:k][m], 1, None))))
vib = float(np.median(d[d < 3]))
def note(f): return librosa.hz_to_note(float(f), unicode=False)
print()
print(f"  원곡 보컬 중앙값   {med:5.0f}Hz ({note(med)})")
print(f"  음역 폭            {p10:.0f}~{p90:.0f}Hz ({note(p10)}~{note(p90)}), {span:.1f}반음")
print(f"  필요한 이동량      {shift:+.1f} 반음")
print(f"  기교(음높이 요동)  {vib:.3f} 반음/프레임")
print()
s_shift = max(0, 100 - abs(shift)*5.5)
s_span  = max(0, 100 - max(0, span-14)*6)
s_vib   = max(0, 100 - max(0, vib-0.08)*400)
total = s_shift*0.4 + s_span*0.25 + s_vib*0.35
print(f"  적합도  이동량 {s_shift:3.0f} / 음역폭 {s_span:3.0f} / 창법 {s_vib:3.0f}  →  종합 {total:3.0f}점")
verdict = "매우 적합" if total>=75 else "적합" if total>=60 else "보통" if total>=45 else "부적합"
print(f"  판정: {verdict}")
print(f"\n  변환 명령:  python cover.py \"{song.name}\" --pitch {int(round(shift))}")
shutil.rmtree(work, ignore_errors=True)
