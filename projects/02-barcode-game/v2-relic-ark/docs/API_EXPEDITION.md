# API_EXPEDITION — 원정·문간 서버 계약 (S15-A, 2026-10-04)

작성: 개발(서버). 근거: `docs/EXPEDITION.md`(§8 서버 제안), 수치 `data/balance/expedition.json`(기획), DECISIONS 2026-10-03(따라가도 기댓값 같음 · 손님은 떠나지 않음 · 밤 판정 상한 없음 · 스팟 발견은 원정 · 덮개는 주민이 늘 때까지 보류).
독자 둘: **거점 화면 개발**(출발·귀환·손님·상자 UI) / **3D 개발**(원정 장면 정적 페이지 + 1~2분 따라 나가기).

**원칙**
- 수치·확률은 전부 서버가 expedition.json 에서 읽어 계산해 내려 준다. 화면은 계산하지 않는다(D2).
- 원정 결과는 **출발 때 시드(`uid|exp_id`)로 한 번 굴려 둔다**(D6). 따라 나가기는 그 목록의 앞 3칸을 손으로 펼치는 것이다. 서버가 행동을 하나씩 검증한다. 줍기는 서버가 내놓은 것 중에서만 고를 수 있어 **기댓값이 바뀌지 않는다**.
- 시간은 실제 시간(초, 유닉스 시각). 화면에 머무는 시간은 아무것도 깎지 않는다.
- 기존 필드는 그대로 두고 **추가만** 한다. 예외: 스팟 '발견'의 의미가 바뀐다(§9).
- 개발 훅은 `RELIC_DEV=1` 에서만 산다: `POST /api/dev/advance {uid, minutes}` 는 그 방주의 시계를 앞으로 민다(테스트·검수용).

## 0. 엔드포인트 요약

| 메서드 | 경로 | 누가 부르나 | 하는 일 |
|---|---|---|---|
| GET | `/api/entrance?uid=` | 거점 | 문간 사람·활동, 기다리는 사람, 손님, 잠자리, 잠수복, 공기 |
| POST | `/api/entrance/guest` `{uid, guest_id, accept}` | 거점 | 손님 들이기(빈 잠자리 필요) / 다른 돔으로 안내 |
| POST | `/api/entrance/suit_repair` `{uid}` | 거점 | 마모가 한계인 공용 잠수복 수리(재료) |
| GET | `/api/expedition/options?uid=` | 거점 | 갈 수 있는 목적지·길이·공기·잠수복·바깥 생물 |
| POST | `/api/expedition/preview` `{uid, members, dest, length}` | 거점 | 미리 보기 숫자(저장 안 함) |
| POST | `/api/expedition/start` `{uid, members, dest, length}` | 거점 | 출발 |
| GET | `/api/expedition?uid=` | 둘 다 | 지금 원정 상태(폴링용, 가볍다) |
| POST | `/api/expedition/recall` `{uid}` | 거점 | 불러들이기 |
| POST | `/api/expedition/seen` `{uid}` | 거점 | 귀환 장면을 봤다 |
| GET | `/api/expedition/scene?uid=` | 3D | 장면 데이터(지형 시드·경로·앞머리 줍기·갈림길·위험) |
| POST | `/api/expedition/scene` `{uid, action, ...}` | 3D | 따라 나가기 행동 하나(서버 검증) |
| GET | `/api/boxes?uid=` | 거점 | 봉인 상자 목록 |
| POST | `/api/box/pry` `{uid, box_id}` | 거점 | 7일 지난 상자를 억지로 연다(절반) |
| POST | `/api/scan` (기존) | 거점 | 같은 갈래 상자가 있으면 하나 연다 → 응답 `box_opened` |
| GET | `/api/ark` (기존) | 거점 | `expedition`·`expedition_return`·`air`·`guests`·`boxes`·`entrance` 덧붙임. 귀환·두드림 정산은 여기서 멱등으로 일어난다 |

