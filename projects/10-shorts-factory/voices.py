# -*- coding: utf-8 -*-
"""edge-tts로 캐릭터 목소리를 만들고 앞뒤 무음을 잘라낸다.

edge-tts 출력은 앞뒤에 0.5~1초씩 무음이 붙는다. 빠른 컷 장르에서는
그 무음이 리듬을 다 죽이므로 반드시 제거해야 한다.
같은 대사는 캐시에서 재사용한다.
"""

import asyncio
import hashlib
from pathlib import Path

import config
from ffutil import probe_duration, run

# 앞쪽 무음만 제거 가능한 필터라, areverse로 뒤집어 두 번 건다
_SR = ("silenceremove=start_periods=1:start_silence=0.05"
       f":start_threshold={config.SILENCE_DB}dB:detection=peak")
TRIM_FILTER = f"{_SR},areverse,{_SR},areverse"


def _cache_path(speaker: str, text: str, cfg: dict) -> Path:
    key = f"{speaker}|{cfg['voice']}|{cfg['pitch']}|{cfg['rate']}|{text}|trim={config.TRIM_SILENCE}"
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return config.CACHE_DIR / f"voice_{speaker}_{h}.mp3"


async def _synth_one(text: str, cfg: dict, raw: Path, sem: asyncio.Semaphore) -> None:
    import edge_tts
    async with sem:
        comm = edge_tts.Communicate(text, cfg["voice"], rate=cfg["rate"], pitch=cfg["pitch"])
        tmp = raw.with_suffix(".part")
        await comm.save(str(tmp))
        tmp.replace(raw)


async def _synth_all(jobs: list[tuple[str, dict, Path]]) -> None:
    sem = asyncio.Semaphore(4)
    await asyncio.gather(*(_synth_one(t, c, r, sem) for t, c, r in jobs))


def build_voices(cuts) -> None:
    """대사가 있는 컷에 voice_path 와 duration 을 채운다."""
    config.CACHE_DIR.mkdir(exist_ok=True)
    jobs: list[tuple[str, dict, Path]] = []
    queued: set[Path] = set()      # 같은 대사가 여러 컷에 나오면 한 번만 생성
    voiced = []

    for cut in cuts:
        if not cut.line:
            cut.duration = config.resolve_cut_duration(cut.length, 0.0)
            continue
        cfg = config.CHARACTERS.get(cut.speaker)
        if cfg is None:
            raise KeyError(
                f"컷 {cut.no}: 모르는 화자 '{cut.speaker}'. "
                f"config.py 에 등록된 화자: {list(config.CHARACTERS)}"
            )
        out = _cache_path(cut.speaker, cut.line, cfg)
        cut.voice_path = out
        voiced.append(cut)
        if not out.exists() and out not in queued:
            queued.add(out)
            jobs.append((cut.line, cfg, out.with_suffix(".raw.mp3")))

    if jobs:
        print(f"  음성 생성 {len(jobs)}건 (캐시 적중 {len(voiced) - len(jobs)}건)...")
        asyncio.run(_synth_all(jobs))
        for _, _, raw in jobs:
            final = raw.with_suffix("").with_suffix(".mp3")   # .raw.mp3 -> .mp3
            if config.TRIM_SILENCE:
                run(["-i", str(raw), "-af", TRIM_FILTER, str(final)], what="무음 제거")
                raw.unlink(missing_ok=True)
            else:
                raw.replace(final)

    for cut in voiced:
        cut.duration = config.resolve_cut_duration(cut.length, probe_duration(cut.voice_path))
