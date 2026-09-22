# -*- coding: utf-8 -*-
"""
gen_audio_ambient.py — 앰비언트 3종 합성 (교본 05_SOUND A1).
안(amb_inside): 물방울·랜턴 지글·먼 터빈 웅웅(40~60Hz)·천 스침. 저역 중심, 짧은 잔향.
밖 낮(amb_outside_day): 바람·새·잎 스침. 고역 열림, 긴 잔향.
밖 밤(amb_outside_night): 바람 낮게·귀뚜라미 펄스·멀리 공룡 울음(저역 스윕) 1~2회.

실행: python tools/gen_audio_ambient.py
출력: static/audio/amb_inside.ogg, amb_outside_day.ogg, amb_outside_night.ogg
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from gen_audio_common import (
    SR, bandpass, lowpass, highpass, sine, glide_sine, exp_env, adsr,
    add_at, apply_reverb, normalize_peak, crossfade_loop, save_wav,
    encode_ogg,
)

ROOT = Path(__file__).resolve().parents[1]
STATIC_AUDIO = ROOT / "static" / "audio"
RAW_TMP = ROOT / "audio" / "_tmp"
RAW_TMP.mkdir(parents=True, exist_ok=True)
STATIC_AUDIO.mkdir(parents=True, exist_ok=True)

LOOP_LEN = 50.0   # 초. 45~60초 규격 안.
FADE = 2.0        # 크로스페이드용 여유(내부용, 최종 루프 길이엔 포함 안 됨)
RAW_LEN = LOOP_LEN + FADE


def _lfo(n, period_sec, phase=0.0, sr=SR):
    """루프 길이에 정확히 맞물리는 저주파 진동자(끊김 없는 루프의 핵심)."""
    t = np.arange(n) / sr
    return np.sin(2 * np.pi * t / period_sec + phase)


def gen_inside(seed=1):
    rng = np.random.default_rng(seed)
    n = int(RAW_LEN * SR)
    buf = np.zeros(n)

    # 1) 먼 터빈 웅웅 40~60Hz: 두 근접 저역음 비트 + 루프주기 앰프 LFO
    t = np.arange(n) / SR
    turbine = 0.6 * np.sin(2 * np.pi * 48.0 * t) + 0.4 * np.sin(2 * np.pi * 55.0 * t)
    turbine_env = 0.7 + 0.3 * _lfo(n, RAW_LEN, phase=0.3)
    turbine = lowpass(turbine * turbine_env, 140.0)
    buf += 0.22 * turbine

    # 2) 랜턴 지글: 고역 미세 노이즈 + 랜덤 플리커
    hiss = bandpass(rng.standard_normal(n), 3200, 8000)
    flicker_raw = rng.standard_normal(int(n / 200) + 2)
    flicker = np.interp(np.linspace(0, len(flicker_raw) - 1, n),
                         np.arange(len(flicker_raw)), flicker_raw)
    flicker = lowpass(flicker, 4.0)
    flicker = 0.5 + 0.5 * (flicker / (np.max(np.abs(flicker)) + 1e-9))
    buf += 0.05 * hiss * flicker

    # 3) 물방울: 성긴 임의 간격 이벤트(가장자리 회피)
    n_drips = 11
    drip_times = rng.uniform(1.0, RAW_LEN - 3.0, n_drips)
    drip_times.sort()
    for dt in drip_times:
        dur = 0.22
        pitch0 = rng.uniform(1000, 1500)
        tone = glide_sine(pitch0, pitch0 * 0.7, dur) * exp_env(int(dur * SR), 0.09)
        click = bandpass(rng.standard_normal(int(0.02 * SR)), 2500, 7000) * exp_env(int(0.02 * SR), 0.006)
        event = tone * 0.5
        add_at(buf, int(dt * SR), event * rng.uniform(0.6, 1.0))
        add_at(buf, int(dt * SR), np.pad(click, (0, len(event) - len(click))) * 0.4)

    # 4) 천 스침: 성긴 대역 노이즈 버스트
    n_rustle = 7
    rustle_times = rng.uniform(0.5, RAW_LEN - 2.0, n_rustle)
    for rt in rustle_times:
        dur = rng.uniform(0.25, 0.5)
        ev = bandpass(rng.standard_normal(int(dur * SR)), 1400, 4200)
        ev *= adsr(len(ev), 0.05, 0.1, 0.4, dur * 0.5)
        add_at(buf, int(rt * SR), ev * rng.uniform(0.08, 0.16))

    buf = lowpass(buf, 4500.0)  # 저역 중심(안)
    buf = apply_reverb(buf, decay_time=0.4, wet=0.18, bright=False, seed=seed)
    buf = normalize_peak(buf, -3.0)
    loop = crossfade_loop(buf, FADE)
    return loop


def gen_outside_day(seed=2):
    rng = np.random.default_rng(seed)
    n = int(RAW_LEN * SR)

    # 1) 바람: 넓은 대역 핑크 노이즈 + 돌풍 LFO(루프 주기 정수배)
    from gen_audio_common import pink_noise
    wind = bandpass(pink_noise(n, rng), 150, 7000)
    gust = 0.55 + 0.45 * _lfo(n, RAW_LEN / 2, phase=0.6)
    wind = wind * gust

    # 2) 잎 스침: 고역 대역 노이즈, 바람과 같은 LFO로 결맞음
    leaves = bandpass(rng.standard_normal(n), 2200, 8500)
    leaves_env = 0.5 + 0.5 * _lfo(n, RAW_LEN / 2, phase=1.2)
    leaves = leaves * leaves_env

    buf = 0.16 * wind + 0.07 * leaves

    # 3) 새소리: 랜덤 글리산도 칩, 가장자리(크로스페이드 구간) 회피
    n_birds = 16
    bird_times = rng.uniform(FADE + 0.5, RAW_LEN - FADE - 0.5, n_birds)
    for bt in bird_times:
        dur = rng.uniform(0.12, 0.32)
        f0 = rng.uniform(2200, 4800)
        f1 = f0 * rng.uniform(0.7, 1.5)
        chirp = glide_sine(f0, f1, dur)
        chirp *= adsr(len(chirp), 0.015, dur * 0.3, 0.3, dur * 0.4)
        add_at(buf, int(bt * SR), chirp * rng.uniform(0.10, 0.22))

    buf = highpass(buf, 70.0)  # 고역 열림(밖), 저역 잡음만 제거
    buf = apply_reverb(buf, decay_time=2.0, wet=0.32, bright=True, seed=seed)
    buf = normalize_peak(buf, -3.0)
    loop = crossfade_loop(buf, FADE)
    return loop


def gen_outside_night(seed=3):
    rng = np.random.default_rng(seed)
    n = int(RAW_LEN * SR)

    # 1) 바람 낮게: 좁고 어두운 대역, 낮은 레벨(밤은 낮보다 저역 비중이 크지만
    #    "밖"이라는 것 자체는 고역이 열려 있어야 하므로 크리켓/야간 대기 히스로 보완한다)
    from gen_audio_common import pink_noise
    wind = bandpass(pink_noise(n, rng), 90, 1800)
    gust = 0.55 + 0.45 * _lfo(n, RAW_LEN / 2, phase=0.2)
    wind = wind * gust

    # 2) 귀뚜라미 펄스: 캐리어 + 트릴 게이트 + 패킷 엔벨로프(밤 특유의 고역)
    t = np.arange(n) / SR
    carrier = np.sin(2 * np.pi * 4200 * t) + 0.4 * np.sin(2 * np.pi * 6100 * t)
    trill = (np.sin(2 * np.pi * 25 * t) > 0).astype(float)
    trill = lowpass(trill, 200.0)  # 클릭 방지
    packet = (np.sin(2 * np.pi * t / 2.5) > -0.3).astype(float)
    packet = lowpass(packet, 6.0)
    crickets = carrier * trill * packet
    crickets = bandpass(crickets, 3000, 8000)

    # 3) 야간 대기 히스: 밖의 "열린 고역"을 밤에도 아주 옅게 유지(별빛 아래 공기)
    night_air = bandpass(rng.standard_normal(n), 1200, 7000)
    night_air_env = 0.6 + 0.4 * _lfo(n, RAW_LEN / 3, phase=2.1)

    buf = 0.055 * wind + 0.15 * crickets + 0.035 * night_air * night_air_env

    # 3) 멀리 공룡 울음(저역 스윕) 1~2회, 가장자리 회피
    n_roars = int(rng.integers(1, 3))
    roar_times = rng.uniform(FADE + 3.0, RAW_LEN - FADE - 4.0, n_roars)
    for rtm in sorted(roar_times):
        dur = rng.uniform(1.6, 2.2)
        f0, f1 = rng.uniform(85, 100), rng.uniform(32, 42)
        growl = glide_sine(f0, f1, dur) + 0.5 * glide_sine(f0 * 2, f1 * 2, dur)
        growl *= adsr(len(growl), 0.35, 0.5, 0.55, dur * 0.35)
        growl = lowpass(growl, 260.0)
        add_at(buf, int(rtm * SR), growl * 0.5)

    buf = apply_reverb(buf, decay_time=1.8, wet=0.28, bright=True, seed=seed + 100)
    buf = normalize_peak(buf, -3.0)
    loop = crossfade_loop(buf, FADE)
    return loop


def main():
    jobs = [
        ("amb_inside", gen_inside, "56k"),
        ("amb_outside_day", gen_outside_day, "56k"),
        ("amb_outside_night", gen_outside_night, "56k"),
    ]
    for name, fn, bitrate in jobs:
        print(f"[gen] {name} ...")
        audio = fn()
        wav_path = RAW_TMP / f"{name}.wav"
        save_wav(wav_path, audio, SR)
        ogg_path = STATIC_AUDIO / f"{name}.ogg"
        encode_ogg(wav_path, ogg_path, bitrate, sample_rate=32000, channels=1)
        size_kb = ogg_path.stat().st_size / 1024
        print(f"  -> {ogg_path} ({size_kb:.1f} KB, {len(audio)/SR:.2f}s)")


if __name__ == "__main__":
    main()
