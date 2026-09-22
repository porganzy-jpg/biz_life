# -*- coding: utf-8 -*-
"""텍스트를 내 목소리로 읽어준다.  (edge-tts 합성 → 이어붙이기 → RVC 음색 변환)

  python say.py "안녕하세요, 독거 아조씨입니다."
  python say.py -f 대본.txt -o 나레이션.wav
  python say.py "..." --pitch -2        # 더 낮게
  python say.py "..." --raw             # 변환 전 합성음도 저장

여러 줄이면 줄마다 합성한 뒤 무음으로 이어붙여 **한 번에** 변환한다.
문장을 따로따로 변환하면 짧은 문장의 음색이 흔들린다(측정: 평균 18.6 vs 통째 14.4).
"""
import argparse, asyncio, glob, os, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, soundfile as sf, librosa

ROOT = Path(__file__).resolve().parent
FFMPEG_DIR = r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin"
os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
FFMPEG = os.path.join(FFMPEG_DIR, "ffmpeg.exe")

VOICE, PITCH_HZ, RATE = "ko-KR-HyunsuMultilingualNeural", "-8Hz", "-5%"  # 실제 음성 측정으로 고른 값
MODEL_NAME = "ajossi_v2_100e_3100s"      # 모델 비교 결과 선택
SR = 44100

ap = argparse.ArgumentParser()
ap.add_argument("text", nargs="*", help="읽을 문장")
ap.add_argument("-f", "--file", help="텍스트 파일에서 읽기")
ap.add_argument("-o", "--out", default="say_out.wav")
ap.add_argument("--pitch", type=int, default=-1, help="반음 조정 (기본 -1)")
ap.add_argument("--index", type=float, default=1.0, help="학습 음색 반영도 0~1")
ap.add_argument("--gap", type=float, default=0.5, help="줄 사이 무음(초)")
ap.add_argument("--raw", action="store_true", help="변환 전 합성음도 저장")
a = ap.parse_args()

raw = open(a.file, encoding="utf-8").read() if a.file else " ".join(a.text)
lines = [l.strip() for l in raw.splitlines() if l.strip()]
if not lines:
    sys.exit('읽을 텍스트가 없습니다.  예: say.py "안녕하세요"')

tmp = Path(tempfile.mkdtemp(prefix="say_"))
async def synth():
    import edge_tts
    for i, line in enumerate(lines):
        await edge_tts.Communicate(line, VOICE, pitch=PITCH_HZ, rate=RATE).save(str(tmp / f"{i:03d}.mp3"))
asyncio.run(synth())
print(f"합성 {len(lines)}줄", flush=True)

# 이어붙이기 — 변환 전에 붙여야 음색이 일정해진다
chunks, sil = [], np.zeros(int(a.gap * SR), dtype=np.float32)
for i in range(len(lines)):
    y, _ = librosa.load(str(tmp / f"{i:03d}.mp3"), sr=SR, mono=True)
    if i: chunks.append(sil)
    chunks.append(y)
joined = tmp / "joined.wav"
sf.write(joined, np.concatenate(chunks), SR)
if a.raw:
    shutil.copy(joined, os.path.splitext(a.out)[0] + "_tts원본.wav")

model = str(ROOT / "models" / (MODEL_NAME + ".pth"))
index = str(ROOT / "models" / "ajossi_v2.index")
if not os.path.exists(model):
    sys.exit(f"모델이 없습니다: {model}")

from infer_rvc_python import BaseLoader
conv = BaseLoader(only_cpu=True, hubert_path=None, rmvpe_path=None)
conv.apply_conf(tag="me", file_model=model, pitch_algo="rmvpe", pitch_lvl=a.pitch,
                file_index=index, index_influence=a.index, respiration_median_filtering=3,
                envelope_ratio=1.0, consonant_breath_protection=0.0)
conv([str(joined)], tag_list=["me"], overwrite=False, parallel_workers=1,
     type_output="wav", show_progress=False)

produced = tmp / "joined_edited.wav"
if not produced.exists():
    sys.exit("변환 결과가 없습니다")
shutil.copy(produced, a.out)
shutil.rmtree(tmp, ignore_errors=True)
info = sf.info(a.out); dur = info.duration
print(f"\n저장: {a.out}  ({len(lines)}줄, {dur:.1f}초)")
