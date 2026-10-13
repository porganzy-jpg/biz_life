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

## 11. S21 바뀐 것 (2026-10-11, 3차 플레이테스트 고침)
- **감쇠**(`core_a.json give_place.diminish`)
  - 같은 사람: **같은 세션 안에서만** ×0.8. 아침·저녁은 따로 센다. 세션을 모르면 4시간 간격을 새 세션으로 본다.
  - 같은 물건 사흘: ×0.6.
  - 둘이 겹치면 곱하지 않고 **작은 쪽 하나만** 쓴다. 그래서 `diminish` 에는 항목이 하나만 온다.
  - `kind` 이름은 그대로다(`same_person_today` / `same_item_3days`).
- **꾸밈**
  - Lv1 칸은 3이다(`core_a decor.slots_by_level`).
  - 「어디로」의 방 제안은 그 방에서 **가장 앞선 꼬리표 하나만** 권한다. 그 꼬리표에 맞지 않는 물건은 그 방이 제안에 나오지 않는다.
  - 방에 놓을 때의 반응(`place_progress`) 꼬리표 이름은 제안한 그 꼬리표다.
  - 방주에서 첫 꼬리표가 붙으면 **다음 날 그 방 손님이 확정**이다. `next_visit` 의 `visitor_expected` 로 미리 약속할 수 있다.
- **제안 순서**: warm 이 아닌 제안이 하나라도 있으면 warm 은 1순위에 오지 않는다.
- **비트**
  - 3일째: 그날 열린 매듭 물음이 없으면 `beats.json` 의 `star_no_ask` 를 쓴다.
  - 5일째: 문어 색 조각을 선반에 놓는다. 선반이 차면 창고 상자에 놓는다. `card_id` 는 `oct-<find>-<day>` 이다.
  - 5일째: `/api/ark.octopus_gift_where` 에 스캔과 같은 모양의 「어디로」가 온다. 추가 키는 `relic_id`·`name` 이다.
  - 5일째 조각은 `POST /api/give {relic_id, target}` 으로 건넨다.
- **떠날 때 `arc_beat_ready`**: 그 매듭을 풀 물건이 선반·창고 상자에 있거나, 답하지 않은 물음이 있을 때만 약속한다. 물음이면 `data.ask_step` 이 붙는다.
- **`POST /api/give` 의 scan_id**: 스캔 기록이 없어도, 그 스캔 물건이 선반·창고 상자에 있으면 받아 준다(`scan_id` = `card_id`). 스캔 기록은 80개까지 넣은 순서대로 둔다.
- **`/api/ark.novelty`**: 켠 날 4부터 세션마다 한 번 온다. 그 세션에 새것이나 모르는 결과(새 방문자·매듭·밤사이 새 항목)가 없으면 아래 순서로 하나를 만든다.
  - `kind` 순서: `memory_hint` → `visitor_hint` → `keepsake_hint` → `octopus_hint`.
  - 필드: `{kind, line, data, resident_id?}`.
  - 밤사이 `kind: "novelty"` 로도 들어간다. 같은 실마리는 다시 쓰지 않는다.
  - 다른 새것이 있으면 `null` 이다.
  - 문장은 `ui_moments.novelty.<kind>[]` 를 종류마다 돌려 쓰고, 응답에 `line_key`(`novelty.<kind>.<n>`)가 붙는다. 배열이 없으면 서버 기본 줄이고 `line_key` 는 null 이다.
- **`POST /api/arc/ask`**
  - `skip: true` 를 보내면 물건·사람 고르기를 넘긴다.
  - 응답에 `answer` 가 붙는다: 고른 선택지, `done`, `skip` 중 하나.
  - `after_ask_ko` 는 **null 이 아니다**. 고르는 순서: `beat.after_ask` 의 답 키(문자열이면 그대로) → `_default` → 서버 기본 줄.
