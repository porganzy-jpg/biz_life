# 크리에이티브 툴체인 구축 기록 (2026-09-19)

> 목표: 2D/3D 게임 에셋 제작, 내 목소리 기반 작곡·작사, AI 쇼츠 영상 제작을
> **무료 툴 + Claude Code 자동화**로 할 수 있는 환경을 만든다.

## 0. 시작 시점 환경

| 항목 | 값 |
|---|---|
| OS | Windows 10 Home 19045 |
| CPU / RAM | i5-9400F / 16GB |
| GPU | GTX 1050 (VRAM 2GB) → **로컬 AI 생성 불가** |
| Python | 3.13 (설치됨) |
| 없음 | Node.js, Blender, Godot, ffmpeg(PATH), DAW |

## 1. 설계 원칙

1. **생성(AI)은 웹 무료 티어, 조립·가공·자동화는 로컬 CLI 툴.**
   VRAM 2GB로는 Stable Diffusion, 영상 생성 모델, RVC 학습 모두 불가.
2. Claude가 조작할 수 있는 툴 기준은 **CLI 또는 Python API가 있는가**.
   - 자동화 가능: Blender(bpy), Godot(headless), MuseScore(mscore CLI), ffmpeg, Pollinations(HTTP), faster-whisper, music21, Manim
   - 수동 단계(웹 UI만 있음): Suno/Udio, Meshy/Tripo3D, Kling/Hailuo/Pika
3. 수동 단계는 10-shorts-factory의 `clips/` 방식처럼 **"폴더에 파일 넣으면 이후는 자동"** 구조로 설계.

## 2. 영역별 툴 선정

### 2-1. 게임 그래픽 에셋 (2D/3D)
| 툴 | 용도 | 자동화 |
|---|---|---|
| Blender | 3D 모델링·리깅·렌더, bpy 스크립트 | O |
| Godot 4 | 2D/3D 게임 엔진, GDScript, headless export | O |
| Krita / Inkscape | 2D 페인팅 / 벡터(SVG는 코드 생성 가능) | 부분 |
| Pixelorama | 픽셀아트, 스프라이트 시트 | X |
| Pollinations.ai | 키 없는 이미지 생성 API (컨셉·텍스처 초안) | O |
| Meshy / Tripo3D | 이미지→3D(GLB) 무료 티어 | 수동 |
| Kenney, Quaternius, Poly Haven, Mixamo | CC0 에셋·애니메이션 | 다운로드 |

### 2-2. 목소리 기반 작곡·작사
| 툴 | 용도 | 자동화 |
|---|---|---|
| music21 + MuseScore 4 | 코드로 멜로디/화성 작곡 → MIDI/MusicXML → mp3 렌더 | O |
| LMMS | 무료 DAW, 편곡 | 수동 |
| Audacity | 녹음·편집 | 수동 |
| Ultimate Vocal Remover | 보컬/MR 분리 (CPU 동작) | 수동 |
| Suno / Udio | 가사→완곡, 오디오 업로드 기반 커버 | 수동 |
| RVC | 보이스 클로닝. **학습은 Colab 무료 GPU**, 추론만 로컬 CPU | 부분 |

### 2-3. 쇼츠 AI 영상 (10-shorts-factory 확장)
| 툴 | 용도 |
|---|---|
| ffmpeg (시스템) | imageio 내장 바이너리 대체, 전체 필터 사용 |
| faster-whisper | 음성→타임코드 자막 (CPU int8) |
| Manim | 코드 기반 모션그래픽 |
| Node.js (+Remotion) | React 영상 렌더, 선택 |
| OBS Studio | 게임 플레이 녹화 |

## 3. 설치 로그

(아래는 작업하면서 채움)

### 3-1. pip 패키지 (완료)
```
pip install faster-whisper music21 mido requests manim
```
| 패키지 | 버전 | 검증 |
|---|---|---|
| faster-whisper | 1.2.1 | base 모델(int8, CPU): 로드 17s, 한국어 9초 음성 → 2.0s 전사, 타임코드 정상 |
| music21 | 10.5.0 | C-G-Am-F 8마디 피아노 → MIDI + MusicXML 생성 성공 |
| manim | 0.21.0 | 텍스트+라인 애니메이션 480p 렌더 성공 (LaTeX 없이 동작) |
| mido | 1.3.3 | import OK |

