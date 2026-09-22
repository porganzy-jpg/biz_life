# Colab 재학습 — 처음부터 끝까지

> 목표: `ajossi_v2_dataset.zip` (10분, 65클립) 으로 새 음성 모델을 학습해 받아오기
> 총 소요 약 1시간 10분 (설치 10분 + 학습 50분 + 내려받기 5분). 비용 0원.

---

## 0단계 · 준비물 확인

내 PC에 이 파일이 있어야 합니다. 없으면 알려주세요.

```
C:\Users\user\Desktop\biz_life\projects\02-barcode-game\media\song\rvc\ajossi_v2_dataset.zip   (44MB)
```

---

## 1단계 · Applio 노트북 열기 (1분)

아래 주소를 브라우저에 붙여넣으세요. Applio 공식 Colab 노트북입니다.

```
https://colab.research.google.com/github/iahispano/applio/blob/main/assets/Applio.ipynb
```

구글 로그인이 안 돼 있으면 로그인 창이 먼저 뜹니다.

---

## 2단계 · GPU 켜기 (1분) — 빼먹으면 학습이 안 됩니다

1. 상단 메뉴 **런타임 → 런타임 유형 변경**
2. 하드웨어 가속기에서 **T4 GPU** 선택
3. **저장**

확인하려면 코드 셀을 하나 추가(`+ 코드`)해서 실행하세요.

```python
!nvidia-smi --query-gpu=name,memory.total --format=csv
```

`Tesla T4, 15360 MiB` 같은 줄이 나오면 정상입니다. 오류가 나면 GPU가 안 켜진 것입니다.

---

## 3단계 · 설치 셀 실행 (8~10분)

노트북 맨 위부터 셀을 순서대로 실행합니다. 셀 왼쪽의 **▶ 재생 버튼**을 누르거나 `Shift+Enter`.

| 셀 | 제목 | 실행 여부 |
|---|---|---|
| 1 | Install Applio / Clone repo | **실행** |
| 2 | Install requirements | **실행** (가장 오래 걸림, 5~8분) |
| 3 | **Sync with Google Drive** | **건너뛰기** ← 드라이브 용량 초과 상태라 여기서 막힘 |
| 4 | Start server | **아직 실행 안 함** (5단계에서) |

"경고: 이 노트북은 Google에서 작성하지 않았습니다" 창이 뜨면 **그대로 실행**을 누르세요.

> **셀 번호 보는 법**: 셀 왼쪽 대괄호가 `[ ]` 면 아직 실행 안 한 것, `[5]` 처럼 숫자가 있으면 실행된 것,
> `[*]` 면 지금 실행 중입니다. 지난번에 압축 해제가 안 된 이유가 `[ ]` 상태였기 때문입니다.

---

## 4단계 · 데이터셋 올리고 풀기 (3분)

1. Colab 화면 **왼쪽 세로 막대의 폴더 아이콘(📁)** 클릭 → 파일 탐색기가 열립니다
2. 내 PC에서 `ajossi_v2_dataset.zip` 을 그 탐색기로 **끌어다 놓기** (업로드 1~2분)
3. 업로드가 끝나면 코드 셀을 하나 추가하고 아래를 붙여넣어 실행

```python
!mkdir -p /content/dataset
!unzip -q -j /content/ajossi_v2_dataset.zip -d /content/dataset/ajossi_v2
!ls /content/dataset/ajossi_v2 | wc -l
```

**마지막 줄에 `65` 가 나와야 정상입니다.** 0이 나오면 업로드가 덜 끝난 것이니 잠시 후 다시 실행하세요.

---

## 5단계 · 웹 화면 띄우기 (2분)

**Start server** 셀을 실행합니다. method 는 `gradio` 그대로 두세요.

출력에 이런 줄이 나옵니다.

```
* Running on public URL: https://xxxxxxxx.gradio.live
```

그 **gradio.live 링크를 클릭**하면 Applio 화면이 새 탭에서 열립니다.
이 셀은 화면이 떠 있는 동안 계속 실행 상태로 남습니다. **정상입니다. 끄지 마세요.**

---

## 6단계 · 학습 설정 (2분)

Applio 화면에서 상단 **Train** 탭을 누르고 아래대로 입력합니다.

| 항목 | 입력값 |
|---|---|
| Model Name | `ajossi_v2` |
| Dataset Path | `/content/dataset/ajossi_v2` |
| Sampling Rate | `40k` |
| Total Epoch | `300` |
| Batch Size | `8` |
| Save Every Epoch | `50` |
| **Vocoder** | **HiFi-GAN** ← 반드시 이것 |
| Pretrained | 체크 켜둠 (기본값) |
| F0 Method (추출 단계) | `rmvpe` |

> Model Name 을 `ajossi_v2` 로 하는 이유: 기존 `ajossi` 모델을 덮어쓰지 않기 위해서입니다.
> 새 모델이 더 나쁠 경우 돌아갈 곳이 있어야 합니다.

