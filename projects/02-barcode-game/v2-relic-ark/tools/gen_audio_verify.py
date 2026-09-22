# -*- coding: utf-8 -*-
"""
gen_audio_verify.py — static/audio 산출물 검증 (교본 05_SOUND A8, §5 자가검수).
각 파일: 존재·길이·크기·RMS(dB)·피크(dB)·스펙트럼 중심주파수(Hz).
총 용량 ≤3MB 확인, 안/밖 스펙트럼 중심주파수 대비를 수치로 출력.

실행: python tools/gen_audio_verify.py
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
STATIC_AUDIO = ROOT / "static" / "audio"

FILES = [
    "amb_inside.ogg", "amb_outside_day.ogg", "amb_outside_night.ogg",
    "sfx_lantern_on.ogg", "sfx_campfire.ogg", "sfx_water_splash.ogg",
    "sfx_scan_ok.ogg", "sfx_note_arrive.ogg", "sfx_card_place.ogg",
    "sfx_dog_warn.ogg", "cue_spot_found.ogg",
]


def decode_to_array(path):
    """soundfile이 ogg를 못 읽을 경우 ffmpeg로 임시 wav 변환 후 로드."""
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


def spectral_centroid(x, sr):
    if len(x) < 2:
        return 0.0
    n = len(x)
    win = np.hanning(n)
    X = np.abs(np.fft.rfft(x * win))
    freqs = np.fft.rfftfreq(n, d=1 / sr)
    mag_sum = np.sum(X) + 1e-12
    return float(np.sum(freqs * X) / mag_sum)


def analyze(path):
    data, sr = decode_to_array(path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    dur = len(data) / sr
    rms = float(np.sqrt(np.mean(data ** 2)) + 1e-12)
    peak = float(np.max(np.abs(data)) + 1e-12)
    rms_db = 20 * np.log10(rms)
    peak_db = 20 * np.log10(peak)
    centroid = spectral_centroid(data, sr)
    size_kb = path.stat().st_size / 1024
    return dict(name=path.name, dur=dur, sr=sr, rms_db=rms_db, peak_db=peak_db,
                centroid=centroid, size_kb=size_kb)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    rows = []
    missing = []
    total_bytes = 0
    for fname in FILES:
        p = STATIC_AUDIO / fname
        if not p.exists():
            missing.append(fname)
            continue
        total_bytes += p.stat().st_size
        rows.append(analyze(p))

    print(f"{'파일':<24}{'길이(s)':>9}{'크기(KB)':>10}{'RMS(dB)':>10}{'피크(dB)':>10}{'중심주파수(Hz)':>16}")
    for r in rows:
        print(f"{r['name']:<24}{r['dur']:>9.2f}{r['size_kb']:>10.2f}{r['rms_db']:>10.1f}{r['peak_db']:>10.1f}{r['centroid']:>16.1f}")

    total_kb = total_bytes / 1024
    print(f"\n총 용량: {total_kb:.1f} KB ({total_kb/1024:.3f} MB) / 예산 3MB → {'OK' if total_kb/1024 <= 3.0 else 'FAIL'}")

    if missing:
        print(f"\n누락 파일: {missing}")

    by_name = {r["name"]: r for r in rows}
    if "amb_inside.ogg" in by_name and "amb_outside_day.ogg" in by_name:
        ci = by_name["amb_inside.ogg"]["centroid"]
        cd = by_name["amb_outside_day.ogg"]["centroid"]
        cn = by_name["amb_outside_night.ogg"]["centroid"] if "amb_outside_night.ogg" in by_name else None
        print(f"\n안/밖 대비: amb_inside 중심주파수={ci:.0f}Hz, amb_outside_day={cd:.0f}Hz "
              f"(밖이 {cd/ci:.2f}배 더 높음, 목표: 밖 > 안)")
        if cn:
            print(f"amb_outside_night 중심주파수={cn:.0f}Hz (낮 대비 {cn/cd:.2f}배, 목표: 밤 < 낮이지만 안보다는 높거나 유사)")

    return 0 if not missing and total_kb / 1024 <= 3.0 else 1


if __name__ == "__main__":
    sys.exit(main())