**이슈 1 — faster-whisper 모델 다운로드 실패 `WinError 1314`**
Hugging Face 캐시가 심볼릭 링크를 만들려다 권한 오류. Windows 개발자 모드가 꺼져 있으면 발생.
해결: 사용자 환경변수 `HF_HUB_DISABLE_SYMLINKS=1` 영구 설정(`setx`). 새 셸부터 적용.

**메모** — base 모델은 "무료 툴로 쇼츠" → "무료투로 슈트"로 오인식. 실전 자막은 `small` 이상 사용.

### 3-2. Pollinations.ai 이미지 API (완료)
- 인증 없이 `GET https://image.pollinations.ai/prompt/<url-encoded prompt>?width=768&height=768&nologo=true&seed=N`
- "low poly wooden treasure chest" 테스트: 200 OK, 33KB JPEG, 3.4초
- 품질: 형태·색은 잡히나 디테일이 흐림 → **컨셉/텍스처 초안, 배경 플레이트용**. 최종 에셋은 손질 필요.

### 3-3. Pixelorama (완료, 포터블)
- winget에 없음 → GitHub 릴리스 v1.2.3 64bit zip 직접 다운로드
- 위치: `C:\Users\user\AppData\Local\Programs\Pixelorama\Pixelorama-Windows-64bit\Pixelorama.exe`

### 3-4. winget 로컬 툴
**이슈 2 — 첫 실행 전부 exit 94**
`msstore` 소스 인증서 오류(0x8a15005e)로 winget이 소스 선택을 요구하며 중단.
해결: 모든 명령에 `--source winget` 명시.

**이슈 3 — 머신 범위 MSI 설치는 UAC 승인 필요**
`--silent`로도 UAC는 우회 불가. 설치 중 화면의 UAC 창을 직접 승인해야 진행됨.

| 툴 | 결과 |
|---|---|
| Gyan.FFmpeg 9.0.1 | 설치 성공, PATH 등록 (ffmpeg/ffplay/ffprobe) |
| OpenJS.NodeJS.LTS 24.19.0 | 설치 성공 (UAC 승인 필요했음), npm 11.17 |
| BlenderFoundation.Blender 5.2.1 LTS | 설치 성공 (UAC). `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` |
| GodotEngine.GodotEngine 4.7.2 | 설치 성공 (포터블). `%LOCALAPPDATA%\Microsoft\WinGet\Packages\GodotEngine.GodotEngine_*\Godot_v4.7.2-stable_win64.exe` |

### 3-5. Blender / Godot 헤드리스 검증 (완료)
**Blender 5.2.1** — `blender -b --python script.py -- <out_dir>`
- bpy로 저폴리 보물상자(큐브 3개 + 머티리얼) 생성 → GLB 내보내기(5KB) → EEVEE 512px 렌더(약 50초, GTX 1050)
- 이슈 4: Blender 5.x에서 렌더 엔진 enum은 `BLENDER_EEVEE` (4.2~4.x의 `BLENDER_EEVEE_NEXT` 아님)
- 이슈 5: `light_add(type='SUN')` 기본 회전은 수직 아래 → 옆면 전부 검게 나옴. 태양 회전 지정 + World 배경광 추가로 해결
- 결론: 모델 생성·리깅·렌더·포맷 변환을 코드로 반복 실행 가능. Meshy 등에서 받은 GLB 후처리에도 사용

**Godot 4.7.2** — `godot --headless --path <project> [--import]`
- 최소 프로젝트(project.godot + main.tscn + main.gd)로 64x64 PNG를 코드로 생성하고 종료. 정상 동작
- 결론: 씬/스크립트를 텍스트로 작성해 헤드리스로 실행·검증·export 가능. 최초 1회 `--import`로 캐시 생성 필요
| Musescore.Musescore 4 | 설치 성공 (UAC). `C:\Program Files\MuseScore 4\bin\MuseScore4.exe` |

### 3-6. 작곡 파이프라인 검증 (완료)
`music21(코드로 작곡) → MusicXML/MIDI → MuseScore4.exe -o out.mp3 / out.png`
- C-G-Am-F 진행 8마디, 멜로디+반주 2파트 → 악보 PNG(1장) + mp3(44.1kHz, 23.9초) 렌더 성공
- MuseScore CLI는 GUI 없이 동작하며 `-o` 확장자로 포맷 자동 결정(mp3, wav, png, pdf, mid)
- 결론: 가사·멜로디·화성을 제가 코드로 작성하고 바로 들을 수 있는 데모 mp3까지 자동화 가능.
  이 mp3를 Suno "오디오 업로드" 또는 사용자 녹음 가이드(기준음)로 사용.
