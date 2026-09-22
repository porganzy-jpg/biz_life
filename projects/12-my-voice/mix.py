# -*- coding: utf-8 -*-
"""변환된 보컬을 완성곡처럼 마스터링한다.

  python mix.py songs/노래_내목소리_파트
  python mix.py songs/노래_내목소리_파트 --air 3.5 --warmth 3 --width 0.35 --reverb 0.3
  python mix.py -v 보컬.wav -i 반주.wav -o 완성.wav

체인
  저역 정리 → 저음 특색(내 기본 주파수) → 뭉침 제거 → 밀어붙이는 힘 → 존재감
  → 하모닉 익사이터(없는 고음을 만들어 뻗게 함) → 공기감 → 디에서
  → 컴프레서(어택 늦춰 자음 강조)
  → [드라이 + 더블링(폭) + 병렬압축(두께) + 포화(힘·거친 배음) + 리버브(공간)] → 리미터
"""
import argparse, os, subprocess, sys, tempfile, shutil
from pathlib import Path
import numpy as np, soundfile as sf

FFDIR = r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin"
os.environ["PATH"] = FFDIR + os.pathsep + os.environ.get("PATH", "")
FFMPEG = os.path.join(FFDIR, "ffmpeg.exe")
SR = 44100

ap = argparse.ArgumentParser()
ap.add_argument("parts", nargs="?", help="cover.py --keep-parts 로 만든 _파트 폴더")
ap.add_argument("-v", "--vocal"); ap.add_argument("-i", "--inst"); ap.add_argument("-o", "--out")
ap.add_argument("--air",      type=float, default=3.0,  help="고음 뻗침 (익사이터+셸프) 0~5")
ap.add_argument("--warmth",   type=float, default=2.8,  help="저음 특색 보강 dB 0~5")
ap.add_argument("--width",    type=float, default=0.30, help="더블링으로 폭 넓히기 0~0.45")
ap.add_argument("--parallel", type=float, default=0.33, help="병렬압축 두께 0~0.5")
ap.add_argument("--reverb",   type=float, default=0.26, help="리버브 0~0.5")
ap.add_argument("--comp",     type=float, default=3.4,  help="메인 컴프레서 비율 (낮을수록 강약이 살아 감정이 남음)")
ap.add_argument("--drive",    type=float, default=0.30, help="포화(배음 왜곡)로 힘과 거친 질감 0~0.5")
ap.add_argument("--punch",    type=int,   default=18,   help="컴프 어택 ms. 클수록 자음이 튀어 또렷해진다")
ap.add_argument("--vocal-gain", type=float, default=1.0)
ap.add_argument("--inst-gain",  type=float, default=0.88)
a = ap.parse_args()

if a.parts:
    d = Path(a.parts)
    voc, inst = d/"02_변환보컬.wav", d/"03_반주.wav"
    out = Path(a.out) if a.out else d.parent/(d.name.replace("_파트","") + "_믹싱.wav")
else:
    if not (a.vocal and a.inst): sys.exit("파트 폴더 또는 -v/-i 를 지정하세요")
    voc, inst = Path(a.vocal), Path(a.inst)
    out = Path(a.out) if a.out else voc.with_name(voc.stem + "_믹싱.wav")
for p in (voc, inst):
    if not p.exists(): sys.exit(f"없음: {p}")

tmp = Path(tempfile.mkdtemp(prefix="mix_"))
# ── 리버브 임펄스 응답: 고역이 살아있는 밝은 홀 ──
rng = np.random.default_rng(11)
L = int(1.8 * SR); t = np.arange(L)/SR
ir = rng.normal(0, 1, (L, 2)) * np.exp(-t*3.4)[:, None]
hi = rng.normal(0, 1, (L, 2)) * np.exp(-t*6.5)[:, None] * 0.55   # 밝은 성분을 덜 감쇠
ir = ir + hi
for ms, g in ((13,.52),(19,.44),(27,.36),(37,.28),(51,.2)):
    i = int(ms/1000*SR)
    if i < L: ir[i] += g
ir[:int(0.005*SR)] *= np.linspace(0,1,int(0.005*SR))[:,None]
ir /= np.abs(ir).max()*3.2
irp = tmp/"ir.wav"; sf.write(irp, ir.astype(np.float32), SR)

exc = max(0.0, a.air)          # 익사이터 강도
chain = (
    "[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
    "highpass=f=70,"                                                  # 아주 낮은 잡음만 제거 (저음 특색은 남김)
    f"equalizer=f=135:t=q:w=1.1:g={a.warmth},"                        # 내 기본 주파수 대역 = 목소리 무게
    "equalizer=f=330:t=q:w=1.3:g=-3.5,"                               # 뭉침
    "equalizer=f=1800:t=q:w=1.2:g=2.0,"                               # 밀어붙이는 힘
    "equalizer=f=2800:t=q:w=1.0:g=2.4,"                               # 존재감
    f"aexciter=level_in=1:level_out=1:amount={exc}:drive=7:blend=1.5:freq=6800:ceil=16000,"  # 없는 고음 생성
    f"treble=f=10500:g={a.air*0.9:.2f}:w=0.7,"                        # 공기감
    "deesser=i=0.5:m=0.5:f=0.5,"                                      # 익사이터로 세진 치찰음 정리
    f"acompressor=threshold=0.055:ratio={a.comp}:attack={a.punch}:release=160:makeup=2.1,"
    "asplit=5[dry][wide][par][drv][send];"
    f"[wide]adelay=14|23,volume={a.width}[w];"                        # 좌우 시간차 = 폭
    f"[par]acompressor=threshold=0.012:ratio=12:attack=3:release=90:makeup=3,volume={a.parallel}[p];"
    f"[drv]asoftclip=type=tanh:threshold=0.45,highpass=f=180,volume={a.drive}[g];"
    f"[send][2:a]afir=dry=10:wet=10:length=1,volume={a.reverb}[r];"
    f"[dry]volume={a.vocal_gain}[d];"
    "[d][w][p][g][r]amix=inputs=5:normalize=0[v];"
    f"[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume={a.inst_gain}[i];"
    "[v][i]amix=inputs=2:duration=longest:normalize=0,"
    "alimiter=limit=0.97:attack=5:release=60[outa]"
)
print("마스터링 중...", flush=True)
r = subprocess.run([FFMPEG,"-y","-loglevel","error","-i",str(voc),"-i",str(inst),"-i",str(irp),
                    "-filter_complex",chain,"-map","[outa]","-ar","44100","-ac","2",str(out)],
                   capture_output=True, text=True)
shutil.rmtree(tmp, ignore_errors=True)
if r.returncode != 0:
    print(r.stderr[-1500:]); sys.exit("실패")
print(f"완성: {out}")
