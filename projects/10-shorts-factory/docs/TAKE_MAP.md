# 생성 체크리스트

대본 5편 = 컷 107개. 원본 클립명 88종이었으나 **테이크 12개 + 개별 16개 = 28회 생성**으로 정리됨.

프롬프트는 `AI_PROMPTS.md`. 만든 파일은 `clips/` 에 **저장 파일명 그대로** 넣으면 됩니다.

## 1) 캐릭터 테이크 (image-to-video, 5초, 9:16)

| | 저장 파일명 | 커버 | 등장 |
|---|---|---|---|
| 1 | `kkamu_front_take.mp4` | 17컷 | EP01,EP02,EP04,EP05 |
| 2 | `bawi_front_take.mp4` | 12컷 | EP01,EP02,EP04,EP05 |
| 3 | `kkamu_tilt_take.mp4` | 11컷 | EP01,EP02,EP03,EP04 |
| 4 | `bawi_sit_take.mp4` | 10컷 | EP01,EP03,EP04 |
| 5 | `bawi_sofa_take.mp4` | 8컷 | EP02,EP05 |
| 6 | `kkamu_bowl_take.mp4` | 7컷 | EP01,EP04,EP05 |
| 7 | `bawi_sleep_take.mp4` | 7컷 | EP01,EP02 |
| 8 | `bawi_react_take.mp4` | 6컷 | EP01,EP02,EP03,EP04 |
| 9 | `kkamu_run_take.mp4` | 4컷 | EP01,EP03,EP05 |
| 10 | `kkamu_blanket_take.mp4` | 2컷 | EP03 |
| 11 | `kkamu_props_take.mp4` | 2컷 | EP02 |
| 12 | `bawi_paw_bowl.mp4` | 1컷 | EP04 |

## 2) 사물 · 배경 (text-to-video 또는 정지 이미지)

정지 이미지가 더 쌉니다. `clips/` 에 png를 넣으면 켄번스가 자동 적용됩니다.

| | 저장 파일명 | 커버 |
|---|---|---|
| 1 | `scale_paws.mp4` 또는 `scale_paws.png` | 2컷 |
| 2 | `phone_buzz.mp4` 또는 `phone_buzz.png` | 2컷 |
| 3 | `leash_closeup.mp4` 또는 `leash_closeup.png` | 2컷 |
| 4 | `sofa_back_two.mp4` 또는 `sofa_back_two.png` | 2컷 |
| 5 | `door_open.mp4` 또는 `door_open.png` | 1컷 |
| 6 | `window_sunny.mp4` 또는 `window_sunny.png` | 1컷 |
| 7 | `night_walk.mp4` 또는 `night_walk.png` | 1컷 |
| 8 | `door_lock.mp4` 또는 `door_lock.png` | 1컷 |
| 9 | `broken_pot.mp4` 또는 `broken_pot.png` | 1컷 |
| 10 | `wet_pawprints.mp4` 또는 `wet_pawprints.png` | 1컷 |
| 11 | `wet_floor.mp4` 또는 `wet_floor.png` | 1컷 |
| 12 | `window_sunset.mp4` 또는 `window_sunset.png` | 1컷 |
| 13 | `owner_sees_paw.mp4` 또는 `owner_sees_paw.png` | 1컷 |
| 14 | `two_blankets.mp4` 또는 `two_blankets.png` | 1컷 |
| 15 | `owner_pov_sofa.mp4` 또는 `owner_pov_sofa.png` | 1컷 |
| 16 | `empty_bag.mp4` 또는 `empty_bag.png` | 1컷 |

## 진행 확인

```bash
python make.py --all --shotlist   # 남은 것 확인
python make.py --all             # 채운 만큼 반영해서 렌더
```

**누적 효과** — 위에서부터 만들 때 채워지는 컷:

- 1개까지 만들면 **17컷** (15%)
- 2개까지 만들면 **29컷** (27%)
- 3개까지 만들면 **40컷** (37%)
- 4개까지 만들면 **50컷** (46%)
- 5개까지 만들면 **58컷** (54%)
- 6개까지 만들면 **65컷** (60%)