## 1. 목적지·길이 (`dest`, `length`)

```json
"dest": {"kind": "door"}                                   // 문 앞 바닥
"dest": {"kind": "spot",    "id": "spot_jelly_bloom"}      // 아는 곳(원정으로 발견한 스팟)
"dest": {"kind": "clue",    "id": "spot_vent_garden"}      // 단서를 따라(스캔 단서는 있고 아직 발견 안 함)
"dest": {"kind": "unknown"}                                 // 모르는 쪽
"length": "short" | "half" | "long"                         // 30분 / 4시간 / 10시간(밤 넘기기)
```
- 길이 제한: 문 앞 short·half, 모르는 쪽 half·long, 스팟·단서는 그 스팟의 `min_length` 이상. `long` 은 에어락 Lv1 이상이 있어야 한다.
- 스팟·단서는 거점 깊이가 `min_base_depth_m` 이상이어야 한다.
- **첫 원정**(그 방주의 첫 번째)은 **튜토리얼**이다. 목적지는 문 앞, 위험 없음, 줍기 3번이고 셋째가 '빈 원' 상자(아무 갈래로나 열림)다. 출발하면 따라 나가기 장면이 열리고, 장면이 끝나면(`done`) 바로 돌아온다(`returns_at = started`).

## 2. `GET /api/expedition/options?uid=`
```json
{
  "air": {"value": 8.0, "supply": 8.0, "band": 1.0},
  "suits": {"total": 1, "usable": 1, "wear": [0], "wear_limit": 5, "pair_ok": false},
  "out": null,
  "lingering": {"creature": "claws", "name": "손톱 무리", "add": 0.25} | null,
  "residents": [{"id": "scout-1", "name": "…", "can": true, "why": null, "stats": {"hand":4,"eye":7,"breath":7,"nerve":5}}],
  "dests": [
    {"dest": {"kind": "door"}, "ko": "문 앞 바닥", "lengths": ["short","half"], "can": true, "why": null, "category": "unknown"},
    {"dest": {"kind": "clue", "id": "spot_vent_garden"}, "ko": "단서를 따라 · 열수구 정원", "lengths": ["half","long"],
     "can": false, "why": "거점이 60m 까지 내려와야 갈 수 있다", "category": "electronics"},
    {"dest": {"kind": "unknown"}, "ko": "모르는 쪽", "lengths": ["half","long"], "can": true}
  ],
  "lengths": {"short": {"ko": "잠깐", "minutes": 30, "tank": 2, "can": true, "returns_at": 1759…},
              "half":  {"ko": "반나절", "minutes": 240, "tank": 4, "can": true, "returns_at": 1759…},
              "long":  {"ko": "밤 넘기기", "minutes": 600, "tank": 6, "can": false, "why": "에어락 Lv1 이 필요하다"}},
  "tutorial": true
}
```
`residents[].can=false` 인 이유: 부상, 이미 밖에 나감. 습격 중에도 나갈 수는 있다(손톱 무리면 관문이 깨진다. 미리 보기가 그렇게 말한다).

## 3. `POST /api/expedition/preview` → 저장 안 함
```json
{"ok": true, "actions": 5, "carry": 6, "air_cost": 4, "air_after": 4.0, "returns_at": 1759…,
 "danger": {"p": 0.15, "lingering_add": 0.0,
            "kinds": [{"kind":"air","ko":"공기가 샌다","stat":"breath","weight":0.3,"p_pass":0.69}, …]},
 "rescue_p": 0.12, "clue_p": 0.08, "discover_p": 0.52, "visit_bonus": {"food": 4} | null,
 "finds_p": {"material": 0.36, "box": 0.10, "relic": 0.09, "empty": 0.45},
 "warnings": ["손톱 무리가 바깥에 있다 — 접촉 때 밖에 사람이 있으면 관문이 깨진다"],
 "errors": []}
```
`errors` 가 비어 있지 않으면 start 가 같은 이유로 400 을 낸다(공기 부족·잠수복·부상·이미 나간 조·길이 제한·깊이).

