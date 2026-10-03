# API_S13 — 스프린트 13-A 서버 계약 (클라이언트 개발용)

작성: 개발(서버), 2026-10-03. 근거: `docs/reports/review_fun_collection_20261003.md` 추천 1~4(사용자 승인), 수치 정본 `data/balance/stakes.json`(기획), 문장 정본 `data/ui_moments.json`(시나리오).

**원칙**
- 기존 필드는 지우거나 의미를 바꾸지 않는다. 전부 **추가**다. (예외 한 곳: `/api/codex` 의 카테고리 항목에 `entries` 가 붙는다. 옛 필드 `category/total/found/names` 는 그대로.)
- 수치는 서버가 `stakes.json` 에서 읽어 계산해 내려 준다. 화면은 계산하지 않는다(D2).
- 화면 문장은 `GET /api/text/moments` 로 받는다(`data/ui_moments.json` 그대로). 서버가 문장을 조립해 주는 곳에는 `*_ko` 필드로 **치환이 끝난 한 줄**이 같이 온다. 키를 직접 쓰고 싶으면 `key` 필드를 보면 된다.
- 개발 훅(`debug_*`)은 `RELIC_DEV=1` 에서만 산다. 배포에는 없다. 새 훅: `GET /api/ark?debug_night=1` (밤 판정 시각을 기다리지 않고 지금 판정).

## 0. 새로 불러야 하는 엔드포인트 (요약)

| 엔드포인트 | 언제 | 비고 |
|---|---|---|
| `GET /api/text/moments` | 화면 처음 열 때 1회 | 문장 묶음 |
| `GET /api/codex?uid=` | 도감 화면 열 때 | 실루엣 포함 전 칸. 옛 필드 유지 |
| `GET /api/collection?uid=` | 도감의 가문·생물·문어 탭 | 가문 세트 18 + 생물 + 문어 선물 + 희귀도 요약 |
| `GET /api/wishes?uid=` | 주민 카드 열 때 | 지금 있는 주민의 바람 |
| `POST /api/octopus/name` | 이름 짓기 | `{uid, name}` |
| `GET /api/day_end?uid=` | 하루 마감 컷(밤 진입 또는 버튼) | |
| `POST /api/ark/repair` | 금 간 방 수리 | `{uid, slot, use_patch?}` |
| `GET /api/event/today?uid=` · `POST /api/event/resolve` | 관리실 쪽지(사건) | 이미 있음. /base 가 아직 안 부른다 |
| `GET /api/rumors?uid=` | 소문 목록 | 이미 있음. /base 가 아직 안 부른다 |

## 1. `GET /api/text/moments`
`data/ui_moments.json` 을 그대로(키 고정) 돌려준다. 파일이 없으면 `{}`.
```json
{"shelf": {"rescan": "…「{item}」, 한 번 더 닦아 두었습니다.", "levels": {"1": {"label": "건진 그대로", "line": "…"}}},
 "variant": {"label": "바다 무늬", "found": "…"}, "family_set": {"progress": "…{n}…{total}…", "complete.8801043": "…"},
 "codex": {...}, "crack": {...}, "staffing": {...}, "lid": {...}, "night_judge": {...}, "day_end": {...},
 "octopus_gift": {...}, "event_strip": {...}}
```

## 2. `POST /api/scan` (바뀜 — 필드 추가)
요청은 그대로 `{uid, barcode, user_category?}`. **category_lock**: 이 방주에서 그 바코드에 처음 정해진 카테고리(정체불명 제외)가 있으면 `user_category` 는 무시되고 고정값이 쓰인다.

