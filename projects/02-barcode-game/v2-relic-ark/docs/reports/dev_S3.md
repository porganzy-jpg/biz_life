# 개발 보고서 — 스프린트 3-C: 심해 1막 데이터 연결 + S2 잔여 막힘 해소 (2026-09-22)

담당: relic-dev / 태스크: S3-C
근거: `docs/CONCEPT_DEEP_SEA.md`, `DECISIONS.md` 2026-09-22 결정 6건, `docs/reports/review_sprint3.md` PM 결정 4·5, `docs/reports/scenario_S3.md`, `docs/WORLD_BIBLE_DEEP.md` §7, `docs/reports/dev_world_S2.md` §3-3

> 한 줄: **심해 16장이 오늘부터 실제로 뽑히고, 그 위기를 넘긴 사람이 실제로 변한다.** 그리고 발견 텍스트가 JS 상수에서 API로 내려왔다.

---

## 1. 만든 것과 경로

| # | 산출물 | 경로 | 내용 |
|---|---|---|---|
| 1 | **`/api/spots` 신설** | `server.py` (`load_spots()`, `SPOT_FILES`, `spot_gate()`, `@app.get("/api/spots")`) | `spots.json` + `spots_deep.json` 목록 병합. `discovery_text`·`pos`·`unlocked`·`gate` 포함. `spots_deep.json` 없어도 정상 |
| 2 | **`EVENT_FILES` 에 `events_deep.json`** | `engine/storyteller.py` | 38 → **54장**, 심해 16장 전부 추첨 대상 |
| 3 | **각인 4종 런타임 등재** | `server.py` `DEEP_IMPRINTS` | 「아낀 숨」·「금을 본 자」·「깊이의 자국」·「두드림을 들은 자」. 파일 우선 병합 |
| 4 | **심해 flag 별칭** | `server.py` `DEEP_FLAG_ALIAS` | `deep_*` 카드의 `dino_escaped` → `beast_left` 로 **읽을 때** 변환. 데이터 파일 무수정 |
| 5 | **`SPOT_POS` 교체** | `server.py` | `dev_world_S2.md` §3-3 제안표 그대로. 지형 밖 3곳 교정 |
| 6 | **소문 동기화 점검기 + 폴백 교정** | `server.py` `rumor_rule_audit()`, `/api/rumors` | 결함 4스팟 적발, 조건 미달 줄 대신 `spots.json` `clue_text` 로 물러남 |
| 7 | **`tribe` enum 4값 + 클라이언트 표기** | `data/events_schema.json`, `static/app.js` | `gauge`·`anchor`·`net`·`guest` → 눈금·닻·그물·손님 **무리** |
| 8 | **개발 훅 스위치** | `server.py` `DEV_MODE` | `?debug_force_event=` 는 `RELIC_DEV=1` 에서만. 기본 404 |
| 9 | 검증 스크린샷 3장 | `docs/reports/dev_S3_home.png`, `dev_S3_hall_imprint.png`, `dev_S3_deep_slip.png`, `dev_S3_world_regress.png` | — |

수정 파일은 전부 개발 소유: `server.py`, `engine/storyteller.py`, `static/app.js`, `data/events_schema.json`.
**`data/` 내용 파일(events·spots·rumors·imprints)과 `static/world.html`·`world3d.js` 는 한 줄도 고치지 않았다**(읽기만).

---

## 2. `/api/spots` — `/api/rumors` 와의 정본 분담 (요구된 근거)

두 API의 겹치는 필드는 `spot_id/name`, `pos`, `unlocked`, `progress`, `clue_text` 다. 다음과 같이 갈랐다.

| 필드 | 정본 | 근거 |
|---|---|---|
| `name`·`discovery_text`·`resource`·`danger_note`·`tribe_hint` | **`/api/spots`** | 스팟 그 자체의 정적 내용. 한 곳에서만 나가야 D7("데이터가 규칙을 든다")이 성립 |
| `pos`·`unlocked`·`progress`·`gate` | **값은 한 함수에서** (`SPOT_POS`, `spot_gate()`) | 두 API가 **같은 함수를 호출**하므로 값이 갈라질 수 없다. `/api/rumors` 의 `pos` 는 S2 지도 표식 호환 때문에 남겼다 |
| `clue_text`·`who`·`is_new` | **`/api/rumors`** | 여러 줄 중 **한 줄을 고르는 행위**라 시드가 필요하다(D6). 같은 선택을 두 곳에서 하면 시드가 갈라져 서로 다른 소문이 나온다. 그래서 `/api/spots` 는 `clue_text` 를 아예 내지 않는다 |

해금 게이트의 우선순위: **서버 `RUMOR_RULES` 가 정본**(DECISIONS 2026-09-20). 다만 표에 **없는** 스팟(= 앞으로 올 심해 6곳)만 파일의 `unlock` 을 임시 게이트로 받는다 — 그렇지 않으면 시나리오가 `spots_deep.json` 을 채워도 영영 열리지 않는다. 표에 들어오는 순간 표가 이긴다. 응답의 `gate.source` 가 `rules`/`file` 로 어느 쪽인지 밝힌다.

