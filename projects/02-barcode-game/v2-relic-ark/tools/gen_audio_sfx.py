# -*- coding: utf-8 -*-
"""
gen_audio_sfx.py — SFX 7종 합성 (교본 05_SOUND A6, A8: 각 ≤2초 ≤40KB).
sfx_lantern_on, sfx_campfire(1.5s 루프), sfx_water_splash, sfx_scan_ok,
sfx_note_arrive, sfx_card_place, sfx_dog_warn(저역, 짖음이 위협보다 먼저=A5).

실행: python tools/gen_audio_sfx.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from gen_audio_common import (
    SR, bandpass, lowpass, sine, glide_sine, exp_env, adsr, add_at,
    apply_reverb, normalize_peak, crossfade_loop, save_wav, encode_ogg,
)

ROOT = Path(__file__).resolve().parents[1]
STATIC_AUDIO = ROOT / "static" / "audio"
RAW_TMP = ROOT / "audio" / "_tmp"
RAW_TMP.mkdir(parents=True, exist_ok=True)
STATIC_AUDIO.mkdir(parents=True, exist_ok=True)


def gen_lantern_on(seed=10):
    rng = np.random.default_rng(seed)
    dur = 0.55
    n = int(dur * SR)
    buf = np.zeros(n)
    click = bandpass(rng.standard_normal(int(0.012 * SR)), 3200, 9000) * exp_env(int(0.012 * SR), 0.004)
    add_at(buf, 0, click * 0.9)
    boom_dur = 0.28
    boom = sine(72.0, boom_dur) * exp_env(int(boom_dur * SR), 0.09)
    boom = lowpass(boom, 180.0)
    add_at(buf, int(0.02 * SR), boom * 0.8)
    buf = normalize_peak(buf, -3.0)
    return buf


def gen_campfire(seed=11):
    rng = np.random.default_rng(seed)
    loop_len = 1.5
    fade = 0.12
    raw_len = loop_len + fade
    n = int(raw_len * SR)
    base = bandpass(rng.standard_normal(n), 400, 5000) * 0.05
    buf = base.copy()
    n_pops = 9
    pop_times = rng.uniform(0.05, raw_len - 0.05, n_pops)
    for pt in pop_times:
        pdur = rng.uniform(0.02, 0.06)
        pop = bandpass(rng.standard_normal(int(pdur * SR)), 700, 6500) * exp_env(int(pdur * SR), pdur * 0.3)
        add_at(buf, int(pt * SR), pop * rng.uniform(0.5, 1.0))
    buf = lowpass(buf, 6500.0)
    buf = normalize_peak(buf, -4.0)
    loop = crossfade_loop(buf, fade)
    return loop


def gen_water_splash(seed=12):
    rng = np.random.default_rng(seed)
    dur = 0.9
    n = int(dur * SR)
    buf = np.zeros(n)
    main = bandpass(rng.standard_normal(int(0.35 * SR)), 400, 6500) * exp_env(int(0.35 * SR), 0.06)
    add_at(buf, 0, main * 0.9)
    plop = glide_sine(300, 140, 0.12) * exp_env(int(0.12 * SR), 0.04)
    add_at(buf, 0, plop * 0.5)
    n_drops = 4
    drop_times = rng.uniform(0.15, dur - 0.1, n_drops)
    for dt in drop_times:
        ddur = 0.06
        drop = bandpass(rng.standard_normal(int(ddur * SR)), 1500, 6500) * exp_env(int(ddur * SR), 0.02)
        add_at(buf, int(dt * SR), drop * rng.uniform(0.2, 0.4))
    buf = normalize_peak(buf, -3.0)
    return buf


def gen_scan_ok(seed=13):
    rng = np.random.default_rng(seed)
    dur = 1.4
    n = int(dur * SR)
    buf = np.zeros(n)
    b1 = sine(1180, 0.09) * adsr(int(0.09 * SR), 0.005, 0.02, 0.6, 0.05)
    add_at(buf, int(0.0 * SR), b1 * 0.5)
    b2 = sine(1580, 0.09) * adsr(int(0.09 * SR), 0.005, 0.02, 0.6, 0.05)
    add_at(buf, int(0.14 * SR), b2 * 0.5)
    tear_dur = 0.38
    tear_env_raw = rng.uniform(0.2, 1.0, 40)
    tear_env = np.interp(np.linspace(0, len(tear_env_raw) - 1, int(tear_dur * SR)),
                          np.arange(len(tear_env_raw)), tear_env_raw)
    tear = bandpass(rng.standard_normal(int(tear_dur * SR)), 900, 5200) * tear_env
    add_at(buf, int(0.30 * SR), tear * 0.45)
    cart_start = int(0.72 * SR)
    cart_dur = 0.4
    n_clicks = 16
    for i in range(n_clicks):
        jitter = rng.uniform(-0.003, 0.003)
        t0 = cart_start + int((i * cart_dur / n_clicks + jitter) * SR)
        cdur = 0.012
        c = bandpass(rng.standard_normal(int(cdur * SR)), 1800, 4500) * exp_env(int(cdur * SR), 0.01)
        decay = 1.0 - (i / n_clicks) * 0.6
        add_at(buf, t0, c * 0.35 * decay)
    buf = normalize_peak(buf, -3.0)
    return buf


def gen_note_arrive(seed=14):
    rng = np.random.default_rng(seed)
    dur = 1.1
    n = int(dur * SR)
    buf = np.zeros(n)
    slide_dur = 0.35
    slide_env = adsr(int(slide_dur * SR), 0.05, 0.1, 0.5, 0.15)
    slide = bandpass(rng.standard_normal(int(slide_dur * SR)), 500, 3500) * slide_env
    add_at(buf, 0, slide * 0.35)
    bell_start = int(0.30 * SR)
    bell_dur = 0.6
    bell = (sine(1800, bell_dur) + 0.5 * sine(3600, bell_dur) + 0.25 * sine(5400, bell_dur))
    bell *= exp_env(int(bell_dur * SR), 0.18)
    add_at(buf, bell_start, bell * 0.35)
    buf = normalize_peak(buf, -3.0)
    return buf


def gen_card_place(seed=15):
    rng = np.random.default_rng(seed)
    dur = 0.35
    n = int(dur * SR)
    buf = np.zeros(n)
    flutter = bandpass(rng.standard_normal(int(0.12 * SR)), 500, 3200) * exp_env(int(0.12 * SR), 0.03)
    add_at(buf, 0, flutter * 0.6)
    thump = sine(150, 0.1) * exp_env(int(0.1 * SR), 0.025)
    thump = lowpass(thump, 300.0)
    add_at(buf, int(0.08 * SR), thump * 0.5)
    buf = normalize_peak(buf, -3.0)
    return buf


def gen_dog_warn(seed=16):
    rng = np.random.default_rng(seed)
    dur = 0.75
    n = int(dur * SR)
    buf = np.zeros(n)
    for i, start in enumerate([0.0, 0.32]):
        bdur = 0.16
        bark_noise = bandpass(rng.standard_normal(int(bdur * SR)), 200, 1600)
        bark_tone = glide_sine(260, 120, bdur)
        bark = bark_noise * 0.6 + bark_tone * 0.6
        bark *= adsr(int(bdur * SR), 0.01, 0.05, 0.5, 0.08)
        bark = lowpass(bark, 900.0)
        add_at(buf, int(start * SR), bark * 0.8)
    buf = normalize_peak(buf, -3.0)
    return buf


def main():
    jobs = [
        ("sfx_lantern_on", gen_lantern_on),
        ("sfx_campfire", gen_campfire),
        ("sfx_water_splash", gen_water_splash),
        ("sfx_scan_ok", gen_scan_ok),
        ("sfx_note_arrive", gen_note_arrive),
        ("sfx_card_place", gen_card_place),
        ("sfx_dog_warn", gen_dog_warn),
    ]
    for name, fn in jobs:
        print(f"[gen] {name} ...")
        audio = fn()
        wav_path = RAW_TMP / f"{name}.wav"
        save_wav(wav_path, audio, SR)
        ogg_path = STATIC_AUDIO / f"{name}.ogg"
        encode_ogg(wav_path, ogg_path, "80k", sample_rate=32000, channels=1)
        size_kb = ogg_path.stat().st_size / 1024
        print(f"  -> {ogg_path} ({size_kb:.2f} KB, {len(audio)/SR:.2f}s)")


if __name__ == "__main__":
    main()