- **warm 반응**
  - 관리실 줄(`announce`)은 `give.soft_thanks` 이다.
  - 주민 줄(`line`)은 그 역할의 `warm_lines` 이다.
  - 같은 사람에게 줄을 돌려 쓴다. 8줄이라 7일 안에 같은 줄이 다시 나오지 않는다.
  - `warm_lines` 가 없으면 `line` 은 null 이다. 같은 문장을 두 번 내지 않는다.
  - `liked_lines`·`needed_lines` 도 같은 방식으로 돌려 쓴다.
- **`/api/ark` 의 필요 받음 표시**(S21 후속): `core.residents[rid].given_need_today: bool`, `needs_today[].met: bool`. 오늘 그 사람이 받은 물건 중 오늘의 필요에 맞는 것이 있으면 true 다(사슬·기억 등급이어도). 돌려준 물건은 세지 않는다. 화면 `base_core.js` normTaste 가 「받음」 표시에 이 값을 읽는다.

## 12. S22 바뀐 것 (2026-10-11, 1단계 「약속을 지키는 루프」 앞쪽)
수치는 `core_a.json` 의 `s22_server_numbers`(기획 확정)에서 읽는다. 문장은 시나리오 데이터에서 읽는다. 필드 이름은 시나리오·클라이언트 에이전트에게 알렸다.

### ① 「이게 뭐예요?」 — 하위 종류는 플레이어가 고른다
- **묻는 바코드**: 하위 종류가 정해지지 않은 바코드다. 알려진 가문 18곳, 책(978/979), 정체불명은 묻지 않는다.
- **`/api/scan` 응답 `where.subtype_pick`**: `{needed: true, options: [{id, ko}], suggest: {id, ko, arks}|null, ask_ko, suggest_ko}`
  - 묻지 않는 바코드면 null 이다.
  - `options`: 그 갈래 `_subtypes` 앞에서부터 최대 6개다. 가문 전용 종류(음료 alcohol)는 뺀다.
  - `suggest`: 다른 방주의 이름이다. 서로 다른 방주 3곳 이상이고 같은 답이 60% 이상일 때만 온다. `arks` 는 그 이름으로 부른 방주 수다.
- **`POST /api/scan/subtype {uid, scan_id, subtype}`**
  - 그 방주에서 그 바코드의 하위 종류를 **영구 고정**한다. 이미 정했으면 400, 다른 갈래 종류면 400 이다.
  - 응답: `{ok, card, where, subtype, subtype_ko, done_ko}`. `card` 는 새 이름·종류가 반영된 카드다. `where` 는 다시 계산한 「어디로」다.
  - 선반·창고 상자 물건의 이름도 바뀐다.
  - 다시 찍으면 고른 값으로 만든다. 고르지 않은 바코드는 예전과 바이트까지 같은 카드다.
- **전역 투표**: `subtype_votes` 표에 방주마다 한 표(uid·바코드·갈래·종류·시각)를 넣는다. 화면에는 숫자만 나간다.
- **카드 필드**: `card.subtype`·`card.subtype_ko` 이고, `card.history: [{day, to_name, resident_id|slot}]` 가 새로 붙는다. history 는 이 방주에서 그 바코드를 전에 누구에게, 어느 방에 줬는지다. 스캔 응답에는 `card.history`, `/api/give` 응답에는 `item.history` 로 온다.
- **의도**: 그날 필요를 처음 보여 준 시각(첫 `/api/ark`) **뒤에** 찍은 물건으로 그 사람의 필요를 채우면, `/api/give` 응답에 `intent: true` 가 붙는다(같은 사람은 하루 한 번).
  - tier 가 need 이면 문장이 `resident_tastes.announce.give_intent[]` 와 `roles.<role>.intent_lines[]` 로 바뀐다.
  - 값 보너스는 없다.

### ② 멈춘 사슬
- 좁은 조건(하위 종류·희귀도) 매듭이 열린 뒤 **켠 날 2일** 동안 안 풀리면 조건이 넓어진다.
  - 하위 종류 조건 → 그 갈래 전체.
  - 희귀도 조건 → 한 단계 아래.
- 넓어지면 `core.residents[rid].arc.next` 에 `soft: true` 가 붙고, `hint_ko` 도 넓은 말(예: 「전자」)로 바뀐다. `soft_hint` 는 데이터에 그 줄이 있을 때만 온다.
- `novelty` 의 `memory_hint` 는 이 방주가 실제로 찍은 적 있는 하위 종류만 귀띔한다.

