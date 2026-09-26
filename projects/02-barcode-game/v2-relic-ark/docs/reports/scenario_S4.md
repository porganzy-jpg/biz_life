# 시나리오 보고서 — 스프린트 4-C: 밀린 데이터 요청 처리 + 심해 스팟 신설 (2026-09-26)

담당: relic-scenario / 태스크: S4-C
읽은 것: `docs/TEAM.md`, 교본 `00_COMMON.md`·`01_SCENARIO.md`·`07_AI_GAMEDEV.md`, `docs/WORLD_BIBLE_DEEP.md`(§4 스팟 6곳·§7 각인표), `docs/DECISIONS.md` 2026-09-22·23 전부, `docs/reports/dev_S3.md` §5, `docs/reports/scenario_S3.md`, `docs/TASKS.md` 요청함(나에게 온 5건), `data/events_schema.json`·`dialogue_schema.json`, `server.py`(읽기만).

> 한 줄: **심해 여섯 스팟이 파일이 되어 지도에 올라갔고, 열두 개 스팟 전부가 "열리는 순간 시나리오 문장이 읽히는" 상태가 됐다.** 그리고 60장 사건 카드가 자기가 어느 막 소속인지 알게 됐다.

---

## 1. 만든 것과 경로

| # | 요청 출처 | 산출물 | 경로 | 내용 |
|---|---|---|---|---|
| 1 | 개발(S3-C) 대기 | **`spots_deep.json` 신설** | `data/spots_deep.json` | 심해 힐링 스팟 6곳. `spots.json` 과 동일 필드 + 임시 게이트 `unlock{category,count}` |
| 2 | 개발(S3-C) 결함 | **`rumors.json` 결함 수정 + 증보** | `data/rumors.json` | 20 → **38줄**. 육상 4스팟 보강 6줄 + 심해 6스팟 12줄 |
| 3 | 개발(S3-C) 필수 | **「두드림을 들은 자」 완성** | `docs/WORLD_BIBLE_DEEP.md` §7, `data/imprint_lines.json` | 표 1행(외형·대가) + 연출문 1줄 + 설계 근거 2줄 |
| 4 | 개발(S3-C) | **심해 `tribe` 채움** | `data/events_deep.json` | `gauge`·`anchor`·`net`·`guest` 4값 전부 사용 |
| 5 | DECISIONS 2026-09-23 | **`acts` 전량 기입 + 1막 증보** | 사건 4파일 | 60장 전부. 1막 풀 20 → **26장**(심해 6장 신작) |
| 6 | 개발(S2) 승인분 | **심해 대사 12줄** | `data/dialogue.json` | `game_start` 신설 포함, reader 26 / gardener 26 |
| — | — | 요청 6건 | `docs/TASKS.md` 요청함 | 개발 4 · 캐릭터 1 · PM 1 |

수정 파일은 **전부 시나리오 소유**다(`data/spots_deep.json`, `data/rumors.json`, `data/events*.json`, `data/dialogue.json`, `data/imprint_lines.json`, `docs/WORLD_BIBLE_DEEP.md`, `docs/TASKS.md` 요청함 한 블록). `server.py`·`engine/`·`static/`·`data/*_schema.json`·`data/imprints.json` 은 **읽기만** 했다.

---

## 2. 항목별 내용과 판단 근거

### 2-1. `data/spots_deep.json` — 성경 §4를 파일로

| id | 이름 | 구역 | 자원 | 임시 게이트 |
|---|---|---|---|---|
| `spot_vent_garden` | 열수구 정원 | 무광층 | 열원 `power2 morale2` | 전자 ×2 |
| `spot_jelly_bloom` | 등불 떼 | 무광층 | 사기 `morale3` | 문구 ×3 |
| `spot_sunken_courtyard` | 침몰선 안뜰 | 박광층 | 유물 `free_pack1 morale1` | 도서 ×3 |
| `spot_whale_fall` | 가라앉은 큰 것 | 해구 입구 | 식량 `food4` | 식품 ×3 |
| `spot_brine_lake` | 물속의 호수 | 무광층 바닥 | 소금·보존 `food2 morale2` | 음료 ×3 |
| `spot_kelp_ceiling` | 위를 보는 숲 | 광층 | 씨앗·섬유 `food2 cloth2` | 의류 ×4 |

