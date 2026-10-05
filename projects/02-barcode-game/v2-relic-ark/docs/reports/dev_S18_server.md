# 개발(서버) S18-A 보고서 — 7일 플레이테스트 고침 + 기획 S18-D 수치 + 습격 카드 단서 모드 (2026-10-05)

근거: `docs/reports/playtest_7day_20261004.md` §5 버그·§6 추천, 기획 S18-D(economy.json `shelf`·`workshop_trade`·`material_sources`·`scan.rescan_decay`·`rooms.storage_cap`, threats.json `first_week_guarantee`, stakes.json `polish`·`raid_card`), 시나리오 S18-S(relic_templates subtype, ui_moments `depth.*`·`morning.*`·`raid_preview.*`·`shelf.full.*`·`shelf.rescan_zero`, creatures.json `habit`), 사용자 결정(raid_card 단서 모드 승인, 재스캔 바닥 0.1 승인). 계약: `docs/API_S13.md` §S18. 커밋하지 않았다. 중간에 사용량 한도로 끊겼고, 작업 트리에서 이어 했다.

**내 파일이 아닌 변경**: 작업 트리의 `data/imprints.json`·`creatures.json`·`relic_templates.json`·`ui_moments.json` 변경은 시나리오 것이다(나는 손대지 않았다). 내가 고친 데이터는 `data/events_schema.json` 한 줄(`min_depth_m` 필드, 개발 소유 스키마)이다.

## 1. 버그 (§5)
| # | 고친 것 | 위치 |
|---|---|---|
| 2 | 180m 전용 쪽지가 1일째 0m 에 나오던 것. 쪽지에 **깊이 문**을 걸었다. 정본은 카드의 `min_depth_m`(스키마 추가)이고, 값이 오기 전에는 임시표를 쓴다(needle 120, followed_home 180 — 카드 note 와 같다) | `engine/storyteller.py` `min_depth_of`, `ArkState.depth_m` |
| 3 | 「상자 하나 열어 두었습니다」를 말해 놓고 상자가 없던 것. 목소리 줄이 **전제하는 사실**(box_opened)이 있을 때만 그 줄을 고른다. 쪽지·습격에서 상자를 주지 않으니 그 줄은 이제 나오지 않는다(효과를 지어내지 않고 약속을 지웠다). 줄에 `requires` 가 붙으면 그것이 이긴다 | `voice_for(facts=)`, `line_requires` |
| 4 | 하루 마감 사실 넷. (a) 각인의 출처(event·raid·expedition)를 일지에 함께 적고, 「돌아온 뒤」류 줄은 원정에서 생긴 각인일 때만 쓴다. (b) 「되찾은 층」은 물 찬 칸을 다시 지은 수(`reclaimed_total`)이고, 0이면 말하지 않는다. (c) 울음 간격은 지금 게이지 값으로 말한다(80/85 어긋남). (d) 「아이 손목」류 줄은 아이 주민이 있을 때만 쓴다. 맞는 줄이 없으면 그 상황은 생략한다 | `day_end`, `pick_fact_line` |
| 5 | 같은 쪽지가 이틀 연속 나오던 것. 본 날을 기록해 두고 `events.no_repeat_days`(안전값 3) 안에는 빼고 뽑는다 | `event_today`, `recent_event_ids` |
| 6 | 같은 각인이 두 사람에게 같은 문장으로 나오던 것. 아침 줄을 각인별로 한 줄로 묶고, 이름을 「가·나」로 이어 각인 문장 틀에 다시 넣는다 | `merge_morning` |
| 8 | 1막에 지상 스팟 소문이 나오던 것. `/api/rumors` 는 지금 막만 보낸다. `/api/spots` 의 다른 막 스팟은 `other_act` 이고 열리지 않는다 | `rumors`, `spots` |
| 10 | 미리보기 시제. `would_ko` 를 ui_moments `raid_preview.*`(미래형)에서 읽는다 | `raid_public` |
| 12 | `ready.parts` 의 「刻 knock_heard」를 「각인 「두드림을 들은 자」」로 바꿨다. 엔진은 그대로 두고 서버가 표시만 바꾼다 | `parts_display` |
| 13 | 튜토리얼 미리보기 줍기를 3으로, 잠수복 수리 응답에 `ko` 문장을 넣었다. 돌려보낸 카드 문장의 조사도 고쳤다(`ui_rewrite_s18.tsv`) | |

