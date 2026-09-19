# 내 목소리로 노래 부르기 — RVC 보이스 클로닝 가이드

> 이 PC(GTX 1050, 2GB)로는 학습이 불가능하므로 **Google Colab 무료 GPU(T4)** 에서 학습하고,
> 변환(추론)만 로컬에서 합니다. 총 소요 약 40~60분, 비용 0원.

## 준비된 것
| 파일 | 내용 |
|---|---|
| `ajossi_dataset.zip` | 유튜브 @styn844 토크 영상 2편(삼체 후기, 폭싹 후기)에서 추출·정규화한 **39개 클립, 10.5분**. 3.5~10초, 44.1kHz mono |
| `../song_full.mp3` | 「천국 가는 버스」 멜로디+피아노 데모 (기준음) |
| `../song_backing.mp3` | 피아노 반주만 (노래 얹을 MR) |
| `../song_guide_melody.mid` | 멜로디 MIDI (가이드 보컬 합성용) |
| `../song_full.pdf` | 가사 붙은 악보 |

목소리 분석: 말소리 F0 중앙값 84~112Hz (E2~A2). 노래 음역은 **D3~D4**로 작곡했습니다.
`song_full.mp3`를 들어보고 높으면 `compose.py`에서 `key.Key('G')`→`'F'` 또는 `'E'`로 낮춰 다시 렌더하세요.

## 1단계 — Colab에서 학습 (약 30~40분)
1. https://colab.research.google.com 접속 → 새 노트 → 런타임 유형 **T4 GPU**
2. 검색: "RVC WebUI colab" 또는 "Applio colab" (Applio가 UI가 가장 쉬움). 노트 열기 → 셀 순서대로 실행
3. WebUI가 뜨면 **Train** 탭:
   - Model name: `ajossi`
   - Dataset: `ajossi_dataset.zip` 업로드 (Colab 파일 패널에 드래그) → 압축 해제 경로 지정
   - Sample rate 40k, f0 method **rmvpe**, Epochs **200** (10분 데이터 기준), batch 8
   - Preprocess → Extract features → Train → Train index
4. 완료되면 `ajossi.pth` + `added_*.index` 다운로드 → 이 폴더(`rvc/models/`)에 저장

## 2단계 — 노래 원본 만들기 (내 목소리 얹기 전)
RVC는 "이미 부른 노래"를 내 음색으로 바꾸는 도구입니다. 원본 보컬이 필요합니다. 셋 중 하나:
- **A. 직접 부르기(추천)**: `song_backing.mp3` 들으며 휴대폰으로 녹음. 음정이 조금 틀려도 RVC가 음색만 바꾸므로 그대로 쓰면 됨. 가장 자연스러움.
- **B. Suno 커버**: suno.com → Create → 가사 붙이기(`../LYRICS.md`) → 스타일 "acoustic ballad, male low voice, korean" → 생성된 곡의 보컬을 UVR로 분리
- **C. 허밍**: 멜로디를 허밍으로 녹음 → RVC 변환(가사 없는 버전)

## 3단계 — 변환 (Colab 또는 로컬 CPU)
- Colab WebUI **Inference** 탭: 모델 `ajossi` 선택, 원본 보컬 업로드, pitch 0 (원본이 내 음역이면), f0 rmvpe, index rate 0.6 → Convert → 다운로드
- 로컬(CPU, 느리지만 가능): `pip install rvc-python` 후 `python infer_local.py <원본보컬.wav>` (이 폴더의 스크립트)

## 4단계 — 믹스
```
ffmpeg -i vocal_converted.wav -i ../song_backing.mp3 -filter_complex "[0:a]volume=1.0[v];[1:a]volume=0.8[b];[v][b]amix=inputs=2:duration=longest" -c:a libmp3lame -q:a 2 cheonguk_bus_final.mp3
```
Audacity로 열어 보컬 리버브 살짝, 컴프레서 → 완성.

## 주의
- 학습 데이터에 **강아지 소리·BGM이 섞인 구간**은 제외했습니다(신세한탄 영상은 음량이 너무 낮아 제외).
- 결과가 웅얼거리면 epochs를 300으로, 금속성이 들리면 index rate를 0.3으로.

## 추가 — 옛 목소리(2015·2022) 선별 데이터셋
`ajossi_2022_young.zip` (13클립, 2.6분, 목록은 `DATASET_2022_LIST.md`). 2016 뜨개질 영상 5편은 목소리가 없어 제외.
2022년 영상은 다른 사람 목소리·개 소리가 섞여 있어 음높이(95~175Hz)와 유성 비율로 본인 구간만 자동 선별.
- 옛 목소리 F0 중앙값 ≈ 120Hz, 2025년 ≈ 84~112Hz → 실제로 더 밝고 젊은 톤.
- **2.6분은 단독 학습에 부족**(최소 5분). 권장: Colab에서 `ajossi_young` 폴더에 2022 클립 + 2025 클립 중 F0가 높은 편(`Ud43udYSj4U_*`) 15개를 합쳐 학습하거나, 반주 들으며 3~5분 직접 녹음해 추가.