### 응답 예시 (curl)
```
$ curl -s "http://127.0.0.1:8002/api/spots" | head
{
 "id": "spot_flooded_train",
 "name": "물에 잠긴 전철",
 "discovery_text": "잊힌 역의 선로 끝, 물이 무릎까지 차오른 승강장에 열차 한 량이 …",
 "resource": {"key": "water", "ko": "맑은 물", "gain": {"water": 4}},
 "danger_note": "돌아오는 길은 물을 건너야 한다. …",
 "tribe_hint": "길손. 그들은 200년 동안 이 선로를 지나다녔지만 …",
 "pos": {"x": 62, "y": 30}, "has_pos": true,
 "unlocked": false, "rumor_seen": false,
 "progress": {"have": 0, "need": 3},
 "gate": {"categories": ["drink","medical"], "categories_ko": "음료·의약·화학", "need": 3, "source": "rules"},
 "source_file": "spots.json"
}

$ curl -s "http://127.0.0.1:8002/api/spots?uid=dev_s3_rumor"
  spot_flooded_train       unlocked=False progress={'have': 0, 'need': 3} gate=rules pos={'x': 62, 'y': 30}
  spot_goldfish_canal      unlocked=True  progress={'have': 2, 'need': 2} gate=rules pos={'x': 100, 'y': -18}
  spot_greenhouse_cafe     unlocked=False progress={'have': 0, 'need': 4} gate=rules pos={'x': 30, 'y': 92}
  spot_forest_train_door   unlocked=False progress={'have': 0, 'need': 2} gate=rules pos={'x': 178, 'y': 70}
  spot_rooftop_garden      unlocked=False progress={'have': 0, 'need': 2} gate=rules pos={'x': -30, 'y': 105}
  spot_lantern_river       unlocked=False progress={'have': 0, 'need': 2} gate=rules pos={'x': 148, 'y': 55}

$ curl -s "http://127.0.0.1:8002/api/rumors?uid=dev_s3_rumor"   (두 번째 행)
{"spot_id":"spot_goldfish_canal","name":"금붕어 수로",
 "clue_text":"교역 자리에서 말린 잎 한 줌 값에 소문 하나를 샀다. 다리 아래로 등불이 줄지어 흘러간다는 말이었고, 판 사람은 웃지 않았다.",
 "who":"wayfarer","unlocked":true,"is_new":false,"progress":{"have":2,"need":2},
 "categories":["tobacco"],"categories_ko":"담배·주류","pos":{"x":100,"y":-18}}
```
두 API의 `unlocked`·`progress`·`pos` 전 6행 일치를 자동 대조로 확인했다(§4 회귀 ⑦).

### `spots_deep.json` 이 없어도, 생겨도
파일이 없는 현재: 6행 정상 응답, 예외 0. 시나리오가 파일을 냈을 때의 동작은 **데이터 파일을 만들지 않고**(소유 영역 밖) 로더에 픽스처를 주입해 확인했다.
```
[spots] spots_deep.json 중복 id 건너뜀: spot_flooded_train      ← 먼저 읽은 파일이 이긴다
[spots] spots_deep.json 줄 건너뜀: id/name 없음 {'id': '', …}   ← 깨진 줄은 게임을 죽이지 않는다
병합 개수: 8
  spot_vent_garden   src=spots_deep.json  gate={'categories': ['medical'], 'need': 3, 'source': 'file'}
  spot_whale_fall    src=spots_deep.json  gate=None      ← unlock 없으면 게이트 미정(잠김)
spots_deep.json 없을 때(현재 실파일): 6 개 — 오류 없음
```

---

## 3. 심해 16장 — 병합과 추첨 시뮬레이션

```
$ python -c "sys.path.insert(0,'engine'); from storyteller import load_events, EVENT_FILES; …"
EVENT_FILES = ('events.json', 'events_tribes.json', 'events_outside.json', 'events_deep.json')
총 54 장 / deep_ 16    id 유일: True
```

추첨 시뮬레이션 (300 방주 × 14일 = 4,200회, `storyteller.pick_event` 실물):
```
심해 카드 1266회 (30.1%) — 풀 비중 16/54 = 29.6%  → 가중치가 심해를 밀지도 막지도 않는다
구역별: 무광층 835 · 해구 197 · 박광층 181 · 광층 53
  deep_glass_hairline     무광층 sev2   58회      deep_trench_call        해구  sev2   49회
  deep_air_thin           무광층 sev2   86회      deep_whale_fall         해구  sev0   61회
  deep_longneck_at_glass  박광층 sev2   83회      deep_ballast_loose      해구  sev2   87회
  deep_gatekeeper_pass    무광층 sev3   62회      deep_cut_moorings       무광층 sev2   62회
  deep_vent_found         무광층 sev0   70회      deep_dock_arms          무광층 sev2   84회
  deep_dome_signal        무광층 sev1   85회      deep_seam_mold          무광층 sev2  127회
  deep_drift_bundle       무광층 sev0   62회      deep_announcement_wakes 박광층 sev1   98회
  deep_school_writes      무광층 sev0  139회      deep_eight_arms_bring   광층  sev0   53회
한 번도 안 나온 심해 카드: 없음
```
**무광층·해구 카드가 실제로 뽑힌다**(무광층 835회, 해구 197회). 해구가 적은 것은 해구 카드가 3장뿐이기 때문이고, `deep_gatekeeper_pass`(sev3)가 62회로 낮은 것은 `weight_for()` 의 1~3일차 억제 규칙(×0.3)이 의도대로 걸린 결과다.

