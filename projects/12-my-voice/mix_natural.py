# -*- coding: utf-8 -*-
"""원곡을 기준(레퍼런스)으로 삼아 변환 보컬을 자연스럽게 섞는다.

  python mix_natural.py songs/노래_내목소리_파트
  python mix_natural.py songs/노래_내목소리_파트 --vocal 02_변환보컬_원키.wav -o songs/노래_원키.mp3

mix.py 와 다른 점 — 모든 수치를 '원곡 엔지니어가 이미 정해둔 값'에 맞춘다.
  1) 호흡   원곡 가수의 음량 흐름(엔벨로프)을 변환 보컬에 입힌다  → 끝음이 꺼지지 않음
  2) 음색   원곡 보컬의 주파수 분포에 맞춘다(일부만)            → 저역 뭉침·먹먹함 제거
  3) 밸런스 원곡의 보컬:반주 음량비를 그대로                    → 보컬이 따로 놀지 않음
  4) 공간   반주와 같은 공간으로 들리는 짧은 리버브 + 보컬 들어올 때 반주를 살짝 비켜줌
  5) 마스터 완성 믹스 전체를 원곡 마스터의 주파수·라우드니스에 맞춘다
"""
import argparse, os, subprocess, sys, tempfile, shutil
from pathlib import Path
import numpy as np, soundfile as sf, librosa, pyloudnorm as pyln
from scipy.signal import firwin2, fftconvolve, butter, sosfilt

FFDIR = r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin"
FFMPEG = os.path.join(FFDIR, "ffmpeg.exe")
SR = 44100

ap = argparse.ArgumentParser()
ap.add_argument("parts", help="cover.py --keep-parts 로 만든 _파트 폴더")
ap.add_argument("--vocal", default="02_변환보컬.wav", help="파트 폴더 안의 변환 보컬 파일명")
ap.add_argument("--ref", default=None, help="원곡 파일 (생략하면 파트 폴더 이름에서 추정)")
ap.add_argument("-o", "--out", default=None)
ap.add_argument("--breath",  type=float, default=0.7,  help="원곡 호흡(음량 흐름)을 얼마나 따를지 0~1")
ap.add_argument("--tone",    type=float, default=0.65, help="원곡 보컬 음색 분포에 얼마나 맞출지 0~1")
ap.add_argument("--vocal-db", type=float, default=0.5, help="원곡 보컬:반주 비율 대비 보컬 추가 음량 dB")
ap.add_argument("--reverb",  type=float, default=0.16, help="리버브 0~0.35")
ap.add_argument("--master",  type=float, default=0.5,  help="원곡 마스터 주파수에 맞추는 정도 0~1")
a = ap.parse_args()

d = Path(a.parts)
ref = Path(a.ref) if a.ref else d.parent / (d.name.replace("_내목소리_파트", "") + ".mp3")
out = Path(a.out) if a.out else d.parent / (d.name.replace("_파트", "") + "_자연믹스.mp3")
for p in (d / "01_원본보컬.wav", d / a.vocal, d / "03_반주.wav", ref):
    if not p.exists(): sys.exit(f"없음: {p}")

def load(p, mono):
    y, _ = librosa.load(str(p), sr=SR, mono=mono)
    return y if mono or y.ndim == 2 else np.stack([y, y])

orig = load(d / "01_원본보컬.wav", True)
voc = load(d / a.vocal, True)
inst = load(d / "03_반주.wav", False)
song = load(ref, False)
n = min(len(orig), len(voc), inst.shape[1], song.shape[1])
orig, voc, inst, song = orig[:n], voc[:n], inst[:, :n], song[:, :n]

HOP = 512
def env_db(y, smooth_ms=60):
    r = librosa.feature.rms(y=y, frame_length=2048, hop_length=HOP)[0] + 1e-7
    k = max(1, int(smooth_ms / 1000 * SR / HOP))
    r = np.convolve(r, np.ones(k) / k, mode="same")
    return 20 * np.log10(r + 1e-7)

def to_samples(g_db):
    t = np.arange(len(g_db)) * HOP
    return 10 ** (np.interp(np.arange(n), t, g_db) / 20)

# ── 1) 호흡: 원곡 가수의 음량 흐름을 입힌다 ─────────────────────
eo, ev = env_db(orig), env_db(voc)
m = min(len(eo), len(ev)); eo, ev = eo[:m], ev[:m]
active = eo > eo.max() - 40
offset = np.median((eo - ev)[active])                        # 전체 음량 차이는 빼고 '흐름'만 본다
g = a.breath * (eo - ev - offset)
g = np.where(active, np.clip(g, -6, 6), np.minimum(g, 0))     # 원곡이 쉬는 곳은 키우지 않음(잡음 방지)
g = np.convolve(g, np.ones(5) / 5, mode="same")              # 게인이 덜컥거리지 않게
voc = voc * to_samples(g)

# ── 2) 음색: 원곡 보컬의 주파수 분포 쪽으로 ───────────────────
def ltas(y):
    S = np.abs(librosa.stft(y, n_fft=4096, hop_length=2048)) ** 2
    e = S.sum(0); S = S[:, e > np.percentile(e, 30)]           # 소리 나는 구간만
    return 10 * np.log10(S.mean(1) + 1e-12)