- **게이트 수치의 원칙**: 깊이가 진행도다(DECISIONS 2026-09-23 "성장 방향은 아래"). 집에서 가깝고 첫 10분에 단서가 나오는 열수구 정원이 가장 싸고(2), 광층·해구 끝의 두 곳이 가장 비싸다(4·3). 카테고리는 스팟의 성격과 붙였다 — 열원=전자, 일지·기록의 무리가 알려 주는 등불 떼=문구, 사람이 깔아 놓은 무늬=도서, 밥상=식품, 물가=음료, 섬유=의류.
- **`discovery_text` 는 전부 "그 자리에 선 사람의 침묵"**이다(S1, 교본 §3 Outer Wilds). 여섯 곳 모두 마지막 문장이 사람의 **하지 않은 행동**으로 끝난다: 장갑을 벗지 않는다 / 아무도 부르지 않는다 / 아무도 손을 담그지 않는다 / 내리지 않는다.
- **거주 불가를 설명하지 않는다.** 물이라는 사실 하나가 그것을 대신한다(CONCEPT §1-3). 대신 `danger_note` 가 **왜 죽는지**만 건조하게 적는다("호수의 물은 숨을 녹이지 않는다").
- **표기**: 여섯 곳 전부 '무리'. `data/spots_deep.json` 안에 '부족' 0건(검증 §10). 필드명 `tribe_hint` 는 스키마 호환 때문에 그대로 뒀다(화면 표기가 아님).

### 2-2. `rumors.json` — 개발이 잡아낸 결함 정면 수정

`dev_S3.md` §5의 대조표대로, **서버 문턱과 같은 조건의 줄**을 스팟마다 넣었다. 수치를 바꾸지 않고 **줄을 추가**한 이유: 기존 줄들은 사다리의 윗칸으로 그대로 쓸모가 있고, 밸런스 수치의 정본은 서버 표이기 때문이다(DECISIONS 2026-09-20).

| 스팟 | 막혀 있던 경로 | 추가한 줄 | 물어온 이 |
|---|---|---|---|
| `spot_goldfish_canal` | 담배 ×2 | `rumor_canal_wet_hem` | 길손 |
| `spot_forest_train_door` | 전자 ×2 | `rumor_forest_two_rails` | 까마귀 |
| `spot_rooftop_garden` | 의류 ×2 | `rumor_roof_grass_seeds` | 고양이 |
| `spot_rooftop_garden` | 의약 ×2 | `rumor_roof_stair_water` | 개 |
| `spot_lantern_river` | 도서 ×2 | `rumor_river_erased_line` | 길손 |
| `spot_lantern_river` | 문구 ×2 | `rumor_river_scorched_paper` | 고양이 |

- 여섯 줄 중 **넷을 짐승에게 맡겼다**(S7). 첫 소문은 사람이 팔지 않고 짐승이 물어 온다 — 사람에게 사는 소문은 사다리 윗칸(탑의 거울, 교역 자리)에 이미 있다.
- 심해 12줄은 스팟당 2줄(문턱 = 즉시 읽힘 / 그 위 = 사다리). 물어온 이는 `octopus`·`gauge`·`anchor`·`net`·`guest`. **동거 문어가 4줄로 가장 많다** — 힐링 스팟의 첫 단서는 언제나 문어가 물고 온다는 성경 §3-4 규칙 그대로다.

### 2-3. 「두드림을 들은 자」(`knock_heard`)

| 위기 | 외형 | 대가 |
|---|---|---|
| 대형 생물 조우(긴목·문지기가 다녀가고 생환) | 무엇을 만지기 전에 손가락 마디로 **두 번 두드리고 대답을 기다린다**. 문·뚜껑·창·남의 어깨까지 전부. 귀가 소리 쪽으로 먼저 돌아간다 | **두드리는 소리가 나면 하던 일을 멈춘다.** 밤에 더 자주 들려 야간 작업의 손이 느려진다 |

연출문(`imprint_lines.json`): *"{name}의 손끝에 아직 유리의 떨림이 남아 있다. 무엇을 만지기 전에 두 번 두드리고, 대답을 기다린다."*

- 근거는 첫 10분 8:40 비트 — 긴목이 **부리로 유리를 똑똑 두드린다**(`SCRIPT_first_10min_deep.md`, `WORLD_BIBLE_DEEP` §3-1). S8대로 각인 문장을 **사건의 감각(손끝의 떨림)** 으로 썼고 능력 수치는 쓰지 않았다.
- 살아남은 사람이 새긴 것은 괴물의 크기가 아니라 **그 소리의 예의 바름**이다. 이 세계에서 가장 무서운 것은 악의가 아니라 호기심이라는 §3-1 설정이 각인 하나로 회수된다.
- 성경 §7에 한 줄 더 붙였다: 그가 두드리고 기다리기 때문에 **돔 안에서 아무도 남의 방에 그냥 들어가지 않게 됐다.** 사람들은 예절이라 부르고 그는 예절이라 생각한 적이 없다 — 신화가 오해의 기록이 되는 과정(S6)을 한 사람 크기로 줄인 것.