추가 응답 필드:
```json
{
  "card": {"...기존...": "", "sea_variant": true},
  "shelf_slot": 3,
  "shelf_new": false,
  "category_locked": "food",
  "variant": {"id": "sea", "shiny": true, "week": "2026-W40", "label": "바다 무늬",
              "ko": "관리실에서 알려 드립니다. 이번 「…」에는 바다 무늬가 들어 있습니다. …"},
  "polish": {"barcode": "8801043015097", "slot": 3, "level": 2, "prev_level": 1, "leveled_up": true,
             "scans": 3, "next_at": 8, "max": 3, "counted_today": true, "value_mult": 1.25,
             "label": "한 번 닦음", "ko": "같은 물건이 또 들어왔습니다. 선반에 있던 「…」, 한 번 더 닦아 두었습니다."},
  "first_meet": [{"kind": "family", "key": "8801043", "line": "붉은 성문입니다. …"},
                 {"kind": "category", "key": "food", "line": "돔에 냄새가 하나 늘었습니다. …"}],
  "family_set": {"code": "8801043", "name": "붉은 실 가문", "have": 2, "total": 3, "completed": false,
                 "just_completed": false, "reward": null, "ko": "「붉은 실 가문」 가문 물건이 2개 모였습니다. 3개면 한 벌입니다."},
  "wishes_done": [{"id": "wish_cook_seat", "resident_id": "cook-123", "name": "…", "line": "…line_after…"}]
}
```
- `shelf_slot`: 이미 선반에 있는 바코드면 **그 칸 번호**(새 칸을 먹지 않는다). `shelf_new` 가 새로 놓였는지 알려 준다. 선반이 차서 못 놓으면 `null`.
- `variant`: 바다 무늬가 아니면 `{"id": null, "shiny": false, "week": "2026-W40"}`. 시드 = `barcode:ISO주`(전 세계 동일), 확률 `stakes.variant.rate`. **수치 보상 없음**(표시만). `card.variant`(새벽/낮/저녁/밤)는 예전 그대로 남는다.
- `polish`: 선반에 이미 있던 바코드를 찍었을 때만(아니면 `null`). **놓인 날이 아닌 다른 날**, 바코드당 하루 한 번만 센다(`counted_today`). `scans` = 지금까지 센 재스캔 수, `next_at` = 다음 레벨 문턱(누적, `stakes.polish.scans_per_level` [3,5] → Lv2 는 3, Lv3 는 8). 이미 최대면 `ko` 는 `shelf.rescan_max`, 세지 않은 같은 날 재스캔이면 `ko: null`(닦았다고 말하지 않는다).
- `family_set`: 알려진 가문 18곳(`family_names.json`)의 바코드일 때만. `total` = `stakes.family_sets.pieces_required`(지금 3). `have` = 이 방주가 찍은 **서로 다른 바코드** 수. 완성 순간 `just_completed: true`, `reward: {"story": "…", "decor": "…", "morale": 2}`, `ko` = `family_set.complete.<code>`(없으면 `complete_default`). 사기는 서버가 이미 더했다.
- `first_meet`: 처음 보는 가문·카테고리일 때만 줄이 있다(가문 먼저). 없으면 `[]`.

## 3. `GET /api/peek?barcode=&uid=` (바뀜 — `uid` 선택 인자, **화면은 uid 를 붙여 주세요**: 안 붙이면 고정된 바코드에도 카테고리를 다시 묻는다. 서버는 어차피 고정값을 쓴다)
`uid` 를 주면 그 바코드에 고정된 카테고리가 있을 때 `"locked_category": "food", "needs_category": false`. `uid` 없으면 예전과 같다.

