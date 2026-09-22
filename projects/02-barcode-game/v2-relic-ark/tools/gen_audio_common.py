# -*- coding: utf-8 -*-
"""
gen_audio_common.py — 잔해 방주 사운드 합성 공통 DSP 유틸.
소유: relic-sound. numpy/scipy 기반 로컬 합성(교본 05_SOUND A9).
외부 CC0 음원을 쓰지 않고 전부 절차적으로 생성한다(재현 가능 = 시드 고정).
"""
import numpy as np
from scipy import signal

SR = 44100  # 작업 샘플레이트. 인코딩 시 ffmpeg가 목표 샘플레이트로 리샘플.


# ---------- 노이즈 ----------

def white_noise(n, rng):
    return rng.standard_normal(n)


def pink_noise(n, rng):
    """1/f 노이즈(핑크). FFT 스펙트럼을 1/sqrt(f)로 성형."""
    white = rng.standard_normal(n)
    X = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n)
    freqs[0] = freqs[1] if len(freqs) > 1 else 1.0
    X = X / np.sqrt(freqs)
    pink = np.fft.irfft(X, n)
    peak = np.max(np.abs(pink)) + 1e-12
    return pink / peak


def brown_noise(n, rng):
    """1/f^2 노이즈(브라운). 백색소음 누적 후 DC 제거."""
    white = rng.standard_normal(n)
    brown = np.cumsum(white)
    brown = highpass(brown, 10.0)
    peak = np.max(np.abs(brown)) + 1e-12
    return brown / peak


# ---------- 필터 ----------

def bandpass(x, low, high, order=4):
    nyq = SR / 2
    low = max(1.0, low) / nyq
    high = min(SR / 2 - 1, high) / nyq
    sos = signal.butter(order, [low, high], btype="band", output="sos")
    return signal.sosfiltfilt(sos, x)


def lowpass(x, cutoff, order=4):
    nyq = SR / 2
    sos = signal.butter(order, cutoff / nyq, btype="low", output="sos")
    return signal.sosfiltfilt(sos, x)


def highpass(x, cutoff, order=4):
    nyq = SR / 2
    sos = signal.butter(order, cutoff / nyq, btype="high", output="sos")
    return signal.sosfiltfilt(sos, x)


# ---------- 오실레이터 / 이벤트 ----------

def sine(freq, dur, phase=0.0, sr=SR):
    t = np.arange(int(dur * sr)) / sr
    return np.sin(2 * np.pi * freq * t + phase)


def glide_sine(f0, f1, dur, sr=SR):
    """f0->f1로 선형 글리산도하는 사인(위상 적분으로 클릭 없이)."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    freq_t = np.linspace(f0, f1, n)
    phase = 2 * np.pi * np.cumsum(freq_t) / sr
    return np.sin(phase)


def exp_env(n, tau_sec, sr=SR):
    t = np.arange(n) / sr
    return np.exp(-t / max(tau_sec, 1e-6))


def adsr(n, a, d, s_level, r, sr=SR):
    na, nd, nr = int(a * sr), int(d * sr), int(r * sr)
    ns = max(0, n - na - nd - nr)
    env = np.concatenate([
        np.linspace(0, 1, max(na, 1)),
        np.linspace(1, s_level, max(nd, 1)),
        np.full(ns, s_level),
        np.linspace(s_level, 0, max(nr, 1)),
    ])
    if len(env) < n:
        env = np.pad(env, (0, n - len(env)))
    return env[:n]


def add_at(buf, start_sample, event):
    """buf에 event를 start_sample 위치부터 더한다(경계 클리핑)."""
    n = len(buf)
    s = start_sample
    e = s + len(event)
    if e <= 0 or s >= n:
        return
    ev_s = max(0, -s)
    ev_e = len(event) - max(0, e - n)
    buf[max(0, s):min(n, e)] += event[ev_s:ev_e]


# ---------- 리버브 ----------

def make_reverb_ir(decay_time, bright=False, seed=0, sr=SR):
    n = max(int(decay_time * sr), 8)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n)
    t = np.arange(n) / sr
    env = np.exp(-t / (decay_time / 4.5))
    ir = noise * env
    if bright:
        ir = highpass(ir, 400.0, order=2)  # 밝은 잔향: 저역 덜어내고 개방감
    else:
        ir = lowpass(ir, 2200.0, order=2)  # 어두운 잔향: 콘크리트, 고역 죽임
    peak = np.max(np.abs(ir)) + 1e-12
    return ir / peak


def apply_reverb(x, decay_time, wet=0.25, bright=False, seed=0, sr=SR):
    ir = make_reverb_ir(decay_time, bright=bright, seed=seed, sr=sr)
    wet_sig = signal.fftconvolve(x, ir, mode="full")[: len(x)]
    peak_dry = np.max(np.abs(x)) + 1e-12
    peak_wet = np.max(np.abs(wet_sig)) + 1e-12
    wet_sig = wet_sig / peak_wet * peak_dry
    return (1 - wet) * x + wet * wet_sig


# ---------- 레벨 / 루프 ----------

def db_to_lin(db):
    return 10 ** (db / 20.0)


def normalize_peak(x, target_db=-3.0):
    peak = np.max(np.abs(x)) + 1e-12
    return x * (db_to_lin(target_db) / peak)


def crossfade_loop(x, fade_sec, sr=SR):
    """x(길이 L+fade)를 길이 L의 매끄러운 루프로 만든다.
    핵심: 루프 시작 지점(i=0)을 실제로 이어지는 꼬리(연속된 랜덤과정)로 채우고,
    fade 구간에 걸쳐 원래 head 콘텐츠로 등파워 크로스페이드한다.
    """
    fade = int(fade_sec * sr)
    n = len(x)
    L = n - fade
    if L <= 0:
        return x
    out = x[:L].copy()
    w = np.linspace(0, 1, fade, endpoint=False)
    f_continuation = np.cos(w * np.pi / 2) ** 2  # 1 -> 0
    f_head = np.sin(w * np.pi / 2) ** 2          # 0 -> 1
    tail = x[L:L + fade]
    if len(tail) < fade:
        tail = np.pad(tail, (0, fade - len(tail)))
    out[:fade] = tail * f_continuation + out[:fade] * f_head
    return out


def silence(dur_sec, sr=SR):
    return np.zeros(int(dur_sec * sr))


def save_wav(path, x, sr=SR):
    import soundfile as sf
    x = np.clip(x, -1.0, 1.0).astype(np.float32)
    sf.write(str(path), x, sr)
    return path


def encode_ogg(wav_path, ogg_path, bitrate_k, sample_rate=None, channels=1):
    """ffmpeg로 WAV -> OGG(Vorbis) 인코딩. bitrate_k: 예 '48k'."""
    import subprocess
    args = ["ffmpeg", "-y", "-i", str(wav_path), "-c:a", "libvorbis",
            "-b:a", str(bitrate_k)]
    if sample_rate:
        args += ["-ar", str(sample_rate)]
    args += ["-ac", str(channels), str(ogg_path)]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패: {ogg_path}\n{r.stderr[-2000:]}")
    return ogg_path
