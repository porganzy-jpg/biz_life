# API_S19 — 핵심 루프 A 서버 계약 (클라이언트 개발용)

작성: 개발(서버), 2026-10-05. 사양 `docs/CORE_LOOP_A.md`, 수치 `data/balance/core_a.json`(없으면 `data/draft/core_a.json`),
문장·매칭 `data/resident_tastes.json`·`arcs.json`(+`arcs2.json`)·`room_decor.json`·`visitors.json`·`beats.json`·`next_visit.json`
(각각 `data/` 에 있으면 그것, 없으면 `data/draft/`).

**원칙**
- 기존 필드는 지우거나 뜻을 바꾸지 않는다. 전부 **추가**다. 예외는 §9(바뀐 동작) 에 따로 적었다.
- 서버가 문장을 조립해 주는 곳에는 치환이 끝난 한 줄(`*_ko` 또는 `announce`/`line`)과 원본 키(`*_key`)가 같이 온다.
- 수치는 서버가 계산해 내려 준다. 화면은 계산하지 않는다(D2).
- 시드는 전부 `uid|day|목적`(D6). 같은 날 같은 방주 = 같은 필요·같은 제안.

## 0. 요약 — 화면이 새로 부를 것

| 엔드포인트 | 언제 | 요청 |
|---|---|---|
| `POST /api/scan` | (그대로) 응답에 `where` 가 붙는다 | — |
| `POST /api/give` | 「어디로」 줄에서 하나 누름 / 끌어다 놓기 / 닫기(=선반) | `{uid, scan_id? , relic_id?, target}` |
| `POST /api/decor/remove` | 방 꾸밈 칸의 물건을 선반으로 되돌림 | `{uid, slot, item_id}` |
| `POST /api/arc/ask` | 매듭이 묻는 것 하나에 답함(안 해도 됨) | `{uid, arc_id, step, choice? , relic_id? , resident_ids?}` |
| `POST /api/feast` | 잔치(비트 10일째·넘치는 식량의 출구) | `{uid, pair:[rid, rid]}` |
| `GET /api/leaving?uid=` | 세션을 닫을 때(≡ → 잠깐 쉬기, 창 닫기 직전) | — |
| `POST /api/overnight/seen` | (그대로) 밤사이 패널을 **닫을 때도** 부른다 | `{uid}` |

`GET /api/ark` 응답에 새 키: `core`, `needs_today`, `room_decor`, `visits`, `beat_today`, `next_visit`, `session`, `arc_events`, `entrance_airlock` (§2~§7).

---

## 1. 「어디로」 — `POST /api/scan` 응답의 `where`

```json
"card": {"...기존...": "", "id": "8801043015097-1759650000000", "subtype": "noodle", "subtype_ko": "면"},
"where": {
  "scan_id": "8801043015097-1759650000000",
  "suggest": [
    {"kind": "resident", "target": {"resident_id": "cook-123"}, "name": "도담", "role": "cook",
     "tier": "chain_beat", "icon": "chain", "value": 1.2, "mult": 1.0,
     "reason_ko": "이야기가 움직입니다", "arc_id": "arc_cook_seat", "step": 2},
    {"kind": "resident", "target": {"resident_id": "scout-9"}, "name": "하루", "role": "scout",
     "tier": "need", "icon": "need", "value": 1.1, "mult": 1.0, "reason_ko": "오늘 필요하신 물건"},
    {"kind": "room", "target": {"slot": 2}, "room_id": "pantry", "name": "식량창고",
     "tier": "decor", "icon": "decor", "value": 1.0, "tag": "warm_kitchen", "tag_ko": "따뜻한 부엌",
     "tag_have": 1, "tag_need": 2, "free_slots": 1, "reason_ko": "따뜻한 부엌까지 하나"}
  ],
  "shelf": {"target": "shelf", "value": 0.8, "label": "선반에"},
  "default": "shelf",
  "compact": false
}
```
- `suggest` 는 최대 3개, `value` 높은 순(같으면 chain > memory > need > like > decor). 제안이 없으면 `[]` — 선반만 보인다.
- `tier` ∈ `chain_beat | memory | need | like | decor | plain | not_for_me`. 제안에는 `plain`/`not_for_me` 가 오지 않는다(끌어다 놓기로만 생긴다).
- `icon` ∈ `chain | memory | need | like | decor`. 「어디로」 줄의 작은 아이콘.
- `compact: true` = 이번 세션에서 둘째 스캔부터. 줄을 작게 그려 달라(design 위험 4).
- `where` 는 선반 자리와 무관하다. 스캔이 선반/창고 상자에 놓은 물건은 **준 순간** 그 사람·방으로 옮겨 간다.
- 값 0 재스캔(감쇠 0.1)도 `where` 가 온다. 재스캔의 새 쓸모다.