def match_fir(src, tgt, amount, cut_max, boost_max, taps=4097):
    f = librosa.fft_frequencies(sr=SR, n_fft=4096)
    diff = ltas(tgt) - ltas(src)
    diff -= np.average(diff[(f > 500) & (f < 4000)])          # 중역 기준으로 정렬 (음량이 아니라 '모양'만)
    sm = np.empty_like(diff)                                   # 1/3 옥타브 평활
    for k, fk in enumerate(f):
        lo, hi = fk / 2 ** (1 / 6), fk * 2 ** (1 / 6)
        sm[k] = diff[(f >= lo) & (f <= max(hi, lo + 22))].mean()
    gain = np.clip(sm * amount, -cut_max, boost_max)
    gain[f < 40] = gain[np.searchsorted(f, 40)]
    h = firwin2(taps, f / (SR / 2), 10 ** (gain / 20))
    return h, f, gain

h, f, tone_gain = match_fir(voc, orig, a.tone, cut_max=9, boost_max=6)
voc = fftconvolve(voc, h, mode="same")

# ── 3) 밸런스: 원곡의 보컬:반주 음량비 ─────────────────────────
hp = butter(2, 200, "highpass", fs=SR, output="sos")           # 귀가 듣는 음량에 가깝게 저역 제외하고 잰다
def rms_db(y): y = sosfilt(hp, y); return 10 * np.log10(np.mean(y ** 2) + 1e-12)
target = rms_db(orig) - rms_db(inst.mean(0)) + a.vocal_db
voc *= 10 ** ((target - (rms_db(voc) - rms_db(inst.mean(0)))) / 20)

tmp = Path(tempfile.mkdtemp(prefix="mixn_"))
vp, ip = tmp / "v.wav", tmp / "i.wav"
sf.write(vp, voc.astype(np.float32), SR); sf.write(ip, inst.T.astype(np.float32), SR)

# 짧고 어두운 플레이트 리버브 IR — 반주와 같은 방에 있는 것처럼
rng = np.random.default_rng(7)
L = int(1.3 * SR); t = np.arange(L) / SR
ir = rng.normal(0, 1, (L, 2)) * np.exp(-t * 5.2)[:, None]
pre = int(0.022 * SR); ir = np.concatenate([np.zeros((pre, 2)), ir])[:L]
ir /= np.abs(ir).max() * 4
irp = tmp / "ir.wav"; sf.write(irp, ir.astype(np.float32), SR)

# ── 4) 보컬 체인 + 공간 + 반주 비켜주기 ───────────────────────
chain = (
    "[0:a]highpass=f=75,"
    "deesser=i=0.4:m=0.5:f=0.5,"
    "acompressor=threshold=0.08:ratio=2.4:attack=12:release=150:makeup=1,"   # 가볍게. 강약은 1)에서 원곡대로 맞춤
    "treble=f=12000:g=1.5:w=0.7,"                                          # 잘린 16kHz 위 공기감 소폭 복원
    "aformat=channel_layouts=stereo,asplit=3[vd][vs][key];"
    "[vs]highpass=f=300,lowpass=f=8000[vs2];"
    f"[vs2][2:a]afir=dry=10:wet=10:length=1,volume={a.reverb}[rv];"
    "[vd][rv]amix=inputs=2:normalize=0[v];"
    "[1:a][key]sidechaincompress=threshold=0.06:ratio=1.8:attack=25:release=280:makeup=1[i];"  # 보컬이 나올 때 반주 1~2dB 양보
    "[v][i]amix=inputs=2:normalize=0[outa]"
)
pm = tmp / "premaster.wav"
r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(vp), "-i", str(ip), "-i", str(irp),
                    "-filter_complex", chain, "-map", "[outa]", "-ar", str(SR), "-c:a", "pcm_f32le", str(pm)],
                   capture_output=True, text=True)
if r.returncode: print(r.stderr[-1500:]); sys.exit("믹스 실패")

# ── 5) 마스터: 원곡 마스터의 주파수 모양 + 라우드니스 ─────────────
mix, _ = sf.read(pm)
mix = mix[:n]
hm, _, master_gain = match_fir(mix.mean(1), song.mean(0), a.master, cut_max=4, boost_max=4)
mix = np.stack([fftconvolve(mix[:, c], hm, mode="same") for c in range(2)], 1)
meter = pyln.Meter(SR)
lufs_ref, lufs_mix = meter.integrated_loudness(song.T), meter.integrated_loudness(mix)
mix *= 10 ** ((lufs_ref - lufs_mix) / 20)
mp = tmp / "m.wav"; sf.write(mp, mix.astype(np.float32), SR)
r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(mp),
                    "-af", "alimiter=limit=0.89:attack=4:release=80:level=false",
                    "-codec:a", "libmp3lame", "-b:a", "320k", str(out)], capture_output=True, text=True)
if r.returncode: print(r.stderr[-1500:]); sys.exit("인코딩 실패")
shutil.rmtree(tmp, ignore_errors=True)

def band(gs, lo, hi): return gs[(f >= lo) & (f < hi)].mean()
print("음색 보정  저역(80-250) %+.1f dB  중저역(250-1k) %+.1f dB  고역(12k+) %+.1f dB"
      % (band(tone_gain, 80, 250), band(tone_gain, 250, 1000), band(tone_gain, 12000, 20000)))
print(f"원곡 라우드니스 {lufs_ref:.1f} LUFS 에 맞춤")
print(f"완성: {out}")