7일 시뮬(`python engine/storyteller.py`)에서도 심해 카드가 섞여 나온다:
```
Day 1: 여덟 팔이 물고 온 것 대항 성공  {'spot_clue': 'spot_kelp_ceiling', 'morale': 1}  → 사기 6, 부상 0
Day 2: 재고 감사관     피해  {'morale': -2, 'trade': -1}  → 사기 4, 부상 0
Day 3: 거울 신호      대항 성공  {'knowledge': 2, 'trade': 1}  → 사기 4, 부상 0
Day 4: 가라앉지 않는 사람 피해  {'injured': 1, 'morale': -3}  → 사기 1, 부상 1
Day 5: 담보 상자      피해  {'food': -3, 'morale': -2}  → 사기 0, 부상 1
Day 6: 기계 잔재 순찰   대항 성공  {'parts': 3}  → 사기 0, 부상 1
Day 7: 돌아갈 아이     피해  {'morale': -2}  → 사기 0, 부상 1
```

---

## 4. 각인 4종 — 등재·연결·검증

### 4-1. 무엇을 넣었나 (`WORLD_BIBLE_DEEP.md` §7 표 그대로)

| id | 이름 | 위기(crisis) | 붙는 카드 | 효과 | 대가 |
|---|---|---|---|---|---|
| `saved_breath` | **아낀 숨** | `air_out` 공기 부족 | `deep_air*`, flag `air_survived` | `air_cap +0.2` (예약) | 남의 사기를 덜 올린다 (`morale_heal_others −1`) |
| `crack_seen` | **금을 본 자** | `hull_breach` 유리 균열 | `deep_glass*`, flag `room_sealed` | `counter_bonus {부품 .3, 청사진 .2}` | 동선 손해 (`production_penalty +0.05`) |
| `depth_mark` | **깊이의 자국** | `descent` 해구 하강 | `deep_trench*`, `deep_ballast*`, flag `deep_descent` | `depth_cap +0.2` (예약) | 얕은 곳 사기 −1 (`morale_daily −1`) |
| `knock_heard` | **두드림을 들은 자** | `beast` 대형 생물 조우 | flag **`beast_left`** | (문구 대기) | (문구 대기) |

`air_cap`·`depth_cap` 은 기존 `light_cap` 과 같은 **예약 키**다(공기·깊이 게이지가 아직 없다). `_effect_keys` 의 예약 관례를 따랐다.

### 4-2. 「두드림을 들은 자」는 자리만 만들었다 (PM 결정 4)
외형·연출문·대가 문구가 `WORLD_BIBLE_DEEP` §7 표에 없다. **판정·연결·아침 연출 큐는 전부 동작**하고, 문구만 자리표시(`_pending_text: true`)다. 서버가 `pending` 플래그를 함께 내려보내고 **클라이언트가 자리표시 문구를 화면에 절대 띄우지 않는다**(각인 배지 툴팁은 이름만, 결과 화면의 `외형 — / 대가 —` 줄은 생략). 시나리오가 `data/imprints.json` 에 id `knock_heard` 정식 항목을 넣으면 파일 우선 병합이라 코드 자리표시가 자동으로 밀려난다 → `TASKS.md` 요청함 1줄.

### 4-3. 심해 flag 매핑 (데이터 파일 무수정)
`events_deep.json` 의 대형 생물 카드 2장은 임시로 육상 flag `dino_escaped` 를 쓰고 있다. 데이터는 시나리오 소유라 **읽을 때 옮긴다** — `ev["id"].startswith("deep_")` 일 때만 `DEEP_FLAG_ALIAS` 로 치환한다. 육상 공룡 카드(`dino_*`)는 영향이 없다.