## 4. `GET /api/ark` (바뀜 — 필드 추가)
```json
{
  "rooms": [{"id": "pantry", "slot": 2, "level": 1, "cracked": true, "cracked_day": 5}],
  "shelf": [{"slot": 0, "prop_id": "…", "name": "…", "category": "food", "rarity": "common", "family": "…",
             "scanned_at": 0, "barcode": "8801043015097", "polish": 2, "polish_label": "한 번 닦음", "variant": "sea"}],
  "production": {"2": {"room_id": "pantry", "staff": 0, "staff_mult": 0.5, "cracked": true, "crack_mult": 0.7,
                       "mult": 0.35, "label": "일손 없음", "ko": "식량창고에 일하시는 분이 안 계셔서 …"}},
  "repair": {"cost": {"cloth": 1, "med": 1}, "patch_tool": "patch", "have_patch": 0},
  "night_judge": {"hour": 21, "worst": "breached", "report": null},
  "flooded_cells": [{"slot": 3, "was_id": "greenhouse", "was_name": "온실", "was_level": 2, "flooded_day": 4, "by": "big_maw", "reclaim": "build"}],
  "octopus": {"arrived": true, "name": null, "mood": {"id": "watching", "ko": "지켜봄", "stage": 2, "line": "…"},
              "gift_today": {"id": "oct_screw_cap", "name": "나사선 살아 있는 마개", "line": "…", "kind": "relic_shard",
                             "ko": "문어가 선물을 하나 물어 왔습니다. 「…」, …"}},
  "wishes_new": [],
  "families_done": ["8801043"],
  "decor": [{"code": "8801043", "name": "붉은 실타래 걸이"}]
}
```
- `flooded_cells` (**사용자 결정 2026-10-03**): 잃은 방은 영구 삭제가 아니라 **물 찬 칸**이다. `rooms[]` 에도 `flooded: true` 로 그대로 있고(예전과 같다), 잃기 전 종류·레벨을 `was_*` 로 기억한다. 되찾기 = **그 칸에 보통 짓기** `POST /api/ark/build {uid, room_id, slot}` — 보통 건설비(economy.json), **Lv1**. 아무 방이나 지을 수 있고, 화면은 `was_id` 를 먼저 권하면 된다. 응답에 `reclaimed: {id, level, slot, rebuilt_as, ...}`. 물 찬 칸에 사람 배치는 400.
- `production[slot]`: 생산하는 방만. `mult = staff_mult[그 방에 서 있는 사람 수] × (금 갔으면 crack.prod_mult)`. 다음 8시간 정산이 이 값으로 계산된다. **`staffing.measure = contact_snapshot`**: 습격 접촉(누름 또는 밤 판정) 순간의 배치가 **그 틱**의 생산을 정한다 — 그 틱 동안은 `snapshot: true`, `mult` 가 접촉 순간 값, `now_mult` 가 지금 배치로 다음 틱부터 적용될 값이다(옮겨 막고 바로 되돌려도 비용이 남는다). `label/ko` 는 사람 0명일 때만(`staffing.*`).
- `night_judge.report`: 밤 자동 판정이 **이번 요청에서** 일어났으면 한 번 온다 `{"raid_id", "creature", "result", "capped": true|false, "room": "식량창고", "lost_room": "식량창고"|null, "key": "night_judge.cracked", "ko": "좋은 아침입니다, …"}`. **사용자 결정 2026-10-03: 상한 없음**(`stakes.night_judge.worst_result = "breached"`) — 누른 것과 같은 결과다. 상실이면 `key: "night_judge.lost"` 인데 이 키가 아직 ui_moments.json 에 없어 `ko` 는 생물의 상실 문장(creatures.json)으로 대신 온다(시나리오 요청함). 다음 요청부터는 `null`(중복 없음).
- `octopus`: `companion_octopus.json arrival.day` 이전이면 `{"arrived": false}`. 첫 등장 날에는 `"arrival": {"beats": [...], "closing": "…"}` 가 한 번 붙는다. 선물은 하루 1개, 시드 `uid|day`, 전날 찍은 카테고리와 맞으면 가중치 가산.
- `wishes_new`: 이번 요청에서 이뤄진 바람(한 번만).

## 5. `POST /api/ark/repair`
요청 `{"uid": "…", "slot": 2, "use_patch": false}`. 금 간 방이 아니면 400. `use_patch: true` 면 재료 대신 봉합 패치 하나(`tools` 보유 수)를 쓴다.
```json
{"ok": true, "slot": 2, "paid": {"cloth": 1, "med": 1}, "used_patch": false,
 "ko": "식량창고 유리 수리를 마쳤습니다. …", "state": { "...public_state..." : "" }}
```
실패: `400 {"detail": "모자랍니다: 직물 1"}`.