### ③ 꾸밈 → 손님
- **꼬리표는 방주에 한 번만** 붙는다(`core.tags_formed`). 다른 방이 이미 가진 꼬리표는 그 방에 권하지도 붙이지도 않는다.
  - `room_decor[slot].tags[].elsewhere: true` 가 그 표시다.
- 제안한 꼬리표가 실제로 붙는 꼬리표다. 둘이 함께 차면 제안한 쪽을 먼저 말한다.
- 값이 같은 제안 사이에서는 많이 찬 꼬리표 방이 먼저 온다.
- **같은 이름 방 구분**: `where.suggest[].name` 에 구분하는 말을 붙인다. 그 방에 선 사람이 있으면 「거주실(소리 님 방)」, 없으면 「거주실(위층)」 꼴이다. 원래 이름은 `name_ko` 로 따로 온다.
- **첫 꼬리표가 붙으면 다음 세션(30분 이상 뒤)에 그 방 첫 손님이 와 있다.** `visits[]` 의 그 줄에는 `forced: true` 가 붙는다. 그날 못 오면 다음 날 굴림에서 확정이다.
- **`/api/ark.decor_trace: [{slot, tag, tag_ko, visitor_id, ko, line}]`**: 꼬리표까지 하나 남은 방의 흔적이다(예고). `line` 은 `visitors.json trace[]` 에서 하루에 하나 고른다.
- **`/api/ark.visitors_book: [{id, ko, tag, count, first_day, souvenir, souvenir_name}]`**: 여덟 칸이고, 아직 안 온 손님은 count 0 이다.
  - 같은 손님이 세 번 오면 기념품 유물이 선반에 놓인다(`souvenir: {name, relic_id, day}`).
  - 그때 밤사이에 `kind: "souvenir"` 줄이 들어간다.

### ④ 4차 버그
- r4-1: 이미 푼 매듭(기록이 남은 번호)은 다시 제안하지도 풀지도 않는다. 같은 조건을 그대로 재현하지 못해 방어로 막았다.
- r4-2: 선반 물건(`relic_id`)을 건넬 때도 「어디로」의 warm 제안을 지킨다. 그래서 돌려받지 않는다. 문어 조각은 한 번 건네면 `octopus_gift_where` 가 null 이 된다.
- r4-3: 아직 온 적 없는 손님 약속은 `next_visit.json promises.visitor_expected_first[]` 를 쓴다(「또」가 없는 줄).
- r4-4: 6일째 구조가 없으면 `beats.json` 의 `star_no_rescue`({name} = 처음 셋 뒤에 온 가장 최근 식구)를 쓴다. 그런 식구도 없으면 `alt` 를 쓴다.
- r4-5: 넘침 문장이 「식량 21개는 들이지 못했습니다. 대신 사기를 3 올려 두었습니다」 꼴이다. `(은)는` 같은 조사 자리표시가 없다.
- r4-6: 줄에 `requires_role` 가 붙어 있고 그 역할이 없으면 `<field>_alt` 를 쓴다. 대상은 문어 선물 `line`, 사슬 매듭 announce·line·beat·log, `{text, requires_role, text_alt}` 꼴의 줄이다.
- r4-7: 매듭의 관리실 줄이 비면 이 순서로 대신한다: `ui_moments.arc_fallback.octopus_with[]`(문어 매듭) → 문어 서술(`beat`) → 입말.
- 넘침 수치는 기획 확정값을 쓴다: 식량·물 5:1, 사기 하루 3까지, 그 밖 5:1.

### ⑤ 아침 실마리
- `novelty` 판정에서 매일 되풀이되는 줄과 비트는 새것으로 세지 않는다. 되풀이되는 줄은 머리맡, 사슬 뒷날 줄, 두 번째 이후 방문이다.
- 진짜 새것은 이것뿐이다: 첫 방문, 매듭, 귀환, 두드림, 바람, 각인, 단서, 기념품.

