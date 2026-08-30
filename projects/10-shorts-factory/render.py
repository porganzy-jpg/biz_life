# -*- coding: utf-8 -*-
"""컷 단위로 ffmpeg 인코딩 → concat → BGM 믹스. 최종 mp4를 만든다."""

from pathlib import Path

import config
import placeholder
import subtitles
from ffutil import find_asset, is_image, run

VCODEC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(config.CRF),
          "-pix_fmt", "yuv420p", "-r", str(config.FPS)]
ACODEC = ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"]



def _kenburns(cut, idx: int, d: float) -> str:
    """정지 이미지에 슬로우 줌/팬을 건다.

    zoompan은 출력 해상도에서 x/y를 정수로 계산해 떨림이 생긴다.
    미리 2배로 키운 뒤 zoompan을 걸어 s= 로 되돌리면 부드러워진다.
    """
    z = config.KENBURNS_ZOOM
    n = max(1, round(d * config.FPS))
    mode = cut.clip_mode or config.KENBURNS_MODES[cut.no % len(config.KENBURNS_MODES)]

    cy = "ih/2-(ih/zoom/2)"
    if mode in ("out", "zoomout"):
        zexpr, x, y = f"{z}-({z}-1)*on/{n}", "iw/2-(iw/zoom/2)", cy
    elif mode in ("left", "panleft"):
        zexpr, x, y = f"{z}", f"(iw-iw/zoom)*(1-on/{n})", cy
    elif mode in ("right", "panright"):
        zexpr, x, y = f"{z}", f"(iw-iw/zoom)*(on/{n})", cy
    else:  # in / zoomin / 알 수 없는 값
        zexpr, x, y = f"1+({z}-1)*on/{n}", "iw/2-(iw/zoom/2)", cy

    w2, h2 = config.WIDTH * 2, config.HEIGHT * 2
    return (
        f"[{idx}:v]scale={w2}:{h2}:force_original_aspect_ratio=increase,"
        f"crop={w2}:{h2},"
        f"zoompan=z='{zexpr}':x='{x}':y='{y}':d=1:s={config.WIDTH}x{config.HEIGHT}"
        f":fps={config.FPS},"
        f"setsar=1,trim=duration={d},setpts=PTS-STARTPTS[v0]"
    )