```
심해 16장 → 각인 판정 (대항 성공 시, 서버 imprint_for 그대로)
  deep_glass_hairline        flag=[]                   →[]                     각인 = 금을 본 자      ← 신설
  deep_air_thin              flag=[]                   →[]                     각인 = 아낀 숨        ← 신설
  deep_longneck_at_glass     flag=['dino_escaped']     →['beast_left']         각인 = 두드림을 들은 자 ← 신설·매핑
  deep_gatekeeper_pass       flag=['dino_escaped']     →['beast_left']         각인 = 두드림을 들은 자 ← 신설·매핑
  deep_trench_call           flag=[]                   →[]                     각인 = 깊이의 자국     ← 신설
  deep_ballast_loose         flag=[]                   →[]                     각인 = 깊이의 자국     ← 신설
  deep_vent_found / deep_whale_fall / deep_eight_arms_bring → 물의 기억 (기존, 변화 없음)
  deep_seam_mold → 포자의 표식 / deep_cut_moorings·deep_dock_arms → 지킨 자 (기존, 변화 없음)
  deep_dome_signal, deep_drift_bundle, deep_school_writes, deep_announcement_wakes → 각인 없음

대조: flag 매핑을 끄면(옛 동작)
  deep_longneck_at_glass  → 발자국   (물속에 발자국이 남던 문제)
  deep_gatekeeper_pass    → 발자국
```
시나리오 보고서 §3-5가 "나머지 7장 각인 없음"이라고 적었던 것이 **4장으로 줄었다.** 남은 4장은 교섭·지식 계열이라 각인이 없는 것이 맞다(위기의 종류가 아니다).

### 4-4. 실제 플레이 경로 e2e (`RELIC_DEV=1`, 새 uid)
```
★ deep_air_thin / 숨이 얕다 · 태그 ['전력','부품'] · 심각도 2
  대항: none 실패 | 적용 {'injured': 1, 'morale': -2, 'power': -2}
  ▶ 각인 「아낀 숨」 → 바람 | 위기=공기 부족 (숨이 바닥난 원정에서 생환)
     연출문: 바람의 문장이 짧아졌다. 숨을 아껴 본 사람은 말도 아낀다.
★ deep_glass_hairline / 유리에 금 · 태그 ['부품','청사진']
  대항: card 성공 | ▶ 각인 「금을 본 자」 → 이슬 | 연출문: 이슬은 이제 창을 만지며 지나간다. 손끝으로 먼저 안다.
★ deep_trench_call / 해구에서 오는 소리 · 태그 ['야행','사기']
  대항: card 성공 | ▶ 각인 「깊이의 자국」 → 이슬 | 연출문: 이슬의 귀 뒤에 눌린 자국이 남았다. 목소리가 한 뼘 낮아졌다.
★ deep_longneck_at_glass / 창에 닿은 목 · 태그 ['조명','야행']
  대항: card 성공 | 적용(원본 flag 그대로) {'morale': 1, 'flag': 'dino_escaped'}
  ▶ 각인 「두드림을 들은 자」 → 다올 | 위기=대형 생물 조우 (생환) | 문구대기=True
★ deep_gatekeeper_pass  → 각인 없음   ← 이슬이 이미 각인 3개(상한). 규칙대로

최종: 이슬 **노래잡이**(역할 진화) 각인=[빈 자리, 금을 본 자, 깊이의 자국] 겪은위기=[loss, hull_breach, descent, raid]
      바람 기술자 각인=[빈 자리, 아낀 숨]
```
상한 3·1회성·`crises` 누적·역할 진화까지 기존 규칙 그대로 동작한다(S1 결함 교정 유지).

---

## 5. `rumors.json` `unlock` ↔ `RUMOR_RULES` 동기화 (정본 = 서버 표)

먼저 성격을 분리했다. 파일의 `unlock` 은 **해금 조건이 아니라 그 한 줄이 읽힐 조건**(사다리: 음료 2 → 5)이고, 해금 자체는 서버 표가 정한다. 그래서 값이 다른 것 자체는 결함이 아니다(단순 대조로는 20줄 중 17줄이 "불일치"로 나오지만 대부분 의미 없는 차이다).

**실제 결함은 하나다 — 스팟이 열리는 순간 읽을 수 있는 줄이 한 줄도 없는 경우.** 그때 예전 코드는 조건을 못 채운 줄로 되돌아가, 플레이어가 **아직 얻지 않은 지식이 적힌 소문**을 읽었다. 최악의 경로(표의 카테고리 하나만으로 문턱을 넘는 경우)를 전수 검사했다.

| 스팟 | 문제가 되는 해금 경로 | 서버 `RUMOR_RULES`(정본) | 파일 `rumors.json` 줄 조건 | 결과 |
|---|---|---|---|---|
| `spot_goldfish_canal` | tobacco×2 | tobacco×2 | drink×4, tobacco×3, tobacco×6 | 읽을 줄 0 → 폴백 |
| `spot_forest_train_door` | electronics×2 | electronics·food×2 | food×2, apparel×3, electronics×3 | 읽을 줄 0 → 폴백 |
| `spot_rooftop_garden` | apparel×2 | apparel·medical×2 | medical×3, electronics×4, apparel×4 | 읽을 줄 0 → 폴백 |
| `spot_rooftop_garden` | medical×2 | apparel·medical×2 | 〃 | 읽을 줄 0 → 폴백 |
| `spot_lantern_river` | book×2 | book·stationery×2 | stationery×4, book×5, electronics×6 | 읽을 줄 0 → 폴백 |
| `spot_lantern_river` | stationery×2 | book·stationery×2 | 〃 | 읽을 줄 0 → 폴백 |