## 2. `POST /api/give`

요청
```json
{"uid": "u1", "scan_id": "8801043015097-1759650000000", "target": {"resident_id": "cook-123"}}
{"uid": "u1", "scan_id": "...", "target": {"slot": 2}}
{"uid": "u1", "scan_id": "...", "target": "shelf"}
{"uid": "u1", "relic_id": "<선반/창고 상자 물건의 card_id 또는 stored id>", "target": {"resident_id": "..."}}
```
- `scan_id` = 스캔 응답 `where.scan_id`(= `card.id`). 같은 `scan_id` 는 **한 번만** 줄 수 있다(두 번째는 400 `"이미 자리를 정한 물건입니다"`). 오늘·어제 스캔만 유효.
- `relic_id` = 선반(`shelf[].card_id`)이나 창고 상자(`stored[].id`)에 있는 물건. 진열을 다시 정할 때.
- 재료는 **들지 않는다**(core_a `give_does_not_remove_materials`).

응답
```json
{"ok": true, "tier": "need", "value": 1.1, "mult": 1.0, "diminish": null,
 "target": {"resident_id": "cook-123"}, "who": {"id": "cook-123", "name": "도담", "role": "cook"},
 "reaction": {"announce_key": "resident_tastes.announce.give_needed",
              "announce": "「…」, 도담 님께 드렸습니다. 마침 필요하셨던 물건이랍니다.",
              "line_key": "resident_tastes.roles.cook.needed_lines.0", "line": "마침 바닥이 보이던 참이었어요. …"},
 "effects": {"morale": 2, "room_bonus": {"slot": 2, "pct": 10, "day": 5},
             "keepsake": {"name": "…", "line": "도담 님은 머리맡에 「…」 하나를 두고 주무십니다."},
             "memory": null, "arc": null, "decor": null, "returned_to_shelf": false},
 "item": {"name": "…", "category": "food", "subtype": "grain"},
 "state": { "...public_state..." : "" }}
```
- `diminish`: `{"kind": "same_person_today", "mult": 0.5}` 또는 `{"kind": "same_item_3days", "mult": 0.3}`(둘 다면 곱). 값이 깎여도 반응 문장은 그대로, 사기만 줄어든다(소수는 `morale_frac` 에 쌓인다).
- `tier: not_for_me` → `effects.returned_to_shelf: true`, 물건은 선반(또는 창고 상자)으로 돌아간다. 벌은 없다.
- `effects.memory`: `{"id": "cook_one_drop", "announce": "…", "line": "…"}` — 사람×기억마다 한 번.
- `effects.arc`: `{"arc_id", "title", "step", "steps", "size": "small|big", "announce", "line", "beat", "log", "ask", "done": bool, "deferred": bool}`. `deferred: true` = 조건은 찼지만 오늘 큰 매듭이 이미 나왔다 → 다음 조용한 순간(다음 `/api/ark`)에 `arc_events` 로 온다.
- `effects.decor`(방에 놓을 때): `{"slot", "room_id", "items": n, "cap": n, "tag_added": {"id","ko","announce","look"} | null, "tags": [...]}`. 칸이 차 있으면 400 `"꾸밈 칸이 다 찼습니다"`(먼저 `/api/decor/remove`).
- 사람에게 준 물건은 그 사람 곁에 남는다(`core.residents[rid].items`). 처음 `like` 받은 물건이 머리맡 물건(keepsake)이 된다.

## 3. `GET /api/ark` — `core`, `needs_today`

