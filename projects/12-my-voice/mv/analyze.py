# -*- coding: utf-8 -*-
"""뮤직비디오용 곡 구조 분석 — 템포, 박자, 악기별 등장 시점, 고조 곡선.

  python mv/analyze.py            # mv/stems/htdemucs/동상이래요/ 의 4개 스템을 읽는다
결과: mv/structure.json  (스토리보드·Blender 스크립트가 공통으로 읽는다)
"""
import json, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, librosa, scipy.signal
if not hasattr(scipy.signal, "hann"): scipy.signal.hann = scipy.signal.windows.hann   # 구 librosa + 신 scipy 호환

HERE = Path(__file__).resolve().parent
SONG = HERE.parent / "songs" / "동상이래요.mp3"
STEMS = HERE / "stems" / "htdemucs" / "동상이래요"
SR, HOP = 22050, 512

y, _ = librosa.load(str(SONG), sr=SR, mono=True)
dur = len(y) / SR
tempo, beats = librosa.beat.beat_track(y=y, sr=SR, hop_length=HOP)
beat_t = librosa.frames_to_time(beats, sr=SR, hop_length=HOP)
tempo = float(np.atleast_1d(tempo)[0])

def env(sig, win_s=2.0):
    r = librosa.feature.rms(y=sig, frame_length=2048, hop_length=HOP)[0]
    k = max(1, int(win_s * SR / HOP))
    return np.convolve(r, np.ones(k) / k, mode="same")

t = None
stems = {}
for name in ("vocals", "drums", "bass", "other"):
    s, _ = librosa.load(str(STEMS / f"{name}.wav"), sr=SR, mono=True)
    e = env(s); stems[name] = e
    if t is None: t = librosa.frames_to_time(np.arange(len(e)), sr=SR, hop_length=HOP)

def first_on(e, rel=0.15, hold_s=2.0):
    """곡 전체 최대의 rel 배를 hold_s 이상 넘는 첫 시점 = 그 악기가 '등장'한 때."""
    on = e > e.max() * rel
    k = int(hold_s * SR / HOP)
    for i in range(len(on) - k):
        if on[i:i + k].all(): return float(t[i])
    return None

entries = {n: first_on(e) for n, e in stems.items()}

# 고조 곡선: 전체 음량 + 반주 밀도(활성 악기 수)를 0~1로
total = env(y, 4.0)
active = sum((e > e.max() * 0.15).astype(float) for e in stems.values())
act_s = np.convolve(active, np.ones(int(4 * SR / HOP)) / int(4 * SR / HOP), mode="same")
n = min(len(total), len(act_s), len(t))
intensity = 0.6 * (total[:n] / total[:n].max()) + 0.4 * (act_s[:n] / 4)

# 구간 경계: 박자 단위 특징의 변화점 (신시사이저 없이도 동작하는 고전적 방법)
chroma = librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=HOP)
mfcc = librosa.feature.mfcc(y=y, sr=SR, hop_length=HOP, n_mfcc=13)
feat = np.vstack([librosa.util.normalize(chroma, axis=1), librosa.util.normalize(mfcc, axis=1)])
feat_b = librosa.util.sync(feat, beats, aggregate=np.median)
k_seg = 9
bounds = librosa.segment.agglomerative(feat_b, k_seg)
bound_t = sorted(set([0.0] + [float(beat_t[min(b, len(beat_t) - 1)]) for b in bounds if b > 0] + [dur]))

# 보컬 구간 (노래하는 부분 / 쉬는 부분)
v = stems["vocals"][:n]; von = v > v.max() * 0.12
vocal_spans, st = [], None
for i, on in enumerate(von):
    if on and st is None: st = t[i]
    if not on and st is not None:
        if t[i] - st > 2: vocal_spans.append([round(float(st), 1), round(float(t[i]), 1)])
        st = None
if st is not None: vocal_spans.append([round(float(st), 1), round(dur, 1)])

sections = []
for a, b in zip(bound_t[:-1], bound_t[1:]):
    m = (t[:n] >= a) & (t[:n] < b)
    sections.append({"start": round(a, 1), "end": round(b, 1),
                     "intensity": round(float(intensity[m].mean()), 2),
                     "vocal": round(float(von[m].mean()), 2),
                     "stems": {k: round(float((stems[k][:n][m] > stems[k].max() * 0.15).mean()), 2) for k in stems}})

step = int(1.0 * SR / HOP)
out = {"duration": round(dur, 2), "tempo": round(tempo, 1), "beats": [round(float(b), 3) for b in beat_t],
       "entries": {k: (round(v_, 1) if v_ is not None else None) for k, v_ in entries.items()},
       "vocal_spans": vocal_spans, "sections": sections,
       "intensity_1s": [round(float(x), 3) for x in intensity[::step]]}
(HERE / "structure.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

print(f"길이 {dur:.1f}s  템포 {tempo:.1f} BPM  박자 {len(beat_t)}개")
print("악기 등장:", {k: v_ for k, v_ in out["entries"].items()})
print("보컬 구간:", vocal_spans)
for s in sections:
    bar = "█" * int(s["intensity"] * 20)
    print(f"{s['start']:6.1f}-{s['end']:6.1f}  고조 {s['intensity']:.2f} {bar:<20} 보컬 {s['vocal']:.0%}  "
          + " ".join(f"{k[:2]}{v_:.0%}" for k, v_ in s["stems"].items()))