## 6. 습격 (`GET /api/raid/today`, `POST /api/raid/advance`) — 필드 추가
- `raid.lid_revealed: true` — 덮개(`lid`)이고 `stakes.lid.reveal_target` 이면 `reveal_from_stage`(지금 `silhouette`)부터 `target_slot/target_room` 이 보이고, 이때 `raid.reveal_ko` 에 `lid.target_revealed` 문장이 온다. **그 단계부터의 이동은 덮개의 `moves` 에 세지 않는다**(기획 note). 소리 단계 이동은 센다.
- `raid.auto: true` — 밤 자동 판정으로 끝난 습격. `raid.capped: true` 면 원래 결과가 `night_judge.worst_result` 보다 나빠 막힌 것(지금 값 breached → 일어나지 않는다. 데이터만 바꾸면 다시 켜진다).
- **덮개는 보류**(사용자 결정 2026-10-03): `data/balance/threats.json` `min_grade.lid = 6`(1막 등급은 1~5) → 1막 무작위 습격에 나오지 않는다. 손님·원정 주민이 생기면 4로 되돌린다. 공개 규칙은 그대로 남아 `debug_raid=lid` 로 확인할 수 있다.
- 판정 결과가 금(scarred)이면 그 방은 `cracked: true` 가 되고 수리 전까지 생산 ×`crack.prod_mult`, 방어 바탕 `crack.room_base_penalty`(미리보기 `ready.parts` 에 「금 간 유리」 줄로 보인다).

## 7. `GET /api/codex?uid=` (바뀜 — `entries` 추가, 옛 필드 유지)
```json
[{"category": "food", "category_ko": "식품", "total": 4, "found": 1, "names": ["말린 실의 부적"],
  "entries": [
    {"stem": "말린 실의 부적", "known": true, "name": "붉은 말린 실의 부적", "count": 3,
     "rarity_best": "rare", "rarities": ["common", "rare"], "variant_seen": false, "tags": ["열원"], "flavor": "…"},
    {"stem": null, "known": false, "silhouette": "봉지 모양 그림자입니다. …", "hint_ko": "아직 못 본 물건입니다. 봉지 모양 그림자입니다. …",
     "rarity_best": null, "variant_seen": false, "tags": ["사기"]}
  ],
  "rarity": {"common": 1, "uncommon": 0, "rare": 1, "epic": 0, "legendary": 0}}]
```
모르는 칸은 이름을 주지 않는다(`stem: null`). 실루엣 문장 = `codex.category_hints.<cat>`(없으면 `codex.unknown_no_hint`).

## 8. `GET /api/collection?uid=`
```json
{
  "families": [{"code": "8801043", "known": true, "name": "붉은 실 가문", "category": "food", "category_ko": "식품",
                "have": 2, "total": 3, "completed": false, "story": null, "decor": null, "flavor": "…"},
               {"code": "8801062", "known": false, "name": null, "category_ko": "식품", "have": 0, "total": 3,
                "silhouette": "아직 못 본 물건입니다. 봉지 모양 그림자입니다. …"}],
  "families_done": 0, "families_total": 18,
  "creatures": [{"id": "longneck", "known": true, "name": "긴목", "how": "…", "times": 2, "last_result": "held"},
                {"id": "lid", "known": false, "name": null, "silhouette": "…creatures.json silhouette…"}],
  "octopus_finds": [{"id": "oct_lid_stamp", "known": true, "name": "성문 찍힌 뚜껑", "line": "…", "count": 1},
                    {"id": "oct_color_chip", "known": false, "name": null}],
  "rarity": {"common": 10, "uncommon": 3, "rare": 1, "epic": 0, "legendary": 0},
  "variants": {"seen": 1},
  "spots": {"found": 2, "total": 6}
}
```
완성 가문은 `story`(lore 이야기)와 `decor`(장식 이름)가 열린다.