## 4. `POST /api/expedition/start`
요청 `{uid, members: ["rid"] | ["rid","rid"], dest, length}` → `{ok, expedition: <§5>, state: <public_state>}`.
- 공기는 출발 때 `tank × 인원`만큼 낸다. 밖에 나간 사람은 `outside` 에 들어간다. 방어(관문·점수)·생산·밤 판정에서 **없는 사람**이다. 배치(stations)는 기억해 두었다가 돌아오면 그 자리로 간다.
- 한 번에 한 조만 나갈 수 있다(`entrance.parties_out_max`).

## 5. `GET /api/expedition?uid=` — 폴링(가볍다)
```json
{"expedition": {"id": "exp-4-2", "members": ["scout-1"], "member_names": ["…"],
                "dest": {"kind": "unknown"}, "dest_ko": "모르는 쪽", "length": "half",
                "started": 1759…, "returns_at": 1759…, "now": 1759…, "progress": 0.42,
                "air_used": 4, "lingering": null, "recalled": false, "tutorial": false,
                "scene": {"open": true, "committed": false}},
 "expedition_return": null}
```
돌아올 시각이 지난 뒤 처음 읽으면 정산된다(멱등). `expedition` 이 null 이 되고 `expedition_return` 에 결과가 온다(§8). 화면이 `seen` 을 부를 때까지 계속 온다.

## 6. 따라 나가기 — `GET /api/expedition/scene?uid=` (3D)
```json
{"exp_id": "exp-4-2", "terrain_seed": "<uid>|unknown", "dest": {"kind":"unknown"},
 "started": 1759…, "returns_at": 1759…, "now": 1759…, "progress": 0.03,
 "members": [{"id":"scout-1","name":"…","role":"scout","stats":{…},"imprints":[…]}],
 "lantern_radius_m": 8,
 "waypoints": [{"x":0,"z":0}, {"x":6.2,"z":3.1}, …],        // 문(0,0)에서 시작해 돌아오는 고리. 진행도로 보간한다
 "head": {
   "picks": [{"i":0,"pos":{"x":4.0,"z":2.5},"state":"sparkle"}, {"i":1,…}, {"i":2,…}],  // 줍기 전엔 종류 비공개
   "fork": {"after":3, "pos":{"x":…,"z":…}, "options":[{"id":"lit","ko":"불빛 쪽","hint":"재료가 잘 나온다"},
                                                     {"id":"dark","ko":"어둠 쪽","hint":"상자·유물이 잘 나온다"}],
            "auto":"lit", "chosen":null},
   "danger": {"before_pick": 1, "kind":"beast", "ko":"큰 것이 지나간다", "stat":"nerve", "p_hide":0.62,
              "options":["hide","turn_back"], "auto":"hide", "chosen":null} | null
 },
 "carry": {"slots": 6, "used": 0, "items": []},
 "air_band": 1.0,                                            // 줍기마다 한 칸 준다(초가 아니다)
 "open": true, "committed": false, "next": "pick:0" | "danger" | "fork" | "drop" | "done",
 "discovers": {"spot_id":"spot_vent_garden","pos":{"x":…,"z":…}} | null,   // 참일 때만. 귀환 장면에서 discover() 연출
 "auto_rules": {"fork":"오늘 가장 모자란 쪽", "danger":"판정 확률 ≥ 0.55 면 숨는다", "drop":"상자 > 유물 > 재료"}}
```
- `open` 은 출발 뒤 **원정 길이의 10% 또는 30분 중 짧은 쪽** 안에서만 참이다. 그 뒤에는 자동 규칙으로 확정된다. 장면은 그 뒤에도 보기 전용(④ 들여다보기)으로 계속 읽을 수 있다.
- `waypoints` 의 단위는 m, 좌표계는 문이 원점이다(+x 바깥 트인 쪽, +z 아래). 지형은 `terrain_seed` 로 클라이언트가 만든다(같은 목적지는 같은 땅이다).