1번(아침에 하루 마감이 열림)·7번(발견 연출)·9·11번은 화면 쪽이다. 서버는 「밤사이」 한 장(`overnight`)을 마련했다.

## 2. 기능
| 항목 | 내용 | 읽는 곳 |
|---|---|---|
| **선반이 자란다** | 칸 = 식량창고 6 + 창고 방마다 레벨별 8/14/22(큰 것 둘까지) + 되찾은 층마다 4. 꽉 차면 새 유물은 **창고 상자**(`stored`)로 가고 사라지지 않는다. 스캔 응답이 바꿀 후보(가장 덜 닦인 것부터)를 준다(`swap_offer`). 바꾸기는 `POST /api/shelf/swap`. 창고 상자에 있는 바코드를 다시 찍으면 닦는다(중복이 생기지 않는다). 원정 유물 조각·상자 유물도 넘치면 창고 상자로 간다 | economy.json `shelf` |
| **자원 저장 상한** | 재료당 상한 = 창고 선반 수 × 6(창고 없음 24 / Lv1 36 / Lv2 72 / Lv3 120). 한 요청에서 **늘어난 분만** 잘라 낸다. 이미 넘쳐 있던 재고는 깎지 않는다(B4). `storage.full` 과 넘친 양을 내려 준다 | economy.json `rooms.storage_cap`. 구조 키 없이 글로 된 정본이라 `per_shelf=6`·`no_storage_shelves=4` 를 그 글에서 옮겼다(키가 오면 키가 이긴다) |
| **첫 주 위협 보장** | 4일째까지 위협이 한 번도 없었으면 긴목·세기 0이 사람이 서 있는 방으로 온다(4일을 건너뛴 사람은 7일째까지 첫 방문 날). `raid.guaranteed` | threats.json `first_week_guarantee` |
| **재스캔 감쇠** | [1, .5, .25, .1], 네 번째부터 0.1(사용자 승인). 창도 데이터에서 읽는다 | economy.json `scan.rescan_decay` |
| **값 낮은 재스캔 반응** | 배율 < 1 이면 순서대로 첫 해당 하나를 낸다: 상자 열쇠 힌트 → 닦기 진척 → 바람 힌트 → 문어 기분(사기 +0.1, 하루 3번). 아무것도 없고 배율이 바닥이면 `shelf.rescan_zero` 한 줄 | stakes `polish.zero_reaction` |
| **공방 바꾸기** | `POST /api/workshop/trade` — 식량·물 4 → 직물·부품·잔해 1. 하루 2개까지, 재고 12 이상은 남긴다 | economy.json `workshop_trade` |
| **재료 출처** | `/api/ark.material_sources` | economy.json `material_sources` |
| **유물 이름·문장** | 알려진 가문은 그 가문 subtype 줄기만 쓴다(커피 가문에 술 문장 없음). 모르는 가문은 `_family_only`(음료=술)를 빼고 시드로 고른다(PM 결정). 줄기는 4개에서 12~15개로 늘었다(시나리오) — 모르는 식품 60개 → 18종 | relic_templates.json `subtype`·`_family_subtypes`·`_family_only` |
| **깊이 문턱 방송** | 60·120·180m 를 처음 넘으면 한 번 방송한다. 짓기 응답과 `/api/ark` 의 `depth_crossed`, 밤사이 묶음에 들어간다. 이전 저장은 이미 넘은 문턱을 조용히 넘긴 것으로 친다 | ui_moments `depth.first_<m>`, stakes `depth_announce.thresholds`(안전값) |
| **밤사이 한 장** | 밤 판정·원정 귀환·깊이·각인(묶음)·문어 선물·두드림·바람을 `overnight.items` 하나로 모은다. `POST /api/overnight/seen` 으로 비운다 | ui_moments `morning.*` |
| **습격 카드: 단서 먼저**(사용자 승인) | 같은 위협을 2번 만나기 전까지는 버릇 한 줄(`habit`)과 동사 목록(불·전원·자리·도구·행동 — 행동은 관문 행동 **전부**)만 보인다. 동사를 고르면(`POST /api/raid/verb`, 몇 번이든 바꿀 수 있다) 같은 미리보기 엔진의 결과·대가가 열리고 관문 문장만 숨는다. 2번 만난 뒤에는 예전처럼 답을 보여 준다. 생물별 만난 수는 `combat.encounters`. 타이머는 없다 | stakes `raid_card`, creatures.json `habit` |

