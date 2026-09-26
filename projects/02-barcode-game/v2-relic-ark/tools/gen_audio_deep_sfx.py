# -*- coding: utf-8 -*-
"""
gen_audio_deep_sfx.py — 심해 1막 SFX 6종 (스프린트 4-D).
교본 05_SOUND A6(짧고 유물답게)·A8(SFX ≤40KB)·A10(침묵 설계).

sfx_airlock_cycle : 문 도는 소리(걸쇠+바퀴) + 물 차오름. 크로스페이드 트리거의 기준 파형.
sfx_glass_crack   : 손톱으로 긁는 소리 -> 유리에 금이 가는 소리(전조 -> 사건).
sfx_knock_glass   : 긴목이 유리를 두드림 — 생물이 흉내 내는 것이라 **간격이 조금씩 어긋난다**.
sfx_air_low       : 공기 부족 경고 — 숫자·비프가 아니라 **호흡이 얕아지는** 느낌.
sfx_collect       : 해저에서 조각 줍기 — 물속에서 먹먹한 클링크 + 잔거품.
sfx_room_flood    : 격벽이 닫히고 방이 잠김 — 쾅(닫힘) -> 밀려드는 물 -> 급격히 죽는 꼬리
                    (그 뒤로 "그 방만 소리가 없어진다"는 게임 쪽 처리를 유도하는 급감 엔벨로프).

실행: python tools/gen_audio_deep_sfx.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from gen_audio_common import (
    SR, bandpass, lowpass, sine, glide_sine, exp_env, adsr, add_at,
    normalize_peak, save_wav, encode_ogg,
)

ROOT = Path(__file__).resolve().parents[1]
STATIC_AUDIO = ROOT / "static" / "audio"
RAW_TMP = ROOT / "audio" / "_tmp"
RAW_TMP.mkdir(parents=True, exist_ok=True)
STATIC_AUDIO.mkdir(parents=True, exist_ok=True)


def gen_airlock_cycle(seed=201):
    """0.0 걸쇠 풀림 -> 0.3~1.8 바퀴 돌아감(라쳇 클릭) -> 1.0~3.0 물 차오름 -> 3.0~4.0 정착.
    큐시트 §심해-2의 크로스페이드 타이밍이 이 파형의 구간에 맞춰져 있다."""
    rng = np.random.default_rng(seed)
    dur = 4.0
    n = int(dur * SR)
    buf = np.zeros(n)

    # 걸쇠 풀림: 저역 쿵 + 금속성 클랑크
    thunk = sine(65.0, 0.3) * exp_env(int(0.3 * SR), 0.09)
    thunk = lowpass(thunk, 160.0)
    add_at(buf, 0, thunk * 0.85)
    clank = bandpass(rng.standard_normal(int(0.05 * SR)), 800, 3200) * exp_env(int(0.05 * SR), 0.015)
    add_at(buf, int(0.01 * SR), clank * 0.5)

    # 바퀴 돌아감: 라쳇 클릭 다발(가속 -> 감속)
    n_clicks = 10
    click_frac = np.linspace(0.0, 1.0, n_clicks)
    accel_shape = np.sin(click_frac * np.pi)  # 느림->빠름->느림
    t0 = 0.30
    span = 1.5
    pos = t0 + np.cumsum(0.06 + 0.10 * (1 - accel_shape))
    for i, tp in enumerate(pos):
        if tp > t0 + span:
            break
        cdur = 0.03
        cn = int(cdur * SR)
        c = bandpass(rng.standard_normal(cn), 1200, 4000) * exp_env(cn, 0.012)
        add_at(buf, int(tp * SR), c * 0.30)

    # 물 차오름: 노이즈 스웰(1.0~3.0s) + 거품 클릭
    fill_start, fill_dur = 1.0, 2.0
    fn = int(fill_dur * SR)
    fill = bandpass(rng.standard_normal(fn), 200, 4500)
    ramp = np.linspace(0, 1, fn) ** 0.7
    fill = fill * ramp
    add_at(buf, int(fill_start * SR), fill * 0.30)
    n_bub = 14
    bub_times = rng.uniform(fill_start + 0.2, fill_start + fill_dur - 0.1, n_bub)
    for bt in bub_times:
        bdur = 0.05
        bn = int(bdur * SR)
        bub = glide_sine(rng.uniform(500, 1200), rng.uniform(250, 500), bdur) * exp_env(bn, 0.02)
        add_at(buf, int(bt * SR), bub * 0.15)

    # 정착(3.0~4.0): 잔잔한 하이패스 히스가 잦아듦
    settle = bandpass(rng.standard_normal(int(1.0 * SR)), 300, 2500) * exp_env(int(1.0 * SR), 0.3)
    add_at(buf, int(3.0 * SR), settle * 0.12)

    buf = normalize_peak(buf, -3.0)
    return buf


def gen_glass_crack(seed=202):
    """0.0~0.9 손톱으로 긁는 소리(불규칙 스타카토) -> 0.9~1.6 유리에 금(날카로운 전조+공명)."""
    rng = np.random.default_rng(seed)
    dur = 1.6
    n = int(dur * SR)
    buf = np.zeros(n)

    # 손톱 긁기: 짧은 노이즈 스터터, 불균일 간격/피치
    n_scratch = 9
    st = np.sort(rng.uniform(0.0, 0.85, n_scratch))
    for s in st:
        sdur = rng.uniform(0.03, 0.07)
        sn = int(sdur * SR)
        f_lo = rng.uniform(2500, 4000)
        f_hi = f_lo + rng.uniform(1500, 3000)
        scr = bandpass(rng.standard_normal(sn), f_lo, f_hi) * exp_env(sn, sdur * 0.35)
        add_at(buf, int(s * SR), scr * rng.uniform(0.25, 0.45))

    # 금 가는 소리: 날카로운 트랜지언트 + 유리 공명(배음 몇 개, 빠른 감쇠)
    crack_t = 0.95
    click = bandpass(rng.standard_normal(int(0.008 * SR)), 1500, 9000) * exp_env(int(0.008 * SR), 0.003)
    add_at(buf, int(crack_t * SR), click * 0.9)
    partials = [(2200, 1.0, 0.10), (3300, 0.6, 0.07), (4900, 0.35, 0.05), (6600, 0.18, 0.035)]
    ring_dur = 0.55
    rn = int(ring_dur * SR)
    ring = np.zeros(rn)
    for f, amp, tau in partials:
        ring += amp * np.sin(2 * np.pi * f * np.arange(rn) / SR) * np.exp(-np.arange(rn) / SR / tau)
    add_at(buf, int(crack_t * SR), ring * 0.35)

    buf = normalize_peak(buf, -3.0)
    return buf


def gen_knock_glass(seed=203):
    """긴목이 유리를 두드림. 3회, **간격이 조금씩 어긋난다**(생물의 흉내 = 완전 등간격 금지)."""
    rng = np.random.default_rng(seed)
    dur = 1.35
    n = int(dur * SR)
    buf = np.zeros(n)
    # 의도적으로 불균일한 간격(등간격이면 기계처럼 들림)
    knock_times = [0.0, 0.42, 0.93]
    amps = [0.85, 0.55, 0.70]
    for kt, amp in zip(knock_times, amps):
        kdur = 0.14
        kn = int(kdur * SR)
        # 유리 같은 금속성 공명(배음비가 정수배가 아니게)
        partials = [(1500, 1.0), (2350, 0.5), (3550, 0.28)]
        knock = np.zeros(kn)
        for f, a in partials:
            knock += a * np.sin(2 * np.pi * f * np.arange(kn) / SR)
        knock *= exp_env(kn, 0.045)
        thud = sine(180, 0.03) * exp_env(int(0.03 * SR), 0.012)
        add_at(buf, int(kt * SR), knock * amp * 0.55)
        add_at(buf, int(kt * SR), np.pad(thud, (0, kn - len(thud))) * amp * 0.3)
    buf = normalize_peak(buf, -3.0)
    return buf


def gen_air_low(seed=204):
    """공기 부족 경고 — 비프 없음. 짧고 얕아지는 숨 3회, 간격이 점점 좁아진다(조급함)."""
    rng = np.random.default_rng(seed)
    dur = 2.0
    n = int(dur * SR)
    buf = np.zeros(n)
    starts = [0.0, 0.55, 0.95]  # 간격 0.55 -> 0.40 (좁아짐)
    durs = [0.42, 0.34, 0.26]   # 숨이 점점 짧아짐(얕아짐)
    for st, bd in zip(starts, durs):
        bn = int(bd * SR)
        breath = bandpass(rng.standard_normal(bn), 250, 1900)
        env = adsr(bn, bd * 0.25, bd * 0.2, 0.5, bd * 0.35)
        add_at(buf, int(st * SR), breath * env * 0.5)
    buf = normalize_peak(buf, -4.0)
    return buf


def gen_collect(seed=205):
    """해저에서 조각 줍기 — 먹먹한 클링크(물속) + 작은 거품."""
    rng = np.random.default_rng(seed)
    dur = 0.9
    n = int(dur * SR)
    buf = np.zeros(n)
    # 먹먹한 클링크: 고역이 물에 걸러진 금속성 틱
    clink = bandpass(rng.standard_normal(int(0.05 * SR)), 900, 2400) * exp_env(int(0.05 * SR), 0.02)
    add_at(buf, 0, clink * 0.6)
    tone = sine(1450, 0.09) * exp_env(int(0.09 * SR), 0.03)
    tone = lowpass(tone, 2600.0)
    add_at(buf, int(0.005 * SR), tone * 0.3)
    # 거품 2~3개
    n_bub = 3
    bub_times = rng.uniform(0.08, 0.6, n_bub)
    for bt in bub_times:
        bdur = 0.06
        bn = int(bdur * SR)
        bub = glide_sine(rng.uniform(600, 1000), rng.uniform(300, 500), bdur) * exp_env(bn, 0.025)
        add_at(buf, int(bt * SR), bub * 0.22)
    buf = lowpass(buf, 3200.0)  # 물속 먹먹함
    buf = normalize_peak(buf, -3.0)
    return buf


def gen_room_flood(seed=206):
    """격벽 닫힘(쾅) -> 물 밀려듦(로어) -> 급격히 죽는 꼬리(이 방의 소리가 사라짐을 암시)."""
    rng = np.random.default_rng(seed)
    dur = 2.2
    n = int(dur * SR)
    buf = np.zeros(n)
    # 격벽 쾅: 저역 임팩트 + 금속 클랑
    slam = sine(58.0, 0.35) * exp_env(int(0.35 * SR), 0.07)
    slam = lowpass(slam, 150.0)
    add_at(buf, 0, slam * 0.9)
    clang = bandpass(rng.standard_normal(int(0.06 * SR)), 700, 3000) * exp_env(int(0.06 * SR), 0.02)
    add_at(buf, int(0.005 * SR), clang * 0.5)
    # 물 밀려듦: 노이즈 로어, 빠르게 부풀었다가 "삼켜지듯" 급감
    roar_start = 0.25
    roar_dur = 1.1
    rn = int(roar_dur * SR)
    roar = bandpass(rng.standard_normal(rn), 150, 5000)
    swell = np.concatenate([
        np.linspace(0, 1, int(rn * 0.35)) ** 0.6,
        np.linspace(1, 0.0, rn - int(rn * 0.35)) ** 2.2,  # 급격한 죽음(그 방의 소리가 없어진다)
    ])
    roar = roar * swell
    add_at(buf, int(roar_start * SR), roar * 0.55)
    # 꼬리: 거의 무음(방이 잠긴 뒤의 정적을 암시하는 짧은 저역 잔향만)
    tail = sine(40.0, 0.5) * exp_env(int(0.5 * SR), 0.12)
    add_at(buf, int(1.5 * SR), tail * 0.06)
    buf = normalize_peak(buf, -3.0)
    return buf


def main():
    jobs = [
        ("sfx_airlock_cycle", gen_airlock_cycle, "56k"),
        ("sfx_glass_crack", gen_glass_crack, "64k"),
        ("sfx_knock_glass", gen_knock_glass, "56k"),
        ("sfx_air_low", gen_air_low, "56k"),
        ("sfx_collect", gen_collect, "56k"),
        ("sfx_room_flood", gen_room_flood, "56k"),
    ]
    for name, fn, bitrate in jobs:
        print(f"[gen] {name} ...")
        audio = fn()
        wav_path = RAW_TMP / f"{name}.wav"
        save_wav(wav_path, audio, SR)
        ogg_path = STATIC_AUDIO / f"{name}.ogg"
        encode_ogg(wav_path, ogg_path, bitrate, sample_rate=32000, channels=1)
        size_kb = ogg_path.stat().st_size / 1024
        print(f"  -> {ogg_path} ({size_kb:.2f} KB, {len(audio)/SR:.2f}s)")


if __name__ == "__main__":
    main()