## 9. `GET /api/wishes?uid=`
지금 방주에 있는 주민의 역할에 맞는 바람만(1막 시작 3인 = 요리사·기술자·정찰병).
```json
[{"id": "wish_cook_seat", "resident_id": "cook-123", "name": "…", "role": "cook", "wish": "한 번은 서서 말고 앉아서 먹어 보고 싶다.",
  "condition": "곳간 선반에 찍어 온 식품이 세 칸 이상 쌓인다. …", "done": false, "done_day": null,
  "line": "…line_before…", "progress": {"have": 1, "need": 3}}]
```
이뤄지면 `line` 이 `line_after` 로 영구히 바뀐다. 보상 수치는 없다(대사가 바뀌는 것이 보상, PLAYER_JOURNEY E5).

## 10. `POST /api/octopus/name`
요청 `{"uid": "…", "name": "먹물"}` (1~12자). 응답 `{"name": "먹물", "ko": "먹물. 아이가 세 번 불러 보았고, …"}` (`naming.after_name_line` / 두 번째부터 `rename_line`).

## 11. `GET /api/day_end?uid=`
오늘 바뀐 것만, `day_end.json` 상황표(우선순위·최대 줄 수)로 고른다. 같은 날 같은 결과(시드 `uid|day`).
```json
{"day": 5, "title": "오늘 바뀐 것", "open": "관리실에서 오늘 마감 말씀 드립니다.",
 "lines": [{"id": "room_lost", "text": "…"}, {"id": "octopus_brought", "text": "…"}],
 "facts": {"scan_count": 6, "blocked": 1, "floors": 3},
 "facts_ko": ["오늘 새로 들어온 물건은 6점입니다.", "다녀간 손님은 1번 잘 돌려보냈습니다."],
 "closing": "내일 아침에 확인할 것이 하나 있습니다.", "close": "편히 쉬십시오. 이상, 관리실이었습니다."}
```

## 12. 스팟 해금 (`/api/rumors`, `/api/spots`) — 의미 변경
`stakes.spot_unlock.count_distinct_barcodes` 가 참이면 진행도 `progress.have` 는 그 카테고리의 **서로 다른 바코드 수**다. 응답 모양은 같다.

## 13. 저장 이전
구버전 방주는 처음 읽을 때 자동 보강된다: 선반 물건에 `barcode`(card_id 앞부분)·`polish: 1` 을 채우고, **같은 바코드가 두 칸 이상이면 첫 칸만 남긴다**(옛 중복 칸 버그). `barcodes`(카테고리 고정)는 `scans` 표에서 첫 카테고리로 채운다. 이미 `cracked: true` 인 방은 이제 실제로 금 간 상태로 돈다.

---

# §S14 — 능력치가 생산을 바꾼다 (S14-A, 2026-10-03)

수치 정본: `data/balance/stakes.json` 의 `stat_production`(기획). 화면은 **게임 숫자를 계산하지 않는다**(D2, PM 결정) — 드래그 미리보기도 서버가 미리 계산해 `move_preview` 로 내려 준다.

## S14-1. 생산식 (서버 정산 = 미리보기 = 같은 함수)
```
방 산출(한 틱) = Σ_k (기본 생산[레벨][k] + 그 방에 선 사람들의 역할 보정[k])
               × staff_mult[n] × stat_mult × (금 갔으면 crack.prod_mult) × (불 꺼짐 0.5)
n        = 그 방에 서 있는 사람 수(밖에 나간 사람 제외; injured_counts=false 면 부상자도 제외)
stat_mult = clamp(1 + per_point × A, min_mult, max_mult),  d_i = 그 사람의 room_stat[방] 값 − center
   aggregate "mean": A = 평균(d_i) / "sum_excess": A = 합(d_i) / "best_plus": A = 최대 d + best_plus_others × 나머지 양수 d 합
   사람이 없으면 1.0 (빈 방 값은 staff_mult[0])
```
- **역할 보정은 그 방에 선 사람 것만**(`role_bonus_in_room_only`). 예: 요리사의 식량창고 food +1 은 요리사가 식량창고에 서 있을 때만. 각인의 방 보정도 같은 규칙이다. 다른 역할 효과(건설 할인·회복 등)는 예전 그대로 어디서든.
- 부상자(`injured_counts=false`)는 머릿수·능력치·역할 보정 어디에도 세지 않는다.
- 담(nerve)은 생산에 쓰지 않는다(전투 전용).
- **접촉 스냅숏**(`staffing.measure=contact_snapshot`): 접촉 순간 **누가** 서 있었는지(id)를 남긴다 — 그 틱은 머릿수·능력치·역할 보정 모두 그 사람들로 센다.