```json
"core": {
  "residents": {
    "cook-123": {
      "needs_today": [{"category": "food", "subtype": ["grain"], "ko": "곡물·밥"}],
      "likes": [{"category": "food", "subtype": ["noodle","sauce","canned"], "ko": "면·양념·통조림·절임"}, "..."],
      "twist": {"like": {"category": "drink", "subtype": "milk", "ko": "우유", "line": "…"},
                "dislike": {"category": "stationery", "subtype": "toy", "ko": "장난감", "line": "…"}},
      "keepsake": {"name": "…", "category": "food", "day": 3} ,
      "items": [{"name": "…", "category": "food", "day": 3}],
      "memories_seen": ["cook_one_drop"],
      "given_today": 1,
      "arc": {"id": "arc_cook_seat", "title": "앉아서 먹는 저녁", "step": 1, "steps": 4,
              "next": {"step": 2, "open": true, "opens_day": 4, "hint_ko": "식품 서로 다른 것 2개", "icon": "chain",
                       "ask": null},
              "done": false}
    }
  }
},
"needs_today": [{"resident_id": "cook-123", "name": "도담", "need": {"category":"food","subtype":["grain"],"ko":"곡물·밥"},
                 "announce": "도담 님이 오늘 곡물·밥 쪽 물건을 찾으십니다."}]
```
- 필요는 하루에 사람마다 하나(시드 `uid|rid|day|need`). 아침 `overnight` 에도 `kind: "needs"` 한 장으로 온다.
- `arc.next.open` = 그 매듭을 지금 풀 수 있나(엇갈림 `min_days_after_prev` 가 지났나). 화면은 머리 위 매듭 아이콘에 쓴다.

## 4. 방 꾸밈 — `room_decor`
```json
"room_decor": {"2": {"room_id": "pantry", "level": 1, "cap": 2,
                     "items": [{"id": "dec-…", "name": "…", "category": "food", "subtype": "noodle", "boxed": false}],
                     "tags": [{"id": "warm_kitchen", "ko": "따뜻한 부엌", "have": 2, "need": 2, "on": true, "look": "…"}],
                     "boxed": []}}
```
- 칸 = 방 레벨 1/2/3 → 2/3/4. 같은 꼬리표 `feeds` 에 맞는 물건 둘이면 꼬리표가 붙는다(방마다 많아야 둘).
- 금 간 방: 꾸밈 물건은 `boxed` 로(창고 상자에 들어간 것으로 표시), 수리하면 제자리. 물 찬 방: 물건은 `stored`(창고 상자)로, 되찾으면 돌아온다.

## 5. 방문자 — `visits`
```json
"visits": [{"day": 6, "slot": 2, "room": "식량창고", "tag": "warm_kitchen", "kind": "visitor",
            "visitor_id": "steam_eel", "ko": "김 따라온 꼬마 장어", "where": "window", "first": true,
            "line": "관리실에서 알려 드립니다. 식량창고 김 서린 창에 …"},
           {"kind": "octopus", "slot": 2, "line": "문어가 그 방에서 한참 놀다 갔습니다."},
           {"kind": "residents", "slot": 2, "resident_ids": ["…"]},
           {"kind": "guest_tilt", "slot": 2, "roles": {"cook": 2}},
           {"kind": "newhuman_tilt", "slot": 2, "lineage": "…"}]
```
- 하루 한 번 굴린다(`uid|day|visit|slot`). 확률: residents 1.0 · octopus 0.5 · small_fish(=visitors.json 손님) 0.5 · gardener 0.15. 손님·신인류는 **오는 횟수는 그대로**, 두드림·구조 때 역할 가중만 ×2.
- 아침 `overnight` 에 `kind: "visit"` 로도 온다.

## 6. 비트 캘린더 — `beat_today`, `session`
```json
"beat_today": {"play_day": 4, "beat": "first_threat_longneck", "star": "관리실에서 …", "teaser": "…",
               "alt": false, "big": true, "new": true, "queued": 0},
"session": {"n": 7, "new": true, "big_windows": 1, "big_left": 1, "evening": false}
```
- 날 = **켠 날의 차례**(실제 날짜가 아니다). 사흘 쉬어도 다음은 다음 비트. 1~14는 `beats.json`, 15일째부터는 「하루 하나·주 하나·두 주 하나」 규칙으로 서버가 고른다(`beat` = `daily_*`/`weekly_log`/`fortnight_*`).
- `new: true` 는 이 세션에서 처음 보여 주는 것. 화면은 그때 한 번 띄우고, 같은 세션의 다음 `/api/ark` 에서는 `new: false`.
- 큰 창(`big`)은 세션당 2개까지. 넘치면 `queued` 에 남고 다음 세션에 온다.
- 세션 = `/api/ark` 사이 간격이 30분을 넘으면 새 세션.

## 7. 떠날 때 카드 — `next_visit`, `GET /api/leaving`
```json
"next_visit": {"kind": "expedition_return", "title": "다음에 켜시면",
               "line": "하루 님이 오후 3:40쯤 문간으로 돌아오십니다. 마중은 관리실이 하겠습니다.",
               "data": {"return_at": 1759660000}}
```
`GET /api/leaving?uid=` → `{"title": "이번에 바뀐 것", "changed": ["…", "…"], "next_visit": {…}, "close_label": "잠깐 쉬기"}`.
- 약속 종류(우선순위): `expedition_return > guest_at_door > arc_beat_ready > box_key_hint > visitor_expected > need_tomorrow > nothing`. **서버가 지킬 수 있는 것만** 약속한다(원정은 실제 귀환 시각, 매듭은 실제로 열린 것, 손님은 실제로 문간에 있는 사람).

