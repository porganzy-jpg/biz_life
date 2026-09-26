# -*- coding: utf-8 -*-
"""
gen_audio_deep_verify.py — 심해 1막 오디오(static/audio) 검증 (스프린트 4-D, PM 피드백 반영판).

교본 05_SOUND A8·§5. 각 파일 길이·크기·RMS·피크, 그리고 **PM 지적(2026-09-26) 이후 지표**:
- 스펙트럼 중심주파수는 **파워 가중**(|X|^2)으로 통일(기존 진폭 가중에서 변경 — PM 요청).
- 200Hz 이하 에너지 비중(물이 고역을 먹는다는 물리와 "낮고 비어 있다"는 서술을 함께 검증).
- 포락(엔벨로프) 변동폭(dB): 10~90퍼센타일 비율.
- 순간 사건 밀도(회/초): 포락 미분 피크 검출.
- 포락 자기상관 주기·계수: 두 파일이 같은 변조를 공유하는지(허위 유사성) 탐지.

실행: python tools/gen_audio_deep_verify.py
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

ROOT = Path(__file__).resolve().parents[1]
STATIC_AUDIO = ROOT / "static" / "audio"

AMBIENT_FILES = ["amb_dome_inside.ogg", "amb_outside_deep.ogg", "amb_trench.ogg"]
SFX_FILES = [
    "sfx_airlock_cycle.ogg", "sfx_glass_crack.ogg", "sfx_knock_glass.ogg",
    "sfx_air_low.ogg", "sfx_collect.ogg", "sfx_room_flood.ogg",
]
OTHER_FILES = ["cue_vent_garden.ogg", "amb_far_call.ogg"]
FILES = AMBIENT_FILES + SFX_FILES + OTHER_FILES

SFX_LIMIT_KB = 40.0
AMB_LIMIT_KB = 600.0
TOTAL_LIMIT_MB = 2.0


def decode_to_array(path):
    try:
        data, sr = sf.read(str(path), dtype="float32", always_2d=False)
        return data, sr
    except Exception:
        tmp = path.with_suffix(".verify.wav")
        subprocess.run(["ffmpeg", "-y", "-i", str(path), str(tmp)],
                        capture_output=True, text=True, check=True)
        data, sr = sf.read(str(tmp), dtype="float32", always_2d=False)
        tmp.unlink(missing_ok=True)
        return data, sr


def power_spectrum(x, sr):
    n = len(x)
    win = np.hanning(n)
    X = np.abs(np.fft.rfft(x * win)) ** 2
    freqs = np.fft.rfftfreq(n, d=1 / sr)
    return freqs, X


def power_spectral_centroid(x, sr):
    """PM 요청: 파워 가중(|X|^2) 중심주파수. 기존(진폭 가중)보다 저역 성분을 강하게 반영한다."""
    if len(x) < 2:
        return 0.0
    freqs, X = power_spectrum(x, sr)
    s = np.sum(X) + 1e-12
    return float(np.sum(freqs * X) / s)


def band_energy_ratio_below(x, sr, cutoff=200.0):
    if len(x) < 2:
        return 0.0
    freqs, X = power_spectrum(x, sr)
    total = np.sum(X) + 1e-12
    below = np.sum(X[freqs < cutoff])
    return float(below / total)


def envelope(x, sr, smooth_hz=8.0):
    """Hilbert 포락선 + 저역통과(오디오-레이트 잔물결 제거, 사람이 듣는 '박동감' 스케일만 남김).
    포락 변동폭·자기상관(§느린 매크로 다이내믹스)용 — 8Hz."""
    analytic = signal.hilbert(x)
    env = np.abs(analytic)
    sos = signal.butter(2, smooth_hz / (sr / 2), btype="low", output="sos")
    return signal.sosfiltfilt(sos, env)


def envelope_variation_db(env):
    e = np.maximum(env, 1e-6)
    lo = np.percentile(e, 10)
    hi = np.percentile(e, 90)
    return float(20 * np.log10((hi + 1e-9) / (lo + 1e-9)))


def event_density(x, sr, fast_hz=45.0, floor_hz=1.2, margin_db=4.0, min_gap_sec=0.10):
    """순간 사건(물방울·클릭·발소리 등 '배경 위로 튀어나오는 것') 개수/초.
    연속 배경(바람·해류·히스 같은 상시 노이즈)은 그 자체로도 미세하게 흔들리므로, 단순 미분/온셋으로는
    배경 텍스처를 사건으로 오검출한다. 여기서는 **빠른 포락(45Hz)이 느린 지역 배경(1.2Hz)보다
    margin_db 이상 튀어나온 순간**만 '사건'으로 센다 — 숨소리 같은 완만한 스웰은 배경 자체를 따라
    올라가므로 초과폭이 작고, 물방울/클릭처럼 배경 위에 얹힌 순간음만 큰 초과폭을 남긴다."""
    env_fast = envelope(x, sr, smooth_hz=fast_hz)
    env_floor = envelope(x, sr, smooth_hz=floor_hz)
    excess_db = 20 * np.log10(np.maximum(env_fast, 1e-7)) - 20 * np.log10(np.maximum(env_floor, 1e-7))
    peaks, _ = signal.find_peaks(excess_db, height=margin_db, distance=max(1, int(min_gap_sec * sr)))
    dur = len(x) / sr
    return float(len(peaks) / dur), int(len(peaks))


def envelope_autocorr_period(env, sr, min_period=1.0, max_period=10.0):
    """포락 자기상관에서 (1~10초 구간의) **뚜렷한 국소 피크**를 '주기'로 보고한다.
    구간 내 최댓값(argmax)만 보면 순수 비주기(단조 감쇠) 신호에서도 탐색 구간 경계값을 억지로
    '주기'로 잘못 보고하게 된다(경계 인공물). 그래서 인접 값보다 실제로 더 큰 **국소 피크**만 인정하고,
    없으면 "뚜렷한 주기 없음"(period=None)을 보고한다 — 두 파일 모두 이 경우라면 그 자체가
    "공유 변조가 없다"는 좋은 신호다."""
    factor = max(1, int(sr / 200))  # ~200Hz로 다운샘플(속도)
    e = env[::factor] - np.mean(env[::factor])
    sr_ds = sr / factor
    ac = np.correlate(e, e, mode="full")
    mid = len(ac) // 2
    ac = ac[mid:]
    ac = ac / (ac[0] + 1e-12)
    lag_min = int(min_period * sr_ds)
    lag_max = min(int(max_period * sr_ds), len(ac) - 1)
    if lag_max <= lag_min:
        return None, 0.0
    seg = ac[lag_min:lag_max]
    peaks, _ = signal.find_peaks(seg)
    if len(peaks) == 0:
        return None, float(np.max(seg))  # 국소 피크 없음 = 뚜렷한 주기성 없음
    best = peaks[np.argmax(seg[peaks])]
    period = (best + lag_min) / sr_ds
    coef = float(seg[best])
    return period, coef


def analyze(path):
    data, sr = decode_to_array(path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    dur = len(data) / sr
    rms = float(np.sqrt(np.mean(data ** 2)) + 1e-12)
    peak = float(np.max(np.abs(data)) + 1e-12)
    rms_db = 20 * np.log10(rms)
    peak_db = 20 * np.log10(peak)
    centroid = power_spectral_centroid(data, sr)
    below200 = band_energy_ratio_below(data, sr, 200.0)
    size_kb = path.stat().st_size / 1024
    return dict(name=path.name, dur=dur, sr=sr, rms_db=rms_db, peak_db=peak_db,
                centroid=centroid, below200=below200, size_kb=size_kb, data=data)


def analyze_ambient_extra(r):
    """앰비언트 전용 추가 지표(포락 변동·사건 밀도·자기상관 주기)."""
    env = envelope(r["data"], r["sr"])  # 느린 포락(8Hz) — 변동폭·자기상관용
    var_db = envelope_variation_db(env)
    density, n_events = event_density(r["data"], r["sr"])  # 빠른 포락(45Hz) — 어택 검출용
    period, coef = envelope_autocorr_period(env, r["sr"])
    return dict(var_db=var_db, density=density, n_events=n_events, ac_period=period, ac_coef=coef)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    rows = []
    missing = []
    fail_size = []
    total_bytes = 0
    for fname in FILES:
        p = STATIC_AUDIO / fname
        if not p.exists():
            missing.append(fname)
            continue
        total_bytes += p.stat().st_size
        r = analyze(p)
        rows.append(r)
        limit = AMB_LIMIT_KB if fname in AMBIENT_FILES or fname == "cue_vent_garden.ogg" else SFX_LIMIT_KB
        if r["size_kb"] > limit:
            fail_size.append((fname, r["size_kb"], limit))

    print(f"{'파일':<24}{'길이(s)':>9}{'크기(KB)':>10}{'RMS(dB)':>10}{'피크(dB)':>10}{'중심주파수(Hz,파워)':>20}{'<200Hz비중':>12}")
    for r in rows:
        print(f"{r['name']:<24}{r['dur']:>9.2f}{r['size_kb']:>10.2f}{r['rms_db']:>10.1f}{r['peak_db']:>10.1f}{r['centroid']:>20.1f}{r['below200']*100:>11.1f}%")

    total_kb = total_bytes / 1024
    print(f"\n총 용량(심해분): {total_kb:.1f} KB ({total_kb/1024:.3f} MB) / 예산 {TOTAL_LIMIT_MB}MB "
          f"-> {'OK' if total_kb/1024 <= TOTAL_LIMIT_MB else 'FAIL'}")

    if missing:
        print(f"\n누락 파일: {missing}")
    if fail_size:
        print(f"\n개별 용량 초과: {fail_size}")

    by_name = {r["name"]: r for r in rows}

    # 안/밖/해구 파워 가중 중심주파수 + <200Hz 비중 (PM 재현 방식과 통일)
    order_ok = None
    if all(k in by_name for k in AMBIENT_FILES):
        c_dome = by_name["amb_dome_inside.ogg"]["centroid"]
        c_out = by_name["amb_outside_deep.ogg"]["centroid"]
        c_trench = by_name["amb_trench.ogg"]["centroid"]
        print(f"\n[파워 가중 중심주파수] 돔 안={c_dome:.1f}Hz  바깥={c_out:.1f}Hz  해구={c_trench:.1f}Hz "
              f"(해구가 가장 낮아야 '물이 고역을 먹는다'는 물리와 일치 — PM 2026-09-26 재해석)")
        order_ok = c_trench < c_dome and c_trench < c_out

    # 앰비언트 3종 추가 지표(포락 변동/사건 밀도/자기상관) — PM이 지적한 핵심 검증
    extra = {}
    if all(k in by_name for k in AMBIENT_FILES):
        print(f"\n{'파일':<24}{'<200Hz비중':>12}{'포락변동(dB)':>14}{'사건밀도(회/초)':>16}{'자기상관주기(s)':>16}{'자기상관계수':>12}")
        for fname in AMBIENT_FILES:
            r = by_name[fname]
            ex = analyze_ambient_extra(r)
            extra[fname] = ex
            period_str = f"{ex['ac_period']:.2f}" if ex['ac_period'] is not None else "없음"
            print(f"{fname:<24}{r['below200']*100:>11.1f}%{ex['var_db']:>14.1f}{ex['density']:>16.2f}{period_str:>16}{ex['ac_coef']:>12.2f}")

        d_in = extra["amb_dome_inside.ogg"]
        d_out = extra["amb_outside_deep.ogg"]
        gap_centroid = abs(by_name["amb_dome_inside.ogg"]["centroid"] - by_name["amb_outside_deep.ogg"]["centroid"])
        gap_var = abs(d_in["var_db"] - d_out["var_db"])
        gap_density = abs(d_in["density"] - d_out["density"])
        both_have_period = d_in["ac_period"] is not None and d_out["ac_period"] is not None
        period_close = (both_have_period and abs(d_in["ac_period"] - d_out["ac_period"]) < 0.5
                         and min(d_in["ac_coef"], d_out["ac_coef"]) > 0.5)
        print(f"\n[안/밖 분리 진단] 중심주파수 차={gap_centroid:.1f}Hz, 포락변동 차={gap_var:.1f}dB, "
              f"사건밀도 차={gap_density:.2f}회/초, 공유주기 의심={'예(위험)' if period_close else '아니오(뚜렷한 주기 없음 또는 서로 다름)'}")
        separation_ok = gap_density > 0.5 and not period_close
        print(f"분리 판정: {'OK' if separation_ok else 'FAIL — 안/밖이 스펙트럼·포락상 너무 비슷함'}")

    # 참고: 해구가 가장 비어 있음(RMS 최저 + 사건 드묾)
    if all(k in by_name for k in AMBIENT_FILES) and extra:
        ex_trench = analyze_ambient_extra(by_name["amb_trench.ogg"])
        r_dome = by_name["amb_dome_inside.ogg"]["rms_db"]
        r_out = by_name["amb_outside_deep.ogg"]["rms_db"]
        r_trench = by_name["amb_trench.ogg"]["rms_db"]
        print(f"\n[해구 '비어 있음' 근거] RMS: 돔={r_dome:.1f}dB 바깥={r_out:.1f}dB 해구={r_trench:.1f}dB "
              f"(가장 낮아야 함) / 해구 사건밀도={ex_trench['density']:.2f}회/초(아주 가끔)")

    ok = not missing and not fail_size and total_kb / 1024 <= TOTAL_LIMIT_MB and (order_ok is not False)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