def _render_cut(cut, out: Path, missing: list[str]) -> None:
    d = round(cut.duration, 3)
    inputs: list[str] = []
    chains: list[str] = []
    idx = 0

    # ── 비디오 소스 ───────────────────────────────────────────
    clip = find_asset(config.CLIPS_DIR, cut.clip) if cut.clip else None
    if cut.clip and clip is None:
        missing.append(cut.clip)

    if clip and is_image(clip):
        inputs += ["-loop", "1", "-framerate", str(config.FPS), "-t", str(d), "-i", str(clip)]
        chains.append(
            _kenburns(cut, idx, d) if config.KENBURNS else
            f"[{idx}:v]scale={config.WIDTH}:{config.HEIGHT}"
            f":force_original_aspect_ratio=increase,"
            f"crop={config.WIDTH}:{config.HEIGHT},setsar=1[v0]"
        )
    elif clip:
        if cut.clip_start:
            inputs += ["-ss", str(cut.clip_start)]
        inputs += ["-i", str(clip)]
        chains.append(
            f"[{idx}:v]fps={config.FPS},"
            f"scale={config.WIDTH}:{config.HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={config.WIDTH}:{config.HEIGHT},setsar=1,"
            f"tpad=stop_mode=clone:stop_duration={d},"      # 클립이 짧으면 마지막 프레임 정지
            f"trim=duration={d},setpts=PTS-STARTPTS[v0]"
        )
    elif config.PLACEHOLDER:
        inputs += ["-loop", "1", "-t", str(d), "-i", str(placeholder.render_card(cut))]
        chains.append(f"[{idx}:v]fps={config.FPS},setsar=1[v0]")
    else:
        inputs += ["-f", "lavfi", "-t", str(d),
                   "-i", f"color=c=black:s={config.WIDTH}x{config.HEIGHT}:r={config.FPS}"]
        chains.append(f"[{idx}:v]setsar=1[v0]")
    idx += 1

    # ── 자막 오버레이 ─────────────────────────────────────────
    png = subtitles.render_overlay(cut)
    if png:
        inputs += ["-i", str(png)]
        chains.append(f"[v0][{idx}:v]overlay=0:0:format=auto[v]")
        idx += 1
    else:
        chains.append("[v0]null[v]")

    # ── 오디오: 무음 베이스 + 대사 + 효과음 ────────────────────
    inputs += ["-f", "lavfi", "-t", str(d), "-i", "anullsrc=r=44100:cl=stereo"]
    alabels = [f"[{idx}:a]"]
    idx += 1

    for path, gain in (
        (cut.voice_path, config.VOICE_GAIN),
        (find_asset(config.SFX_DIR, cut.sfx) if cut.sfx else None, config.SFX_GAIN),
    ):
        if not path:
            continue
        inputs += ["-i", str(path)]
        tag = f"a{idx}"
        chains.append(
            f"[{idx}:a]atrim=duration={d},asetpts=PTS-STARTPTS,"
            f"aformat=sample_rates=44100:channel_layouts=stereo,volume={gain}[{tag}]"
        )
        alabels.append(f"[{tag}]")
        idx += 1

    if len(alabels) == 1:
        chains.append(f"{alabels[0]}anull[a]")
    else:
        chains.append(
            "".join(alabels) + f"amix=inputs={len(alabels)}:duration=first:normalize=0[a]"
        )

    run([*inputs, "-filter_complex", ";".join(chains),
         "-map", "[v]", "-map", "[a]", "-t", str(d),
         *VCODEC, *ACODEC, str(out)],
        what=f"컷 {cut.no}")


def render(ep, out_path: Path | None = None) -> Path:
    config.BUILD_DIR.mkdir(exist_ok=True)
    work = config.BUILD_DIR / ep.slug
    work.mkdir(exist_ok=True)
    out_path = out_path or config.BUILD_DIR / f"{ep.slug}.mp4"

    missing: list[str] = []
    parts: list[Path] = []
    for cut in ep.cuts:
        part = work / f"cut{cut.no:03d}.mp4"
        _render_cut(cut, part, missing)
        parts.append(part)
        print(f"  컷 {cut.no:>2}/{len(ep.cuts)}  {cut.duration:>4.2f}s  {cut.line or cut.caption or ''}")

    # ── 이어붙이기 ────────────────────────────────────────────
    listfile = work / "concat.txt"
    listfile.write_text(
        "\n".join(f"file '{p.name}'" for p in parts) + "\n", encoding="utf-8"
    )
    joined = work / "_joined.mp4"
    run(["-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(joined)],
        what="컷 이어붙이기")

    # ── BGM ──────────────────────────────────────────────────
    bgm = find_asset(config.BGM_DIR, ep.bgm) if ep.bgm else None
    if bgm:
        run(["-i", str(joined), "-stream_loop", "-1", "-i", str(bgm),
             "-filter_complex",
             f"[1:a]volume={config.BGM_GAIN}[b];[0:a][b]amix=inputs=2:duration=first:normalize=0[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", *ACODEC,
             "-movflags", "+faststart", str(out_path)],
            what="BGM 믹스")
    else:
        run(["-i", str(joined), "-c", "copy", "-movflags", "+faststart", str(out_path)],
            what="최종 출력")

    if missing:
        uniq = sorted(set(missing))
        print(f"\n  [주의] clips/ 에 없어서 검은 화면으로 대체된 클립 {len(uniq)}개:")
        for m in uniq:
            print(f"         - {m}")

    return out_path