### `POST /api/expedition/scene` — 행동 하나씩, 서버가 순서를 검증한다
```json
{"uid":"…", "action":"pick",   "i":0}
{"uid":"…", "action":"danger", "choice":"hide" | "turn_back"}
{"uid":"…", "action":"fork",   "choice":"lit" | "dark"}
{"uid":"…", "action":"drop",   "keep":[0,2]}       // 손이 넘칠 때만(next == "drop"): 들고 갈 항목 번호
{"uid":"…", "action":"done"}                        // 나머지는 자동 규칙. 원정마다 한 번(멱등)
```
응답은 갱신된 scene. `pick` 은 그 칸의 **이미 굴려 둔** 내용을 공개한다:
`{"i":0,"state":"picked","item":{"kind":"material","res":"parts","ko":"부품 1"} | {"kind":"box","cat":"drink"} | {"kind":"relic","rarity":"rare"} | {"kind":"empty"}}`.
- 순서가 틀리면 400 이다. 위험이 그 줍기 앞에 걸려 있으면 `danger` 부터 해야 한다. 줍기는 0→1→2 순서다. 갈림길은 셋째 줍기 뒤에 온다.
- `turn_back`: 판정 없이 남은 줍기를 버리고 돌아온다. 다치지 않고 각인도 없다. `returns_at` 이 앞당겨진다.
- **기댓값**: 줍는 순서와 탭은 결과에 영향이 없다. 안 고른 것은 자동 규칙이 고른다. 갈림길 두 길은 기획이 기댓값을 같게 맞춘 값이다(내용물만 다르다). 위험 앞의 선택과 두고 갈 것은 플레이어의 결정이다.

## 7. 불러들이기 `POST /api/expedition/recall`
지금까지 지난 시간 비율만큼의 행동까지만 남기고 귀환을 예약한다. 도착은 20분 뒤이고, 에어락 Lv3 이면 즉시다. 도착 전까지는 아직 밖에 있는 사람이다(손톱 무리 관문). 기존 `POST /api/ark/recall` 도 원정이 있으면 이것을 부른다.
응답 `{ok, arrives_at, kept_actions, expedition, state}`.

## 8. 귀환 결과 — `/api/ark` 와 `/api/expedition` 의 `expedition_return`
```json
{"id":"exp-4-2", "members":[…], "dest_ko":"모르는 쪽", "length":"half", "returned_at":1759…,
 "haul": {"materials":{"parts":2,"water":1}, "boxes":[{"id":"box-…","cat":"drink"}], "relics":[{"rarity":"rare","shelf_slot":3}]},
 "left_behind": {"materials":{"food":1}, "boxes":0, "relics":0},
 "danger": {"kind":"beast","ko":"큰 것이 지나간다","ok":false,"choice":"auto"} | null,
 "injured": "누리" | null, "imprints": [<grant_imprints 결과>], "newcomer": {"guest_id":"…","name":"…"} | null,
 "rescued_but_no_room": false, "clue": {"spot_id":…,"name":…} | null,
 "discovered": {"spot_id":"spot_vent_garden","name":"열수구 정원","discovery_text":"…"} | null,
 "visit_bonus": {"power":2,"morale":2} | null, "breath_grew": [{"id":…,"to":8}],
 "greeted_by": {"id":…,"name":…} | null, "line": "…일지 한 줄…", "recalled": false, "tutorial": false}
```
**절대 없는 것**: 죽음, 못 돌아옴, 장비 소멸, 방 상실(규칙상 0). 잠수복은 마모만 된다.

