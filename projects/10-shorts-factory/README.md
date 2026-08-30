# 10-shorts-factory

까뮈 & 바위 유튜브 쇼츠 자동 제작 파이프라인.
**대본 마크다운 한 장 → 자막·더빙·컷편집이 끝난 세로 mp4.**

## 설치

```bash
pip install -r requirements.txt
```
ffmpeg은 따로 설치할 필요 없습니다 (`imageio-ffmpeg`가 내장 바이너리 제공).

## 사용법

```bash
python make.py scripts/ep01_monday.md --dry    # 대사 길이/총 시간만 확인 (렌더 X)
python make.py scripts/ep01_monday.md          # 렌더 → build/ep01_monday.mp4
python make.py --all                           # scripts/ 전부 렌더
python make.py --all --shotlist                # 촬영해야 할 클립 목록
```

**클립이 하나도 없어도 렌더됩니다.** 검은 화면 + 자막 + 더빙만 나오는
"애니매틱"이 만들어지는데, 촬영 전에 대사 리듬과 총 길이를 귀로 확인하는 용도입니다.
먼저 `--dry`로 길이를 다듬고, 애니매틱을 들어보고, 그 다음에 촬영하세요.

## 대본 형식

`scripts/*.md` 의 마크다운 표. 열 순서는 자유(헤더 이름으로 인식).

```markdown
# EP01 월요일
> bgm: lofi_soft

| # | 길이 | 클립              | 화자 | 대사        | 자막     | 효과음 |
|---|------|-------------------|------|-------------|----------|--------|
| 1 | 1.3  | bawi_sleep_face   |      |             | 月 06:00 | snore  |
| 2 | 1.0  | kkamu_stare@12.5  | 까뮈 | 일어나.     |          | thud   |
```

- **길이** — 원하는 컷 길이(초). 대사가 더 길면 자동으로 늘어납니다(`config.resolve_cut_duration`).
- **클립** — `clips/` 안의 파일명. 확장자 생략 가능.
  - 영상(mp4/mov/…): `@12.5` 는 원본 12.5초 지점부터
  - **정지 이미지(png/jpg/…)**: 켄번스(슬로우 줌/팬)로 자동 변환.
    `@in` `@out` `@left` `@right` 로 모션 지정, 생략하면 컷 번호 순으로 자동 순환
- **화자** — `config.CHARACTERS` 의 키. 없으면 나레이션 없는 컷.
- **자막** — 화면 상단 상황 자막 (흰색). 대사와 동시에 나올 수 있습니다.
- **효과음** — `sfx/` 안의 파일명. 확장자 생략 가능.
- **bgm** — `bgm/` 안의 파일명. 짧으면 자동 반복됩니다.

## 구조

| 파일 | 역할 |
|---|---|
| `config.py` | 캐릭터 목소리, 화면 규격, 자막 스타일, **컷 길이 결정 로직** |
| `parse_script.py` | 대본 md → 컷 리스트 |
| `voices.py` | edge-tts 더빙 + 앞뒤 무음 제거 + 캐싱 |
| `subtitles.py` | PIL로 자막 PNG 렌더 |
| `placeholder.py` | 촬영 전 스토리보드 카드 생성 |
| `render.py` | 컷별 ffmpeg 인코딩 → 이어붙이기 → BGM 믹스 |
| `make.py` | CLI |
| `docs/SHOOTING_GUIDE.md` | 실사 촬영 가이드 |
| `docs/AI_VIDEO_GUIDE.md` | **AI 영상 제작 가이드 — 먼저 읽으세요** |
| `docs/AI_PROMPTS.md` | 테이크별 i2v 프롬프트 전문 |

## 목소리 바꾸기

`config.py`의 `CHARACTERS`에서 `pitch`/`rate`를 조정합니다.
두 캐릭터를 **반대 방향으로** 밀어야 자막 없이도 구분됩니다.

```bash
python -m edge_tts --list-voices | grep ko-KR   # 사용 가능한 한국어 화자
```

바꾼 뒤에는 `.cache/` 를 지워야 새 목소리로 다시 생성됩니다.

## 정지 이미지로 컷 채우기

`clips/` 에 mp4 대신 **png/jpg 한 장**을 넣어도 컷이 만들어집니다.
슬로우 줌/팬(켄번스)이 자동으로 걸려서 정지 사진처럼 보이지 않습니다.

```markdown
| 14 | 1.4 | window_sunset.png       | | | | |        <- 모션 자동 배정
| 19 | 1.6 | wet_pawprints.png@left  | | | 젖은 발자국 | |  <- 왼쪽으로 팬
```

AI 이미지, 폰 사진, 스톡 이미지 아무거나 됩니다. AI **영상**보다 훨씬 싸고 빠르며,
나중에 실사 mp4로 교체하면 파일만 바꿔도 자동으로 전환됩니다.

- `config.KENBURNS_ZOOM` 기본 1.18. 1.3 넘기면 화질이 뭉개집니다.
- 원본 이미지는 **세로 1080x1920 이상** 권장. 확대되므로 작으면 깨집니다.
- 정지 이미지 컷은 2초를 넘기지 마세요. 켄번스로도 정지 티가 납니다.

## 알아둘 것

- edge-tts 출력은 앞뒤에 0.5~1초 무음이 붙습니다. `TRIM_SILENCE=True`가 이걸 제거합니다.
  껐다가는 18컷짜리가 25초 → 38초로 부풀면서 리듬이 죽습니다.
- 컷 상한은 `CUT_MAX=3.0`초. 이 장르에서 3초 넘는 컷은 스크롤을 부릅니다.
- 총 길이 45초 넘으면 `--dry`가 경고합니다. 쇼츠 완주율이 급감하는 지점입니다.