문제 없는 스팟: `spot_flooded_train`(drink×2 줄이 문턱 이하), `spot_greenhouse_cafe`(food×4 정확히 일치).

**수치는 고치지 않았다**(밸런스는 PM·시나리오 몫). 대신 **코드 쪽 폴백을 교정**했다: 읽을 줄이 없으면 조건 미달 줄 대신 조건이 없는 `spots.json` 의 `clue_text` 로 물러난다. 검증:
```
담배 2회 후 — 해금: True 진행: {'have': 2, 'need': 2}
  → "교역가가 다른 통로에서 들은 소문: 다리 아래에 등불이 흘러간다더라. 서고 부족은…"  (spots.json, who=None)
담배 3회 후 — rumors.json 의 tobacco×3 줄이 읽히는가:
  → "교역 자리에서 말린 잎 한 줌 값에 소문 하나를 샀다. …"  who = wayfarer
```
사다리가 제대로 올라간다. 시나리오에 수치 확인 요청 1줄을 `TASKS.md` 요청함에 남겼다.

점검기는 `server.rumor_rule_audit()` 로 상시 호출 가능하다(게임 동작에 영향 없음).

---

## 6. `SPOT_POS` 교체

옛 임시값은 6곳 중 3곳이 `world.html` 지형(400×250m) 밖이거나 강 한가운데였다(`-170`, `-120`, `-90`).

| spot_id | 옛 (x, y) | 새 (x, z) = `dev_world_S2.md` §3-3 | 문턱에서 |
|---|---|---|---|
| `spot_flooded_train` | (−120, 70) | **(62, 30)** | 69 m |
| `spot_goldfish_canal` | (60, 95) | **(100, −18)** | 102 m |
| `spot_greenhouse_cafe` | (130, 20) | **(30, 92)** | 97 m |
| `spot_rooftop_garden` | (−60, −90) | **(−30, 105)** | 109 m |
| `spot_lantern_river` | (−170, 40) | **(148, 55)** | 158 m |
| `spot_forest_train_door` | (170, −60) | **(178, 70)** | 191 m |

`pos{x, y}` 의 `y` 에 월드 Z를 넣는 S2 규약을 유지했다(클라이언트 무변경).

---

## 7. 개발 훅 스위치 (`RELIC_DEV`)

```
$ python server.py                 # 배포 기본
$ curl ".../api/event/today?uid=dev_s3_sw&debug_force_event=deep_air_thin"
{"detail":"없는 질의입니다"}
HTTP 404
$ curl ".../api/event/today?uid=dev_s3_sw"     # 같은 엔드포인트, 정상 동작
{"event":{"id":"relic_cache","name":"숨겨진 유물 창고", …

$ RELIC_DEV=1 python server.py     # 개발·검수
→ ?debug_force_event= 동작 (위 §4-4 e2e 가 이 모드에서 나온 로그)
```
존재를 알리지 않기 위해 403이 아니라 404를 쓴다. 02_DEV §4-4 "배포 전 제거 목록"의 이 항목은 닫힌 것으로 본다.

---

## 8. 검증 — 구문·기동·회귀 7항목

### 8-1. 구문 검사
```
$ python -m py_compile server.py engine/storyteller.py engine/relic_generator.py
PY COMPILE OK
$ python -c "json.load(...)"   data/events_schema.json / events_deep.json / spots.json → json ok ×3
$ node --check static/app.js static/life.js static/rooms.js → JS OK ×3
```

### 8-2. 기동
```
$ RELIC_DEV=1 python server.py
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8002
UP after 1s   (GET /api/stats 200)
```

### 8-3. 회귀 7항목 (새 uid `dev_s3_new`, 전부 HTTP 경유)
```
── ① 새 방주 생성 /api/ark
  DAY 1 주민 3 방 ['pantry'] 자원 food 4 /사기 5
  각인 카탈로그 12 종: 포자의 표식, 빈 위장, 지킨 자, 햇빛의 기억, 빈 자리, 발자국, 갚은 자,
                      물의 기억, 아낀 숨, 금을 본 자, 깊이의 자국, 두드림을 들은 자
── ② 스캔  (3회, 카테고리·희귀도·획득 정상)
  8801056030162 → 따뜻한 불타는 투명수 [drink/common]   획득 {'water':3,'chem':1,'med':1}
  8801062636273 → 말없는 겨울 씨앗 주머니 [food/uncommon] 획득 {'food':4,'morale':1,'cloth':1}
  8801094081010 → 말없는 불타는 투명수 [drink/uncommon]  획득 {'water':4,'chem':1,'food':1}
── ③ 건설
  well 건설 OK → 방 ['pantry','well']  자원 차감 반영
── ④ 사건 today → resolve
  카드: tribe_white_glass_visit 유리 너머의 문진 · 태그 ['치료','해독']
  결과 countered=False how=none 적용 {'injured':1,'morale':-1}
  나선 사람: ['도담(정찰병)'] 신뢰 -5
  각인: [('도담','포자의 표식'), ('도담','빈 자리')]
── ⑤ 주민
  온새 요리사 부상=True 각인=[] / 새벽 기술자 부상=False / 도담 정찰병 각인=['spore_mark','empty_seat']
── ⑥ 도감
  [('food','1/4'), ('drink','1/4')]
── ⑦ 소문 /api/rumors ↔ /api/spots 대조 — 6행 전부 unlocked·progress·pos 일치=True
```

