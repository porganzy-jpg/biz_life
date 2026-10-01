# -*- coding: utf-8 -*-
"""
gen_audio_combat_sfx.py — 전투(배치 방어) 전용 SFX (스프린트 10-A).

근거: docs/COMBAT_AND_DEFENSE.md §3(소리→실루엣→접촉), data/creatures.json(각 항목 sound/silhouette/contact
플레이버), docs/TASKS.md 요청함(시나리오 S9-B·개발 S8-B가 미리 요청해 둔 5+4종), 교본 05_SOUND A5·A6·A10.

이 스프린트의 핵심 문제: "전투에 소리가 없다" — 습격 3단계(소리→실루엣→접촉) 중 1단계(소리)가
대부분 생물에서 비어 있거나 엉뚱한 기존 파일(sfx_water_splash·amb_far_call·amb_outside_deep 등)을
억지로 돌려 쓰고 있다(engine/combat.py CREATURES[*].audio 현재값 참고). 여기서 **종마다 다른** 예고음을
만든다 — "같은 방식의 반복이 장르를 지루하게 만드는 주범"(COMBAT_AND_DEFENSE §4)은 소리에도 적용된다.

설계 원칙(이번 스프린트에서 지킨 것):
  - 악당이 없다(DECISIONS 2026-10-01). 으르렁대지 않는다. 배고프거나 궁금하거나 겨누거나 지나갈 뿐이다.
  - 긴목·윗물 아이는 "사람 소리를 흉내 낸 것"이라 리듬이 **미묘하게 어긋난다**(완전 등간격 금지).
  - 문지기·손톱 무리·덮개·그늘은 **없음으로 신호한다**(이 파일에 자산 없음 — 큐시트에 덕킹 스펙만).
  - 「먼 울음」(amb_far_call.ogg)은 건드리지 않는다. 문지기의 "sound" 필드는 현재 이 파일을
    placeholder로 재사용 중인데(engine/combat.py:68), 그대로 두면 "먼 울음"의 신비와 "문지기"의 위협이
    같은 소리로 섞여 혼동을 만든다 — 이번 스프린트가 이 placeholder를 없애는 것이 목적 중 하나다.

실행: python tools/gen_audio_combat_sfx.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from gen_audio_common import (
    SR, bandpass, lowpass, highpass, white_noise, pink_noise, brown_noise,
    sine, glide_sine, exp_env, adsr, add_at, apply_reverb,
    normalize_peak, save_wav, encode_ogg,
)

ROOT = Path(__file__).resolve().parents[1]
STATIC_AUDIO = ROOT / "static" / "audio"
RAW_TMP = ROOT / "audio" / "_tmp"
RAW_TMP.mkdir(parents=True, exist_ok=True)
STATIC_AUDIO.mkdir(parents=True, exist_ok=True)


def _buf(dur):
    return np.zeros(int(dur * SR)), int(dur * SR)


# ───────────────────────── 1. 예고음(소리 단계) ─────────────────────────

def gen_warn_longneck(seed=301):
    """긴목 예고(소리 단계) — 기존 sfx_knock_glass(접촉 단계, 코앞)보다 **멀고 먹먹하다**.
    사람이 내던 소리를 흉내 낸 것이라 간격이 완전 등간격이 아니다(±jitter)."""
    rng = np.random.default_rng(seed)
    dur = 1.9
    buf, n = _buf(dur)
    nominal = 0.46
    t = 0.0
    partials = [(1500, 1.0), (2350, 0.46), (3550, 0.22)]
    for i in range(3):
        jitter = rng.uniform(-0.09, 0.09) * nominal
        kt = t
        kdur = 0.13
        kn = int(kdur * SR)
        knock = np.zeros(kn)
        for f, a in partials:
            knock += a * np.sin(2 * np.pi * f * np.arange(kn) / SR)
        knock *= exp_env(kn, 0.05)
        amp = rng.uniform(0.5, 0.7)
        add_at(buf, int(kt * SR), knock * amp * 0.35)
        t += nominal + jitter
    buf = lowpass(buf, 2200.0)               # 멀고 물을 거친 느낌(접촉 단계보다 먹먹)
    buf = apply_reverb(buf, 1.6, wet=0.28, bright=False, seed=seed)
    buf = normalize_peak(buf, -5.0)
    return buf


def gen_warden_press(seed=302):
    """문지기 — **소리 단계는 자산 없음**(다른 모든 소리가 사라지는 덕킹, 큐시트 참고).
    이 파일은 실루엣 단계용 — '그림자가 아니라 압력이 먼저 온다. 유리가 한 번 휜다'(creatures.json)."""
    rng = np.random.default_rng(seed)
    dur = 2.2
    buf, n = _buf(dur)
    press = sine(46.0, 1.4) * exp_env(int(1.4 * SR), 0.6)
    env = np.concatenate([
        np.linspace(0, 1, int(0.5 * SR)) ** 1.5,
        np.linspace(1, 0.15, int(1.4 * SR) - int(0.5 * SR)),
    ])
    env = np.pad(env, (0, len(press) - len(env)), mode="edge")[:len(press)]
    press = press * env
    press = lowpass(press, 90.0)
    add_at(buf, int(0.1 * SR), press * 0.9)
    creak_n = int(0.6 * SR)
    creak = bandpass(rng.standard_normal(creak_n), 3200, 6000) * exp_env(creak_n, 0.18)
    add_at(buf, int(0.35 * SR), creak * 0.08)   # 유리가 휘는 아주 희미한 고역
    buf = normalize_peak(buf, -4.0)
    return buf


def gen_warn_swarm(seed=303):
    """작은 떼 — 이음매를 긁는 **잘고 많은** 잔소리. 높고 바쁘다(손톱 무리와 반대)."""
    rng = np.random.default_rng(seed)
    dur = 2.1
    buf, n = _buf(dur)
    n_scr = 13
    times = np.sort(rng.uniform(0.0, dur - 0.15, n_scr))
    for tt in times:
        sdur = rng.uniform(0.04, 0.09)
        sn = int(sdur * SR)
        f_lo = rng.uniform(3000, 4500)
        scr = bandpass(rng.standard_normal(sn), f_lo, f_lo + rng.uniform(1200, 2200))
        scr *= exp_env(sn, sdur * 0.4)
        add_at(buf, int(tt * SR), scr * rng.uniform(0.18, 0.32))
    buf = normalize_peak(buf, -6.0)
    return buf


def gen_warn_claws(seed=304):
    """손톱 무리 — 실루엣 단계용(소리 단계는 '없음'으로 신호, 큐시트 참고). **느리고 많다**:
    낮은 대역·굵은 입자·느린 간격. swarm(높고 바쁨)과 스펙트럼·리듬 둘 다 반대로 설계."""
    rng = np.random.default_rng(seed)
    dur = 3.0
    buf, n = _buf(dur)
    n_scr = 8
    times = np.sort(rng.uniform(0.0, dur - 0.3, n_scr))
    for tt in times:
        sdur = rng.uniform(0.12, 0.22)
        sn = int(sdur * SR)
        scr = bandpass(rng.standard_normal(sn), 700, 1900)
        scr *= exp_env(sn, sdur * 0.55)
        add_at(buf, int(tt * SR), scr * rng.uniform(0.22, 0.4))
    buf = lowpass(buf, 2400.0)                 # 모래 속에서 들리는 먹먹함
    buf = apply_reverb(buf, 1.2, wet=0.22, bright=False, seed=seed + 1)
    buf = normalize_peak(buf, -7.0)
    return buf


def gen_warn_mirroreye(seed=305):
    """거울눈 — 긁는 소리가 아니라 **비비는** 소리(유리에 몸을 미는, 연속음)."""
    rng = np.random.default_rng(seed)
    dur = 2.4
    buf, n = _buf(dur)
    noise = bandpass(rng.standard_normal(n), 1400, 3400)
    glide = 0.5 + 0.5 * np.sin(2 * np.pi * np.linspace(0, 1.3, n))
    env = np.concatenate([
        np.linspace(0, 1, int(0.3 * SR)),
        np.ones(n - int(0.3 * SR) - int(0.3 * SR)),
        np.linspace(1, 0, int(0.3 * SR)),
    ])
    env = np.pad(env, (0, n - len(env)), mode="edge")[:n]
    buf = noise * glide * env * 0.5
    buf = normalize_peak(buf, -7.0)
    return buf


def gen_warn_straight(seed=306):
    """곧은치 — 물이 한 번 당겨졌다 놓이는 소리, 그 뒤 **완전한 정지 2초**(겨누는 중)."""
    rng = np.random.default_rng(seed)
    dur = 2.8
    buf, n = _buf(dur)
    pull_dur = 0.55
    pn = int(pull_dur * SR)
    pull = bandpass(rng.standard_normal(pn), 300, 1600)
    ramp = np.linspace(0.1, 1.0, pn) ** 1.6
    pull *= ramp
    add_at(buf, 0, pull * 0.45)
    release = bandpass(rng.standard_normal(int(0.08 * SR)), 500, 2200) * exp_env(int(0.08 * SR), 0.02)
    add_at(buf, pn, release * 0.5)
    # 0.75s ~ 2.75s: 완전한 정지(거의 무음, 숨죽인 아주 희미한 저역만 — 들린다기보다 있는 줄만 안다)
    hold = sine(42.0, 2.0) * 0.005
    add_at(buf, int(0.75 * SR), hold)
    buf = normalize_peak(buf, -6.0)
    return buf


def gen_warn_needle(seed=307):
    """바늘 — 낮고 긴 마찰음이 위에서 아래로 **15초 이상** 지나간다(명단에서 가장 긴 큐).
    '한 번에 끝나지 않는다' → 겹치는 스웰 여러 개로 울퉁불퉁하게."""
    rng = np.random.default_rng(seed)
    dur = 16.0
    buf, n = _buf(dur)
    base = bandpass(rng.standard_normal(n), 55, 260)
    # 위->아래로 지나가는 인상: 대역이 느리게 하강(센터 주파수를 시간에 따라 낮춘다)
    seg = n // 8
    out = np.zeros(n)
    centers = np.linspace(230, 70, 8)
    for i, c in enumerate(centers):
        s, e = i * seg, min(n, (i + 1) * seg + int(0.3 * SR))
        chunk = bandpass(base[s:e] if e <= n else np.pad(base[s:], (0, e - n)), max(30, c - 60), c + 60, order=3)
        out[s:min(e, n)] += chunk[: min(e, n) - s]
    # 여러 개의 겹치는 스웰(한 번에 끝나지 않음)
    for i in range(4):
        st = i * (dur / 4.2)
        sd = rng.uniform(4.0, 6.0)
        sn = int(sd * SR)
        s0 = int(st * SR)
        if s0 >= n:
            continue
        seg = out[s0:s0 + sn]
        sn2 = len(seg)
        swell = np.linspace(0, 1, sn2 // 2)
        swell = np.concatenate([swell ** 0.8, swell[::-1] ** 1.3])
        swell = np.pad(swell, (0, max(0, sn2 - len(swell))))[:sn2]
        add_at(buf, s0, seg * swell * rng.uniform(0.3, 0.45))
    buf = lowpass(buf, 320.0)
    buf = apply_reverb(buf, 3.0, wet=0.3, bright=False, seed=seed)
    buf = normalize_peak(buf, -6.0)
    return buf


def gen_warn_bigmaw(seed=308):
    """큰 입 — 아주 느린 물의 밀림. '랜턴 불꽃이 같은 간격으로 두 번 눕는다' → 느린 스웰 2회."""
    rng = np.random.default_rng(seed)
    dur = 7.6
    buf, n = _buf(dur)
    base = bandpass(rng.standard_normal(n), 25, 140)
    for i, st in enumerate([0.3, 4.0]):
        sd = 3.0
        sn = int(sd * SR)
        s0 = int(st * SR)
        if s0 >= n:
            continue
        swell = np.concatenate([
            np.linspace(0, 1, int(sn * 0.45)) ** 0.7,
            np.linspace(1, 0, sn - int(sn * 0.45)) ** 1.4,
        ])
        seg = base[s0:s0 + sn]
        swell = swell[: len(seg)]
        add_at(buf, s0, seg * swell * 0.6)
    buf = lowpass(buf, 110.0)
    buf = apply_reverb(buf, 2.4, wet=0.26, bright=False, seed=seed + 2)
    buf = normalize_peak(buf, -5.0)
    return buf


def gen_warn_follower(seed=309):
    """따라온 것 — 창고 쪽 유리가 한 번 운다. 한참 뒤 아래에서 같은 소리가 **답한다**(더 낮고 먹먹하게)."""
    rng = np.random.default_rng(seed)
    dur = 5.6
    buf, n = _buf(dur)

    def groan(f0, f1, d, bright):
        gn = int(d * SR)
        g = glide_sine(f0, f1, d) * exp_env(gn, d * 0.4)
        g = bandpass(g + 0.3 * rng.standard_normal(gn), max(1, f0 - 60), f1 + 300, order=3)
        return g

    first = groan(210, 160, 0.9, True)
    add_at(buf, int(0.1 * SR), first * 0.4)
    second = groan(130, 95, 1.1, False)
    second = lowpass(second, 220.0)
    second = apply_reverb(second, 2.0, wet=0.4, bright=False, seed=seed + 3)
    add_at(buf, int(2.6 * SR), second * 0.42)      # "한참 뒤" + 아래(먹먹)
    buf = normalize_peak(buf, -6.0)
    return buf


def gen_warn_upperchild(seed=310):
    """윗물 아이 — 긴목과 같은 음색 계열인데 **더 빠르고 더 어긋나고** 겁먹은 느낌(떨림)."""
    rng = np.random.default_rng(seed)
    dur = 1.6
    buf, n = _buf(dur)
    partials = [(1700, 1.0), (2650, 0.4), (4000, 0.2)]   # 긴목보다 살짝 높은 음역(작은 몸)
    t = 0.0
    for i in range(5):
        jitter = rng.uniform(-0.35, 0.35)
        kdur = 0.09
        kn = int(kdur * SR)
        knock = np.zeros(kn)
        for f, a in partials:
            knock += a * np.sin(2 * np.pi * f * np.arange(kn) / SR)
        trem = 1.0 + 0.15 * np.sin(2 * np.pi * 14 * np.arange(kn) / SR)  # 떨림
        knock *= exp_env(kn, 0.03) * trem
        add_at(buf, int(max(0.0, t) * SR), knock * rng.uniform(0.35, 0.55) * 0.4)
        t += 0.22 + 0.22 * jitter
    buf = lowpass(buf, 3200.0)
    buf = normalize_peak(buf, -6.0)
    return buf


def gen_octopus_enter(seed=311):
    """동거 문어 입장 — 에어락 틈새 물소리 + 빨판. 위협 큐들과 확실히 다르게 **따뜻하고 작다**."""
    rng = np.random.default_rng(seed)
    dur = 1.1
    buf, n = _buf(dur)
    trickle = bandpass(rng.standard_normal(int(0.45 * SR)), 500, 2600)
    trickle *= np.linspace(0, 1, int(0.45 * SR)) ** 0.6
    add_at(buf, 0, trickle * 0.28)
    for i, t0 in enumerate([0.5, 0.75]):
        pdur = 0.07
        pn = int(pdur * SR)
        pop = glide_sine(230, 140, pdur) * exp_env(pn, 0.02)
        add_at(buf, int(t0 * SR), pop * 0.3)
    buf = lowpass(buf, 3000.0)
    buf = normalize_peak(buf, -6.0)
    return buf


# ───────────────────────── 2. 결과음(접촉 이후) ─────────────────────────

def gen_defend_held(seed=312):
    """막았다 — 안도. 승리 팡파르가 아니라 **물러가는 소리 + 작은 안도의 숨**(DECISIONS: 죽이는 것이 동사가 아니다)."""
    rng = np.random.default_rng(seed)
    dur = 1.7
    buf, n = _buf(dur)
    whoomph = bandpass(rng.standard_normal(int(0.5 * SR)), 150, 900) * exp_env(int(0.5 * SR), 0.18)
    add_at(buf, 0, whoomph * 0.4)
    # 부드러운 공명 두 음(완전5도): 안도감 있는 화음, 타악기적 신스 아님
    t1 = sine(220.0, 1.1) * exp_env(int(1.1 * SR), 0.5)
    t2 = sine(330.0, 1.1) * exp_env(int(1.1 * SR), 0.45) * 0.6
    tone = (t1 + t2)
    tone = lowpass(tone, 2600.0)
    add_at(buf, int(0.15 * SR), tone * 0.22)
    buf = apply_reverb(buf, 1.1, wet=0.2, bright=True, seed=seed)
    buf = normalize_peak(buf, -5.0)
    return buf


# ───────────────────────── 3. 조작음 ─────────────────────────

def gen_pickup_person(seed=313):
    rng = np.random.default_rng(seed)
    dur = 0.35
    buf, n = _buf(dur)
    rustle = bandpass(rng.standard_normal(n), 2200, 5200) * exp_env(n, 0.09)
    buf = rustle * 0.35
    buf = normalize_peak(buf, -9.0)
    return buf


def gen_place_person(seed=314):
    rng = np.random.default_rng(seed)
    dur = 0.4
    buf, n = _buf(dur)
    thud = bandpass(rng.standard_normal(int(0.08 * SR)), 120, 420) * exp_env(int(0.08 * SR), 0.03)
    add_at(buf, 0, thud * 0.4)
    tail = bandpass(rng.standard_normal(int(0.2 * SR)), 2000, 4500) * exp_env(int(0.2 * SR), 0.06)
    add_at(buf, int(0.03 * SR), tail * 0.15)
    buf = normalize_peak(buf, -9.0)
    return buf


def gen_light_off(seed=315):
    rng = np.random.default_rng(seed)
    dur = 0.5
    buf, n = _buf(dur)
    click = bandpass(rng.standard_normal(int(0.006 * SR)), 800, 6000) * exp_env(int(0.006 * SR), 0.002)
    add_at(buf, 0, click * 0.5)
    hum = sine(118.0, 0.32) * np.linspace(0.5, 0.0, int(0.32 * SR)) ** 1.2
    add_at(buf, int(0.01 * SR), hum * 0.12)
    buf = normalize_peak(buf, -10.0)
    return buf


def gen_light_on(seed=316):
    rng = np.random.default_rng(seed)
    dur = 0.45
    buf, n = _buf(dur)
    click = bandpass(rng.standard_normal(int(0.006 * SR)), 800, 6000) * exp_env(int(0.006 * SR), 0.002)
    add_at(buf, 0, click * 0.5)
    hum = sine(118.0, 0.3) * np.linspace(0.0, 0.5, int(0.3 * SR)) ** 0.8
    add_at(buf, int(0.01 * SR), hum * 0.12)
    buf = normalize_peak(buf, -10.0)
    return buf


def gen_power_down(seed=317):
    rng = np.random.default_rng(seed)
    dur = 1.6
    buf, n = _buf(dur)
    thunk = sine(55.0, 0.25) * exp_env(int(0.25 * SR), 0.05)
    thunk = lowpass(thunk, 140.0)
    add_at(buf, 0, thunk * 0.6)
    clank = bandpass(rng.standard_normal(int(0.03 * SR)), 600, 2600) * exp_env(int(0.03 * SR), 0.01)
    add_at(buf, int(0.005 * SR), clank * 0.35)
    spindown = glide_sine(78.0, 18.0, 1.2)
    env = np.linspace(0.35, 0.0, int(1.2 * SR)) ** 1.3
    spindown = spindown[: len(env)] * env
    add_at(buf, int(0.25 * SR), spindown * 0.5)
    buf = normalize_peak(buf, -6.0)
    return buf


def gen_tool_install(seed=318):
    rng = np.random.default_rng(seed)
    dur = 0.65
    buf, n = _buf(dur)
    for i, t0 in enumerate([0.0, 0.1]):
        cn = int(0.02 * SR)
        clack = bandpass(rng.standard_normal(cn), 1000, 3800) * exp_env(cn, 0.008)
        add_at(buf, int(t0 * SR), clack * 0.4)
    settle = bandpass(rng.standard_normal(int(0.3 * SR)), 500, 1600) * exp_env(int(0.3 * SR), 0.08)
    add_at(buf, int(0.12 * SR), settle * 0.18)
    buf = normalize_peak(buf, -8.0)
    return buf


def main():
    jobs = [
        ("sfx_warn_longneck", gen_warn_longneck, "48k"),
        ("sfx_warden_press", gen_warden_press, "48k"),
        ("sfx_warn_swarm", gen_warn_swarm, "48k"),
        ("sfx_warn_claws", gen_warn_claws, "48k"),
        ("sfx_warn_mirroreye", gen_warn_mirroreye, "48k"),
        ("sfx_warn_straight", gen_warn_straight, "40k"),
        ("sfx_warn_needle", gen_warn_needle, "32k"),
        ("sfx_warn_bigmaw", gen_warn_bigmaw, "36k"),
        ("sfx_warn_follower", gen_warn_follower, "40k"),
        ("sfx_warn_upperchild", gen_warn_upperchild, "48k"),
        ("sfx_octopus_enter", gen_octopus_enter, "48k"),
        ("sfx_defend_held", gen_defend_held, "48k"),
        ("sfx_pickup_person", gen_pickup_person, "48k"),
        ("sfx_place_person", gen_place_person, "48k"),
        ("sfx_light_off", gen_light_off, "48k"),
        ("sfx_light_on", gen_light_on, "48k"),
        ("sfx_power_down", gen_power_down, "48k"),
        ("sfx_tool_install", gen_tool_install, "48k"),
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