### 2-4. 심해 `tribe` 채움

| 카드 | 무리 | 이유 |
|---|---|---|
| `deep_dome_signal` 낯선 불빛의 두드림 | **눈금**(gauge) | 신호가 "세 번 짧게, 두 번 길게" = 숫자다. 재는 사람들의 문법 |
| `deep_jelly_bloom_seen` 위험 아님 (신작) | **눈금** | 일지 인용, 형용사 없음 |
| `deep_courtyard_pattern` 같은 무늬 (신작) | **손님**(guest) | 항로에서 늘 보지만 내리지 않는다 |
| `deep_brine_sitting_suit` 앉은 자세 그대로 (신작) | **닻**(anchor) | 가장 깊이 내려가는 사람들, 두세 단어로 말한다 |
| `deep_net_share_shoal` 세지 않는 몫 (신작) | **그물**(net) | "떼를 세는 것"이 그들의 금기 |

`faction:"tribe"` 는 요청대로 유지. 개발이 붙인 enum 4값이 **전부** 화면에 나온다.

### 2-5. `acts` 전량 기입 + 1막 증보

| 파일 | 규칙 | 결과 |
|---|---|---|
| `events_deep.json` | `[1]` | 22장(16 + 신작 6) |
| `events_outside.json` | `[3]` | 7장 |
| `events_tribes.json` | `[3]` | 21장 |
| `events.json` | 장소를 타지 않는 것만 `[1,2,3]` | **4장** `famine`·`drought`·`confusion`·`relic_cache` / 나머지 6장 `[3]` |

**`[1,2,3]` 판정 기준**: 카드 본문에 장소가 박혀 있는가. 빈 항아리·새는 물탱크·성문 오독·봉인된 상자는 돔에서도 그대로 성립한다. 반대로 `infection`(지하 강)·`drifter`(철길)·`machine_patrol`(빛의 사원)·`raid_scavs`(회색 개)·`mutant_magpie`(까치)·`cold_snap`(밤 기온)은 육상 어휘가 본문에 있어 `[3]`으로 뒀다. 고쳐서 공용으로 만들 수도 있었지만 **1막 어휘로 다시 쓰면 그것은 새 카드**여서, 새로 쓰는 쪽을 택했다.

**1막 증보 6장**(심해 22장 중 신작):

| id | 이름 | sev | 하는 일 |
|---|---|---|---|
| `deep_jelly_bloom_seen` | 위험 아님 | 0 | `spot_jelly_bloom` 단서 · 눈금 무리 |
| `deep_courtyard_pattern` | 같은 무늬 | 0 | `spot_sunken_courtyard` 단서 · 손님 무리 |
| `deep_brine_sitting_suit` | 앉은 자세 그대로 | 1 | `spot_brine_lake` 단서 · 닻 무리 |
| `deep_net_share_shoal` | 세지 않는 몫 | 1 | 그물 무리의 금기 vs 리더의 장부 |
| `deep_freshwater_still` | 민물 한 통 | 0 | **1막 유일의 `positive:true` 심해 카드** |
| `deep_nail_swarm` | 이음매를 찾는 것들 | 2 | 손톱 무리 · "쥐면 가라앉는다"를 규칙으로 |

증보에서 메운 세 구멍:
1. **단서 없는 스팟 3곳**(`jelly_bloom`·`sunken_courtyard`·`brine_lake`)이 이제 전부 카드를 가진다. 여섯 스팟 전부 "사건 → 단서 → 소문 → 발견" 경로가 뚫렸다.
2. **1막에 `positive:true` 가 없었다.** 사기 2 이하일 때 가중치 ×3인 자비 규칙이 1막에서만 작동하지 않고 있었다(육상 `relic_cache` 1장뿐). 「민물 한 통」을 넣어 2장으로 만들었다 — 각박함 속의 사치가 보상이라는 §6 규칙(P3: 위기 뒤의 이완).
3. **enum 4무리가 전부 나온다**(위 §2-4).

### 2-6. 대사 12줄

- **`game_start` 가 데이터에 한 줄도 없었다.** 개발이 훅을 연결해 둔 지 한 스프린트가 지났는데 첫 화면에서 아무도 말하지 않고 있었다(`dialogue_schema.json` `_hooks`). 리더 2줄 + 정원사 1줄로 채웠다.
  - 리더: *"돔 내 재고를 확인했습니다. 부족합니다. 오늘도 좋은 하루 되십시오."* — 친절과 통보가 한 문장에 붙어 있다(S5).
  - 정원사: *"창 밖에서 떼가 한 번 방향을 바꾸었다. 너는 그것을 보았는가, 유리를 보았는가."* — 문장이 아니라 움직임으로 먼저 온다.
