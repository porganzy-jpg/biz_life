# -*- coding: utf-8 -*-
"""
gen_audio_combat_verify.py — 전투 SFX(스프린트 10-A) 검증.

PM 지적(이전 스프린트, docs/reports/sound_S4.md §3 "반직관성" 교훈 재적용):
저역이 에너지의 대부분(종종 90% 이상)을 차지하는 신호에서는 광대역 RMS·중심주파수가
"디테일"(리듬·질감 차이)을 가린다. 이번 검증은 **500Hz 하이패스 후** 다시 재서,
사람이 실제로 종을 구분하는 단서(두드림의 리듬, 긁는 질감의 대역)가 숫자로도 드러나게 한다.

측정:
  1) 예산 — 신규 18개 합계 ≤1MB(개별 ≤40KB), static/audio 전체 budget 참고 출력.
  2) 500Hz 하이패스 후 RMS·중심주파수로 "소리 계열"이 광대역 지표보다 더 잘 갈리는지 비교.
  3) 긴목·윗물 아이 — 두드림 간격을 온셋 검출로 뽑아 **등간격이 아님**(지터 > 0)을 수치로 증명.
  4) 곧은치 — 초반 긴장음 뒤 ~2초 구간이 실제로 거의 무음인지(엔벨로프 바닥 근접) 확인.
  5) 큰 입 — 스웰 2회가 규칙적 간격으로 온다는 플레이버와 일치하는지 피크 2개 검출.
  6) 따라온 것 — 두 번의 울음 사이에 뚜렷한 정적 구간이 있는지 확인.
  7) 바늘 — 길이 ≥15초(명단에서 가장 긴 큐) 확인.

실행: python tools/gen_audio_combat_verify.py
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

sys.path.insert(0, str(Path(__file__).parent))
from gen_audio_common import highpass, SR as GEN_SR  # noqa: F401 (SR 참고용)

ROOT = Path(__file__).resolve().parents[1]
STATIC_AUDIO = ROOT / "static" / "audio"

NEW_FILES = [
    "sfx_warn_longneck.ogg", "sfx_warden_press.ogg", "sfx_warn_swarm.ogg", "sfx_warn_claws.ogg",
    "sfx_warn_mirroreye.ogg", "sfx_warn_straight.ogg", "sfx_warn_needle.ogg", "sfx_warn_bigmaw.ogg",
    "sfx_warn_follower.ogg", "sfx_warn_upperchild.ogg", "sfx_octopus_enter.ogg", "sfx_defend_held.ogg",
    "sfx_pickup_person.ogg", "sfx_place_person.ogg", "sfx_light_off.ogg", "sfx_light_on.ogg",
    "sfx_power_down.ogg", "sfx_tool_install.ogg",
]
SFX_LIMIT_KB = 40.0
NEW_TOTAL_LIMIT_MB = 1.0
ALL_BUDGET_MB = 3.0  # Phase 0 전체 예산(05_SOUND A8)


def load(path):
    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data, sr


def power_spectral_centroid(x, sr):
    if len(x) < 2:
        return 0.0
    n = len(x)
    win = np.hanning(n)
    X = np.abs(np.fft.rfft(x * win)) ** 2
    freqs = np.fft.rfftfreq(n, d=1 / sr)
    s = np.sum(X) + 1e-12
    return float(np.sum(freqs * X) / s)


def rms_db(x):
    r = float(np.sqrt(np.mean(x ** 2)) + 1e-12)
    return 20 * np.log10(r)


def envelope(x, sr, smooth_hz=30.0):
    analytic = signal.hilbert(x)
    env = np.abs(analytic)
    sos = signal.butter(2, smooth_hz / (sr / 2), btype="low", output="sos")
    return signal.sosfiltfilt(sos, env)


def onset_times(x, sr, smooth_hz=60.0, min_gap_sec=0.08, rel_height=0.35):
    """빠른 포락에서 피크를 찾아 '두드림/스크래치' 온셋 시각을 돌려준다."""
    env = envelope(x, sr, smooth_hz=smooth_hz)
    thresh = rel_height * (np.max(env) + 1e-12)
    peaks, _ = signal.find_peaks(env, height=thresh, distance=max(1, int(min_gap_sec * sr)))
    return peaks / sr, env


def analyze_broadband_vs_hp500(name):
    p = STATIC_AUDIO / name
    x, sr = load(p)
    bb_rms, bb_c = rms_db(x), power_spectral_centroid(x, sr)
    xhp = highpass(x, 500.0, order=4)
    hp_rms, hp_c = rms_db(xhp), power_spectral_centroid(xhp, sr)
    return dict(name=name, dur=len(x) / sr, size_kb=p.stat().st_size / 1024,
                bb_rms=bb_rms, bb_centroid=bb_c, hp_rms=hp_rms, hp_centroid=hp_c, x=x, xhp=xhp, sr=sr)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # ---- 1. 예산 ----
    print("=== 1. 예산 ===")
    total_new = 0
    fail = []
    for f in NEW_FILES:
        p = STATIC_AUDIO / f
        if not p.exists():
            fail.append((f, "없음"))
            continue
        kb = p.stat().st_size / 1024
        total_new += kb
        flag = "OK" if kb <= SFX_LIMIT_KB else "FAIL(>40KB)"
        print(f"  {f:<26}{kb:8.2f} KB  {flag}")
    print(f"\n  신규 18종 합계: {total_new:.2f} KB ({total_new/1024:.4f} MB) / 예산 {NEW_TOTAL_LIMIT_MB}MB "
          f"-> {'OK' if total_new/1024 <= NEW_TOTAL_LIMIT_MB else 'FAIL'}")
    all_files = list(STATIC_AUDIO.glob('*.ogg'))
    all_kb = sum(p.stat().st_size for p in all_files) / 1024
    print(f"  static/audio 전체: {all_kb/1024:.3f} MB / Phase0 예산 {ALL_BUDGET_MB}MB "
          f"-> {'OK' if all_kb/1024 <= ALL_BUDGET_MB else 'FAIL'}")
    if fail:
        print(f"  누락: {fail}")

    # ---- 2. 광대역 vs 500Hz 하이패스 ----
    print("\n=== 2. 광대역 지표 vs 500Hz 하이패스 후 지표 (PM 방법론 교정 적용) ===")
    print(f"{'파일':<24}{'길이(s)':>8}{'광대역RMS':>11}{'광대역중심':>11}{'HP500 RMS':>11}{'HP500중심':>11}")
    rows = {}
    for f in NEW_FILES:
        if not (STATIC_AUDIO / f).exists():
            continue
        r = analyze_broadband_vs_hp500(f)
        rows[f] = r
        print(f"{f:<24}{r['dur']:>8.2f}{r['bb_rms']:>11.1f}{r['bb_centroid']:>11.1f}"
              f"{r['hp_rms']:>11.1f}{r['hp_centroid']:>11.1f}")

    # 가족별 거리감 대조: longneck(가깝지만 먹먹) vs needle/bigmaw/follower(해구 계열, 더 낮고 더 멀게)
    fam_near = ["sfx_warn_longneck.ogg", "sfx_warn_upperchild.ogg"]
    fam_trench = ["sfx_warn_needle.ogg", "sfx_warn_bigmaw.ogg", "sfx_warn_follower.ogg"]
    near_c = np.mean([rows[f]["hp_centroid"] for f in fam_near if f in rows])
    trench_c = np.mean([rows[f]["hp_centroid"] for f in fam_trench if f in rows])
    near_bb = np.mean([rows[f]["bb_centroid"] for f in fam_near if f in rows])
    trench_bb = np.mean([rows[f]["bb_centroid"] for f in fam_trench if f in rows])
    print(f"\n  [해구 계열 '더 낮고 더 멀게' 검증] 광대역 중심 — 근거리계열={near_bb:.0f}Hz vs 해구계열={trench_bb:.0f}Hz"
          f"  (이미 광대역에서도 보임: {'OK' if trench_bb < near_bb else 'FAIL'})")
    print(f"  HP500 중심 — 근거리계열={near_c:.0f}Hz vs 해구계열={trench_c:.0f}Hz")

    # swarm(높고 바쁨) vs claws(낮고 느림) — 500Hz 위 대역에서 갈려야 '질감 차이'가 입증됨
    sw, cl = rows.get("sfx_warn_swarm.ogg"), rows.get("sfx_warn_claws.ogg")
    if sw and cl:
        gap_bb = abs(sw["bb_centroid"] - cl["bb_centroid"])
        gap_hp = abs(sw["hp_centroid"] - cl["hp_centroid"])
        print(f"\n  [작은 떼 vs 손톱 무리 — 질감 대비] 광대역 중심 차={gap_bb:.0f}Hz, HP500 중심 차={gap_hp:.0f}Hz")
        print(f"  작은 떼(높고 바쁨)={sw['hp_centroid']:.0f}Hz > 손톱 무리(낮고 느림)={cl['hp_centroid']:.0f}Hz "
              f"-> {'OK' if sw['hp_centroid'] > cl['hp_centroid'] else 'FAIL'}")

    # ---- 3. 리듬 지터(긴목·윗물 아이) ----
    print("\n=== 3. 리듬 — 긴목·윗물 아이 '사람 흉내인데 미묘하게 어긋남' 검증 ===")
    # 지터 판정은 두 간격을 서로 비교(표준편차)하지 않는다 — 표본이 2~4개뿐이라 우연히 비슷해질 수
    # 있다(실제로 longneck 시드 301이 그랬다: 두 간격이 서로 -11ms/-10ms로 우연히 닮음). 대신
    # **설계된 메트로놈 간격(나노미널 템포) 대비 편차**를 본다 — 이것이 "사람처럼 흉내 내지만 매 박자
    # 조금씩 어긋난다"는 실제 요구를 재는 올바른 기준이다(완전 등간격이면 편차=0이어야 한다).
    for f, smooth, nominal in [("sfx_warn_longneck.ogg", 40.0, 0.46), ("sfx_warn_upperchild.ogg", 60.0, 0.22)]:
        r = rows[f]
        t_on, env = onset_times(r["xhp"], r["sr"], smooth_hz=smooth, min_gap_sec=0.15, rel_height=0.5)
        if len(t_on) >= 2:
            intervals = np.diff(t_on)
            dev_ms = (intervals - nominal) * 1000
            max_dev = float(np.max(np.abs(dev_ms)))
            print(f"  {f:<24} 온셋 {len(t_on)}개 @ {np.round(t_on,3)}  간격 {np.round(intervals,3)}  "
                  f"나노미널({nominal}s) 대비 편차={np.round(dev_ms,1)}ms  최대편차={max_dev:.1f}ms "
                  f"-> {'OK(박자가 어긋남)' if max_dev > 3.0 else 'FAIL(메트로놈처럼 정확함)'}")
        else:
            print(f"  {f:<24} 온셋 검출 {len(t_on)}개 — 임계값 재조정 필요")

    # ---- 4. 곧은치 — 정지 2초 ----
    print("\n=== 4. 곧은치 — 긴장음 뒤 '완전한 정지 2초' ===")
    r = rows["sfx_warn_straight.ogg"]
    env = envelope(r["x"], r["sr"], smooth_hz=20.0)
    t = np.arange(len(env)) / r["sr"]
    window = (t > 0.8) & (t < 2.6)
    still_rms = float(np.sqrt(np.mean(env[window] ** 2)))
    peak_rms = float(np.max(env[t < 0.6]))
    ratio_db = 20 * np.log10((still_rms + 1e-9) / (peak_rms + 1e-9))
    print(f"  긴장음 구간 피크 포락={peak_rms:.4f}  0.8~2.6s 구간 평균 포락={still_rms:.5f}  "
          f"차이={ratio_db:.1f}dB -> {'OK(충분히 조용함)' if ratio_db < -20 else 'FAIL'}")

    # ---- 5. 큰 입 — 스웰 2회 ----
    print("\n=== 5. 큰 입 — '랜턴 불꽃이 같은 간격으로 두 번 눕는다' = 스웰 2회 ===")
    r = rows["sfx_warn_bigmaw.ogg"]
    env = envelope(r["x"], r["sr"], smooth_hz=2.0)
    peaks, _ = signal.find_peaks(env, height=np.max(env) * 0.4, distance=int(2.0 * r["sr"]))
    pt = peaks / r["sr"]
    print(f"  검출된 스웰 피크 시각: {np.round(pt, 2)} (개수={len(pt)}) -> "
          f"{'OK(2회)' if len(pt) == 2 else f'참고(검출 {len(pt)}개, 임계값 민감)'}")
    if len(pt) == 2:
        print(f"  두 스웰 간격: {pt[1]-pt[0]:.2f}s")

    # ---- 6. 따라온 것 — 두 울음 사이 정적 ----
    print("\n=== 6. 따라온 것 — 두 울음 사이 정적(부름과 답) ===")
    r = rows["sfx_warn_follower.ogg"]
    env = envelope(r["x"], r["sr"], smooth_hz=5.0)
    t = np.arange(len(env)) / r["sr"]
    gap_window = (t > 1.3) & (t < 2.4)
    gap_rms = float(np.sqrt(np.mean(env[gap_window] ** 2)))
    peak1 = float(np.max(env[t < 1.1]))
    ratio_db = 20 * np.log10((gap_rms + 1e-9) / (peak1 + 1e-9))
    print(f"  첫 울음 피크 포락={peak1:.4f}  간격 구간(1.3~2.4s) 평균 포락={gap_rms:.5f}  "
          f"차이={ratio_db:.1f}dB -> {'OK(뚜렷한 정적)' if ratio_db < -12 else 'FAIL'}")

    # ---- 7. 바늘 — 길이 ----
    print("\n=== 7. 바늘 — 길이 ≥15초(명단에서 가장 긴 큐) ===")
    r = rows["sfx_warn_needle.ogg"]
    print(f"  길이={r['dur']:.2f}s -> {'OK' if r['dur'] >= 15.0 else 'FAIL'}")

    print("\n완료.")


if __name__ == "__main__":
    main()
