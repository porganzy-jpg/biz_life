# -*- coding: utf-8 -*-
"""
gen_audio_deep_ambient.py — 심해 1막 앰비언트 3종 (스프린트 4-D).
교본 05_SOUND A1(안/밖 대비) + WORLD_BIBLE_DEEP §5-1(에어락=리더/정원사 분리).

amb_dome_inside : 돔 안. 기계 웅웅 + **사람 사는 소리 밀도 1~2회/초**(물방울·유리 삐걱·금속 딸깍·
                  발소리·냄비 소리·짧은 웃음 한 번·먼 웅얼거림). 따뜻하고 좁은 잔향(콘크리트). 저역 중심.
amb_outside_deep: 박광층/무광층 바깥. **착용자 자신의 호흡(4~6초 주기, 들숨/날숨 음색 분리, 헬멧 안처럼
                  가깝고 건조하게 — 잔향 없음)** + 압력(서브베이스) + 먼 해류(광대역, 이 둘에만 리버브).
                  넓고 차갑고 밝은 잔향(호흡 제외). **사람의 소리 0.**
amb_trench      : 해구. 더 낮고 더 빈 소리 — 아주 조용한 광대역 '공백 히스' + 서브베이스 바닥음 +
                  아주 가끔(1회/루프) 정체불명의 먼 신음(구조물이 내는 소리, 「먼 울음」과는 다른 것 —
                  「먼 울음」은 DECISIONS 2026-09-22로 봉인되어 amb_far_call.ogg로 별도 생성).

**2026-09-26 PM 피드백 반영(수정판)**: 원판은 돔 안/바깥의 순간 사건 밀도가 0.18/0.00회·초로만 갈리고
포락(엔벨로프)이 같은 ~2초 주기로 맥동해 "안/밖이 스펙트럼상 거의 같다"는 지적을 받았다. 이번 판은
(1) 바깥 호흡을 5초 주기·들숨/날숨 음색 분리·무잔향(건조)으로 다시 만들고, (2) 안쪽 이벤트를
1~2회/초로 대폭 늘리고(발소리·냄비·웃음 추가), (3) 잔향을 리버브가 걸리는 서브믹스와 안 걸리는
드라이 레이어로 물리적으로 분리해 **두 파일이 같은 변조를 공유하지 않게** 했다. 상세는
`docs/reports/sound_S4.md` §7.

실행: python tools/gen_audio_deep_ambient.py
출력: static/audio/amb_dome_inside.ogg, amb_outside_deep.ogg, amb_trench.ogg
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from gen_audio_common import (
    SR, bandpass, lowpass, highpass, sine, glide_sine, exp_env, adsr,
    add_at, apply_reverb, normalize_peak, crossfade_loop, save_wav,
    encode_ogg, pink_noise,
)

ROOT = Path(__file__).resolve().parents[1]
STATIC_AUDIO = ROOT / "static" / "audio"
RAW_TMP = ROOT / "audio" / "_tmp"
RAW_TMP.mkdir(parents=True, exist_ok=True)
STATIC_AUDIO.mkdir(parents=True, exist_ok=True)

LOOP_LEN = 45.0   # 초. 60초 이내 규격.
FADE = 2.0
RAW_LEN = LOOP_LEN + FADE


def _lfo(n, period_sec, phase=0.0, sr=SR):
    t = np.arange(n) / sr
    return np.sin(2 * np.pi * t / period_sec + phase)


def gen_dome_inside(seed=101):
    """돔 안: 기계 웅웅 + **사람 사는 소리 1~2회/초**(물방울·유리 삐걱·금속 딸깍·발소리·냄비·웃음 1회·
    먼 웅얼거림). 저역·좁은 잔향(유리·금속에 바로 부딪히는 소리 — 잔향 자체도 짧고 좁게 가둔다).
    PM 피드백(2026-09-26): 원판은 순간 사건이 0.18회/초(물방울만)라 "사람이 사는 소리"가 부족했다.
    이번 판은 SCRIPT_first_10min_deep.md 0:15 비트("냄비, 발소리, 웃음 한 번")를 그대로 채워 넣는다."""
    rng = np.random.default_rng(seed)
    n = int(RAW_LEN * SR)
    t = np.arange(n) / SR
    buf = np.zeros(n)

    # 1) 기계 웅웅(45/52Hz) — 루프주기 앰프 LFO
    hum = 0.6 * np.sin(2 * np.pi * 45.0 * t) + 0.4 * np.sin(2 * np.pi * 52.0 * t)
    hum_env = 0.7 + 0.3 * _lfo(n, RAW_LEN, phase=0.15)
    hum = lowpass(hum * hum_env, 120.0)
    buf += 0.20 * hum

    # 2) 물방울: 성긴 글리산도+클릭(밀도 상향 9->22)
    n_drips = 22
    drip_times = np.sort(rng.uniform(0.5, RAW_LEN - 1.0, n_drips))
    for dt in drip_times:
        dur = 0.20
        pitch0 = rng.uniform(950, 1400)
        tone = glide_sine(pitch0, pitch0 * 0.72, dur) * exp_env(int(dur * SR), 0.08)
        add_at(buf, int(dt * SR), tone * 0.40 * rng.uniform(0.6, 1.0))

    # 3) 유리 삐걱: 스틱-슬립 미세클릭 다발(활 켜는 모양의 피치 곡선)
    n_creaks = 2
    creak_times = np.sort(rng.uniform(4.0, RAW_LEN - 6.0, n_creaks))
    for ct in creak_times:
        cdur = rng.uniform(1.2, 1.8)
        cn = int(cdur * SR)
        creak = np.zeros(cn)
        base_f = rng.uniform(180, 320)
        n_micro = int(cdur * 22)
        for i in range(n_micro):
            frac = i / max(n_micro - 1, 1)
            jitter = rng.uniform(-0.02, 0.02)
            pos = int(min(max(frac + jitter, 0.0), 0.98) * cn)
            f = base_f * (1 + 0.35 * np.sin(frac * np.pi))
            mdur = 0.02
            mn = int(mdur * SR)
            click = bandpass(rng.standard_normal(mn), max(f - 60, 40), f + 140) * exp_env(mn, 0.01)
            add_at(creak, pos, click * rng.uniform(0.4, 0.9))
        creak = bandpass(creak, 120, 900)
        env = adsr(cn, 0.15, 0.3, 0.6, cdur * 0.35)
        add_at(buf, int(ct * SR), creak * env * 0.30)

    # 4) 금속 딸깍(파이프·이음매·연장): 아주 짧은 고역 클릭, 성기게 많이(신규, ~18회)
    n_clicks = 18
    click_times = rng.uniform(0.3, RAW_LEN - 0.3, n_clicks)
    for ck in click_times:
        cdur = 0.02
        cn = int(cdur * SR)
        c = bandpass(rng.standard_normal(cn), 1800, 4200) * exp_env(cn, 0.008)
        add_at(buf, int(ck * SR), c * rng.uniform(0.14, 0.26))

    # 5) 발소리(먼 복도): 부드러운 저역 둔탁음, 불규칙 보행 간격(신규, ~14회)
    n_steps = 14
    step_times = np.sort(rng.uniform(1.0, RAW_LEN - 1.0, n_steps))
    for stp in step_times:
        sdur = 0.10
        sn = int(sdur * SR)
        step = sine(rng.uniform(120, 220), sdur) * exp_env(sn, 0.03)
        step = lowpass(step, 320.0)
        add_at(buf, int(stp * SR), step * rng.uniform(0.10, 0.20))

    # 6) 냄비 소리(1회): 금속 다중 배음 + 중간 감쇠 — "냄비, 발소리, 웃음 한 번"(0:15 비트)
    pot_t = rng.uniform(5.0, RAW_LEN - 8.0)
    pdur = 0.35
    pn = int(pdur * SR)
    pot = np.zeros(pn)
    for f, amp in [(620, 1.0), (930, 0.5), (1450, 0.3), (2100, 0.15)]:
        pot += amp * np.sin(2 * np.pi * f * np.arange(pn) / SR) * np.exp(-np.arange(pn) / SR / 0.08)
    add_at(buf, int(pot_t * SR), pot * 0.22)

    # 7) 웃음 한 번(1회): 대역 노이즈 + 빠른 트레몰로(웃음의 "하하하" 리듬), 신원 불명
    laugh_t = rng.uniform(10.0, RAW_LEN - 10.0)
    ldur = 0.45
    ln = int(ldur * SR)
    laugh_noise = bandpass(rng.standard_normal(ln), 350, 1400)
    laugh_trem = 0.5 + 0.5 * (np.sin(2 * np.pi * 7.0 * np.arange(ln) / SR) > 0.1)
    laugh_env = adsr(ln, 0.03, 0.05, 0.6, ldur * 0.4)
    laugh = laugh_noise * laugh_trem * laugh_env
    add_at(buf, int(laugh_t * SR), laugh * 0.16)

    # 8) 먼 사람 웅얼거림: 포먼트풍 대역 노이즈 + 음절 모양 엔벨로프(가사 없음)
    n_murmur = 2
    murmur_times = rng.uniform(2.0, RAW_LEN - 5.0, n_murmur)
    for mt in murmur_times:
        mdur = rng.uniform(1.4, 2.2)
        mn = int(mdur * SR)
        base = bandpass(rng.standard_normal(mn), 350, 1100)
        n_syll = int(rng.integers(3, 6))
        syll_pos = np.sort(rng.uniform(0, mdur * 0.8, n_syll))
        env = np.zeros(mn)
        for sp in syll_pos:
            sdur = rng.uniform(0.12, 0.22)
            sn = int(sdur * SR)
            bump = adsr(sn, 0.03, 0.05, 0.3, sdur * 0.5)
            add_at(env, int(sp * SR), bump)
        env = lowpass(env, 18.0)
        murmur = base * env
        add_at(buf, int(mt * SR), murmur * 0.10)

    buf = lowpass(buf, 3500.0)  # 좁은 고역(따뜻함)
    buf = apply_reverb(buf, decay_time=0.35, wet=0.14, bright=False, seed=seed)  # 짧고 좁게(요청 3)
    buf = normalize_peak(buf, -3.0)
    return crossfade_loop(buf, FADE)


def gen_outside_deep(seed=102):
    """바깥(박광/무광층): **착용자 자신의 호흡**(5초 주기, 들숨/날숨 음색 분리, 헬멧 안처럼
    가깝고 건조하게) + 압력 서브베이스 + 먼 해류(이 둘에만 넓고 밝은 리버브). 사람 소리 0(대화·발소리 등
    "사람이 사는 소리"는 전혀 없다 — 오직 자기 자신의 숨).
    PM 피드백(2026-09-26): 원판은 호흡 주기가 4.7초였지만 실제 측정된 포락 주기는 돔 안과 같은 ~2초로
    나왔고(둘 다 같은 LFO 스타일 변조를 썼기 때문으로 추정), 호흡을 리버브가 걸린 베드에 섞어 "가깝고
    건조함"이 없었다. 이번 판은 (1) 호흡을 압력·해류 베드와 분리해 **리버브 없이 드라이하게** 더하고,
    (2) 들숨(150~900Hz, 길고 부드러움)과 날숨(500~2500Hz, 짧고 거침)의 음색을 분리하고, (3) 호흡 사이에
    짧은 정지(무호흡) 구간을 둬 기계적 반복처럼 안 들리게 했다."""
    rng = np.random.default_rng(seed)
    n = int(RAW_LEN * SR)
    t = np.arange(n) / SR

    # 1) 압력 + 먼 해류: 리버브가 걸리는 "공간" 서브믹스(호흡과 분리)
    # 근접한 두 기본음(32/38Hz)은 6Hz 맥놀이(비트)를 만들어 순간 사건 검출기가 그 맥놀이를
    # "사건"으로 오검출했다(PM 검증 2라운드) — 배음 관계(34Hz+2배음)로 바꿔 맥놀이를 없앤다.
    pressure = 0.62 * np.sin(2 * np.pi * 34.0 * t) + 0.30 * np.sin(2 * np.pi * 68.0 * t)
    pressure_env = 0.75 + 0.25 * _lfo(n, RAW_LEN / 2, phase=0.4)
    pressure = lowpass(pressure * pressure_env, 70.0)

    current = bandpass(pink_noise(n, rng), 90, 3000)
    current_env = 0.6 + 0.4 * _lfo(n, RAW_LEN / 3, phase=1.0)

    space_bed = 0.17 * pressure + 0.11 * current * current_env
    space_bed = highpass(space_bed, 25.0)
    space_bed = apply_reverb(space_bed, decay_time=3.4, wet=0.34, bright=True, seed=seed)  # 길고 확산(요청 3)

    # 2) 숨소리: 5초 주기(4~6초 규격), 들숨/날숨 음색 분리 + 사이 정지, 리버브 없이 드라이(요청 1)
    breath_period = 5.0
    phase = (t % breath_period) / breath_period
    inhale_mask = phase < 0.45
    exhale_mask = (phase >= 0.48) & (phase < 0.80)

    # PM 검증(사건 밀도) 재조정: 실제 호흡은 "느린 스웰"이지 "빠른 어택"이 아니어야 한다.
    # 지수를 올려 상승 곡선 자체를 완만하게 만든다(첫 라운드에서 exhale이 너무 날카로워 순간
    # 사건으로 오검출됐다 — 회당 상승에 걸리는 시간을 늘려 사건 밀도 검출기와 사람 귀 모두에게
    # "튀는 소리"가 아니라 "부풀었다 가라앉는 소리"로 들리게 한다).
    inhale_shape = np.clip(phase / 0.45, 0, 1)
    inhale_env = np.where(inhale_mask, np.sin(inhale_shape * np.pi) ** 1.8, 0.0)  # 길고 아주 부드러운 들숨
    exhale_shape = np.clip((phase - 0.48) / 0.32, 0, 1)
    exhale_env = np.where(exhale_mask, np.sin(exhale_shape * np.pi) ** 1.6, 0.0)  # 날숨도 완만하게(어택 아님)

    inhale_noise = bandpass(rng.standard_normal(n), 150, 900)   # 들숨: 낮고 부드러움
    exhale_noise = bandpass(rng.standard_normal(n), 500, 2500)  # 날숨: 높고 거침(호흡기 특유의 쉿 소리)
    breath = 0.15 * inhale_noise * inhale_env + 0.11 * exhale_noise * exhale_env

    # 헬멧 공명(좁은 대역 살짝 강조 — "가깝다"는 느낌의 근원, 진폭을 낮춰 잔물결로 오검출되지 않게)
    breath_res = bandpass(breath, 320, 520)
    breath = breath + 0.12 * breath_res
    breath = highpass(breath, 110.0)

    buf = space_bed + breath  # 호흡은 리버브 없이 그대로 얹는다(건조함 유지)
    buf = normalize_peak(buf, -3.0)
    return crossfade_loop(buf, FADE)


def gen_trench(seed=103):
    """해구: 더 낮고 더 비어 있음. 광대역 '공백 히스'(아주 조용) + 서브베이스 바닥 +
    아주 가끔(1회) 정체불명의 먼 신음(구조물, 「먼 울음」과 무관 — 그것은 별도 파일)."""
    rng = np.random.default_rng(seed)
    n = int(RAW_LEN * SR)
    buf = np.zeros(n)

    # 1) 공백 히스: 광대역이지만 극히 조용 — '텅 빈' 느낌의 근원
    void = bandpass(pink_noise(n, rng), 500, 6500)
    void_env = 0.7 + 0.3 * _lfo(n, RAW_LEN / 4, phase=0.5)
    buf += 0.028 * void * void_env

    # 2) 서브베이스 바닥음: 좁고 낮음, 아주 조용
    sub = bandpass(rng.standard_normal(n), 25, 55)
    sub_env = 0.6 + 0.4 * _lfo(n, RAW_LEN / 2, phase=1.3)
    buf += 0.045 * sub * sub_env

    # 3) 아주 가끔 정체불명의 먼 신음(1회/루프, 구조물 — 「먼 울음」이 아님)
    gt = rng.uniform(RAW_LEN * 0.30, RAW_LEN * 0.72)
    gdur = rng.uniform(2.0, 3.0)
    gn = int(gdur * SR)
    f0, f1 = rng.uniform(55, 75), rng.uniform(28, 40)
    groan = glide_sine(f0, f1, gdur) * adsr(gn, 0.6, 0.8, 0.5, gdur * 0.4)
    groan = lowpass(groan, 180.0)
    add_at(buf, int(gt * SR), groan * 0.28)

    buf = apply_reverb(buf, decay_time=4.5, wet=0.20, bright=True, seed=seed)
    buf = normalize_peak(buf, -3.0)
    return crossfade_loop(buf, FADE)


def main():
    jobs = [
        ("amb_dome_inside", gen_dome_inside, "48k"),
        ("amb_outside_deep", gen_outside_deep, "48k"),
        ("amb_trench", gen_trench, "48k"),
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
