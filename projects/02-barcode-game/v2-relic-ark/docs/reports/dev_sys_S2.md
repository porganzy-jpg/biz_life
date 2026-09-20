# 개발(시스템) 보고서 — S2-B 규칙 보강 (2026-09-20)

담당: relic-dev(시스템) · 상태: 완료 · 서버: `python server.py` (http://localhost:8002) 기동 중
전제 문서: `docs/TEAM.md`, 교본 `00_COMMON`·`02_DEV`·`07_AI_GAMEDEV`, 성경 `GROWTH_AND_MYTH §1`·`TRUST_AND_COMPANIONS`·`WORLD_PRESENTATION §1~3`, 보고서 `dev_20260920.md`·`review_sprint1.md`

---

## 1. 무엇을 만들었나 (변경 파일)

| 파일 | 상태 | 내용 |
|---|---|---|
| `server.py` | 수정 | ① **각인 참여자 선별**(`event_participants`) ② 두 AI 목소리 로더·`voice_for()`·스캔/사건/야간 3곳 응답 ③ 부족 첫 접촉 1회 소모(`seen_events`, `mark_seen`, `seen_once`) ④ **`/api/rumors`** + `SPOT_POS`·`RUMOR_RULES` 상수, `data/rumors.json` 관용 로더 ⑤ 구버전 방주 필드 보강 `migrate_state()` |
| `engine/storyteller.py` | 수정 | `pick_event(..., exclude=set)` — 소모된 1회성 카드 제외(전부 제외되면 원래 풀로 되돌아간다). `load_events()`를 **파일 목록**(`EVENT_FILES`)으로 바꿔 `events.json`+`events_tribes.json`+`events_outside.json` 병합 |
| `static/app.js` | 수정 | `voiceHtml()`·`voiceToast()`(리더 주황/정원사 청록), 팩 개봉·사건 결과·야간 토스트에 대사 표시, 사건 결과에 **"나선 사람"** 줄, 역 홀 시트에 **소문 목록**(`renderRumors`), `window.ARK`에 `voiceToast`/`renderRumors` 공개(S2-A 월드 화면 재사용용) |
| `static/style.css` | 수정 | `.voice`(리더 `--lamp` / 정원사 `#2FA8A0`), `.voice-toast`, `.rumor`, `.result .went` — 파일 끝 23줄 추가 |
| `engine/relic_generator.py` | 수정 | 가문 표시 이름을 `data/family_names.json`(창작 이름)에서 가져오고 **실제 상표는 응답에서 제외**. 파일 mtime 감시라 재시작 없이 반영 |
| `data/dialogue_schema.json` | **신규**(개발 소유) | 대사 스키마 + `when` enum(`game_start`·`spot_water_reflection`·카테고리별 `scan_*` 포함) + `_hooks`(어느 태그가 화면 어디에 뜨는지) |
| `docs/reports/dev_sys_S2.md` + 스크린샷 5장 | 신규 | 이 문서 |

읽기만 함(수정 없음): `data/dialogue.json`, `data/spots.json`, `data/rumors.json`, `data/imprints.json`, `data/roles.json`, `data/events*.json`, `static/world.html`·`static/world3d.js`(**S2-A 소유, 손대지 않음**), `static/index.html`(수정 불필요 — 토스트를 JS가 만든다).

---

## 2. 각인 참여자 선별 규칙 (S1-B 밸런스 결함의 교정)

`review_sprint1.md` §S1-B 1번: "사건 한 번에 주민 전원이 위기를 겪어 3사건이면 전원 진화". 이제 **사건에 나선 1~2명만** 겪는다.

`server.py: event_participants(roster, ev, seed, how, used_card, hero, pre_injured)` — 우선순위대로 채우고 **상한 2명**:

| 순위 | 규칙 | 근거 |
|---|---|---|
| ① | **hero** — 역할 자동 대항으로 실제로 막은 사람 | 화면에 "○○이(가) 나서서 막았습니다"라고 이미 쓰고 있다. 쓴 대로 각인한다 |
| ② | 사건 `counter_room`에 **배치**된 주민 (`resident.station`) | 자리 배치는 S3 태스크라 지금은 비어 있다. 필드가 생기면 규칙을 고치지 않아도 1순위가 된다(선반영) |
| ③ | 역할 `counter_tags` ∩ 사건 `counter_tags` | 그 일에 나설 이유가 있는 사람. 의무병이 전염에, 정찰병이 습격에 나선다 |
| ④ | **대항 카드로 막은 경우**, 그 카드의 태그와 맞는 역할 1명 | 내가 정한 규칙: 카드는 물건이지만 **쓴 것은 사람**이다. `#치료` 카드를 낸 밤에 나선 사람은 치료를 아는 사람이다. `how == "card"`일 때만 적용하고, 맞는 역할이 없으면 ⑤로 내려간다 |
| ⑤ | 시드 난수 1명 `uid\|day\|who_imprint` | 아무 이유도 없으면 그날의 당번. 같은 입력 = 같은 사람(D6) |

부가 규칙(모두 코드 주석에 같은 말로 적어 뒀다):
- **이미 누워 있던 부상자는 후보에서 뺀다** — 그 밤에 나서지 못했다. 전원이 부상이면 전원이 후보(아무도 안 겪은 일이 되지 않게).
- **roster는 사건 *전* 명단** — 사건 결과로 합류한 표류자는 그 밤을 겪지 않았으므로 후보가 아니다(`s2b_new` 로그에서 새 주민 「다올」이 참여자에 없음을 확인).
- 「빈 자리」(상실) **목격자는 한 명** — 참여자 중 다치지 않은 사람 1명, 없으면 방주에 남은 성한 사람 1명. 전에는 안 다친 전원이 받았다.
- 응답에 `participants[]`를 실어 **화면에 "나선 사람: 온새(정찰병)"로 보인다**(D2 — 규칙은 숫자로 숨지 않는다).

### 단위 검증 (5규칙 + 경계)
```
① hero 우선        : ['도담', '해든']          (hero + 태그 일치 1명, 상한 2)
② counter_room 배치 : ['누리', '해든']          (station='infirmary' 인 요리사가 1순위)
③ 역할 태그        : ['해든']                 (해독·치료 = 의무병)
③ 역할 태그(방어)   : ['도담']                 (방어·탐사 = 정찰병)
④ 카드를 낸 손      : ['누리']                 (사건 태그로는 아무도 안 맞고, 카드 #보존 → 요리사)
⑤ 시드 난수(재현)   : ['도담'] ['도담'] ['새벽'] (같은 시드 = 같은 사람, 시드가 바뀌면 다른 사람)
부상자 제외        : ['해든']                 (cook·engineer·scout 부상 → 의무병만)
전원 부상          : ['해든']                 (전원 후보로 되돌아감)
빈 방주            : []                      (터지지 않는다)
```

### API 검증 — 같은 방주에 사건 3회 (uid=`s2b_ev`, `?debug_force_event`)
```
=== infection   나선 사람: ['새벽/기술자']   각인: [('새벽','포자의 표식'), ('도담','빈 자리')]
=== raid_scavs  나선 사람: ['도담/정찰병']   각인: [('도담','지킨 자')]
=== famine      나선 사람: ['도담/길잡이']   각인: [('도담','빈 위장', 진화=True)]
--- 최종 주민
  누리 요리사   imprints []                                     crises []
  새벽 기술자   imprints ['spore_mark']                          crises ['infection']
  도담 정찰병   imprints ['empty_seat','warden','empty_stomach']  crises ['loss','raid','starvation'] evolved True
```
→ 사건마다 **1명**. 전에는 3사건이면 3명 전원이 각인 3개·진화였다. 이제 한 사람의 이야기가 생기고(도담), 아무 일도 겪지 않은 사람(누리)은 그대로다 — 성경의 "각인이 없는 주민은 몇 년을 살아도 그대로다".

---

## 3. 대사 훅 3곳 (`data/dialogue.json`의 `when`)

`voice_for(tag, seed)` — 태그에 맞는 줄을 **시드로** 고른다(같은 입력 = 같은 줄, D6). 같은 태그에 리더·정원사가 모두 있으면 가중치 2:1로 리더가 자주 나온다(방주 안은 리더의 장부, 정원사는 물가에서 말한다). 300회 분포: `reader 208 / gardener 92`.

| 훅 | 엔드포인트 | 태그 | 시드 | 화면 |
|---|---|---|---|---|
| 스캔 결과 | `POST /api/scan` → `voice` | `scan_<카테고리>` 자동(음료는 줄이 없으면 `scan_food`로 대체). 줄이 없는 카테고리는 조용히 넘어간다 — 매번 말하면 잔소리가 된다 | `uid\|barcode\|오늘스캔수` | 팩 개봉 화면의 획득 자원 아래 |
| 첫 화면 | `GET /api/ark` → `voice` | `game_start` (그 방주 1회, `state.greeted`) | `uid\|start` | 야간 줄보다 우선하는 토스트 |
| 스팟 단서 | `POST /api/event/resolve` → `spot_voice` | `spot_water_reflection` → 없으면 `spot_found` | `uid\|day\|spot` | 결과 블록, 사건 대사 위 |
| 사건 결과 | `POST /api/event/resolve` → `voice` | `event_counter` / `event_fail` | `uid\|day\|event_id` | 결과 블록 맨 아래 |
| 야간 진입 | `GET /api/ark` → `voice` + `is_night` | `night` (21시~05시, app.js의 밤 톤 경계와 동일) | `uid\|day` | 도크 위 토스트, **하루 한 번**(localStorage `ark_night_voice`), 탭하면 사라짐 |

색: 리더 `rgb(242,169,59)`(`--lamp` 주황), 정원사 `rgb(47,168,160)`(청록) — 브라우저 `getComputedStyle`로 확인.

---

## 4. 부족 첫 접촉 카드 1회 소모

- 방주 상태에 `seen_events: []`(최근 200개). 사건이 **제시될 때** 기록(`mark_seen`), 정상 경로·`debug_force_event` 모두.
- `pick_event(..., exclude=seen_once(st))` — `seen_once`는 `tribe_`로 시작하는 id만 모은다(상수 `ONCE_PREFIXES`). 다른 사건은 계속 반복된다.
- 안전장치: 제외하고 나면 후보가 비는 경우 원래 풀로 되돌아간다.

```
사건: tribe_wayfarer_passing 지나가는 줄     → seen_events: ['tribe_wayfarer_passing']
3000회 추첨 — 제외 적용 시 소모 카드 등장 0회 / 제외 없으면 93회
전부 소모돼도 뽑힘: drifter
```

---

## 5. `/api/rumors?uid=` — 스캔 카테고리가 지도를 연다

`WORLD_PRESENTATION §1-3`. 해금 규칙은 **`server.py`의 상수 표**(`RUMOR_RULES`), 좌표도 **`server.py`의 `SPOT_POS`**(m, 몰 문턱이 원점 / +x 동=숲·지상 노선, -x 서=강·터널, +y 남=지하 터널, -y 북=언덕·옥상). `data/spots.json`은 시나리오 소유라 좌표를 넣지 않았다.

| spot | 조건 | pos(m) |
|---|---|---|
| spot_flooded_train | 음료+의약 누적 3 | (-120, 70) |
| spot_goldfish_canal | 담배·주류 2 | (60, 95) |
| spot_greenhouse_cafe | 식품 4 | (130, 20) |
| spot_forest_train_door | 전자 2 | (170, -60) |
| spot_rooftop_garden | 의류 2 | (-60, -90) |
| spot_lantern_river | 도서 2 | (-170, 40) |

응답: `[{spot_id, name, clue_text, who, unlocked, is_new, progress:{have,need}, categories, categories_ko, pos:{x,y}}]`
- **`data/rumors.json`이 있으면 그 문장이 우선**(작업 중 시나리오 에이전트가 20줄을 올렸고 바로 물렸다). 필드명을 넓게 받는다(`spot_id|spot`, `clue_text|text|clue|line|sentence`, `who|carrier|source|from`). 깨져 있으면 조용히 무시하고 `spots.clue_text`로 되돌아간다. 파일 mtime 캐시라 서버 재시작 없이 반영된다.
- 줄마다 자기 `unlock:{category,count}`가 붙어 있으면 **조건을 이미 채운 줄을 먼저** 쓴다(해금 여부 자체는 위 표가 정한다).
- 잠긴 스팟은 `clue_text: null` — 아직 아무도 말해 주지 않은 것이다. 화면에는 `? ? ?`와 진행도만.
- `is_new`는 처음 해금된 호출에서만 true(`rumors_seen`에 기록, 로그 `rumor_unlocked`). 클라이언트가 "새 소문: 등불 축제 터" 토스트를 띄운다.

```
spot_flooded_train       True  3/3 (음료·의약)  who=wayfarer
   지나가던 줄이 걷는 노래의 한 소절을 바꿔 불렀다. 선로 끝에서 물소리가 난다는 대목만 두 번 불렀다.
spot_lantern_river       True  2/2 (도서)      who=dog
   개가 강 쪽 통로에서만 멈춰 서서 귀를 세운다. 우리에게는 아무 소리도 안 나는데, 개에게는 난다.
spot_greenhouse_cafe     False 1/4 (식품)      pos={'x':130,'y':20}
```

---

## 6. 검증

### 6-1. 구문 검사 · 서버 재기동
```
$ python -c "import ast; ast.parse(open('server.py',encoding='utf-8').read()); …"
py syntax OK
PS> $pat = '*serv' + 'er.py*'      # 자기 자신을 죽이지 않도록 패턴 분리
PS> Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.CommandLine -like $pat } | Stop-Process -Force
PS> Start-Process python server.py -WindowStyle Hidden   # 로그 server_http.log
PS> (Invoke-WebRequest "http://localhost:8002/api/stats").StatusCode
200
```

### 6-2. 회귀 7항목 (uid=`s2b_final`, 새 방주)
```
=== 1) 스캔
  8801043015097 -> food   말없는 겨울 씨앗 주머니 {'food':3,'morale':1,'trade':1} voice=scan_food
  9791162241905 -> book   떨리는 약초 도감      {'knowledge':7,'power':1}     voice=scan_book
  4902345678905 -> drink  잠든 투명한 강        {'water':3,'chem':1,'knowledge':1} voice=scan_food
=== 2) 건설
  well@3 -> [('pantry',2), ('well',3)]
  library@4 -> 자원이 부족합니다: {'cloth': 1}
=== 3) 사건
  오늘의 사건 tribe_shelf_audit / room_backup=False / matching=0
  결과 countered=False how=none applied={'morale':-2,'trade':-1} 신뢰-5
  나선 사람 ['누리/요리사'] (상한 2) / 각인 []
  voice 리더: 잃은 것을 세어라. 세어 둔 것은 언젠가 돌려받는다…
  하루 1회 제한 -> 처리할 사건이 없습니다
=== 4) 주민
  주민 3 부상 0 / auto_counter {'열원':0.35,'보존':0.35,'부품':0.4,'전력':0.4,'탐사':0.35,'방어':0.35}
  신뢰 {cook:0, engineer:0, scout:0}
=== 5) 도감 / 6) 야간 목소리
  codex [('food','1/4'), ('drink','1/4'), ('book','1/4')]
  is_night=True voice=정원사: 밤에는 물소리가 커진다. 물이 커진 것이 아니라 네…
=== 7) 소문  (6개 전부 응답, 진행도·좌표 정상)
=== 8) 부족 카드 1회 소모  seen_events ['tribe_shelf_audit'] / rumors_seen []
=== 9) 7일 시뮬 (engine/storyteller.py)
  Day 1: 보고만 있었다 대항 성공 … Day 7: 진동으로 말하는 사절 피해 {'trade':-1,'morale':-2} → 사기 4, 부상 2
=== 10) 구버전 마이그레이션
  smoke:     주민 3 방 ['pantry'] imprints필드 [[],[],[]] seen_events=['mutant_magpie'] rumors_seen=[]
  uakdrgvja: 주민 3 방 []        imprints필드 [[],[],[]] seen_events=[]                rumors_seen=[]
```
→ 7항목(스캔·건설·사건·주민·도감·7일 시뮬·마이그레이션) 모두 종전 동작. 구버전 방주는 `migrate_state()`가 `seen_events`/`rumors_seen`를 채우고, **이미 받아 든 오늘의 사건은 겪은 것으로 기록**한다(부족 카드가 두 번 오지 않게).

추가 회귀: 카드 대항(`how=card`) 정상, 표류자 합류(`resident:+1`) 정상 + 새 주민이 참여자에 섞이지 않음, 긍정 사건은 각인 없음.

### 6-3. 브라우저 (Playwright, `http://localhost:8002/?nointro`) — 콘솔 에러 0 / 경고 0
| 파일 | 내용 |
|---|---|
| `docs/reports/sys_S2_voice.png` | **야간 진입** — 도크 위에 리더 대사 "불을 켜 두어라. 어둠 속에서도 세는 사람만이 아침에 웃는다." 주황 테두리 |
| `docs/reports/sys_S2_scan_voice.png` | **스캔 결과** — 팩 개봉 화면, 「말없는 겨울 씨앗 주머니」 아래 리더 "보존하라. 유통기한은 두려움이 지어낸 말이고…" |
| `docs/reports/sys_S2_event_voice.png` | **사건 결과** — "나선 사람: 온새(정찰병)" → 각인 「지킨 자」 → 신뢰 −5 → 리더 대사 |
| `docs/reports/sys_S2_rumors.png` | **역 홀 소문 목록** — 「등불 축제 터」 해금(개가 물어 온 단서), 잠긴 5곳은 `? ? ?`와 진행도 |
| `docs/reports/sys_S2_morning.png` | **각인 다음 날 아침**(DAY 2) — 금색 토스트 "아침 · 刻 빈 자리 / 누리의 담요는 아침까지 접히지 않았다…", 아래에 밤의 리더 대사 |

콘솔: JS 에러 0. `favicon.ico` 404 한 건은 이 스프린트 이전부터 있던 것(아이콘 파일 없음, 기능 영향 없음).
브라우저는 S2-A 에이전트와 공유 중이라 탭이 서로 바뀌었다 — 스크린샷은 모두 `localhost:8002/?nointro` 탭에서 찍은 것을 확인했다.

정원사 줄도 실제 렌더 확인(`.voice.gardener` border `rgb(47,168,160)`), 사건 카드 대항 성공 시 "막았구나. 막은 것은 무엇이고, 막힌 것은 무엇인가."

---

## 6-4. PM 추가 요청 8건 (2026-09-20 스프린트 2 중 지시)

| # | 요청 | 처리 | 근거 로그 |
|---|---|---|---|
| 1 | `load_events()` 파일 목록화 + `events_outside.json` 병합 | **완료**. `EVENT_FILES = (events, events_tribes, events_outside)` — 파일 한 줄 추가로 새 묶음이 붙는다 | `총 사건 38` (기본 10 + 부족 21 + 바깥 7). `dino_* 4 / expedition_late_return / wet_paws_at_dawn / crow_paper_scrap` 풀에 존재 |
| 2 | 역할 진화 이름을 `roles_evolved.json` 값으로 | **완료**(런타임 우선 병합). `data/imprints.json`은 다른 에이전트와 충돌하지 않게 **고치지 않고**, 서버가 기동 때 덮어쓴다 — 시나리오가 이름을 또 바꿔도 코드·데이터 수정 없이 반영 | `{'scout':'노래잡이','cook':'버림 없는 손','medic':'숨의 손','engineer':'조상 깨우는 이','farmer':'문턱지기','scholar':'낭독하는 이','trader':'빈손 흥정꾼','kid':'짐을 진 아이'}` · 화면 확인(사건 결과 "온새(노래잡이)") |
| 3 | 각인 문장을 `imprint_lines.json`으로 교체 + **다음 날 아침** 1회 | **완료**. 같은 방식(런타임 우선). 각인 시 `state.morning_pending`에 `{day: 오늘+1}`로 쌓고, 그 날 첫 `GET /api/ark`가 `morning_lines[]`로 내려보내며 큐에서 뺀다. 클라이언트는 금색 아침 토스트(여러 명이면 위로 쌓임) | `morning_pending: [(2,'누리','발자국'), (2,'누리','빈 자리')]` → day 2 첫 호출에 2줄, 두 번째 호출 `[]`. 스크린샷 `sys_S2_morning.png` |
| 4 | 소문 게이트 확장 | **완료**. `forest_train_door += food`, `rooftop_garden += medical`, `lantern_river += stationery` | `spot_forest_train_door 1/2 ['electronics','food']`, `spot_rooftop_garden 0/2 ['apparel','medical']`, `spot_lantern_river 1/2 ['book','stationery']` |
| 5 | `game_start`·`spot_water_reflection` 태그 승인 | **완료 + 훅까지 연결**. `game_start` = 그 방주의 첫 `/api/ark` 1회(`state.greeted`), `spot_water_reflection` = `spot_clue`가 나온 사건 결과(`spot_voice`, 줄이 없으면 `spot_found`로 대체). 카테고리별 `scan_*`도 자동 연결로 바꿨다. 허용 목록은 `data/dialogue_schema.json` | 현재 두 태그의 줄이 아직 없어 `game_start`는 조용히 넘어가고 야간 줄로 대체됨(정상). `spot_voice` 실제 출력: 정원사 "잉어들이 네 그림자 아래로 모였다…" |
| 6 | `spot_clue`→「물의 기억」 경로 확인 | **살아 있다.** 서버가 `spot_clue`를 보면 `healing_spot_found` 플래그를 만들고, 각인 판정에서 **플래그는 4단계(최상위)**라 `positive` 여부를 보기 전에 매칭된다. 즉 두 카드에 `positive`가 없어도, 나중에 `positive:true`를 붙여도 경로는 끊기지 않는다 | `crow_paper_scrap` 카드 대항 성공 → `applied {"spot_clue":"spot_lantern_river","knowledge":2}` → 각인 「물의 기억」(새 문장 "…머리카락이 아직 마르지 않아 베개가 서늘하다") |
| 7 | 테스트 uid 지표 제외 | **완료**. `/api/stats`가 `smoke·uakdrgvja·scn_s2_check·log_demo`와 접두어 `pmcheck·scn_·s2b_·imp_·test·dev_`를 뺀다. `?all=1`이면 전부 | `기본: users 2, 제외된 uid 13` / `all=1: users 15` |
| 8 | 가문 실명 비노출 | **완료**. `relic_generator.display_family()` — `data/family_names.json`의 `name`만 화면에 나가고, `known_families.json`의 실제 상표는 **카테고리 판정에만** 쓴다. 파일이 없으면 "이름 잃은 가문 NNNN" 폴백. mtime 감시라 시나리오가 파일을 올린 즉시(재시작 없이) 반영됐다 | `8801043015097` → `family_name: 붉은 실 가문` / `category: food`(판정 그대로). 파일 없던 시점 스캔은 `이름 잃은 가문 1162`로 폴백 |

추가 회귀(38장 풀): `dino_raptor_pack` 실패 → 「발자국」 각인 최초 부여(S1 미완 3번 해소), `expedition_late_return` → 「햇빛의 기억」, 7일 시뮬 정상.

## 7. 적용한 교본 원칙

- **D1 규칙은 적게, 조합은 많게** — 새 시스템을 만들지 않고 기존 곱으로 풀었다. 참여자 = 역할태그 × 사건태그 × 카드, 소문 = 스캔 카테고리 × 스팟. 새 화면 0개, 새 도크 버튼 0개.
- **D2 모든 숫자는 화면의 무엇으로 보인다** — 참여자 규칙 → "나선 사람" 줄, 소문 누적 → 역 홀의 진행 막대와 `? ? ?`, 밤 시간대 → 목소리 토스트.
- **D4 실패는 서사, 막힘은 버그** — 사건 실패에 리더/정원사의 해석이 붙어 손실이 이야기가 된다. 회귀 7항목 로그 첨부, 콘솔 에러 0.
- **D5 첫 3분 루프를 지킨다** — 탭 수 증가 0. 대사는 이미 열리는 화면(팩·결과)에 얹었고, 소문은 이미 있던 역 홀 시트 안에 넣었다.
- **D6 결정성** — 목소리·참여자 난수 모두 `uid|day|목적` 시드. 같은 입력이면 같은 줄, 같은 사람.
- **D7 데이터가 규칙을 든다** — 대사·소문 문장은 전부 `data/*.json`. 코드에 한국어 대사 문자열을 하나도 넣지 않았다. `rumors.json`은 필드명을 넓게 받아 시나리오가 코드를 기다리지 않게 했다.
- **P1 여덟 원형 중 "뒤지기"와 "세트 수집"** — 현실 스캔이 지도를 연다. **P3 감정의 가속도** — 위기 직후 정원사의 질문, 밤에만 오는 한 줄. **P4 D7 리텐션** — "도서를 두 번 더 읽으면 강의 등불이 열린다"는 다음에 올 이유.
- **07 W1 문서가 기억이다** — 규칙을 코드 주석과 이 보고서에 같은 문장으로 적었다. **W2 눈으로 확인** — 스크린샷 4장. **W3 소유권** — `world.html`·`world3d.js`·`data/*.json` 미수정.
- 이탈: 없음. 다만 `04` 카드 규칙은 교본에 없는 내가 만든 규칙이므로 위 §2에 근거를 적었다.

## 8. 02_DEV §5 자가 검수

1. **새 숫자가 화면의 무엇으로 보이는가?** 참여자 상한 2 → 결과의 "나선 사람" 줄과 각인이 한 사람에게만 뜨는 장면. 소문 누적 → 역 홀의 막대와 해금된 한 문장. 밤 21시 → 토스트 한 줄. 화면에 없는 새 숫자는 `pos`(지도 좌표)뿐이고, 그것은 S2-A의 지도 표식으로 보인다.
2. **첫 3분 루프의 탭 수가 늘었나?** 아니다(스캔→카드→방주→대항 그대로, 0회 증가). 소문은 역 홀 안, 대사는 이미 뜨는 화면 위.
3. **같은 입력이면 같은 결과인가?** 그렇다. 목소리·참여자·소문 문장 모두 `uid|…` 시드. 같은 시드 2회 호출 동일 결과를 로그로 확인.
4. **폰 가로 720px에서 손가락으로 조작 가능한가?** 새 조작 요소는 목소리 토스트(전체 폭, 탭 영역 ≥44px)뿐이고 나머지는 읽기 전용 텍스트. 소문 목록은 스크롤되는 시트 안이라 폭에 무관.
5. **회귀 7항목 로그가 있는가?** §6-2에 전문.

## 9. 미완 · 리스크

1. **소문 해금 조건이 두 곳에 있다.** PM 요청대로 서버 표에 `food`·`medical`·`stationery`를 더해 파일 쪽 카테고리와 겹치게 했지만, **횟수**는 여전히 다르다(예: 옥상 정원 서버=2 / 파일=의약 3·전자 4). 지금은 **서버 표가 해금을 정하고 파일은 문장만** 쓴다(조건 못 채운 줄도 폴백으로 나올 수 있음). 정본을 정해야 한다(§10-1).
1-b. **데이터 우선 병합의 반영 시점** — `roles_evolved.json`·`imprint_lines.json`은 **서버 기동 때** 읽는다(대사·소문·가문 이름은 mtime 감시라 즉시 반영). 시나리오가 이 두 파일을 고치면 서버를 한 번 재시작해야 한다.
1-c. **`morning_lines`는 `/api/ark`가 나르는 큐다.** 며칠 뒤에 접속해도 밀린 아침 문장이 그때 한 번에 나온다(날짜가 지났다고 사라지지 않는다). 하루 여러 명이 달라졌으면 토스트가 위로 쌓인다.
2. **`SPOT_POS`는 임시 좌표다.** 부족 방향(WORLD_PRESENTATION §1-1)만 맞춰 둔 눈대중이고, S2-A의 지형 좌표계(약 400×250m)와 원점·축 방향을 합의해야 한다.
3. **참여자 ⑤ 시드 난수는 "공평"하지 않다.** 이미 각인 3개인 사람이 또 뽑힐 수 있다(상한 때문에 각인은 안 붙고 `crises`만 쌓인다). 지시대로 순수 난수로 뒀다. 각인 적은 사람 가중은 S3에서 판단.
3-b. (S1 미완 해소) 「발자국」·「햇빛의 기억」은 `events_outside.json` 병합으로 실제로 붙기 시작했다. 역할 진화 이름도 부족 신화 이름으로 바뀌었다.
4. **`station`(배치) 필드는 아직 아무도 쓰지 않는다.** 자리 잡기 건설(S3)이 나와야 1순위가 실제로 동작한다.
5. **부상 대상은 여전히 "아이 먼저"** — 나선 사람이 먼저 다치는 편이 이야기에 맞지만, 기존 밸런스를 건드리지 않으려고 두었다. S3에서 참여자 우선 부상으로 바꿀지 결정 필요.
6. **대사가 없는 스캔 카테고리** — 의약·전자·문구·의류·담배와 `game_start`·`spot_water_reflection`은 아직 줄이 없어 조용하다. 태그 이름만 맞추면 **코드 수정 없이** 붙는다(`data/dialogue_schema.json`의 enum·`_hooks` 참조).
7. **`?debug_force_event=`는 여전히 개발 전용**(★ 주석). 배포 전 제거 목록.
8. 테스트 uid(`s2b_*`)가 `relic_ark.db`에 남았다. 지표 집계 시 제외.

## 10. 다른 에이전트에게 요청 (`docs/TASKS.md` 요청함에도 한 줄씩 남김)

### PM
1. **소문 해금 조건 정본 결정** — (a) 서버 표 유지(지금), (b) `rumors.json`의 줄별 `unlock` 중 가장 쉬운 것을 스팟 해금 조건으로 삼도록 서버를 데이터 주도로 바꾸기. (b)가 D7("데이터가 규칙을 든다")에 더 맞지만 태스크 지시는 (a)였다.
2. **참여자 선별 규칙을 `DECISIONS.md`에 한 줄** 등록 부탁드립니다: "2026-09-20 — 각인은 사건에 나선 1~2명에게만. 우선순위 hero>배치>역할태그>카드태그>시드난수, 상한 2, 목격자 1명."

### 시나리오
3. `data/rumors.json`의 `unlock` 카테고리가 서버 표와 다릅니다(위 §9-1). 어느 쪽이 의도인지 알려 주세요.
4. `scan_medical`·`scan_electronics`·`scan_apparel`·`scan_tobacco` `when` 태그가 있으면 스캔 대사 빈 구간이 메워집니다(리더 1줄·정원사 1줄씩이면 충분).
5. (완료) 각인 연출 문장·역할 진화 이름은 `imprint_lines.json`·`roles_evolved.json`을 **런타임에서 우선** 읽습니다. `data/imprints.json`은 고치지 않았으니(충돌 방지) 앞으로도 그 두 파일만 고치시면 됩니다. 단, 이 두 파일은 서버 기동 때 읽으므로 수정 뒤 재시작이 필요합니다.
6. `data/family_names.json`은 그대로 물렸습니다(키 없는 접두어는 "이름 잃은 가문 NNNN"). `known_families.json`의 실제 상표는 이제 API 응답에 나가지 않습니다 — 카테고리 판정에만 씁니다.

### 개발(월드, S2-A)
6. 지도 표식은 `/api/rumors`의 `pos`(m)와 `unlocked`를 쓰시면 됩니다. 잠긴 곳은 `clue_text: null`이니 물음표로 두세요. 좌표 원점·축이 지형과 다르면 알려 주세요, `server.py: SPOT_POS`만 고치면 됩니다.
7. 목소리 연출이 필요하면 `window.ARK.voiceToast({who, who_ko, text})`를 그대로 부르세요(스타일 포함). 소문 목록은 `window.ARK.renderRumors()`.