### 8-4. 회귀 — 구버전 방주 마이그레이션 (`residents_list`·`seen_events` 등이 아예 없는 상태를 DB에 직접 주입)
```
구버전 방주 주입: [created, last_tick, resources, rooms, residents, injured, hand, codex,
                  recent_events, today_event, hardcore, blueprint_progress]   ← 신필드 0
마이그레이션 후 DAY 4 | 주민 3 명
   마루 요리사 imprints=[] crises=[] trust키=0
   소리 기술자 …  / 새벽 정찰병 …
보강된 필드: {'seen_events': ['raid_scavs'], 'rumors_seen': [], 'morning_pending': [], 'greeted': True}
오프라인 생산 정산: {'food': 2}    소문 API 6행    스팟 API 6행
```

### 8-5. 브라우저 (Playwright MCP, 실 GPU Chromium)
| 화면 | 결과 | 스크린샷 |
|---|---|---|
| `/` 홈(폰 폭 760) | 정상. 콘솔 에러 0 (favicon 404만, 기존) | `dev_S3_home.png` |
| 역 홀 — 주민·각인·소문 | 「刻 두드림을 들은 자」 배지 표시, **툴팁에 자리표시 문구 노출 없음**. 소문 6행 중 해금 1행이 `spots.json` 문장으로 뜸(폴백 교정 확인) | `dev_S3_hall_imprint.png` |
| 심해 카드 쪽지 + 각인 결과 | `deep_seam_mold`「이음매의 검은 것」이 실제로 뽑히고 각인 2건이 화면에 뜸 | `dev_S3_deep_slip.png` |
| `world.html` (남의 파일, 읽기만) | 1280×720 WebGL 정상, 60fps, 콘솔 에러 0. `/api/spots` 6행 수신 확인 | `dev_S3_world_regress.png` |

`tribe` 표기 검증 (브라우저에서 `window.ARK.tribeLabel`):
```
gauge → 눈금 무리 / anchor → 닻 무리 / net → 그물 무리 / guest → 손님 무리     ← 1막
wayfarer → 길손 부족 / shelf → 진열대 부족 / … / tower → 탑 부족              ← 3막
```

---

## 9. 적용한 교본 원칙

| 원칙 | 어디에 |
|---|---|
| **D7**(데이터가 규칙을 든다) | `/api/spots` 신설의 유일한 이유. 발견 텍스트가 `world3d.js` 상수에서 API로 내려왔다. `SPOT_FILES`·`EVENT_FILES` 를 같은 패턴으로 맞춰 시나리오가 **파일만 내면** 게임에 닿게 했다. `tribe` enum도 스키마부터 고쳤다 |
| **D6**(결정성) | `clue_text` 고르기를 `/api/spots` 가 하지 않는 이유가 이것이다 — 같은 선택을 두 곳에서 하면 시드가 갈라진다. 추첨 시뮬·e2e 전부 `uid\|day` 시드로 재현 |
| **D4**(실패는 서사, 막힘은 버그) | 소문 폴백이 아직 얻지 않은 지식을 읽히던 것은 **버그**로 보고 고쳤다. 밸런스 수치는 서사라 손대지 않고 요청으로 넘겼다. 회귀 7항목 + 마이그레이션 로그 첨부 |
| **D1**(규칙은 적게, 조합은 많게) | 새 시스템 0. 심해 1막을 기존 사건×각인×스팟의 곱으로 표현했다. 「두드림을 들은 자」도 새 규칙이 아니라 flag 별칭 한 줄 |
| **D2**(모든 숫자는 화면의 무엇으로) | 각인 4종 전부 외형·대가 문구를 함께 넣었다. 문구가 없는 「두드림」은 **화면에 안 나오게 막았다** — 숫자만 있는 각인을 띄우지 않기 위해. `air_cap`·`depth_cap` 은 게이지가 생길 때까지 예약 |
| **D5**(첫 3분 루프) | 탭 수 변화 0. `/api/spots` 는 기존 화면이 이미 부르던 URL이고 새 화면·새 버튼을 만들지 않았다 |
| **D8**(성능 예산) | `/api/spots` 는 파일 2개 병합 + 스캔 집계 1쿼리. 폰 폭 760px 스크린샷으로 레이아웃 확인 |
| **P1**(보편적 원형) | 심해 16장이 '뒤지기·둥지·종말 공상' 원형에 그대로 붙는다. 새 원형을 만들지 않았다 |
| **P3**(감정의 가속도) | 각인 4종이 전부 **위기 직후의 변화**다. 특히 「금을 본 자」(방을 닫고 산 사람)는 CONCEPT §3의 "죽는 것은 사람이 아니라 공간"을 시스템으로 받는다 |
| **S1**(보여주고 말하지 않는다) | 자리표시 문구를 화면에 띄우지 않는 결정의 근거. "(문구 대기 — 시나리오)"가 플레이어에게 보이면 세계가 깨진다 |
| **W1**(문서가 기억) | 코드 주석마다 근거 문서·결정 날짜를 적었다(`DECISIONS 2026-09-22`, `dev_world_S2 §3-3`). 다음 스프린트 에이전트가 이유를 재발명하지 않게 |
| **W3**(소유권·스키마로 병렬화) | 데이터 파일 0줄 수정. 각인·flag·스팟 전부 **런타임 병합/별칭**으로 처리해 시나리오 작업과 충돌하지 않는다 |
| **07 §3-2**(AI 코드를 이해 못한 채 쌓기) | 새 함수는 전부 20줄 이하 + 한국어 근거 주석. `rumor_rule_audit()` 처럼 **스스로를 점검하는 코드**를 남겼다 |
| **07 §6**(AI 공개표) | 이번 산출물은 코드뿐 — 공개 대상 아님. 새 행 불필요 |