| Audacity.Audacity 4.0 | 설치 성공. `C:Program FilesAudacity 4Audacity.exe` |
| KDE.Krita | 설치 성공 |
| Inkscape.Inkscape | 설치 성공. `C:\Program Files\Inkscape\bin\inkscape.exe` CLI로 SVG→PNG 변환 확인 |
| LMMS.LMMS | 설치 성공 |
| OBSProject.OBSStudio | **업그레이드 실패(설치기 종료 코드 6)**. 기존 30.1.2가 설치되어 있어 그대로 사용 가능. `C:\Program Files\obs-studio\bin\64bit\obs64.exe`. 필요 시 나중에 `winget upgrade OBSProject.OBSStudio --source winget` 재시도 |

**메모** — Blender, Godot, Inkscape는 PATH에 등록되지 않음(정상). Claude는 절대경로로 호출(4장 참고).

## 4. Claude가 쓰는 명령 치트시트

새 셸에서는 ffmpeg/node가 PATH에 있음. 나머지는 절대경로.

| 작업 | 명령 |
|---|---|
| 3D 생성·렌더 | `"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --python script.py -- <out_dir>` |
| Godot 실행/빌드 | `Godot_v4.7.2-stable_win64.exe --headless --path <proj> --import` → `--headless --path <proj>` / `--export-release <preset> <out>` |
| 악보→mp3 | `"C:\Program Files\MuseScore 4\bin\MuseScore4.exe" -o out.mp3 in.musicxml` |
| 자막 전사 | `WhisperModel("small", device="cpu", compute_type="int8").transcribe(path, language="ko", word_timestamps=True)` |
| 모션그래픽 | `python -m manim -qh -o out.mp4 scene.py SceneName` (`-qh` 1080p, `-ql` 미리보기) |
| 컨셉 이미지 | `GET https://image.pollinations.ai/prompt/<prompt>?width=1024&height=1024&nologo=true&seed=N` |
| 영상 조립 | `ffmpeg` (10-shorts-factory `render.py`가 이미 래핑) |

## 5. 수동 단계 (웹 서비스, 가입만 하면 됨)

| 서비스 | 용도 | 결과 파일을 넣을 곳 |
|---|---|---|
| Suno / Udio | 가사→완곡, 내 허밍 업로드 기반 커버 | (작곡 프로젝트 `songs/` 예정) |
| Meshy / Tripo3D | 이미지→3D GLB | Blender 스크립트 입력 |
| Kling / Hailuo / Pika | 사진→움직이는 영상(i2v) | `10-shorts-factory/clips/` |
| Google Colab | RVC 보이스 클로닝 **학습** (무료 T4) | 학습된 .pth를 로컬 RVC 추론에 사용 |
| Ultimate Vocal Remover | 보컬/MR 분리 (GitHub 릴리스, CPU 동작) | 로컬 설치, 수동 실행 |

## 6. 다음 단계 제안

1. **쇼츠**: 10-shorts-factory에 faster-whisper 자동 자막 + Manim 인트로/도표 컷 통합
2. **게임 에셋**: `Pollinations 컨셉 → Meshy GLB → Blender 정리·렌더 → Godot 임포트` 파이프라인을 새 프로젝트로 (예: `12-asset-forge`)
3. **작곡**: `가사 + music21 데모 → Suno 완곡 → Colab RVC 내 목소리 → Audacity 마무리` 워크플로 문서화 및 첫 곡 제작
4. Pixelorama·Krita·Inkscape·LMMS·OBS는 GUI 툴이므로 사용자가 직접 작업, Claude는 결과 파일 후처리

## 7. 최종 결과 요약

| 영역 | 설치·검증 완료 | 자동화 검증 산출물 |
|---|---|---|
| 3D | Blender 5.2.1 | bpy 스크립트 → GLB + EEVEE 렌더 PNG |
| 게임 엔진 | Godot 4.7.2 | 헤드리스 실행 → 코드 생성 PNG |
| 2D | Inkscape, Krita, Pixelorama | SVG 코드 → Inkscape CLI → PNG 아이콘 |
| 이미지 AI | Pollinations API | 컨셉 JPEG (3초) |
| 작곡 | music21, MuseScore 4, LMMS, Audacity 4 | 8마디 → 악보 PNG + mp3 |
| 쇼츠 | ffmpeg 9, faster-whisper, Manim, Node 24, OBS 30 | 한국어 자막 타임코드, 480p 모션그래픽 |

