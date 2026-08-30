# AI 영상 프롬프트 (image-to-video)

컷 단위가 아니라 **테이크 단위**입니다. 5초 하나를 뽑아 `@초`로 여러 컷에 나눠 씁니다.
프롬프트는 영어로 넣으세요 (서비스 대부분이 영어에서 결과가 좋습니다).

공통 설정: `i2v` / `9:16` / `5초` / `모션 강도 Low`

공통 Negative (전부에 붙이세요):
```
fast motion, jumping, running, morphing face, distorted face, extra limbs,
extra paws, deformed legs, mouth opening, barking, talking, human hands,
text, watermark, logo, blurry, low quality
```

---

# 까뮈 (검은 프렌치 불독)

### TAKE-K1 — 정면 대사용 ★최우선
- 레퍼런스: `ref_kkamu_front.jpg`
- 저장: `kkamu_front_take.mp4`
- 커버: 17컷 — `kkamu_alert` `kkamu_arms` `kkamu_calm` `kkamu_closeup` `kkamu_confident` `kkamu_deadpan`(3회) `kkamu_done` `kkamu_firm` `kkamu_innocent` `kkamu_point` `kkamu_shout` `kkamu_smug` `kkamu_stare` `kkamu_whisper` `kkamu_witness`

```
A black French Bulldog looks directly into the camera with a flat, unimpressed
expression. Subtle motion only: one slow blink, a slight ear twitch, faint
breathing. Static camera, no camera movement. Soft indoor daylight.
```

### TAKE-K2 — 고개 갸웃 / 시선 회피
- 레퍼런스: `ref_kkamu_34.jpg`
- 저장: `kkamu_tilt_take.mp4`
- 커버: 11컷 — `kkamu_casual` `kkamu_defensive` `kkamu_freeze` `kkamu_lookaway`(2회) `kkamu_panic` `kkamu_phone` `kkamu_sigh` `kkamu_stop` `kkamu_think` `kkamu_tilt`

```
A black French Bulldog slowly tilts its head to one side, then glances away
from the camera. Very slow and small movement. Static camera, no camera
movement. Soft indoor daylight.
```

### TAKE-K3 — 물그릇에 발 ★★시그니처 #1
- 레퍼런스: `ref_kkamu_bowl.jpg`
- 저장: `kkamu_bowl_take.mp4`
- 커버: 7컷 — `kkamu_bowl_calm`(3회) `kkamu_paw_bowl`(3회) `kkamu_slow_lift`

```
A black French Bulldog stands beside a white water bowl with one front paw
resting inside the water, looking straight at the camera with a calm,
completely unbothered expression. Motion: one slow blink and a faint water
ripple around the paw. The paw stays in the bowl. Static camera, no camera
movement. Bright indoor daylight.
```
> 물은 AI의 약점입니다. 물결이 이상하면 `faint water ripple` 을 `still water` 로 바꾸세요.
> **발이 물에 잠긴 상태가 유지되는지**가 이 컷의 전부입니다. 발이 빠지면 다시 뽑으세요.

### TAKE-K4 — 이불 속 / 숨기
- 레퍼런스: `ref_kkamu_blanket.jpg`
- 저장: `kkamu_blanket_take.mp4`
- 커버: 2컷 — `kkamu_blanket` `kkamu_hide` `kkamu_in_blanket`

```
A black French Bulldog is nestled inside a soft blanket, only its face
visible, eyes half closed. Motion: slow breathing, one slow blink, the
blanket shifts very slightly. Static camera. Warm dim indoor light.
```

### TAKE-K5 — 도망 (난이도 높음)
- 레퍼런스: `ref_kkamu_34.jpg`
- 저장: `kkamu_run_take.mp4`
- 커버: 4컷 — `kkamu_run`(2회) `kkamu_to_sofa` `kkamu_walkaway`

```
A black French Bulldog turns away from the camera and walks out of frame to
the side. Smooth steady motion, no running. Static camera. Indoor daylight.
```
> **뛰는 동작은 거의 실패합니다.** `walks`로 뽑고 컷을 0.8초로 짧게 쓰면 빠르게 보입니다.
> 그래도 다리가 뭉개지면 이 컷은 포기하고 **빈 방 컷 + 효과음(dash)** 으로 대체하세요.

### TAKE-K6 — 소품 다루는 까뮈
- 레퍼런스: `ref_kkamu_front.jpg`
- 저장: `kkamu_props_take.mp4`
- 커버: 2컷 — `kkamu_food_bag` `kkamu_treat`

```
A black French Bulldog stands next to a dog food bag on the floor, looking
down at it and then up at the camera. Small head movement only. Static
camera. Indoor daylight.
```

---

# 바위 (회색 아메리칸 불리)

### TAKE-B1 — 정면 대사용 ★최우선
- 레퍼런스: `ref_bawi_front.jpg`
- 저장: `bawi_front_take.mp4`
- 커버: 12컷 — `bawi_blink` `bawi_calm` `bawi_deadpan`(2회) `bawi_eyes` `bawi_freeze` `bawi_lookaway` `bawi_point` `bawi_proud` `bawi_serious` `bawi_tilt` `bawi_turn`

```
A grey American Bully looks directly into the camera with a calm, slightly
dopey expression. Subtle motion only: one slow blink, a small ear movement,
faint breathing. Static camera, no camera movement. Soft indoor daylight.
```

