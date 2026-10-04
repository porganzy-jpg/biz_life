# 시나리오 보고 — S15-F 원정·문간 문장 (2026-10-04)

근거: `docs/EXPEDITION.md`(§2·§3·§4·§10의 시나리오 요청 ①~⑥), 목소리: `docs/TEXT_VOICE.md`. 커밋하지 않았다.

## 1. 만든 것·고친 것
| 경로 | 무엇 |
|---|---|
| `data/expedition_text.json` (신규) | 화면 문자열 153개. 키는 고정이다 |
| `docs/ROOMS_AND_ITEMS.md` §2-2·§3-3 | 에어락 줄(Lv1 밤 넘기기·두 번째 공용 잠수복 / Lv2 공기 ×1.25 / Lv3 불러들이기 즉시), 몸 2단계를 「개인 잠수복」으로, 공기통 +1 / +3 |

## 2. 목소리 규칙 하나 (중요)
**집 안에서 들리는 알림은 관리실 방송이고, 문밖(아이소 물속판)에서는 관리실 목소리가 끊긴다**(EXPEDITION §3-6 ①, J3). 그래서 바깥 화면 문장은 방송체가 아니라 짧은 서술체로 썼다.
- 서술체: `expedition.follow.*`, `expedition.danger.kinds.*.prompt/pass/fail`, `spot.discovery_*`
- 방송체: 출발 알림, 귀환 알림, 상자 알림, 손님 알림

## 3. 개발용 키
| 순간 | 키 | 자리표시자 |
|---|---|---|
| 문간 활동 넷 | `entrance.activities.{repair,lookout,pump,welcome}` 아래 `.label`(이름표) / `.caption`(그림 설명, 요청 ①) / `.lines[]`(방송) | {name} |
| 밖에 나간 사람을 기다리는 친구 | `entrance.waiting_friend.lines[]`, 늦어질 때 `.late[]`, 그림 설명 `.caption` | {friend} {name} |
| 아이와 문어, 손님 의자 그림 | `entrance.kid_and_octopus`, `entrance.guest_bench` | — |
| 두드림 | 3일차 첫 두드림 `guest.knock_first`, 그 뒤 `guest.knock[]` | — |
| 손님 대기 | `guest.waiting[]` | — |
| 손님 카드 | `guest.card.title`·`brought_by`·`accept_label`(들이기)·`guide_label`(다른 돔 안내)·`guide_line` | {name} |
| 들임 | `guest.accept[]` | {guest} {role} |
| 잠자리 없음 | `guest.no_bed[]` (재촉 없음) | — |
| 구조된 사람 도착 | `guest.rescued_arrival[]`, 첫 대사 `guest.rescued_first_words[]`(요청 ④), 자리 없을 때 `guest.rescued_no_room` | {name} |
| 출발 | `expedition.send_off[]` | {name} {dest} {return_at} |
| 길이 셋 | `expedition.lengths.{short,half,overnight}` 아래 `.label`·`.time`·`.desc` | — |
| 목적지·미리 보기 이름표 | `expedition.destinations.*`, `expedition.preview_labels.*` | — |
| 보내 두기 | `expedition.leave_it_label`, `expedition.leave_it_line` | {name} |
| 따라 나가기 | `expedition.follow.label`·`start`·`pickup[]`·`handoff` | {name} |
| 갈림길 | `expedition.follow.fork.prompt`·`light_label/desc`·`dark_label/desc` | — |
| 손이 찼을 때 | `expedition.follow.hands_full.prompt`·`drop_label` | — |
| 위험 앞에서 | `expedition.danger.hide_label`(숨기)·`turn_back_label`(돌아서기)·`turn_back_line` | — |
| 위험 넷 × 넘김/못 넘김 | `expedition.danger.kinds.{air_leak,big_one,seam,lost}` 아래 `.prompt`·`.pass`·`.fail`. 귀환 일지 틀(요청 ③)로도 쓴다 | — |
| 귀환 | `expedition.return.{normal[],early[],late[],injured[],found_spot[],spot_not_found,rescued,recalled}` | {name} {spot} |
| 가져온 것 요약 | `expedition.summary.title`·`materials`·`boxes`·`shards`·`left_behind`·`empty`·`log` | {n} {name} {dest} |
| 상자 무늬 여덟 | `sealed_box.patterns.<카테고리>` 아래 `.name`·`.desc`(엔진 카테고리 키 그대로). 튜토리얼 상자는 `sealed_box.blank` | — |
| 상자 위치 | `sealed_box.on_shelf`, 선반이 찼을 때 `sealed_box.on_floor` | {pattern} |
| **헌 바코드로 열림** | `sealed_box.opened_by_old[]` ★ / 새 바코드로 열림 `sealed_box.opened_new` / 같은 날 두 번 `sealed_box.already_today` | {pattern} |
| 7일 뒤 억지로 열기 | `sealed_box.forced_open` | {pattern} {name} |
| 튜토리얼 상자 열림 | `sealed_box.tutorial_open` | — |
| 스팟 단서 | 스캔으로 `spot.clue_from_scan[]` / 원정으로 `spot.clue_from_expedition` | {spot} {name} |
| 스팟 발견 연출 | `spot.discovery_lead` → (기존 `spots_deep.json` `discovery_text`) → `spot.discovery_after` | {name} |

- **★ 헌 바코드로 열리는 순간**은 리더의 버릇(값)을 뒤집는 줄로 썼다. "값이 다 빠진 줄 알았는데, 열쇠로는 아직 쓸 만했네요." 값이 0이 된 물건이 다시 쓸모를 얻는 순간을 관리실이 먼저 놀라는 방식이다.
- **조사 처리**: 자리표시자 바로 뒤에 을/를·이/가·은/는이 오지 않는다(자동 검사 0건). `{return_at}입니다`의 「입니다」는 받침과 상관없이 붙는다.