## 9. 스팟: 단서와 발견을 나눈다
- `/api/spots`·`/api/rumors` 의 각 항목에 `"state": "none" | "clue" | "found"` 를 붙인다. 스캔 문턱을 넘으면 **clue** 다(소문 문장이 열린다). 원정으로 가서 찾으면 **found** 다. 기존 `unlocked` 는 "단서가 열렸다"는 뜻으로 남는다.
- 방 레벨업 조건(온실 Lv3 「위를 보는 숲」 등)과 바람은 **found** 만 센다.
- 모르는 쪽 원정에서 우연히 얻은 단서는 `clue` 가 된다(스캔 없이).
- 이전 저장: 이미 스캔 문턱을 넘었던(`rumors_seen`) 1막 스팟은 발견한 것으로 옮긴다. 진행이 뒤로 가지 않게 하기 위해서다.

## 10. 손님 — `GET /api/entrance?uid=`
```json
{"people":[{"id":…,"name":…,"activity":"hand|eye|breath|nerve|waiting|kid|null","activity_ko":"수선","waiting_for":"rid"|null}],
 "activities":{"hand":"rid","eye":"rid","breath":"rid","nerve":"rid"},          // 활동마다 덤은 한 사람 몫
 "guests":[{"id":"g-…","name":…,"role":"medic","role_ko":"의무병","stats":{…},"quirk":{…},
            "src":"knock|rescue","rescued_by":["rid"],"arrived":1759…}],
 "guest_spots": 2, "beds": {"total": 6, "used": 3, "free": 3},
 "suits": {…§2 와 같다}, "air": {…}}
```
- 두드림: 3일차에 고정으로 한 번 오고, 그 뒤 하루 `knock.daily_chance`(시드 `uid|day|knock`)다. 손님 자리가 찼으면 오지 않는다. 손님은 **스스로 떠나지 않는다**.
- 구조: 원정 결과로 온다(모르는 쪽 첫 원정은 반드시). 자리가 없으면 "가까운 돔까지 데려다주었다"로 끝나고 사기 +1 이다.
- `POST /api/entrance/guest {uid, guest_id, accept:true}` 는 빈 잠자리가 없으면 400 이다. 들이면 주민 목록에 들어간다. 구조된 사람과 구한 사람은 서로 신뢰 20 에서 시작한다. `accept:false` 는 벌도 보상도 없다.

## 11. 봉인 상자
`GET /api/boxes?uid=` → `[{"id","cat","cat_ko","found_day","age_days","from","pry_ok":false,"pry_in_days":3,"any":false}]`.
- **스캔으로 열기**: `POST /api/scan` 이 유효하면 같은 갈래(또는 `any`) 상자 중 **가장 오래된 것** 하나를 연다. 같은 바코드는 하루 한 상자다. 재스캔 감쇠와 무관하다(값 0 인 바코드도 열쇠가 된다). 응답:
  `"box_opened": {"id","cat","gained":{"water":4},"relic":{"rarity":"uncommon","shelf_slot":5} | null}` (아니면 null).
- **억지로 열기** `POST /api/box/pry {uid, box_id}` 는 7일 뒤부터 가능하고 값은 절반이다. 손이 가장 좋은 주민이 연다(`by`).

## 12. 공기
- 하루 공급 = (`air.daily_supply_base` + 온실 레벨 덤 + 문간 숨 활동 1) × 에어락 Lv2 배율. 생산 틱(8시간)마다 공급의 1/3 씩 차고, 공급을 넘지 않는다. `gauges.air` 가 실값이 된다(`fixed:false`, `value` = 남은/공급).
- `/api/ark` 의 `air: {"value": 5.0, "supply": 8.0, "band": 0.625}`.

## 13. 습격과의 관계(서버 규칙)
- 밖에 나간 사람은 지키지 못한다. 손톱 무리 관문(`all_inside`)은 원정대가 밖에 있으면 깨진다. 무작위 차출(`send_outside`)과 "하루 넘기면 outside 비우기"는 없앴다(밤 넘기기가 날을 넘긴다).
- 접촉 전 습격의 생물이 바깥에 있으면 출발하는 원정의 위험이 오른다(`raid_link.lingering_add`). 위험 종류의 60%가 그 생물 쪽(`lingering_kind`)이 된다.
- 덮개 보류 해제는 데이터로 한다: `threats.json` 의 `min_grade_override`(기획 키, 없으면 지금처럼 보류).