## 8. 그 밖의 새 필드·엔드포인트
- `POST /api/arc/ask {uid, arc_id, step, choice}` / `{…, relic_id}` / `{…, resident_ids:[a,b]}` → `{ok, arc_id, step, applied, after_ask_ko, state}`. 안 고르면 `default` 로 간 것으로 친다(타이머 없음 — 매듭을 넘기면 default).
- **`arc.ask` 종류별 예** — 매듭이 풀리면 `arc_events[].ask`, 그 뒤로는 `core.residents[rid].arc.next.ask`(답하기 전까지)에 온다. `next.ask.step` 이 답할 매듭 번호다.
  1. 버튼 고르기(`kind: "choice"`) — 기술자 2매듭
     ```json
     "ask": {"step": 2, "kind": "choice", "label": "오늘 밤 발전실 전기를 대야에 조금 돌릴까요?",
             "options": ["돌리기", "아껴 두기"], "default": "아껴 두기"}
     ```
     → `POST /api/arc/ask {"uid","arc_id":"arc_engineer_warm","step":2,"choice":"돌리기"}`
  2. 유물 고르기(`kind: "place"` 방에 올리기 / `kind: "give"` 그 사람에게 건네기) — 선반·창고 상자에서 `category`(+`subtype`)가 맞는 것만 고르게 한다
     ```json
     "ask": {"step": 2, "kind": "place", "label": "상에 올릴 것", "room": "pantry", "category": "food",
             "subtype": null, "default": "most_polished"}
     "ask": {"step": 2, "kind": "give", "label": "그림 있는 책 한 권 드리기", "category": "book",
             "subtype": ["field_guide", "story"], "default": "skip"}
     ```
     → `POST /api/arc/ask {"uid","arc_id":"arc_cook_seat","step":2,"relic_id":"<shelf[].card_id 또는 stored[].id>"}`.
     맞지 않는 물건은 400 `"그 물건은 맞지 않습니다"`. 응답 `applied` 는 `/api/give` 응답과 같은 모양(꾸밈·반응), `after_ask_ko` 는 매듭의 뒷말.
  3. 두 사람 고르기(`kind: "pick_residents"`) — 요리사 잔치 사슬 2매듭
     ```json
     "ask": {"step": 2, "kind": "pick_residents", "label": "누구 둘을 마주 앉힐까요?", "n": 2, "default": "lowest_trust_pair"}
     ```
     → `POST /api/arc/ask {"uid","arc_id":"arc_cook_feast","step":2,"resident_ids":["<rid>","<rid>"]}`. 고른 두 사람은 다음 매듭 문장의 `{other}` 가 된다.
     잔치 비트(켠 날 10)의 단독 잔치는 `POST /api/feast {"uid","pair":["<rid>","<rid>"]}` 로 같은 두 사람 고르기 화면을 쓴다.
  안 고르면 `default` 로 간 것으로 친다(타이머 없음). `skip`/`most_polished`/`lowest_trust_pair` 는 화면의 기본 선택 표시용이다(서버는 답이 없을 때 아무것도 하지 않는다).