### 원칙과 다르게 한 곳 (이유)
1. **D2 위반 의심 — `air_cap`·`depth_cap` 이 화면의 무엇으로도 보이지 않는다.** 공기·깊이 게이지가 아직 없기 때문이다. 기존 `light_cap` 과 같은 '예약 키' 관례를 따랐고, 게이지가 생기면 그날 연결된다. **지금 이 두 각인의 화면 효과는 외형·대가 문구뿐이며 그것은 실제로 보인다.**
2. **D7 "데이터가 규칙을 든다"에서 살짝 벗어난 곳 — 각인 4종이 JSON이 아니라 코드에 있다.** `data/imprints.json` 이 시나리오 소유라 직접 못 고치기 때문이며, **파일 우선 병합**이라 시나리오가 파일에 넣는 순간 코드가 물러난다(스프린트 2의 `roles_evolved`·`imprint_lines` 와 같은 방식). 임시 상태다.
3. **정본은 서버 표라는 결정에 예외 하나** — 표에 **없는** 스팟만 파일 `unlock` 을 임시 게이트로 받는다. 예외가 없으면 시나리오가 `spots_deep.json` 을 채워도 심해 스팟이 영영 안 열린다. 표에 들어오면 표가 이기므로 결정을 뒤집지 않는다.

---

## 10. 02_DEV §5 자가 검수 5문항

**1. 새 숫자가 화면의 무엇으로 보이는가?**
- 각인 4종: 외형 문구(창을 만지는 손, 짧아진 문장, 눌린 귀)와 대가 문구가 결과 화면·주민 배지·다음 날 아침 연출에 뜬다 — 스크린샷 `dev_S3_deep_slip.png`·`dev_S3_hall_imprint.png`로 확인.
- `/api/spots` 의 `progress`: 소문 패널의 `전자·식품 2/2` 로 이미 보인다(숫자만 있는 게 아니라 "무엇을 더 읽어야 들리는지"로).
- 예외는 `air_cap`·`depth_cap` 둘뿐이고 §9 이탈 1번에 사유를 적었다.

**2. 첫 3분 루프의 탭 수가 늘었나?**
0. 새 화면·새 버튼을 만들지 않았다. `/api/spots` 는 `world3d.js` 가 **이미 폴백 URL로 부르고 있던** 주소라 클라이언트 변경 없이 연결됐다. 사건 카드가 38→54장으로 늘었지만 하루 1장은 그대로다.

**3. 같은 입력이면 같은 결과인가(시드)?**
그렇다. 사건 추첨 `uid|day`, 소문 문장 `uid|spot|rumor`, 각인 참여자 `uid|day|who_imprint` 전부 유지. `/api/spots` 가 `clue_text` 를 내지 않는 것이 바로 이 원칙 때문이다(두 곳에서 고르면 시드가 갈라진다). 추첨 시뮬은 `sim{n}|{day}` 고정 시드라 그대로 재현된다.

**4. 폰 가로 720px에서 손가락으로 조작 가능한가?**
760×900 뷰포트로 홈·역 홀·쪽지 전부 확인했다(스크린샷 3장). 새 터치 요소를 추가하지 않았으므로 44px 규약에 변화가 없다. `world.html`(가로 고정)은 1280×720에서 확인.

**5. 회귀 7항목 로그가 있는가?**
있다 — §8-3(스캔·건설·사건·주민·도감·소문), §8-4(구버전 마이그레이션), §3(7일 시뮬·54장 병합). 전부 HTTP 경유 실서버 로그다.

---