## 14. 구현 메모 (S15-A 구현 후 덧붙임)
- `/api/ark` 에 덧붙는 필드: `expedition`(§5 모양 또는 null), `expedition_return`(§8, seen 전까지), `air`, `guests`(수), `boxes`(§11 목록), `beds`, `spots_found`, `knock`(이번 요청에서 두드림이 왔으면 `{guest_id, name, role}`, 아니면 null).
- 미리 보기 `actions` 는 숨으로 보정한 **기댓값(소수)**이다. 실제 행동 수는 출발 때 시드로 반올림이 정해진다.
- 첫 원정(튜토리얼)은 요청한 목적지·길이와 무관하게 문 앞·잠깐·1명으로 바뀐다. 장면 `done` 전까지 30분 대비 시각이 잡히고, `done` 하면 바로 돌아온다.
- 손 칸 넘침(`next == "drop"`)은 앞머리 줍기 셋으로는 거의 일어나지 않는다(칸 4 이상, 상자 2칸). 보내 놓기 구간은 자동 규칙(상자 > 유물 > 재료)이다.
- 공용 잠수복 마모가 한계(5)에 닿으면 `POST /api/entrance/suit_repair {uid}` — 재료 `gear.repair_cost`.
- 스캔 한 번이 연 상자는 같은 응답의 `box_opened` 로만 알린다. 상자 목록은 `/api/ark.boxes` 또는 `/api/boxes`.
- 개발 훅 `POST /api/dev/advance {uid, minutes}` 는 RELIC_DEV=1 에서만 있다. 그 방주의 저장된 시각(생성·틱·원정·습격·상자)을 뒤로 민다 → 날짜도 넘어간다.

### §14-A2 (2026-10-04 수정)
- **미리 보기 행동 수**: `actions` 는 화면에 보일 **정수**(숨 보정 값의 내림 = 보장되는 수, 최소 1)이고, `actions_expected` 는 시뮬레이션용 기댓값(소수)이다. 실제 수는 출발 때 시드로 `actions` 또는 `actions+1` 이 된다.
- **상자 갈래**는 정본 아홉 가운데 하나만 간다: `food · drink · medical · electronics · stationery · book · apparel · tobacco · blank`. 튜토리얼 빈 원 상자가 `blank` 이고, 어떤 스캔으로도 열린다. 갈래를 모르는 목적지(문 앞·모르는 쪽)의 상자는 만들 때 최근 7일에 찍은 갈래 중 하나로 정한다. 그런 기록이 없으면 여덟 갈래 중 하나다. 옛 저장의 `any` 는 `blank` 로, `unknown` 은 시드로 정한 갈래로 옮긴다. `/api/boxes` 와 `/api/ark.boxes` 의 각 항목에 `pattern`(무늬 이름, `sealed_box.patterns.<cat>.name`)이 붙는다.
- **`/api/ark.entrance`** 는 `GET /api/entrance` 와 같은 모양이다(더 이상 null 이 아니다).
- **`expedition_return.recalled`** 는 불러들인 원정이면 늘 `true` 다.
- **`expedition_return.line`** 은 시나리오 조각 `expedition.log.*`(F2)을 head → haul → left_behind → box_found → shard_on_shelf → danger → imprint_gained → spot/clue → rescue → recall 순서로 이어 붙인 것이다. 튜토리얼은 `tutorial` 한 줄이다. 조각이 없을 때만 서버 임시 문장으로 돌아간다.
- **`GET /api/text/moments`** 는 `ui_moments.json` 에 `expedition_text.json` 의 최상위 묶음(`entrance · guest · expedition · sealed_box · spot`, 파일에 실제로 있는 것)을 덧붙여 돌려준다.