- `POST /api/decor/remove {uid, slot, item_id}` → `{ok, back_to: "shelf"|"stored", state}`.
- `POST /api/feast {uid, pair}` → 식량 30·물 20, 하루 한 번, 사기 +3, 두 사람 신뢰 +5, 다음 아침 한 줄. 모자라면 400.
- `entrance_airlock: {"level": 0|1|2|3}` — 에어락을 **문간 증설**로 지을 수 있다: `POST /api/ark/build {uid, room_id:"airlock", slot:-1}`(칸을 먹지 않는다), 올리기 `POST /api/ark/upgrade {uid, room_id:"airlock"}`. 칸에 지은 옛 에어락도 그대로 동작한다.
- `storage.overflow` 가 이제 `{"day", "lost": {...}, "converted": {"morale": n, "trade": n}, "ko": "창고가 차서 식량 16은 들이지 못했습니다. 대신 …"}` 이고, 아침 `overnight` 에 `kind: "overflow"` 로 온다(말없이 버리지 않는다).
- `overnight.title`·`overnight.open` 은 지금 시각대로(아침 5~11 / 낮 11~17 / 저녁 17~21 / 밤 21~5, `ui_moments.morning.by_time`). 한 번 내려간 밤사이 항목은 다음 날 저절로 비워진다(닫기만 해도 쌓이지 않는다).
- `overnight` 항목 `kind: "octopus"` 에 `who: "문어"`(이름을 지었으면 그 이름)·`label`·`ko`(「문어가 물어 온 것: …」).
- 습격 단서 모드 미리보기: 관문은 맞는데 점수가 모자라면 `raid.preview.short_of: "손"|"눈"|"숨"|"담"|"도구"|"불"` 한 단어.
- 값 낮은 재스캔 반응(`zero_reaction`)은 `ui_moments.shelf.rescan_low[]` 7줄을 돌려 쓴다(`kind: "rescan_low"`).
- 공방 건설비 잔해 −50%(기획 수치가 오기 전 임시). 선반 칸이 늘면 창고 상자에서 자동으로 올라온다(`shelf_autofill` 응답 필드). 식량창고를 잃으면 창고 상자가 선반 구실(`shelf_room.fallback: true`).
- 1주차 단서 하나는 반나절로 갈 수 있다(`expedition/options` 의 그 단서 `lengths` 에 `half`, `week1_half: true`).

## 9. 바뀐 동작
- **바람(wishes)은 저절로 이뤄지지 않는다.** `wishes_new` 는 사슬 끝 매듭이 풀릴 때만 생긴다. `GET /api/wishes` 의 `done` 은 그 사람 사슬이 끝났는지다(옛 저장에서 이미 이룬 바람은 사슬을 끝낸 것으로 옮겼다).
- 「빈 자리」 각인은 사건 쪽지 실패 같은 가벼운 일에는 주지 않는다. 방을 잃었을 때만(그 방에 있던 사람이 아니라 지켜본 한 사람).
- 사건 보상 `free_pack` 은 자원이 아니라 봉인 상자 하나가 된다(`applied.box`). 자원 줄에 `free_pack` 키는 더 이상 없다.
- 1막 사건 풀에서 육상 문장 카드(「숨겨진 유물 창고」)는 빠진다.
- 꾸밈 물건이 있는 방·사슬 물건이 있는 방은 습격 대상 추첨 가중 ×1.5. 첫 주(켠 날 7 이하)에는 꾸밈에 따른 긴목 가중이 없다.

## 10. S20-A 바뀐 것 (2026-10-06)
- `where.suggest[].tier` 에 **`warm`**(아이콘 `warm`, 0.9V, 「반가워하실 것 같습니다」)이 생겼다. 같은 갈래를 좋아하거나 필요한 사람이고, 그런 사람이 없으면 덜 받은 사람을 넣는다. **주민이나 꾸밈 칸이 하나라도 있으면 선반 밖 선택지가 늘 둘 이상**이다. 대체로 들어간 줄에는 `fallback: true` 가 붙는다. 같은 값끼리의 순서는 날·물건마다 달라진다.
- `reaction` 은 선반·방·warm 에서도 늘 문장이 온다(`announce`·`announce_key`, 방은 `line` 도 있다). 키는 `ui_moments.give.<shelf|place_progress|place_tag_formed|place_plain|soft_thanks>.<n>` 이고 줄을 돌려 쓴다.
- `next_visit` 은 지킬 수 있는 약속을 모두 모아 순서대로 고른다: 귀환 > 매듭 > 손님 > 방문자 > 상자 > 모자람. 다른 약속이 있으면 지난 세션과 같은 문장은 쓰지 않는다. 같은 세션 안에서는 바뀌지 않는다.
- 사슬 첫 매듭이 열리는 날은 합류한 날 + `days_since_join` 이다(또는 `opens_day`). 2일째 끝까지 아무 매듭도 안 열리면, 가장 이른 사람 하나의 첫 매듭이 늦어도 2일째에 열린다. 그 매듭의 밤 조건은 저녁 세션으로 대신한다.
- `POST /api/feast`
  - 열리는 때: 켠 날 10부터, 7일에 한 번
  - 비용: 식량 24·물 12
  - 효과: 사기 +3, 그 자리에 있는 모두가 서로 신뢰 +5
  - 응답에 `present`(그 자리에 있던 사람들)가 붙는다. `pair` 는 문장에 쓸 두 사람이다.
- 방문 행 `kind: "visitor"` 에 `effect` 가 붙는다(core_a `visitor_effects`).
- `/api/scan` 의 짧은 줄: `first_meet[].line_short`, `voice.text_short`(없으면 null).