## 4. 검증
- JSON 유효성: 통과.
- 금지어 0건: 탑·봉인 어휘·하늘·도시·거리·옥상·일곱·열하나·위협·줄표·실명·브랜드. 「발자국」(3막 각인 낱말이고, 물속에는 발자국이 없다)도 0건.
- 문어 발화 0건.
- 교본: S1(발견 뒤에는 "아무것도 건드리지 않고 돌아섰다"까지만), S7(구한 사람의 손을 놓지 않는 장면), S9(한두 문장).

## 5. 제안 (요청 ⑥, 선택)
'길을 잃는다'·'이음매'에 맞는 각인이 아직 없다. 후보 둘:
- **「되짚은 길」**(길 잃음을 넘김): 지나온 자리에 작은 표시를 남기는 버릇이 생긴다. 대가: 같은 길만 다시 가려 한다.
- **「꿰맨 손」**(이음매가 뜯겨 다침): 손끝에 바늘 자국이 남는다. 대가: 남의 잠수복을 먼저 손보느라 자기 일이 늦다.

채택하면 `imprints.json`의 내용과 `imprint_lines.json` 줄을 쓰겠다. 효과 수치는 기획이 정한다.

## F2. 귀환 일지·잠수복 수선 키 (2026-10-04, S15-F2)
서버가 임시 문장으로 짓던 `expedition_return.line`을 이 키들로 바꿔 조립하면 된다. 일지는 짧은 서술체다(관리실 방송이 아니다). 자리표시자 바로 뒤에 조사를 두지 않았다(자동 검사 0건).

| 조각 | 키 | 자리표시자 |
|---|---|---|
| 머리 | `expedition.log.head` | {name} {dest} {length}(=`lengths.*.label`) |
| 가져온 양 | `expedition.log.haul` / 빈손 `expedition.log.haul_empty` | {materials} {boxes} {shards} |
| 두고 온 것 | `expedition.log.left_behind` | {n} |
| 상자 찾음 | `expedition.log.box_found` / 선반이 차서 바닥에 `expedition.log.box_on_floor` | {pattern} |
| 유물 조각을 선반에 | `expedition.log.shard_on_shelf` | {item} |
| 위험 넘김/못 넘김 | `expedition.log.danger.{air,beast,seam,lost}.{pass,fail}` — **서버 kind 이름 그대로** | — |
| 각인 생김 | `expedition.log.imprint_gained` | {name} {imprint} |
| 스팟 발견 / 못 찾음 | `expedition.log.spot_found` / `expedition.log.spot_not_found` | {spot} |
| 단서 얻음 | `expedition.log.clue_gained` | {spot} |
| 구조 | `expedition.log.rescue` / 자리 없음 `expedition.log.rescue_no_room` | {guest} |
| 불러들임 | `expedition.log.recall` | — |
| 튜토리얼 귀환 | `expedition.log.tutorial` (이것 한 줄만) | — |
| 잠수복 수선 | `entrance.suit_repair.label`(버튼「잠수복 손보기」)·`worn`(마모 한계)·`done`(수선 완료)·`lacking`(재료 부족) | — |

조립 순서 제안: head → haul(또는 haul_empty) → left_behind → box_found → shard_on_shelf → danger → imprint_gained → spot/clue → rescue → recall. 같은 내용이 `expedition.log._for_dev`에도 있다.

**키 이름 맞춤(TASKS 요청함, 3D 개발)**: 새로 만든 `log.danger`는 서버 이름(`air·beast·seam·lost`)을 쓴다. 기존 S15-F 키(`danger.kinds.air_leak/big_one`, `lengths.overnight`, `destinations.doorstep/known`)는 아직 바꾸지 않았다. 지금 `expedition3d.js TEXT_KEY` 대응표가 그 이름을 읽고 있어서, 이름을 바꾸면 화면이 깨진다. 서버 이름으로 통일할지 PM이 정해 주면 데이터 쪽 키를 한 번에 바꾸고, 개발은 대응표를 지우면 된다.

## F3. 키 이름을 서버 정본으로 통일 (2026-10-04, PM 결정)
`docs/API_EXPEDITION.md` §1·§5·§8의 id를 그대로 따랐다. 3D 개발은 `expedition3d.js TEXT_KEY` 대응표를 지우면 된다.

| 옛 키 | 새 키 |
|---|---|
| `expedition.lengths.overnight` | `expedition.lengths.long` |
| `expedition.destinations.doorstep` | `expedition.destinations.door` |
| `expedition.destinations.known` | `expedition.destinations.spot` |
| `expedition.destinations.clue` · `.unknown` | 그대로 |
| `expedition.lengths.short` · `.half` | 그대로 |
| `expedition.danger.kinds.air_leak` | `expedition.danger.kinds.air` |
| `expedition.danger.kinds.big_one` | `expedition.danger.kinds.beast` |
| `expedition.danger.kinds.seam` · `.lost` | 그대로 |
| `sealed_box.blank` | `sealed_box.patterns.blank` (상자 갈래 아홉이 한곳에 모였다: food·drink·medical·electronics·stationery·book·apparel·tobacco·blank) |
| `expedition.log.danger.*` (F2) | 처음부터 서버 이름이었다 |

문장 내용은 바꾸지 않았다. 파일은 들여쓰기 2칸으로 다시 저장했다(섹션 사이 빈 줄이 없어졌을 뿐이다).