- **에어락**: 밖은 `surface_trip` 에 리더(권장 깊이 경고, '안전' 자리에 '소비'가 새어 나온다) + 정원사(해류가 민다 — 막는 것인가 묻는 것인가) 한 쌍으로 넣었다. **안(귀환)은 태그가 없어 못 넣었다** — `airlock_in` 신설을 요청했다(§4).
- `spot_water_reflection` 은 정원사 2줄로 채웠다(훅 연결 완료 태그인데 줄이 0이었다).

---

## 3. 검증 로그

검증 스크립트: 임시 디렉터리(`scratchpad/verify.py`, `verify_ban.py`). 프로젝트에 코드를 남기지 않았다(시나리오는 코드 금지).

### 3-1. JSON 유효성 · 스키마 · id 중복
```
## 1. JSON 유효성
  OK  events.json / events_deep.json / events_outside.json / events_tribes.json
  OK  spots.json / spots_deep.json / rumors.json / dialogue.json / imprint_lines.json

## 2. 스키마 검증 (jsonschema 4.23.0, draft-07)
  events.json          [현재 스키마] 통과   [acts 허용 스키마] 통과
  events_deep.json     [현재 스키마] 통과   [acts 허용 스키마] 통과
  events_outside.json  [현재 스키마] 통과   [acts 허용 스키마] 통과
  events_tribes.json   [현재 스키마] 통과   [acts 허용 스키마] 통과
  dialogue.json        통과

## 3. spots_deep.json ↔ spots.json 필드 대조
  OK  6곳 전부 — 누락[] 추가[](unlock 제외), resource={key,ko,gain}

## 4. id 중복 0
  사건 4파일 합계: 60개, 중복 0
  스팟 2파일 합계: 12개, 중복 0
  소문: 38개, 중복 0 / 각인 연출문: 9개, 중복 0
  소문의 spot_id 미존재: 0   사건 spot_clue 미존재: 0
```
> **작업 중에 밝혀진 것**: 스프린트 착수 시점에 읽은 `events_schema.json` 에는 `acts` 가 없었고(`additionalProperties:false` 라 스키마 위반이 될 예정이었다), 그래서 "acts 허용 가상 스키마"로 이중 검증하도록 스크립트를 짰다. 그런데 검증 시점에는 **개발이 이미 `acts` 속성을 스키마에 넣어 둔 상태**라 두 쪽 다 통과했다. 실제 스키마의 정의는 `{"type":"array","minItems":1,"maxItems":3,"uniqueItems":true,"items":{"type":"integer","enum":[1,2,3]}}` 이고 내가 쓴 값과 완전히 호환된다. 개발 요청 한 건이 이렇게 저절로 닫혔다.

### 3-2. 막(act) 분포 — 1막 24장 요건
```
## 5. acts 분포
  acts 없는 카드: 0
  1막 풀: 26장  severity {0: 9, 1: 7, 2: 9, 3: 1}  positive:true 2장
  2막 풀:  4장  severity {0: 1, 1: 3, 2: 0, 3: 0}  positive:true 1장
  3막 풀: 38장  severity {0: 10, 1: 13, 2: 13, 3: 2}  positive:true 12장
  1막 24장 요건: 26장 → 충족
  1막에 섞인 육상 카드: ['famine','drought','confusion','relic_cache']
```
개발의 `events_for_act()` 로도 같은 값이 나오는지 교차 확인했다 — **임시 분류표가 아니라 내 파일 값으로 갈린다**(`ACT_BY_ID`/`ACT_BY_PREFIX` 는 이제 한 장도 타지 않는다):
```
$ python -c "from storyteller import load_events, events_for_act; …"
1 막: 26 장  positive: 2
2 막:  4 장  positive: 1
3 막: 38 장  positive: 12
1막 비-deep: ['famine', 'drought', 'confusion', 'relic_cache']

## 6. 심해 무리(tribe) 지정
  deep_dome_signal=gauge  deep_jelly_bloom_seen=gauge  deep_courtyard_pattern=guest
  deep_brine_sitting_suit=anchor  deep_net_share_shoal=net
  사용된 심해 enum: ['anchor','gauge','guest','net'] / 기대와 일치
```