> **Vocoder 를 HiFi-GAN 으로 고정해야 하는 이유 (중요)**
> 1. 내 PC의 변환 도구(`infer-rvc-python`)가 **HiFi-GAN 계열만 지원**합니다.
>    패키지를 확인해보니 `Generator` / `GeneratorNSF` 만 구현돼 있고 MRF HiFi-GAN·RefineGAN 코드가 없습니다.
>    다른 보코더로 학습하면 모델은 만들어져도 **로컬에서 불러오지 못합니다.**
> 2. 데이터가 10분뿐이라 사전학습 모델(pretrained)에 의존해야 하는데, 기본 pretrained 가 HiFi-GAN 기반입니다.
>    보코더를 바꾸면 맞는 pretrained 가 없어 사실상 맨바닥 학습이 되고, 10분으로는 턱없이 부족합니다.
> 3. v1 과 같은 조건이어야 "데이터를 바꾼 효과"만 따로 볼 수 있습니다.

---

## 7단계 · 학습 실행 (45~55분)

Train 탭의 버튼을 **위에서 아래 순서대로** 누릅니다. 앞 단계가 끝나야 다음을 누를 수 있습니다.

| 순서 | 버튼 | 소요 | 끝났다는 표시 |
|---|---|---|---|
| 1 | **Preprocess Dataset** | 1~2분 | "Preprocess completed" |
| 2 | **Extract Features** | 3~5분 | "Extract completed" |
| 3 | **Start Training** | 40~50분 | epoch 300 도달 |
| 4 | **Generate Index** | 1~2분 | "Index generated" |

학습 중에는 노트북의 Start server 셀 출력에 `epoch 12 | loss ...` 같은 줄이 계속 찍힙니다.
**그 줄이 안 보이면 학습이 시작되지 않은 것입니다.**

### 진짜 돌고 있는지 확인하는 법

코드 셀에서 실행하세요.

```python
!nvidia-smi
```

- 아래쪽 **Processes** 에 python 프로세스가 **GPU 메모리 수 GB** 를 쓰고 있으면 학습 중
- 위쪽 **GPU-Util** 이 80% 이상이면 학습 중
- Processes 가 비어 있으면 아무것도 안 돌고 있는 것

### 주의

- **브라우저 탭을 닫지 마세요.** 닫으면 연결이 끊겨 학습이 중단됩니다.
- 90분간 아무 조작이 없으면 Colab이 세션을 끊습니다. 가끔 탭을 눌러 주세요.

---

## 8단계 · 결과 내려받기 (5분) — 세션 끊기기 전에 바로

학습이 끝나면 코드 셀에 아래를 붙여넣어 실행하세요. 필요한 파일만 골라 압축해 내려받습니다.

```python
import glob, os, shutil
from google.colab import files

FOLDER = "/content/Applio/logs/ajossi_v2"

print("[폴더 내용]")
for f in sorted(glob.glob(FOLDER + "/*")):
    print(f"  {os.path.basename(f):45s} {os.path.getsize(f)/1048576:8.1f} MB")

os.makedirs("/content/out2", exist_ok=True)
picked = []
for f in glob.glob(FOLDER + "/*.pth") + glob.glob(FOLDER + "/*.index"):
    name = os.path.basename(f)
    if name.startswith(("G_", "D_")):      # 재학습용 체크포인트 - 제외
        continue
    shutil.copy(f, "/content/out2/" + name)
    picked.append(name)

print("\n[담은 파일]", picked)
shutil.make_archive("/content/ajossi_v2_model", "zip", "/content/out2")
print("압축 크기:", round(os.path.getsize("/content/ajossi_v2_model.zip")/1048576, 1), "MB")
files.download("/content/ajossi_v2_model.zip")
```

**받아야 할 파일**

| 파일 | 개수 | 비고 |
|---|---|---|
| `ajossi_v2_*e_*s.pth` | **3개 이상** | 200 / 250 / 300 에폭 저장본. 과학습 여부를 비교하려면 여러 개 필요 |
| `ajossi_v2.index` | 1개 | |

`G_*.pth`, `D_*.pth` 는 위 코드가 자동으로 제외합니다.

---

## 9단계 · 내 PC에 넣기

받은 zip을 풀어서 이 폴더에 넣어 주세요.

```
C:\Users\user\Desktop\biz_life\projects\02-barcode-game\media\song\rvc\models\
```

**기존 `ajossi_200e_7800s.pth` 와 `ajossi.index` 는 지우지 마세요.** 비교 기준으로 씁니다.

넣고 알려주시면 제가 새 모델 세 개를 전부 변환해 음색 거리를 재고,
가장 좋은 것으로 쇼츠 나레이션을 다시 만들겠습니다.

---

## 막힐 때

| 증상 | 원인과 해결 |
|---|---|
| 셀이 `[ ]` 에서 안 바뀜 | 아직 실행 안 된 것. 재생 버튼을 눌러야 합니다 |
| `65` 대신 `0` | zip 업로드가 덜 끝남. 잠시 후 압축 해제 셀 재실행 |
| GPU 오류 | 2단계를 안 한 것. 런타임 유형을 T4 GPU 로 |
| 드라이브 용량 초과 경고 | 무시해도 됩니다. Sync 셀만 안 누르면 됩니다 |
| T4를 못 받음 | 시간대 혼잡. 30분 뒤 또는 새벽에 재시도 |
| 학습 도중 끊김 | 저장된 중간 에폭(`Save Every 50`)은 남아 있습니다. 8단계로 받으면 됩니다 |