## S14-2. `GET /api/ark` 추가 필드
```json
"stats_meta": {
  "keys": ["hand","eye","breath","nerve"], "ko": {...}, "use": {...}, "max": 10,
  "room_stat": {"pantry": "hand", "greenhouse": "breath", "library": "eye", "hall": "eye", "...": "..."},
  "stat_production": {"center": 5, "per_point": 0.05, "min_mult": 0.88, "max_mult": 1.18, "aggregate": "mean",
                      "best_plus_others": 0.5, "role_bonus_in_room_only": true, "injured_counts": false}
},
"production": {"3": {"room_id": "greenhouse", "staff": 1, "staff_mult": 1.0,
                     "stat": "breath", "stat_mult": 0.88,
                     "per_person": [{"id": "engineer-1", "name": "다올", "stat": "breath", "value": 2, "d": -3, "v": -0.15}],
                     "role_bonus": {}, "cracked": false, "crack_mult": 1.0, "mult": 0.88, "snapshot": false}},
"move_preview": {
  "engineer-1": {
    "2":    {"room_delta_pct": 136.0, "from_delta_pct": -43.2, "can": true},
    "4":    {"room_delta_pct": null,  "from_delta_pct": -43.2, "can": true},
    "hall": {"room_delta_pct": null,  "from_delta_pct": -43.2, "can": true}
  }
}
```
- `stats_meta.room_stat` 이 **정본**이다 — `static/base.js ROOM_STAT` 사본은 이걸로 바꿔 달라(기획이 의무실 hand·정수실 breath·홀 eye 로 바꿨다).
- `production[slot].per_person[].v` = 그 사람이 `1 + …` 안에 더한 몫(클램프 전). `stat_mult` 는 클램프 뒤 값. 스냅숏 틱이면 `now_mult`·`now_stat_mult` 가 다음 틱 값.
- **`move_preview[resident_id][slot | "hall"]`** — 그 사람이 거기로 옮기면:
  - `room_delta_pct`: 옮겨 간 방의 한 틱 산출 변화 %. 쌓이는 산출이 없는 방(공방·발전실·에어락·창고·홀)은 `null`. 빈 산출에서 생기면 100.0.
  - `from_delta_pct`: 떠나는 방의 산출 변화 %(홀에서 떠나거나 생산 없는 방이면 `null`).
  - `can`: 정원이 차서 못 들어가면 `false`.
  - JSON 키에 null 을 쓸 수 없어 **홀(문간·포드 포함) = `"hall"`** 이다(`POST /api/ark/station` 의 `slot: null` 과 같은 곳). 지금 서 있는 칸은 빠진다. 밖에 나간 사람은 없다.
  - 값은 **다음 틱부터** 기준(접촉 스냅숏이 걸린 틱이라도). 배치·스탯·부상·금·불이 바뀔 때마다 `/api/ark` 와 모든 `public_state` 응답(station 등)에 새로 계산돼 온다.

## S14-3. 이번에 안 한 것(후속)
- 공방 「제작 시간 ÷ stat_mult」: 제작에 시간이 없다(즉시). 손 보정은 이미 재료 ±1(`craft_cost`)로 있다.
- 발전실 「공급 × stat_mult」: `power_supply` 를 쓰는 전력 예산 시스템이 아직 없다. 생기면 같은 `room_mult` 를 곱하면 된다.