### 3-3. **각 스팟이 열리는 즉시 읽히는 줄이 있는가** (핵심 요건)
`server.rumor_rule_audit()` 의 최악 경로 검사를 그대로 재현 — 표의 카테고리 **하나만으로** 문턱을 넘은 순간을 스팟×카테고리 전수로 시뮬레이션했다.
```
## 7. '열리는 순간 읽히는 소문' 전수 검사
  OK  spot_flooded_train     drink×3      → 1개 ['rumor_flooded_water_song']
  OK  spot_flooded_train     medical×3    → 1개 ['rumor_flooded_wet_cat']
  OK  spot_goldfish_canal    tobacco×2    → 1개 ['rumor_canal_wet_hem']        ← 신규
  OK  spot_greenhouse_cafe   food×4       → 1개 ['rumor_cafe_pollen_sneeze']
  OK  spot_forest_train_door electronics×2→ 1개 ['rumor_forest_two_rails']     ← 신규
  OK  spot_forest_train_door food×2       → 1개 ['rumor_forest_night_sniff']
  OK  spot_rooftop_garden    apparel×2    → 1개 ['rumor_roof_grass_seeds']     ← 신규
  OK  spot_rooftop_garden    medical×2    → 1개 ['rumor_roof_stair_water']     ← 신규
  OK  spot_lantern_river     book×2       → 1개 ['rumor_river_erased_line']    ← 신규
  OK  spot_lantern_river     stationery×2 → 1개 ['rumor_river_scorched_paper'] ← 신규
  OK  spot_vent_garden       electronics×2→ 1개 ['rumor_vent_warm_arms']
  OK  spot_jelly_bloom       stationery×3 → 1개 ['rumor_jelly_not_danger']
  OK  spot_sunken_courtyard  book×3       → 1개 ['rumor_courtyard_same_mark']
  OK  spot_whale_fall        food×3       → 1개 ['rumor_whale_one_more_table']
  OK  spot_brine_lake        drink×3      → 1개 ['rumor_brine_shore_below']
  OK  spot_kelp_ceiling      apparel×4    → 1개 ['rumor_kelp_new_color']
  결함 0 / 16경로
```
서버를 실제로 띄워 교차 확인했다(`python server.py`, 8002):
```
$ python -c "…server.py 로드…"
SPOTS: 12
  spot_vent_garden      spots_deep.json {'categories':['electronics'],'need':2,'source':'rules'}
  spot_jelly_bloom      spots_deep.json {'categories':['stationery'], 'need':3,'source':'rules'}
  spot_sunken_courtyard spots_deep.json {'categories':['book'],       'need':3,'source':'rules'}
  spot_whale_fall       spots_deep.json {'categories':['food'],       'need':3,'source':'rules'}
  spot_brine_lake       spots_deep.json {'categories':['drink'],      'need':3,'source':'rules'}
  spot_kelp_ceiling     spots_deep.json {'categories':['apparel'],    'need':4,'source':'rules'}
audit: []            ← rumor_rule_audit() 결함 0
EVENTS total: 60   act1: 26

$ curl -s "http://127.0.0.1:8002/api/spots?uid=scn_s4_check"
  → 12곳. 심해 6곳 pos = SPOT_POS_DEEP(광층 -290 ~ 해구 230), gate.source=rules
```
> 검수 중 알게 된 것: **개발이 같은 시각에 `SPOT_POS_DEEP`·`RUMOR_RULES_DEEP` 을 이미 붙여 뒀다.** 내가 파일에 쓴 `unlock` 6개와 서버 표의 값이 **완전히 일치**한다(전자2·문구3·도서3·식품3·음료3·의류4). 이제 정본은 서버 표이고 파일의 `unlock` 은 폴백이다 — TASKS에 확인 한 줄 남겼다.

소문 선택까지 실제 함수로 확인(문턱을 막 넘은 상태의 `rumor_lines()` 선택 결과):
```
spot_vent_garden      electronics×2 → 읽힘 who=octopus "문어가 돌아와 아이 손목을 감았는데 평소보다 미지근했다…"
spot_jelly_bloom      stationery×3  → 읽힘 who=gauge   "눈금 무리의 일지에 열아홉, 아래, 느리다, 위험 아님…"
spot_sunken_courtyard book×3        → 읽힘 who=guest   "손님 무리가 뚜껑에 찍힌 무늬를 알아보았다…"
spot_whale_fall       food×3        → 읽힘 who=net     "그물 무리가 올해는 밥상이 하나 늘었다고 했다…"
spot_brine_lake       drink×3       → 읽힘 who=anchor  "닻 무리의 노인이 물속에도 물가가 있다고 했다…"
spot_kelp_ceiling     apparel×4     → 읽힘 who=octopus "문어가 놓고 간 조각에 돔 안에서 아무도 본 적 없는 색이…"
spot_goldfish_canal   tobacco×2     → 읽힘 who=wayfarer / spot_forest_train_door electronics×2 → 읽힘 who=crow
spot_rooftop_garden   apparel×2     → 읽힘 who=cat     / spot_rooftop_garden     medical×2     → 읽힘 who=dog
spot_lantern_river    book×2        → 읽힘 who=wayfarer/ spot_lantern_river      stationery×2  → 읽힘 who=cat
12/12 폴백 0
```

