# -*- coding: utf-8 -*-
"""
gen_audio_cue.py — 힐링 스팟 발견 큐 (교본 05_SOUND A2, A3, A10).
cue_spot_found.ogg: 0.8초 무음(A10) -> 30초 루프.
순서(A3): 물소리 -> 물튀김(잉어) -> 낮은 피아노풍 사인 배음 한 음 -> 도리안 모달 코드 -> 멜로디 3~4음.
조성: D 도리안(D E F G A B C) — 장조도 단조도 아닌 "아름답지만 낯선" 색.

실행: python tools/gen_audio_cue.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from gen_audio_common import (
    SR, bandpass, lowpass, exp_env, add_at, apply_reverb, normalize_peak,
    crossfade_loop, silence, save_wav, encode_ogg,
)

ROOT = Path(__file__).resolve().parents[1]
STATIC_AUDIO = ROOT / "static" / "audio"
RAW_TMP = ROOT / "audio" / "_tmp"
RAW_TMP.mkdir(parents=True, exist_ok=True)
STATIC_AUDIO.mkdir(parents=True, exist_ok=True)

LOOP_LEN = 30.0
FADE = 1.5
RAW_LEN = LOOP_LEN + FADE
LEAD_SILENCE = 0.8  # A10: 발견 직전 침묵

# D 도리안 음계 주파수(Hz)
D3, E3, F3, G3, A3, B3, C4 = 146.83, 164.81, 174.61, 196.00, 220.00, 246.94, 261.63
D4, F4, G4, A4, D5 = 293.66, 349.23, 392.00, 440.00, 587.33


def bell_tone(freq, dur, partials=((1.0, 1.0), (2.0, 0.5), (3.01, 0.22), (4.2, 0.10)),
              decay_scale=1.0, attack=0.015):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for ratio, amp in partials:
        tau = (dur / (1.1 * ratio)) * decay_scale
        out += amp * np.sin(2 * np.pi * freq * ratio * t) * np.exp(-t / max(tau, 0.05))
    na = int(attack * SR)
    if na > 0:
        out[:na] *= np.linspace(0, 1, na)
    return out


def pad_tone(freq, dur, attack=1.5, detune_cents=6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    d = 2 ** (detune_cents / 1200.0)
    out = 0.5 * np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(2 * np.pi * freq * d * t)
    na = int(attack * SR)
    env = np.ones(n)
    if na > 0:
        env[:na] = (1 - np.cos(np.linspace(0, np.pi, na))) / 2
    release_n = int(min(dur * 0.3, 4.0) * SR)
    if release_n > 0:
        env[-release_n:] *= np.linspace(1, 0, release_n)
    return out * env


def water_bed(n, rng, rise_sec=3.0):
    noise = bandpass(rng.standard_normal(n), 250, 4000)
    slow = rng.standard_normal(int(n / 4410) + 2)
    slow_env = np.interp(np.linspace(0, len(slow) - 1, n), np.arange(len(slow)), slow)
    slow_env = lowpass(slow_env, 1.5)
    slow_env = 0.6 + 0.4 * (slow_env / (np.max(np.abs(slow_env)) + 1e-9))
    rise = np.ones(n)
    rn = int(rise_sec * SR)
    if rn > 0:
        rise[:rn] = np.linspace(0, 1, rn) ** 0.6
    return noise * slow_env * rise


def splash(rng, gentle=True):
    dur = 0.5
    n = int(dur * SR)
    ev = bandpass(rng.standard_normal(n), 700, 6500) * exp_env(n, 0.08)
    drop_n = 3 if gentle else 5
    for i in range(drop_n):
        dt = 0.08 + i * 0.07 + rng.uniform(-0.01, 0.01)
        ddur = 0.05
        dn = int(ddur * SR)
        drop = bandpass(rng.standard_normal(dn), 1800, 7000) * exp_env(dn, 0.02)
        s = int(dt * SR)
        e = s + dn
        if e <= len(ev):
            ev[s:e] += drop * 0.35
    return ev * 0.6


def gen_cue(seed=42):
    rng = np.random.default_rng(seed)
    n = int(RAW_LEN * SR)
    buf = np.zeros(n)

    # 1) 물소리: 서서히 차오름, 전체에 걸쳐 바탕
    bed = water_bed(n, rng, rise_sec=3.0)
    buf += 0.14 * bed

    # 2) 물튀김(잉어)
    sp = splash(rng)
    add_at(buf, int(1.2 * SR), sp)

    # 3) 낮은 피아노풍 사인 배음 한 음 (D3, 도리안 근음)
    tone = bell_tone(D3, 6.0, decay_scale=1.3, attack=0.02)
    add_at(buf, int(3.0 * SR), tone * 0.5)

    # 4) 도리안 모달 코드 (D F A B = Dm6, "장조도 단조도 아닌")
    chord_start = 7.0
    chord_dur = 16.0
    for f, amp in [(D3, 0.30), (F3, 0.22), (A3, 0.22), (B3, 0.18)]:
        pad = pad_tone(f, chord_dur, attack=2.0)
        add_at(buf, int(chord_start * SR), pad * amp)

    # 5) 멜로디 3~4음 (D 도리안: A4-G4-F4-D5, 성기게 배치)
    melody = [(10.0, A4, 1.6), (13.5, G4, 1.6), (17.0, F4, 1.8), (21.0, D5, 2.6)]
    for start, freq, mdur in melody:
        note = bell_tone(freq, mdur, decay_scale=1.0, attack=0.02)
        add_at(buf, int(start * SR), note * 0.28)

    # 두 번째 잔잔한 물튀김(순환 대비)
    sp2 = splash(rng, gentle=True)
    add_at(buf, int(24.5 * SR), sp2 * 0.6)

    buf = apply_reverb(buf, decay_time=3.2, wet=0.35, bright=True, seed=seed)
    buf = normalize_peak(buf, -4.0)
    loop = crossfade_loop(buf, FADE)
    full = np.concatenate([silence(LEAD_SILENCE), loop])
    return full


def main():
    print("[gen] cue_spot_found ...")
    audio = gen_cue()
    wav_path = RAW_TMP / "cue_spot_found.wav"
    save_wav(wav_path, audio, SR)
    ogg_path = STATIC_AUDIO / "cue_spot_found.ogg"
    encode_ogg(wav_path, ogg_path, "112k", sample_rate=44100, channels=1)
    size_kb = ogg_path.stat().st_size / 1024
    print(f"  -> {ogg_path} ({size_kb:.1f} KB, {len(audio)/SR:.2f}s)")


if __name__ == "__main__":
    main()
