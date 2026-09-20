# 잔해 방주 — 아트 레퍼런스 & 3D→2.5D 파이프라인 결정 (2026-09-19)

## 1. 벤치마크에서 배운 것

| 레퍼런스 | 무엇을 배우나 | 우리 적용 |
|---|---|---|
| **Fallout Shelter** (Bethesda) — [ArtStation: Felipe Diaz, Vault rooms](https://www.artstation.com/artwork/QnmdDL), [방 이미지 모음](https://fallout-archive.fandom.com/wiki/Category:Fallout_Shelter_room_images), [Blender 재현 모델](https://sketchfab.com/3d-models/a-room-in-fallout-shelter-64c337e01cee41d4bb8d914f97872066) | 방은 **3D로 만들어 고정 카메라로 렌더**. 방마다 **한 가지 주색**(발전실 노랑, 식당 초록, 의무실 하양)과 **천장 조명 1개**로 3초 안에 용도가 읽힘. 벽은 어둡고 단순, 소품이 중앙에 밀집 | 방 = 주색 1 + 랜턴 1 + 소품 밀집. 정면 살짝 위에서 보는 직교 카메라 |
| **This War of Mine** (11 bit) — [80.lv 인터뷰](https://80.lv/articles/this-war-of-mine-a-game-about-civilians-in-war) | **전부 3D인데 카메라를 가로·세로 팬으로만 제한**해 2.5D로 보이게. 세피아 톤 + **손그림 선** 오버레이(A-ha "Take on Me" 영감)로 사진 같은 사실감과 그림의 거리감을 동시에 | Blender **Freestyle 라인**으로 손그림 외곽선. 후처리에서 세피아 쪽으로 채도 감소. 원격 배경만 평면 텍스처 |
| **Metro 2033 디오라마** — [Karl Tabone](https://www.artstation.com/artwork/DKaaG), [Vishnu Priyan 재현(50k tris)](https://www.artstation.com/artwork/L2ReJk), [Maxime Dhamelincourt 폐역](https://www.artstation.com/artwork/RYoBeE), [Sketchfab 터널 디오라마](https://sketchfab.com/3d-models/post-apocalyptic-metro-tunnel-diorama-33d3ebb532fb40cc843a22ef4be4f568) | 지하철 폐역 = **한 사람이 살아낸 흔적**(침낭, 촛불, 라디오, 걸어둔 옷). 트림 시트 + 타일 텍스처로 저폴리 유지. 어둠 속 **랜턴 하나의 따뜻한 빛**이 전부를 설명 | 터널 이동 씬의 직접 레퍼런스. 우리 방주는 "잊힌 역"이므로 승강장 타일·노선 안내 띠·기둥을 방 벽 재질에 넣는다 |

핵심 원칙 3개: **한 방 = 한 색 = 한 등불**, **3D로 만들고 2D로 보여준다**, **손그림 선으로 AI·3D 티를 지운다**.

## 2. 바로 쓰는 무료 CC0 3D 에셋 (다운로드 완료 → `assets3d/`)

| 팩 | 라이선스 | 포맷 | 우리 방에 쓰는 것 |
|---|---|---|---|
| [Kenney Survival Kit 2.0](https://kenney.nl/assets/survival-kit) (80 모델) | CC0 | GLB/FBX/OBJ | barrel, box(-large,-open), bottle, bucket, bedroll, chest, workbench, metal-panel, structure-metal-*, tool-pickaxe/axe, rock-a/b/c, grass patch, fence-fortified, signpost |
| [Quaternius LowPoly Survival Pack](https://opengameart.org/content/lowpoly-survival-pack) (50+) | CC0 | .blend/FBX/OBJ | Can_Closed/Open/Red, WaterBottle_1~3, FirstAidKit, Bandages, Battery_Big/Small, Radio, Pot/Pan, Torch, Trashcan, PropaneTank(물탱크로), Backpack, Phone |
| 추가 후보 | | | [Quaternius Zombie Apocalypse Kit](https://sketchfab.com/3d-models/zombie-apocalypse-kit-free-b0806eaea83f49a592f7e9a039f7c385) (캐릭터 4종 + 애니 20종, 차량·환경) → 주민 스프라이트·지상 폐차. [Poly Haven](https://polyhaven.com) 콘크리트·녹 텍스처 |

두 팩은 스타일(플랫 셰이딩 저폴리)이 비슷해 한 장면에 섞어도 튀지 않는다. 책·선반·파이프·수반처럼 없는 것은 bpy로 큐브/실린더를 직접 만든다.

## 2.5 시점 결정: 아이소메트릭 (2026-09-19)
사용자 피드백 "디아블로처럼 위에서 사선으로 내려다보는 시야". 측면 단면도는 '도면'처럼, 사선 내려보기는 '장소'처럼 읽힌다. 3D 파이프라인이라 카메라만 바꿔 전환(방위각 45°, 고도 30°, 직교 = 2:1 다이메트릭). 규칙: 카메라 쪽 두 벽 제거, 남은 두 벽은 낮게(2.6m), 미굴착은 벽 없는 흙 덩이, 타일은 투명 PNG + 바닥 마름모 메타로 격자 배치. 레퍼런스: Fallout 1/2, Diablo, XCOM 기지 단면, Frostpunk의 위에서 본 도시.

## 2.7 사용자 제공 컨셉아트 7점 분석 (2026-09-19, Pinterest) → 원칙 수정

캡처: `docs/refs/shot_<pin>.png`

| 핀 | 내용 | 배울 점 |
|---|---|---|
| [2814818512860224](https://kr.pinterest.com/pin/2814818512860224/) | 자유의 여신상 머리가 묻힌 **초록으로 뒤덮인 폐허 도시**, 3/4 내려보기 모바일 RPG("힐링 RPG") | 아포칼립스인데 **밝고 생명력 있음**. 잿빛이 아니라 초록·햇살 |
| [10555380371636419](https://kr.pinterest.com/pin/10555380371636419/) | 배낭 멘 생존자가 **한글 간판이 남은 폐점포** 안에 서 있음, 초록빛 | 우리 세계관과 정확히 일치. **일상 공간(가게)이 유적** |
| [356136283058644181](https://kr.pinterest.com/pin/356136283058644181/) | Mini Survival: Zombie Fight — **아이소 픽셀 거점**, 창고·바·비계, 치비 주민 다수, 주황 톤 | 소품·인물 밀도가 높아야 "사는 곳"으로 읽힘. 카메라 고도 ~45° |
| [1006132373014053996](https://kr.pinterest.com/pin/1006132373014053996/) | **위에서 내려본 손그림 캠프**: 캠핑카·텐트·모닥불·상자·울타리, 따뜻한 흙빛 | 우리 타일의 목표 밀도와 질감. 고도 45~55°, 바닥이 많이 보임 |
| [631207704020350950](https://kr.pinterest.com/pin/631207704020350950/) | 옥상·공장 **요새화 거점** 내려보기, 방수포·물탱크·벽돌, 생존자들 | 지상 타일의 방향. 방수포 천막 + 급수탑 + 채소밭 |
| [1047649932090166120](https://kr.pinterest.com/pin/1047649932090166120/) | **편의점 진열대 사이에 텐트**, 침낭·물통·허스키, 밖은 눈 | "아늑한 생존". 차가운 바깥 + 따뜻한 안. 우리 방주의 정서 |
| [964825920186756482](https://kr.pinterest.com/pin/964825920186756482/) | **계단 밑 생존 은신처**, 물통·통조림·벽의 메모, 위층엔 좀비 실루엣 | 좁은 공간의 아기자기한 살림. 위협은 실루엣으로만 |

### 공통점 → 우리 원칙 변경
1. **잿빛 → 초록.** 7점 중 5점이 식물이 점령한 폐허다. 팔레트 "85% 무채색" 규칙을 "**무채색 콘크리트 위에 이끼·덩굴·화분의 초록, 그리고 등불의 주황**"으로 바꾼다. 방 안에도 화분·덩굴·빨래를 넣는다.
2. **아늑한 생존(cozy survival).** 텐트·침낭·물통·통조림·벽 메모가 반복된다. 우리 바코드 유물(라면·물병·배터리)이 곧 이 소품이다. 방마다 "사람이 오늘 밤 여기서 잔다"는 흔적을 넣는다.
3. **카메라를 더 세운다.** 참고작은 고도 45° 안팎으로 바닥이 넓게 보인다. 우리 30°는 벽이 크고 바닥이 좁다 → **45°**로 변경.
4. **밀도.** 소품이 두 배는 있어야 한다. 빈 바닥은 이야기가 없다.
5. **일상 공간이 유적.** 방주의 방은 "옛 역 + 역내 편의점"이다. 편의점 진열대·냉장고·간판 잔해를 방 소품으로 쓴다.
6. **인물이 보인다.** 치비 생존자가 일하는 모습. 현재 DOM 주민을 3D 렌더 캐릭터로 교체(Phase 1).

## 3. 파이프라인

```
tools/blender_rooms.py  (blender -b --python … -- out_dir)
  방 셸(콘크리트 박스, 정면 개방) + 랜턴(방 주색 포인트라이트 + 발광구)
  + CC0 소품 배치(GLB import / .blend append, 바운딩박스로 스케일 정규화)
  + 직교 카메라(정면, 8° 하향) + EEVEE + Freestyle 라인
  → art_raw/rooms3d/<room>.png (768×512)
tools/gen_art.py --post-only rooms3d   → 채도 -25%, 종이 텍스처, 비네트 → static/art/rooms3d/<room>.png
클라이언트: static/art/rooms3d/<room>.png 있으면 사용, 없으면 rooms.js 절차 픽셀 룸
```

레벨업 외형은 같은 스크립트에 `level` 인자를 넣어 소품 수·조명 밝기만 늘려 렌더한다(3D의 장점: 재렌더 비용 0).

## 4. 지하철 노선 컨셉으로 확장 시 레퍼런스
- 승강장 시각 언어: 노선 색 띠, 역 번호판(지명 없음), 스크린도어 잔해, 타일 벽. 방주 벽 재질에 "옛 역"의 흔적을 남긴다.
- 터널 이동 씬(Phase 2, 실시간 3D): Karl Tabone 디오라마의 조명(랜턴 1 + 멀리 균류 형광)과 Metro 시리즈의 "정거장 사이의 어둠"이 기준.