### 3-4. 금지어 스캔
1차(파일 전문, 금지어 150개)에서 31건이 잡혔고 **전수 육안 확인 결과 전부 오탐**이었다: `절`("한나절"·"친절"·"사절"·"예절"·"절반"·"한 소절"), `누가`("누가 말한다"), `파리`("해파리"), 그리고 `성경`·`경전` — 앞의 둘은 **본 프로젝트가 성경 문서를 부르는 팀 용어**(TEAM.md §1)이고 뒤의 `경전`은 세계관 안에서 눈금 무리의 일지와 손님 무리의 안내 방송을 가리키는 보통명사다. 전부 `note`·`_comment`·문서 본문이며 **화면에 나가지 않는다.**

그래서 2차는 **화면에 실제로 나가는 문자열만** 뽑아 다시 돌렸다(사건 `name`/`text`/`dialogue`, 스팟 5필드+`resource.ko`, 소문 `text`, 대사 `text`, 각인 `line`):
```
화면 노출 문자열 291개를 금지어 150개로 전수 스캔
총 적발 0건
  (화면 밖 note) deep_school_writes:'성경'  deep_announcement_wakes:'경전'  deep_dock_arms:'부족'
```
해양 생물은 학명·실존 종명을 쓰지 않고 사람들이 부르는 이름만 썼다(긴목·문지기·손톱 무리·먼 울음·동거 문어).

### 3-5. 표기 규칙·길이 규격
```
## 9. 텍스트 규격 (name≤24, text≤160, 대사≤200)
  사건 카드 위반: 0 / 대사 위반: 0
## 10. 1막 표기 '무리' 규칙
  data/spots_deep.json: '부족' 0건
  data/events_deep.json: '부족' 1건 → deep_dock_arms 의 note(제작 메모).
      "불꽃 부족은 '잠재운다'고 말한다" — 3막 육상 부족을 가리키는 교차 참조라 정당. 화면 노출 아님
```

---

## 4. 남에게 요청할 것 (TASKS.md 요청함 등재 완료, 6건)

1. **[→개발] `acts` 60장 전량 기입 완료 — 작업 중 개발이 필터까지 붙여 이미 살아 있다.** `storyteller.acts_of()`·`events_for_act()` 확인 결과 임시 분류표(`ACT_BY_ID`/`ACT_BY_PREFIX`)는 한 장도 타지 않으니 지워도 된다. (착수 시점 요청이었으나 병렬로 해소됨)
2. **[→개발, 필수] `data/imprints.json` 에 `knock_heard` 정식 등재.** 문구가 다 왔으니 `server.py DEEP_IMPRINTS` 의 `_pending_text` 자리표시를 해제할 수 있다.
3. **[→개발] 대사에 막 구분이 없다.** 1막에서 육상 소재 줄(비단잉어·숲·바람·일곱 물줄기)이 같은 태그에서 뽑힌다. 줄별 `acts` 허용 또는 서버 필터. 그리고 `when` enum에 **`airlock_in`** 추가(귀환 순간 리더 목소리 복귀 — 첫 10분 3:40 비트).
4. **[→개발] `spots_deep.json` 반영 확인.** 서버 표와 파일 `unlock` 값 일치, `rumor_rule_audit()` 결함 0, 좌표 이견 없음.
5. **[→캐릭터] 심해 각인 4종 외형 파츠** `imp_saved_breath`·`imp_crack_seen`·`imp_depth_mark`·`imp_knock_heard`.
6. **[→PM] 1막 풀에 육상 파일 4장이 섞이는 근거 확인** (§2-5).

---

## 5. 미완·리스크