### ⑥ 두 번째 기회
- `GET /api/leaving` 과 `/api/ark` 에 `missed_chain: {resident_id, name, kind, line}|null` 이 붙는다.
  - 그날 「어디로」가 매듭·기억을 제안했는데 닫았거나 다른 데 준 경우에, 그 사람이 아직 못 풀었으면 한 줄 온다.
  - 문장은 `next_visit.json promises.missed_chain[]` 이다.

### ⑦ 그림용 필드
- `core.residents[rid].keepsakes_recent: [{relic_id, name, category, subtype, prop, day}]`
  - 최근 받은 물건 셋이고, 최근 것이 먼저다.
  - `prop` 을 고르는 순서: `props_meta.json by_subtype[갈래][하위 종류].prop` → 그 갈래의 첫 good → `unknown.any`.
- `card.history`, `visitors_book` 은 위와 같다. `seat`·`props` 는 그대로다.

## 13. S23 바뀐 것 (2026-10-13, 1단계 뒤쪽)
수치는 `core_a.json` 의 `s22.notebook`·`s22.evening_table`·`s19_server_numbers.overflow` 에서 읽는다. 문장은 시나리오 데이터에서 읽는다.

### ① 사람 수첩
- **「어디로」(`where`)**: 응답에 `labels: bool`, `order: "value"|"fixed"` 가 붙는다.
  - 1~2일째, 또는 설정 `labels_always` 가 켜져 있으면 지금처럼 라벨이 붙고 값 순서다(`labels: true`).
  - **3일째부터**는 `labels: false`, `order: "fixed"` 다.
    - `suggest` 는 사람(주민 명단 순서) → 방(칸 순서)이다. 첫자리 강조 표시는 없다.
    - 사람 제안에 `known: bool` 이 붙는다.
    - 그 사람의 그 칸을 이미 알면(`known: true`) 라벨(`tier`·`icon`·`reason_ko`·`value`)이 그대로 오고, `slot` 이 붙는다.
    - 모르면(`known: false`) `tier`·`icon`·`reason_ko`·`value`·`mult` 가 **빠지고** `hint_ko`(기색 한 줄)가 온다. 기색은 `resident_tastes roles.<role>.signs.needs[i]/likes[i]` 에서 고르고, 없으면 `ui_moments.signs_generic[갈래]` 를 쓴다.
    - 사슬 매듭 제안은 늘 `known: true` 다.
- **`/api/give` 응답 `revealed: {kind, big, slot, new, slot_ko, line, line_key}`**
  - `kind` = 실제 결과다: need / like / memory / chain_beat / warm / not_for_me.
  - `big` = 라벨 없이 처음 맞혔다는 뜻이다. 이때 `line` 은 `ui_moments.reveal.discovered[]` 에서 오고, 아니면 `reveal.<kind>[]` 에서 온다.
  - 맞힌 칸은 수첩에 적힌다. 1~2일째 라벨로 건넨 결과도 적히지만 big 은 아니다.
- **`core.residents[rid].notebook: {slots: [{key, kind, kind_ko, known, ko, how, day}], known, total}`**
  - `key` 꼴: `like:i`·`need:i`·`memory:<id>`·`dislike`.
  - 모르는 칸은 `ko: null` 이다.
  - `how` 는 `give` 또는 `gossip` 이다.
- **저녁 귀띔**: 그날 첫 저녁 세션(17~5시)에 한 번 온다. 가장 많이 받은 사람의 모르는 칸 하나를 다른 주민이나 관리실이 흘린다.
  - `/api/ark.notebook_tip: {resident_id, name, slot, kind, ko, teller_id|null, line}` 로 오고, 밤사이에 `kind: "notebook_tip"` 로도 들어간다.
  - 문장은 `ui_moments.notebook.gossip_resident[]` / `gossip_office[]` 다.
- **늘 이름표**: `POST /api/prefs {uid, labels_always}` → `{prefs, label_ko}`. 값은 `/api/ark.prefs.labels_always` 로 읽는다.
- **같은 세션 같은 사람 두 번째**: `/api/give` 응답에 `repeat: {line, other_id, other_name, line_key}` 가 붙는다(`roles.<role>.repeat_lines[]`, {other}). 값은 그대로 ×0.8 이다.