## 11. 미완 · 리스크

| # | 내용 | 영향 | 제안 |
|---|---|---|---|
| R1 | **「두드림을 들은 자」 문구 없음** | 심해 대형 생물 각인이 화면에서 침묵한다(배지 이름만 뜸) | 시나리오 1행 — `TASKS.md` 요청함 (필수) |
| R2 | `spots_deep.json` 미존재 | 심해 스팟 6곳이 게임에 없다. `deep_vent_found` 등 3장의 `spot_clue` 가 가리킬 대상이 없다(서버는 flag만 쓰므로 죽지 않음) | 로더 준비 완료. 시나리오가 파일을 내면 개발이 `SPOT_POS` 심해 좌표 + `RUMOR_RULES` 6줄 추가 |
| R3 | 심해 스팟 좌표계 미정 | `SPOT_POS` 는 **육상 지형(400×250m)** 기준이다. 심해는 세로축(깊이)이 지도라 좌표계 자체가 다르다 | 배경 S3-B 돔 단면이 나온 뒤 `depth` 축을 포함한 좌표 규약을 정할 것. 지금 넣으면 두 번 고친다 |
| R4 | `air_cap`·`depth_cap` 예약 키 | 「아낀 숨」·「깊이의 자국」의 능력이 아직 무효 | 공기 게이지(시나리오 요청 8번, 줄어드는 띠)와 함께 붙인다 |
| R5 | `events_deep.json` 의 `tribe` 필드 공백 | enum·표기는 붙였으나 화면에 무리 이름이 안 뜬다 | 시나리오가 값만 채우면 즉시 반영 — 요청함 |
| R6 | 소문 첫 줄이 시나리오 문장이 아님(4스팟) | 첫 소문이 `spots.json` 의 일반 문장으로 뜬다 | 수치 확인 요청 — §5 표 |
| R7 | 심해 카드 30%가 **육상 카드와 섞여** 나온다 | 1막이 심해인데 육상 공룡·부족 카드가 같은 날 나올 수 있다 | **막 구분이 없다.** 1막/2막/3막 플래그로 사건 풀을 나누는 작업이 필요하다 — 다음 스프린트 PM 결정 사항. 지금 임의로 나누면 육상 38장이 게임에서 사라진다 |
| R8 | `/api/spots?uid=` 가 없는 방주를 만든다 | 임의 uid 조회 시 빈 방주 생성·`ark_created` 로그 | 기존 `/api/rumors` 와 같은 동작이라 그대로 뒀다. 지표는 `is_test_uid` 로 이미 걸러진다 |

---

## 12. 남에게 요청할 것 (`docs/TASKS.md` §요청함에 5줄 등재 완료)
1. **시나리오(필수)** — 「두드림을 들은 자」 각인 표 1행(`WORLD_BIBLE_DEEP` §7)
2. **시나리오** — `rumors.json` 줄 조건 수치 확인(4스팟, §5 표)
3. **시나리오** — `spots_deep.json` 신설(필드·`unlock` 규약 안내 포함)
4. **시나리오** — `events_deep.json` 의 `tribe` 값 채우기
5. **PM** — 서버 기동을 `RELIC_DEV=1 python server.py` 로(개발·검수 시). `?debug_force_event=` 제거 항목 종결 처리

그리고 **R7(막 구분)** 은 요청이 아니라 결정이 필요한 사항이라 §11에만 적었다.

---

## 13. 이 산출물이 게임을 더 재미있게 했는가 (TEAM 마지막 질문에 자답)
세 가지가 실제로 달라졌다.
1. **1막이 존재하게 됐다.** 어제까지 `events_deep.json` 16장은 디스크에만 있었다. 지금은 300방주 시뮬에서 30.1% 확률로 뽑히고, 방금 브라우저에서 「이음매의 검은 것」이 실제로 도착했다. **보지 않은 산출물은 없는 것이다(W2)** — 이제 있다.
2. **심해의 위기가 사람을 바꾼다.** 각인 4종이 붙기 전에는 유리에 금이 가도, 숨이 얕아도, 해구에 내려가도 주민은 어제와 같은 사람이었다. 계단식 성장은 이 게임의 척추인데 1막에서 부러져 있었다. 특히 「금을 본 자」— 방 하나를 닫고 살아남은 사람이 그 뒤로 **창을 만지며 지나간다**는 것은 CONCEPT §3의 "죽는 것은 사람이 아니라 공간"을 설명 없이 보여준다.
3. **발견 텍스트가 코드에서 나왔다.** 이건 재미가 아니라 **재미를 만들 수 있는 조건**이다. 시나리오가 스팟 문장을 고칠 때마다 개발을 기다려야 했던 것이 오늘 끝났다.

가장 아쉬운 것은 R7이다. 1막이 심해인데 같은 날 육상 공룡 카드가 올 수 있다 — 심해 16장을 연결한 이 작업이 그 모순을 **보이게** 만들었다. 다음 스프린트의 첫 안건이 되어야 한다.