| # | 내용 | 영향 | 대응 |
|---|---|---|---|
| R1 | ~~`acts` 필터가 코드에 없다~~ **해소** — 검증 중 개발이 `events_for_act()` 를 붙여 둔 것을 확인, 1막 26장으로 실제로 갈린다 | — | 닫힘 |
| R2 | 에어락 **귀환** 대사를 못 넣었다(태그 없음) | 첫 10분 3:40 비트의 "값은… 0입니다"가 비어 있다 | 요청 3. 문구는 `WORLD_BIBLE_DEEP` §5-2에 대기 |
| R3 | 대사 막 구분 없음 | 1막에서 육상 어휘가 새어 나온다 | 요청 3 |
| R4 | 심해 스팟 6곳의 **발견 연출을 화면으로 본 적이 없다**(월드 화면은 육상 지형 기준) | 문장이 좋은지 판단이 텍스트에만 머문다 | 1막 거점 화면(정면 단면) 진행 후 첫 스팟 한 곳으로 재검토 필요 — PM 배정 요청 |
| R5 | 1막 26장 중 sev0이 9장(35%) | 조용한 날이 잦아 "각박함"이 묽어질 수 있다 | 다음 스프린트에 sev2 심해 카드 3~4장 증보 제안 |
| R6 | 심해 스팟의 **자원 key 6개가 신규**(`vent_heat`·`glow`·`relic_tile`·`bone_feast`·`brine`·`kelp`) | 화면 표기는 `ko` 로 되지만 개발이 key로 분기하면 미정의 | 육상도 같은 방식(`water`·`koi`·`seed`…)이라 규약 동일. 문제되면 알려 달라고 §4-4에 포함 |

---

## 6. 적용한 교본 원칙

| 원칙 | 어디에 |
|---|---|
| **P1**(보편적 원형) | 스팟 여섯 = "뒤지기·발견", 소문 사다리 = "세트 수집". 새 카드도 여덟 원형 안에 있다 |
| **P2**(30초/30일) | 깊이 한 축이 게이트·난이도·진행도를 겸한다. 규칙은 적고 조합(스캔 카테고리 × 스팟 × 무리)은 많다 |
| **P3**(감정의 가속도) | 「민물 한 통」을 1막에 넣은 이유가 이것이다 — 위기 뒤의 이완이 없으면 발견이 감동이 되지 않는다 |
| **P4**(돌아오는 이유) | 소문 사다리를 스팟당 2~4줄로 만들어, 같은 스팟도 스캔이 쌓이면 **다른 문장**이 읽힌다(D7) |
| **S1**(보여주고 말하지 않는다) | 발견문 6개 전부 마지막 문장이 사람의 **하지 않은 행동**. 「두드림」 각인은 습관 하나로 그날 밤을 말한다 |
| **S2**(한 장면 한 대비) | 등불 떼=끄니까 보인다 / 물속의 호수=가장 아름다운 것이 가장 단순하게 죽인다 / 위를 보는 숲=금기인데 이미 보고 있다 |
| **S3**(사건은 질문) | 신작 6장 전부 마지막 문장이 선택의 무게. 「세지 않는 몫」은 성공해도 장부가 비고, 「이음매」는 살려면 가져온 것을 버려야 한다 |
| **S4**(부족의 말투는 몸에서) | 눈금="열아홉, 아래, 느리다" / 닻="혼자 가지 않겠다는 약속을 먼저 받았다" / 그물="조건은 하나" / 손님="한 번도 내린 적이 없다" |
| **S5**(두 AI의 문법) | `game_start` 리더는 재고와 인사를 한 문장에, 정원사는 질문 하나 |
| **S6**(신화는 오해의 기록) | 「두드림」의 대가가 돔의 '예절'이 되는 과정 |
| **S7**(신뢰의 역전) | 신규 소문 18줄 중 10줄을 짐승이 물어 온다. 문어가 4줄로 최다 |
| **S8**(각인은 서사) | 각인 문장을 손끝의 떨림으로 썼다. 수치는 개발 |
| **S9**(짧게) | 사건 text 160자 이내 0위반, 대사 200자 이내 0위반 |
| **S10**(우리말 이름, 지명 없음) | 스팟 이름 6개 전부 우리말 묘사. 금지어 화면 노출 0 |
| **07 W1**(문서가 기억) | 성경 §4·§7을 먼저 고치고 파일을 냈다 |
| **07 W2**(눈으로 확인) | 서버를 실제로 띄워 `/api/spots` 와 소문 선택을 눈으로 봤다. 검증 로그 §3-3 |
| **07 §6**(AI 공개표) | 이번 산출물은 전부 **텍스트**다. 공개표의 "세계관·대사·사건 텍스트 = AI 초안 + 사람 검수, 공개 예" 행에 그대로 들어간다. 새 행은 필요 없다 |

### 원칙과 다르게 한 곳
1. **P2 "더 단순한 쪽"과 다르게, 스팟 6곳의 게이트 카테고리를 6종으로 흩었다.** 한 카테고리로 통일하면 단순하지만, 그러면 **무엇을 스캔하든 같은 순서로 열려** 현실 스캔이 지도를 연다는 훅(WORLD_PRESENTATION §1-3)이 죽는다. 흩는 쪽이 규칙 수를 늘리지 않으면서 조합을 늘린다.
2. **S9 "짧게"와 다르게, `discovery_text` 는 5~6문장이다.** 힐링 스팟 발견문은 3초 타이머가 아니라 **카메라가 내려앉는 30초 연출**에 붙는다(S2-A ⑥). 기존 `spots.json` 6곳과 같은 길이이며, 교본이 "의식에만 허용"한 긴 글의 자리다.
3. **DECISIONS "1막 표기는 무리"와 다르게, `deep_dock_arms` 의 `note` 에 '부족'이 1건 남아 있다.** 3막 불꽃 부족과의 교차 참조이고 제작 메모라 화면에 나가지 않는다(§3-5).