### TAKE-B2 — 앉아서 응시 / 기다림
- 레퍼런스: `ref_bawi_sit.jpg`
- 저장: `bawi_sit_take.mp4`
- 커버: 10컷 — `bawi_at_door` `bawi_door_wide` `bawi_ears` `bawi_same_pose` `bawi_sit_door` `bawi_sit_stare` `bawi_stare_long` `bawi_still_there` `bawi_watching`(2회)

```
A grey American Bully sits upright and stares patiently at the camera without
moving. Motion: only a slow blink and a subtle ear twitch. The body stays
completely still. Static camera. Soft indoor daylight.
```
> EP04의 3초 정적 컷(`bawi_stare_long`)이 여기서 나옵니다. **가만히 있을수록 좋은** 유일한 컷입니다.

### TAKE-B3 — 소파 뒤 ★★시그니처 #2
- 레퍼런스: `ref_bawi_sofa.jpg`
- 저장: `bawi_sofa_take.mp4`
- 커버: 8컷 — `bawi_behind_sofa`(3회) `bawi_pulled_out` `bawi_scolded` `sofa_back_butt`(3회)

```
Wide shot of a living room. A large grey American Bully is hiding behind a
sofa, but its rear end and back legs are clearly still visible sticking out.
Motion: the dog shifts its weight slightly, tail twitches once. Static camera,
wide framing, whole sofa visible. Indoor daylight.
```
> **와이드 프레이밍이 개그의 전부입니다.** 클로즈업으로 나오면 "안 숨겨진다"가 안 읽힙니다.
> 결과가 클로즈업이면 `wide shot`, `full room visible` 을 앞쪽으로 옮겨 다시 뽑으세요.

### TAKE-B4 — 자는 얼굴
- 레퍼런스: `ref_bawi_sleep.jpg`
- 저장: `bawi_sleep_take.mp4`
- 커버: 7컷 — `bawi_blanket` `bawi_burrow` `bawi_collapse` `bawi_despair` `bawi_sleep_face`(2회) `bawi_still`

```
Extreme close-up of a sleeping grey American Bully's face, eyes closed.
Motion: slow deep breathing, a tiny twitch of the lip. Nothing else moves.
Static camera. Dim warm morning light.
```

### TAKE-B5 — 벌떡 / 꼬리 / 반응
- 레퍼런스: `ref_bawi_front.jpg`
- 저장: `bawi_react_take.mp4`
- 커버: 6컷 — `bawi_follow` `bawi_jump` `bawi_look_back` `bawi_own_bowl` `bawi_smile` `bawi_tail`

```
A grey American Bully suddenly perks up, ears lifting and head rising with
interest. Motion is quick but small, body stays in place. Static camera.
Indoor daylight.
```

### TAKE-B6 — 바위도 물그릇에 발 (EP04 반전)
- 레퍼런스: `ref_bawi_front.jpg` + 물그릇이 나오게
- 저장: `bawi_paw_bowl.mp4`
- 커버: 1컷 — `bawi_paw_bowl`

```
A grey American Bully stands beside a white water bowl with one front paw
placed inside the water, looking at the camera with a calm expression.
Motion: one slow blink, still water. Static camera. Indoor daylight.
```

---

# 사물 · 배경 (text-to-video 가능)

레퍼런스 없이 텍스트로 뽑아도 됩니다. **또는 정지 이미지 1장으로 켄번스 처리하는 게 더 쌉니다**
(`clips/`에 png를 넣고 `@left` 등으로 지정 — `README.md` 참고).

| 클립 | 프롬프트 |
|---|---|
| `broken_pot` | `A broken ceramic flower pot on a living room floor, soil scattered. Static camera, no motion except settling dust. Indoor daylight.` |
| `wet_pawprints` | `Wet paw prints on a wooden floor leading away from the camera. Slow camera push in. Indoor daylight.` |
| `window_sunny` | `A bright sunny window seen from inside a living room, clear blue sky. Gentle light shift.` |
| `window_sunset` | `The same living room window at sunset, warm orange light. Slow light change.` |
| `leash_closeup` | `Close-up of a dog leash hanging by a front door. Very slight sway.` |
| `scale_paws` | `Close-up of a digital bathroom scale on the floor. Static.` |
| `empty_bag` | `An empty torn dog treat bag on the floor. Static.` |
| `phone_buzz` | `A smartphone on a bedside table vibrating with an alarm, screen glowing. Static camera, dim morning light.` |
| `wet_floor` | `A wet patch on a wooden floor next to a white water bowl. Static.` |
| `night_walk` | `POV walking a dog on a quiet night street, streetlights. Slow forward motion.` |
| `door_open` | `A front door slowly opening from inside a dark hallway. Static camera.` |
| `two_blankets` | `Two blanket lumps side by side on a bed, both slowly rising and falling with breathing. Static camera.` |

---

# 만드는 순서

크레딧이 하루 몇 개뿐이라면 이 순서대로 하세요. 위에서부터 효과가 큽니다.

1. **TAKE-K3** (물그릇 발) — 시그니처 #1, 7컷 커버
2. **TAKE-B3** (소파 뒤) — 시그니처 #2, 7컷 커버
3. **TAKE-K1** (까뮈 정면) — 9컷 커버
4. **TAKE-B1** (바위 정면) — 8컷 커버
5. **TAKE-B2** (바위 응시) — 8컷 커버
6. 나머지 순서대로

**상위 5개만 만들면 총 39컷**이 채워집니다. 전체 107컷 사용분의 3분의 1이 넘습니다.
