# -*- coding: utf-8 -*-
"""변환된 보컬을 '완성된 곡'처럼 다듬는다. (커버 영상들이 하는 후반 작업)

  python mix.py songs/신곡_내목소리_파트          # 파트 폴더를 넣으면 알아서
  python mix.py -v 보컬.wav -i 반주.wav -o 완성.wav
  python mix.py ... --reverb 0.28 --comp 6        # 공간감 / 압축 강도

처리 단계
  1) 하이패스 85Hz   — 웅웅거리는 저역 제거
  2) EQ              — 250Hz 뭉침 감쇠, 3.5kHz 또렷함 보강, 11kHz 공기감
  3) 디에서          — 치찰음(스, 츠) 완화
  4) 컴프레서        — 약한 구간을 끌어올려 '숨이 모자란' 느낌 해소
  5) 리버브          — 공간감 부여로 '갑갑함' 해소 (합성 임펄스 응답 사용)
  6) 리미터          — 최종 음량 정리
"""
import argparse, os, subprocess, sys, tempfile, shutil
from pathlib import Path
import numpy as np, soundfile as sf

ROOT = Path(__file__).resolve().parent
FFDIR = r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin"
os.environ["PATH"] = FFDIR + os.pathsep + os.environ.get("PATH", "")
FFMPEG = os.path.join(FFDIR, "ffmpeg.exe")
SR = 44100

ap = argparse.ArgumentParser()
ap.add_argument("parts", nargs="?", help="cover.py --keep-parts 로 만든 _파트 폴더")
ap.add_argument("-v", "--vocal"); ap.add_argument("-i", "--inst"); ap.add_argument("-o", "--out")
ap.add_argument("--reverb", type=float, default=0.25, help="리버브 섞는 양 0~0.5")
ap.add_argument("--comp", type=float, default=5.0, help="컴프레서 비율 (클수록 음량이 고르게)")
ap.add_argument("--vocal-gain", type=float, default=1.0)
ap.add_argument("--inst-gain", type=float, default=0.92)
a = ap.parse_args()

if a.parts:
    d = Path(a.parts)
    voc  = d/"02_변환보컬.wav"; inst = d/"03_반주.wav"
    out  = Path(a.out) if a.out else d.parent/(d.name.replace("_파트","") + "_믹싱.wav")
else:
    if not (a.vocal and a.inst): sys.exit("파트 폴더 또는 -v/-i 를 지정하세요")
    voc, inst = Path(a.vocal), Path(a.inst)
    out = Path(a.out) if a.out else voc.with_name(voc.stem + "_믹싱.wav")
for p in (voc, inst):
    if not p.exists(): sys.exit(f"없음: {p}")

tmp = Path(tempfile.mkdtemp(prefix="mix_"))

# ── 리버브용 임펄스 응답 합성 (감쇠하는 잡음 + 초기 반사) ──
rng = np.random.default_rng(7)
L = int(1.4 * SR)
t = np.arange(L) / SR
ir = rng.normal(0, 1, (L, 2)) * np.exp(-t * 4.2)[:, None]      # 잔향 꼬리
for delay_ms, g in ((17, .5), (23, .42), (31, .34), (43, .26)): # 초기 반사
    i = int(delay_ms / 1000 * SR)
    if i < L: ir[i] += g
ir[: int(0.006 * SR)] *= np.linspace(0, 1, int(0.006 * SR))[:, None]
ir /= np.abs(ir).max() * 3.0
irp = tmp / "ir.wav"; sf.write(irp, ir.astype(np.float32), SR)

chain = (
    "[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
    "highpass=f=85,"                                             # 1) 저역 정리
    "equalizer=f=250:t=q:w=1.2:g=-3.5,"                          # 2) 뭉침 감쇠
    "equalizer=f=3500:t=q:w=1.0:g=2.5,"                          #    또렷함
    "equalizer=f=11000:t=q:w=0.9:g=2.0,"                         #    공기감
    "deesser=i=0.45:m=0.5:f=0.5,"                                # 3) 치찰음
    f"acompressor=threshold=0.05:ratio={a.comp}:attack=8:release=140:makeup=2.2,"  # 4) 압축
    "asplit=2[dry][wet];"
    f"[wet][2:a]afir=dry=10:wet=10:length=1[rev];"               # 5) 리버브
    f"[dry]volume={a.vocal_gain}[d];"
    f"[rev]volume={a.reverb}[r];"
    "[d][r]amix=inputs=2:normalize=0[v];"
    f"[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume={a.inst_gain}[i];"
    "[v][i]amix=inputs=2:duration=longest:normalize=0,"
    "alimiter=limit=0.97:attack=5:release=60[outa]"              # 6) 리미터
)
cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", str(voc), "-i", str(inst), "-i", str(irp),
       "-filter_complex", chain, "-map", "[outa]", "-ar", "44100", "-ac", "2", str(out)]
print("믹싱 중...", flush=True)
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-1500:]); shutil.rmtree(tmp, ignore_errors=True); sys.exit("믹싱 실패")
shutil.rmtree(tmp, ignore_errors=True)
print(f"완성: {out}")