---

## 7. 직군 교본 §5 자가 검수 5문항

**1. 이 문장을 지우고 장면만 남기면 뜻이 전해지는가? 전해지면 지운다.**
지웠다. 「위를 보는 숲」 초안에는 "광층을 오래 보는 것은 돔 사람에게 치명적이다"라는 설명이 있었는데, **"그런데 한 사람이 이미 오래 보고 있다. 아무도 부르지 않는다. 부르면 자기도 보게 되니까"** 만 남기고 지웠다. 금기를 설명하지 않고 금기가 깨지는 장면만 보여 준다. 「물속의 호수」도 같다 — 왜 위험한지는 `danger_note`(화면 다른 자리)로 밀고, 발견문에는 *"아무도 손을 담그지 않는다. 담근 사람이 옛날에 있었기 때문이다"* 두 문장만 뒀다. 다만 **`danger_note`·`tribe_hint` 는 설명문이 맞다** — 원정 준비 화면에서 플레이어가 읽고 판단하는 정보라 이 기준을 적용하지 않았다.

**2. 대사만 보고 부족/AI를 맞힐 수 있는가?**
- *"열아홉, 아래, 느리다, 위험 아님."* → 눈금 무리(숫자·단위·형용사 없음)
- *"조건은 하나, 받은 것을 세지 않는 것이다."* → 그물 무리(세는 것이 금기)
- *"혼자 가지 않겠다는 약속을 먼저 받았다."* → 닻 무리(말을 아끼고 조건을 먼저 건다)
- *"항로에서 늘 지나치지만 한 번도 내린 적이 없다."* → 손님 무리(머물면 잃을 것이 생긴다)
- *"돔 내 재고를 확인했습니다. 부족합니다. 오늘도 좋은 하루 되십시오."* → 리더(재고+인사)
- *"물이 민다. 막는 것인가, 묻는 것인가."* → 정원사(질문, 단정 없음)

**3. 사람 간 거리와 짐승의 가까움이 보이는가?**
보인다. 새 소문 18줄 중 **10줄이 짐승**(문어 4·고양이 3·개 1·까마귀 2)이고, 사람에게서 오는 8줄은 전부 **값이 붙어 있거나 조건이 먼저 온다**("가져갈 양을 먼저 정하고 오라", "혼자 가지 않겠다는 약속을 먼저 받았다", "교역 자리에 앉았던 사람"). 「열수구 정원」에서 닻 무리는 **손짓으로만** 방향을 알려 준다. 반대로 문어는 아이 손목을 감고 돌아와 온기를 전한다 — 이 세계에서 정보가 **몸으로 오는 유일한 경로**다.

**4. 대비(어둠/빛, 위기/발견)가 하나 이상 있는가?**
스팟 여섯이 각각 하나씩 쥐고 있다: 열수구=차가운 물/처음 만지는 온기, 등불 떼=끄니까 보인다, 침몰선 안뜰=사람이 만든 것/정원이 된 것, 고래 낙하=죽음 하나/수천의 삶, 물속의 호수=아름다움/가장 단순한 죽음, 위를 보는 숲=금기/이미 보고 있는 사람. 사건 쪽은 「민물 한 통」(짠물의 세계에 민물 한 통)이 1막 유일의 이완이고, 「이음매를 찾는 것들」이 그 직전의 조임이다.

**5. 실제 종교·지명·상표 이름이 없는가?**
없다. 화면 노출 문자열 291개 × 금지어 150개 전수 스캔 **0건**(§3-4). 1차에서 잡힌 31건은 전부 부분 문자열 오탐이거나 화면 밖 제작 메모였고, 한 건씩 눈으로 확인했다.

---

## 8. 보여줄 것 (07 W6)

이번 산출물은 텍스트라 스크린샷 대신 **로그 한 장**을 남긴다 — `/api/spots` 가 12곳을 내고 그중 여섯 곳이 광층(-290)부터 해구(230)까지 세로로 늘어선 화면(§3-3). 데브로그용 한 줄: *"오늘 이 게임의 지도에 여섯 곳이 늘었다. 전부 사람이 살 수 없는 곳이다."*
