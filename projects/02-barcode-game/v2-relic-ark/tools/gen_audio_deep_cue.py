# -*- coding: utf-8 -*-
"""
gen_audio_deep_cue.py — 발견 큐 + 먼 울음 (스프린트 4-D).
교본 05_SOUND A2(음악은 드물게)·A3(물에서 시작)·A10(직전 침묵).

cue_vent_garden : 열수구 정원 발견(spot_vent_garden). 0.8초 무음 -> 30초 루프.
                  물소리 -> 거품(열수구) -> 낮은 음 한 개 -> 리디안 모달 코드 -> 멜로디 3~4음.
                  이전 스프린트(cue_spot_found)가 D 도리안을 썼으므로, 이번은 **G 리디안**으로
                  색을 구분한다(둘 다 장조/단조 아님 — 05_SOUND A3).
amb_far_call    : 해구의 「먼 울음」. 정체를 밝히지 않는다(DECISIONS 2026-09-22 봉인,
                  2막 입구에서 회수 예정). 아주 낮고 짧은 단발음 — 재생 간격은 게임 쪽에서
                  조절(설정상 간격이 점점 짧아진다). 이 파일은 그 "한 번"만 담당한다.

실행: python tools/gen_audio_deep_cue.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from gen_audio_common import (
    SR, bandpass, lowpass, exp_env, adsr, add_at, apply_reverb,
    normalize_peak, crossfade_loop, silence, save_wav, encode_ogg,
    glide_sine,
)

ROOT = Path(__file__).resolve().parents[1]
STATIC_AUDIO = ROOT / "static" / "audio"
RAW_TMP = ROOT / "audio" / "_tmp"
RAW_TMP.mkdir(parents=True, exist_ok=True)
STATIC_AUDIO.mkdir(parents=True, exist_ok=True)

LOOP_LEN = 30.0
FADE = 1.5
RAW_LEN = LOOP_LEN + FADE
LEAD_SILENCE = 0.8  # A10

# G 리디안 음계(G A B C# D E F#) — 장3도+완전5도는 장조와 같으나 #11(C#)이 "낯섦"을 만든다.
G2, B2, D3 = 98.00, 123.47, 146.83
G3, B3, CS4, D4, F4S = 196.00, 246.94, 277.18, 293.66, 369.99
D5, E5, FS5, B4 = 587.33, 659.25, 739.99, 493.88


def bell_tone(freq, dur, partials=((1.0, 1.0), (2.0, 0.5), (3.01, 0.22), (4.2, 0.10)),
              decay_scale=1.0, attack=0.02):
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


def vent_bed(n, rng, rise_sec=3.0):
    """물소리 바탕 — 열수구답게 아주 낮은 '보글거림' 성분을 섞는다(잔잔한 잉어 물튀김 대신)."""
    noise = bandpass(rng.standard_normal(n), 200, 3800)
    slow = rng.standard_normal(int(n / 4410) + 2)
    slow_env = np.interp(np.linspace(0, len(slow) - 1, n), np.arange(len(slow)), slow)
    slow_env = lowpass(slow_env, 1.3)
    slow_env = 0.6 + 0.4 * (slow_env / (np.max(np.abs(slow_env)) + 1e-9))
    rise = np.ones(n)
    rn = int(rise_sec * SR)
    if rn > 0:
        rise[:rn] = np.linspace(0, 1, rn) ** 0.6
    return noise * slow_env * rise


def vent_bubbles(rng):
    """A3의 '물튀김' 자리 — 열수구는 튀는 대신 굵은 거품이 천천히 올라온다."""
    dur = 1.6
    n = int(dur * SR)
    ev = np.zeros(n)
    n_bub = 6
    times = np.sort(rng.uniform(0.0, dur - 0.15, n_bub))
    for i, bt in enumerate(times):
        bdur = rng.uniform(0.08, 0.16)
        bn = int(bdur * SR)
        f0 = rng.uniform(180, 420) * (1 - i * 0.05)
        f1 = f0 * rng.uniform(1.6, 2.2)
        bub = glide_sine(f0, f1, bdur) * exp_env(bn, bdur * 0.4)
        s = int(bt * SR)
        add_at(ev, s, bub * rng.uniform(0.3, 0.55))
    return ev


def gen_vent_garden(seed=52):
    rng = np.random.default_rng(seed)
    n = int(RAW_LEN * SR)
    buf = np.zeros(n)

    # 1) 물소리: 서서히 차오름
    bed = vent_bed(n, rng, rise_sec=3.0)
    buf += 0.13 * bed

    # 2) 거품(열수구의 "물튀김" 대응, A3)
    bub = vent_bubbles(rng)
    add_at(buf, int(1.2 * SR), bub)

    # 3) 낮은 음 한 개(G2, 리디안 근음)
    tone = bell_tone(G2, 6.0, decay_scale=1.3, attack=0.02)
    add_at(buf, int(3.2 * SR), tone * 0.5)

    # 4) 리디안 모달 코드(G B D + C#=#11 — "장조인데 낯섦")
    chord_start = 7.2
    chord_dur = 15.5
    for f, amp in [(G3, 0.28), (B3, 0.20), (D4, 0.20), (CS4, 0.16)]:
        pad = pad_tone(f, chord_dur, attack=2.0)
        add_at(buf, int(chord_start * SR), pad * amp)

    # 5) 멜로디 3~4음(리디안: D5-B4-FS5-E5, 성기게)
    melody = [(10.2, D5, 1.5), (13.6, B4, 1.6), (17.2, FS5, 1.7), (21.2, E5, 2.4)]
    for start, freq, mdur in melody:
        note = bell_tone(freq, mdur, decay_scale=1.0, attack=0.02)
        add_at(buf, int(start * SR), note * 0.26)

    # 두 번째 잔잔한 거품
    bub2 = vent_bubbles(rng)
    add_at(buf, int(24.8 * SR), bub2 * 0.5)

    buf = apply_reverb(buf, decay_time=3.0, wet=0.33, bright=True, seed=seed)
    buf = normalize_peak(buf, -4.0)
    loop = crossfade_loop(buf, FADE)
    full = np.concatenate([silence(LEAD_SILENCE), loop])
    return full


def gen_far_call(seed=53):
    """정체를 밝히지 않는 아주 낮은 단발음. 앞뒤에 짧은 무음 여유를 둬 어디서 잘라도
    자연스럽게 이어 붙일 수 있게 한다(게임이 간격을 조절해 반복 재생)."""
    rng = np.random.default_rng(seed)
    lead, tail = 0.4, 0.6
    call_dur = 2.6
    total = lead + call_dur + tail
    n = int(total * SR)
    buf = np.zeros(n)

    dur = call_dur
    cn = int(dur * SR)
    f0, f1 = 42.0, 27.0
    call = glide_sine(f0, f1, dur)
    call += 0.35 * glide_sine(f0 * 2.01, f1 * 2.03, dur)  # 살짝 불협한 배음 — 생물도 기계도 아니게
    env = adsr(cn, 0.5, 0.7, 0.55, dur * 0.35)
    # 아주 느린 트레몰로(진동)로 "숨쉬는 듯" 하지만 특정 생물 울음 패턴은 아니게
    trem = 0.85 + 0.15 * np.sin(2 * np.pi * 1.3 * np.arange(cn) / SR)
    call = call * env * trem
    call = lowpass(call, 140.0)
    add_at(buf, int(lead * SR), call * 0.6)

    buf = apply_reverb(buf, decay_time=2.5, wet=0.30, bright=False, seed=seed)
    buf = normalize_peak(buf, -4.0)
    return buf


def main():
    print("[gen] cue_vent_garden ...")
    audio = gen_vent_garden()
    wav_path = RAW_TMP / "cue_vent_garden.wav"
    save_wav(wav_path, audio, SR)
    ogg_path = STATIC_AUDIO / "cue_vent_garden.ogg"
    encode_ogg(wav_path, ogg_path, "112k", sample_rate=44100, channels=1)
    print(f"  -> {ogg_path} ({ogg_path.stat().st_size/1024:.1f} KB, {len(audio)/SR:.2f}s)")

    print("[gen] amb_far_call ...")
    audio2 = gen_far_call()
    wav_path2 = RAW_TMP / "amb_far_call.wav"
    save_wav(wav_path2, audio2, SR)
    ogg_path2 = STATIC_AUDIO / "amb_far_call.ogg"
    encode_ogg(wav_path2, ogg_path2, "48k", sample_rate=32000, channels=1)
    print(f"  -> {ogg_path2} ({ogg_path2.stat().st_size/1024:.1f} KB, {len(audio2)/SR:.2f}s)")


if __name__ == "__main__":
    main()