## 3. 검증
- **S18 새 테스트** `python tests/test_s18_server.py` → **60/60**. 대표:
```
OK   깊이 0m 에서 300번 뽑아 깊이 카드 0번 / 깊이 180m 에서는 나온다(14/600)
OK   12일 쪽지: 3일 안 반복 없음, 깊이 카드 없음 (11종)
OK   상자 없이 막은 날 200번 — 상자 약속 줄 0 / 1~7일째 맞는 카드로 막음 — 상자 약속 없음
OK   방주 30개 마감 100줄 — 전제가 틀린 줄 0 / 되찾은 적 없으면 「되찾은 층」 없음 / 울음 줄 = 지금 간격 85초
OK   같은 각인 둘 → 한 줄: 가·나의 손끝에 … / ready.parts: 온새 · 각인 「두드림을 들은 자」
OK   1막 소문에 지상 스팟 [] / 지상 스팟 other_act
OK   식량창고만 6 / 창고 Lv1 14 / Lv2+Lv1+Lv1 → 둘까지 28 / 되찾은 층 +4 / 꽉 찬 뒤 5개 → 창고 상자 5, 바꾸기 / 창고 상자 바코드 재스캔 → 닦기
OK   4일째 보장 습격 longneck 세기 0 → 사람이 선 방 / 이미 위협이 왔으면 보장 안 함
OK   감쇠 [1.0, 0.5, 0.25, 0.1, 0.1, 0.1] / 값 낮은 재스캔 반응 / 공방 바꾸기 4→1 ×2, 하루 상한, 남길 재고 / 식량 상한 24 / 넘쳐 있던 재고는 그대로
OK   커피 가문 줄기 {coffee, tea} / 모르는 음료에 alcohol 없음 / 모르는 식품 60개 → 18종 / 같은 바코드 = 같은 이름
OK   60m 처음 → 방송 / 같은 문턱 한 번 / 밤사이: [night_judge, depth] / 본 뒤 비움 / 이전 저장 조용히
OK   처음 만난 긴목: 버릇 「저 녀석은 불빛을 보면…」, 동사 5, 미리보기 닫힘 / 행동 동사 = 관문 행동 전부
OK   동사 고르면 미리보기(관문 문장 숨김, 미래형 「유리에 금이 갈 겁니다」) / 몇 번이든 바꾼다 / 2번 만난 뒤 답 공개 / encounters {'longneck': 2}
```
- **기존**: S13 109/109, S14 26/26, S15 75/75. 고친 테스트는 둘이다: S13 하루 마감 `floors`(이제 되찾은 수라 0이 맞다), 그리고 S13·S15 습격 테스트 3곳(단서 모드라 미리보기를 보기 전에 동사 하나를 고른다). 전투 스냅숏은 S13 기준과 **바이트 동일**하다(engine/combat.py 를 이번에 고치지 않았다).
- **라이브**(8017, RELIC_DEV=1): `t_reg12` 27/27. 원정 라이브 루프의 두 FAIL 은 스크립트 쪽이다. 하나는 공기 8 가정이고(문간 펌프가 있으면 9가 맞다), 하나는 튜토리얼에서 상자 둘이 나와 손 칸이 넘쳐 `drop` 차례인 것을 스크립트가 처리하지 않았다(규칙대로 동작했다).
- **실제 DB 사본** 216방주: 읽기·틱·day_tick·저장(상한)·하루 마감·도감 오류 0.
- **API 차집합(아)**: 서버 − /base = `dev/advance`(개발), `expedition/scene`(3D), `stats`(관리) 와 새 넷 `overnight/seen`·`raid/verb`·`shelf/swap`·`workshop/trade`(화면 개발 몫). /base − 서버 = 없음.
- **브라우저** `/base`(8017): 콘솔 오류 0. `docs/reports/shots/dev_S18A_server_base.png`.