### ② 받는 저녁, 한 상
- **`/api/ark.evening_table`**: 저녁(17~5시)에만 온다. 낮에는 null 이다.
  - 아직 안 차렸으면 `{open: true, open_ko, table_prompt, seat_prompt, returned: [...], candidates: {items: [{relic_id, name, category, today}], residents: [{id, name, role}]}, food_cost, table_store}`.
  - `returned` 는 오늘 건넨 물건 `[{name, to_name, resident_id}]` 과 오늘 온 손님 `[{visitor_id, name, room}]` 이다.
  - 차렸으면 `{open: false, done: true, result}` 다.
- **`POST /api/table {uid, relic_id, seats: [[rid, rid]]}`**
  - 저녁에만, 하루 한 번 차린다.
  - 식량 4는 「한 상 몫」(`table_store`)부터 쓰고, 모자라면 재고에서 쓴다. 그래도 모자라면 물건만 올려도 된다.
  - 신뢰: 둘 다 +3. 둘 중 하나가 그 물건을 좋아하면 +5, 둘 다 좋아하면 +7. 직전 상과 같은 짝이면 ×0.5.
  - 응답: `{ok, pair, names, item, relic_id, trust_delta, liked_by, repeat_pair, food_paid, table_store_paid, talk: [{who, name, line}×2], talk_key, promise, state}`.
  - 대화는 `evening.talk.pairs["역할+역할"]`(쓴 것은 다시 안 씀) → `evening.talk.generic.<food|drink|other>` 순으로 고른다.
  - 물건은 상에 올렸다가 제자리로 돌아온다.
- **넘침**: 넘친 식량·물은 「한 상 몫」(최대 12)부터 채우고, 남은 것을 사기로 바꾼다(`to_table_store_first`).
- **밤 손님**: `visitors.json night_visitors[]` 이 19시부터 하루 한 번, 불 켜진 방 창에 온다. 거주실이 먼저다.
  - `visits[]` 에 `kind: "night_visitor"` 로 들어간다.
  - 다음 날 아침 밤사이에 `kind: "night_trace"` 흔적이 남는다.

### ③ 내일의 부탁
- `GET /api/leaving` 과 `/api/ark` 에 `tomorrow_ask: {resident_id, name, day, need: {category, subtype, ko}, line}` 가 붙는다.
- **내일 실제로 뜰 필요와 같은 시드**다(다음 날 `needs_today` 와 일치, 테스트 확인).
- 문장 순서: `roles.<role>.tomorrow.needs[i][]` → `roles.<role>.tomorrow_ask[]` → `next_visit promises.tomorrow_ask[]`.

### ④ 이름 투표 어긋남
- 전역 이름(3곳 이상·60%)이 정해진 바코드를 이 방주가 다른 종류로 정했으면, 필요를 채워도 `intent: false` 다(큰 장면 없음). 보통 건네기는 그대로다.

### 서버 안쪽 메모
- `where_for` 결과에는 서버만 쓰는 `_internal`(라벨을 가리기 전의 원래 제안)이 붙는다. API 응답 전에 뺀다.
- 기존 테스트 중 값 정렬을 보는 것(S20 1순위 비율, S21 warm 1순위)은 `labels_always` 를 켜고 돈다.

### S23 후속 (라운드 5 사전 점검)
- 3일째부터의 순서는 `order: "least_recent"` 다. **가장 오래 못 받은 사람부터** 놓는다(받은 적 없는 사람이 먼저). 같으면 그 사람이 선 방 순서다. 값은 드러나지 않고, 첫 제안만 누르는 사람도 받는 사람이 돌아간다.
- 기색은 이 순서로 고른다: 그 칸 정확히(`signs.needs/likes[i]`) → 역할×갈래(`signs.by_category[cat]`) → 갈래 공통(`signs_generic[cat]`).
  - **한 「어디로」 안에서 같은 템플릿을 두 사람에게 쓰지 않는다.**
  - 갈래 공통 줄에는 역할을 붙인다(「요리사 도담 님이…」).