환경변수 변경: `HF_HUB_DISABLE_SYMLINKS=1` (사용자), PATH에 ffmpeg·Node 추가(winget 자동).
소요 시간: 약 25분 (17:25 ~ 17:50), UAC 승인 4회.

## 8. 실전 적용 (같은 날, 02-barcode-game)

툴체인을 바로 바코드 게임 두 파트에 적용. 산출물과 방법은 `projects/02-barcode-game/media/README.md`.

| 산출물 | 툴 | 비고 |
|---|---|---|
| 3층 천국 버스 3D (GLB + 히어로/야간 스틸 + 24프레임 턴테이블) | Blender 5.2 bpy | 기획서 4.4 버스 가이드를 코드로 구현. 5.x API 차이: 렌더 엔진 `BLENDER_EEVEE`, F-curve 대신 `preferences.edit.keyframe_new_interpolation_type`, 색이 바래면 `view_transform='Standard'` |
| 잠이·풍경 3종·주방 단면 / 몬스터 3종·던전·포탈 (12장) | Pollinations API | "3층 버스"는 그리지 못함 → 버스는 Blender로. 우하단 로고는 4.5% 크롭 |
| 바코드 스캔 애니메이션 (1080x1920) | Manim `-r 1080,1920` | Hell 쇼츠 훅 |
| 쇼츠 BGM 2곡 | music21 → MuseScore CLI | heaven_lofi 72bpm / hell_pulse 128bpm |
| 쇼츠 2편 (30.3초 / 22.3초) | 10-shorts-factory | `SHORTS_PROJECT` 환경변수로 외부 프로젝트 렌더 지원 추가, 화자 3명 추가 |
| 「천국 가는 버스」 악보·데모·반주·MIDI·가사 | librosa(F0 분석) + music21 + MuseScore | 말소리 F0 84~112Hz → 멜로디 D3~D4 |
| RVC 데이터셋 39클립 10.5분 + Colab 가이드 + 로컬 추론 스크립트 | yt-dlp + librosa | 학습은 Colab T4에서 사용자 실행 필요 |

추가 설치: `pip install yt-dlp librosa soundfile`

## 9. 저녁 추가 — 게임 적용, 2.5D 컨셉, Pollinations 교훈

- **게임 클라이언트 적용**: FastAPI에 `/artwork`, `/media` 정적 마운트 추가(기존엔 서버 실행 시 모든 이미지가 404→이모지였음), `<model-viewer>`로 Blender GLB 버스를 게임 안에서 회전 표시, 몬스터 이미지는 AI 컨셉아트 우선. `?view=bus` 딥링크.
- **보이스 데이터셋 2종**: 2025 토크(39클립 10.5분) + 2015/2022 선별(13클립 2.6분, F0 95~175Hz·유성률 55%로 본인 구간 자동 선별).
- **2.5D 몬스터 컨셉 24종** (`projects/02-barcode-game/concept-2.5d/`): 4테마(식품·전자기기·생활용품·국가코드 전설).

**Pollinations 교훈 (중요)**
1. **IP당 동시 요청 1개.** 에이전트 4개를 병렬로 돌리면 3개는 429 "Queue full for IP"로 대기만 함. 이미지 생성은 반드시 순차. 병렬 에이전트는 문서 작성처럼 API를 안 쓰는 일에만.
2. **모델이 시간대에 따라 바뀜.** 오후엔 flux(선명), 저녁엔 `/models`가 `["sana"]`만 반환. `model=flux`를 붙여도 무시됨. 생성 전 `curl https://image.pollinations.ai/models`로 확인.
3. **sana 대응 프롬프트 레시피**: 긴 스타일 프리픽스("2.5D isometric... soft cel shading... toy-like")는 얼굴 없는 파란 덩어리를 만듦. 대신 `kawaii mascot character design, 3D render, chibi proportions, isometric three-quarter view, studio lighting, sharp focus, ` + **소재 하나 + 얼굴 묘사** 짧게. 복합 소재(김밥+슬라임)는 "onigiri character with big eyes"처럼 사물을 캐릭터화하는 문장이 잘 됨.
4. `nologo=true`는 무시됨 → 하단 4.5% 크롭.