## 4. 교본 원칙
- **D2·정직**: 문장은 상태에서 확인한 사실만 말한다(전제 확인). 미리보기 숫자·대가는 서버가 계산한다.
- **D6**: 이름·문장·첫 주 보장 생물과 대상·값 0 반응·하루 마감 줄은 모두 시드로 결정된다. 같은 바코드면 같은 이름이다(줄기 수가 바뀌어 예전과는 다르다 — 시나리오·PM이 허용했다).
- **D7**: 수치는 전부 economy/threats/stakes 에서 읽는다. 이름 고르는 법도 relic_templates 의 `_for_dev` 를 따른다.
- **B4**: 상한은 늘어나는 분만 막는다. 넘친 재고를 빼앗지 않는다. 창고 상자는 사라지지 않는다.
- **이탈**: 저장 상한의 정본이 글로 되어 있어 숫자 둘(6·4)을 그 글에서 옮겼다(구조 키가 오면 키가 이긴다). 「상자를 열어 두었다」는 효과를 새로 만들지 않고 약속을 지웠다(경제 변경 없이).

## 5. 자가 검수
1. 새 숫자가 화면에 보이나 — 선반 칸·창고 상자·저장 상한·재료 출처·만난 수·밤사이 묶음을 서버가 내려 준다. 화면 연결은 화면 개발 몫이다.
2. 첫 3분 탭 — 서버는 탭을 늘리지 않는다. 단서 모드는 습격에 "동사 고르기" 탭 하나를 더하지만, 사용자가 승인한 설계다.
3. 결정성 — 예.
4. 720px — 해당 없음.
5. 회귀 — §3.

## 6. 미완·리스크·요청
- **화면**: 새 엔드포인트 넷(`raid/verb`·`shelf/swap`·`workshop/trade`·`overnight/seen`)과 `stored`·`storage`·`material_sources`·`overnight`·`depth_crossed`·`card_mode/habit/verbs` 를 연결해야 한다. `shelf_room.capacity` 가 합계라서 여러 방에 걸친 선반을 그리는 법을 정해야 한다.
- **기획**: `events.no_repeat_days`, `depth_announce.thresholds` 는 안전값(3일, 60/120/180)으로 돈다. stakes.json 에 키를 넣어 주면 그것을 읽는다. 저장 상한은 구조 키(`per_shelf`, `no_storage_shelves`)로 바꿔 주면 좋다.
- **시나리오**: 문장 전제 확인은 지금 문자열 휴리스틱 표(「돌아온 뒤」·「아이 손목」·「상자 하나 열어」 등)에 기대고 있다. day_end·dialogue 줄에 `requires: ["returned"|"kid"|"box_opened"]` 를 붙이면 그것이 정본이 된다. 값 0 반응의 `zero.*` 키(box_key_hint·polish_progress·wish_hint·octopus_mood)가 아직 없어 `ko` 가 null 로 간다(`shelf.rescan_zero` 만 있다).
- 첫 주 보장은 `raid/today` 를 연 날에만 습격이 생기는 지금 구조를 따른다(4일을 건너뛴 사람은 7일째까지).
- 바람 조건 판정과 문장의 어긋남(플레이테스트 §4-5)은 이번 범위 밖이다.
