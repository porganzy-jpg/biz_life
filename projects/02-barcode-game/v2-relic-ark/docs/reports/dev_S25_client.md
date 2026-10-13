# 개발 S25 — 화면(첫 주 해금 달력·가보 칸·드문 손님·남은 것) 보고

서버 b3e6e9d(계약 docs/API_S19.md §15)에 맞춘 화면 작업. 8002 를 작업 트리 서버로 띄워(RELIC_DEV=1) 검증했다. **커밋하지 않음**(PM 확인 후 커밋).

## 1. 만든 것

| 파일 | 변경 |
|---|---|
| static/base_core.js | 해금 판정 `unlocked(f)`(= `/api/ark.unlocked.features`, 없으면 다 열림) · 메뉴 가림(내보내기=expedition, 한 상=evening_table) · 해금 방송 한 번(`unlocked.new[].line`, 켠 날별로 한 번만 기억) · 5일째 첫 원정 장면(`beat_today.first_session_scene.lines` 6줄, 작은 카드, 관리실/서술 글씨 구분, [내보내기][그렇군요]) · 떠날 때 카드에 다음 해금 예고(`leaving.unlock_teaser`) · 「나중에 이름 붙이기」(`subtype_pick.later_ok` && !needed → 단추 하나만, 누르면 고르기 펼침) · 가보 줄(`where.heirloom` → 「가보로 · ○○」, 바꾸기 물음 `ask_swap` → [바꿔 드리기][그대로 두기], 결과 줄 placed/swapped/use/speak, 전설은 「세 번째 기억」 큰 카드) · 사람 카드 가보 표시(이름·등급·상자에) · 드문 손님 색 바꿔 그리기(새 그림 없이 hue-rotate) · **자리 소품**(아래) · 다른 카드의 고르기 잔여 제거 · **「어디로」 자가 검사 `ARKCORE.selfTest()`** · 패널이 열려 있으면 문어 「어디로」 카드 숨김 |
| static/base_collect.js | 도감 「찾아온 이」 칸 16칸(보통 8 + 드문 8, `visitors_book[].rare`), 드문 칸 설명 줄, 문어 이름 칸은 `octopus_name` 해금 뒤에만, 밤사이 `third_memory` |
| static/base.js | 방 카드 「내보내기」는 expedition 해금 뒤에만 · 사람 줄/이름 `evolved_ko` 우선 · `drawRoomExtra` 에 그 방 사람 목록 전달(자리 소품용). PM 의 WALK_PACE 수정 5곳 그대로 |
| static/base.css | S25 칸: `.subpick.later`/`.sublater`, `.heirrow`, `.leave-in .teaser`, `.scenecard .sl-*`, `.their`, `.cx.vb.rare` |

### 자리 소품(남은 것)
- `decor_meta.keepsake_spots.by_plate` 를 그 방 플레이트(없는 방은 plate_name_map: pantry/lounge→storage, decoder→quarters, bath→infirmary, well→greenhouse, generator→power)로 찾아, **그 방에 선 사람 순서대로 앞자리부터** 하나씩. 놓는 물건 우선순위: 끝 매듭 자리(seat) > 가보(상자에 넣은 것 제외) > 최근 받은 물건 1개.
- 끝 매듭: `core.residents[rid].seat.item`(이름) → 그 사람 items 에서 찾아 갈래·하위 종류 소품 → `seat_stand.png` 를 먼저, 그 위(item_floor_y=18)에 물건. `own_prop_arcs` 넷(arc_cook_seat 등)은 받침 없이 기존 매듭 소품이 이미 방에 있으므로 건너뛴다.
- 자리가 모자라거나 방에 서지 않은(문간·홀) 사람은 예전처럼 발치에 그린다(같은 물건을 두 번 그리지 않게 같은 프레임에 자리에 그렸으면 발치는 건너뜀). 배율은 칸 좌표 ×1.6(선반 위 다른 물건과 같은 크기 — ×2.4 는 너무 커서 줄임).

## 2. 버그 확인 — 「요리사 기색 줄이 정찰병 옆에」
- 화면 경로를 다시 읽었다: `normSuggest` 는 각 행의 `target.resident_id` 로 사람을 찾고, 얼굴·이름·기색(hint_ko)을 **그 행에서만** 꺼낸다. 배열 번호로 명부와 짝 짓는 곳은 없다(「어디로」, 문어 「어디로」 둘 다).
- 지금 재현되지 않는다. 다만 얼굴 함수는 사람을 명부에서 못 찾으면 `role` 이 없을 때 정찰병 얼굴로 떨어지는 기본값이 있었다 — 이 경로가 의심 지점이다(명부가 잠시 비었던 응답 등). 서버 행에는 `role` 이 있으므로 그 경우에도 이제 서버 행 role 을 함께 검사한다.
- **자가 검사 추가**: `ARKCORE.selfTest()` — 「어디로」의 사람 칸마다 (얼굴 role) = (명부 role) = (서버 행 role), (보이는 이름) = (명부 이름). 단추에 `data-rid`·`data-srole`, 얼굴에 `data-role` 을 붙였다.
- 결과: 1일째(라벨)·3일째(기색) 14번 검사 모두 ok. 예) 3일째 「새벽(cook) — 새벽 님이 국자를 내려놓고 빈 컵에 김만 쐬고…」 얼굴 cook, 서버 행 cook.

## 3. 검증

방법: scratchpad `t_s25.py`(Playwright, 새 uid, 1일째 → 가보 두 번 → 떠날 때 카드 → /api/dev/advance 로 2·3·5일째), `t_s25spots.py`(/api/ark/station 으로 셋을 식량창고에 세우고 자리 소품·받침 확인).

| 항목 | 844×390 | 1280×800 |
|---|---|---|
| 콘솔 오류 | 0 | 0 |
| 400 이상 응답(403 포함) | 0 | 0 |
| braceCheck(dom/토스트/캔버스) | 0/0/0 | 0/0/0 |
| ArkMove.selfTest | ok | ok |
| ARKCORE.selfTest(「어디로」 얼굴·기색) | 5/5 ok | 9/9 ok |
| 1일째 내보내기·한 상 숨김, 방 카드 내보내기 없음 | 예 | 예 |
| 5일째 첫 원정 장면 6줄 + 내보내기 열림 | 예 | 예 |
| 도감 찾아온 이 16칸(드문 8) | 예 | 예 |

API 엔드포인트 비교(아): 서버에만 있고 화면이 안 부르는 것 = /api/dev/advance, /api/dev/imprint(개발용), /api/expedition/scene, /api/stats — 이전과 같음.

### (자) 응답 필드 → 화면 사용 (두 크기 모두 seen=used=true)
| 필드 | 화면에서 |
|---|---|
| unlocked(features) | 1일째 메뉴 내보내기·한 상 숨김, 방 카드 내보내기 없음 |
| unlocked.new[].line | 2일째 방송 「오늘부터 방에도 물건을 둘 수 있습니다…」(로그 `unlock decor_place`) |
| leaving.unlock_teaser | 떠날 때 카드 「방에도 물건을 둘 수 있습니다. 다음에 켜시면…」 |
| beat_today.first_session_scene | 5일째 「문간 문」 카드 6줄 |
| where.subtype_pick.later_ok | 「나중에 이름 붙이기」만 보이고 누르면 고르기 펼침 |
| where.heirloom | 진귀함 음료 → 「가보로 · ○○」 3명 |
| ask_swap | 전설 식품을 같은 사람에게 → 「○○ 님은 이미 「녹슨 노란 거품 병」 가보를 아끼십니다…」 [바꿔 드리기][그대로 두기] |
| heirloom.lines | 바꿔 드리기 → `heir give legendary swapped`, 줄 띄움 |
| core.residents[].heirloom | 사람 카드 「가보 「작은 기름 잠긴 생선 통」 전설」, 식량창고 선반 자리에 그 소품 |
| visits[].form=rare | 서버 조건(진귀함 이상 진열 + 꼬리표 + 확률)이 며칠 걸려 **견본 주입**: 서버 모양 그대로 넣고 그려짐 확인(`ARKCORE.rare()` = {blanket_crab: 2}) |
| visitors_book[].rare | 서버가 준 rare 칸 8개를 그대로 그림, 1칸은 견본 주입으로 켜진 모습 확인 |

스크린샷(docs/reports/shots/, 각 _844·_1280): s25_day1, s25_day1_scan, s25_later_closed, s25_later_open, s25_heir_row, s25_heir_placed, s25_heir_swap, s25_heir_lines, s25_their, s25_leave_teaser, s25_day2_broadcast, s25_day3_signs, s25_day5_scene, s25_rare_visitor, s25_codex_visitors, s25_spots, s25_seat.

## 4. 교본 적용
- D2(숫자는 화면의 무엇으로): 가보 등급은 사람 카드 표식과 방 선반 위 실제 소품으로, 끝 매듭은 받침 위 물건으로 보인다.
- D4(막힘은 버그): 패널 위에 문어 카드가 겹치던 것(큰 창 둘)을 고쳤고, 「어디로」 짝 검사를 자가 검사로 남겼다.
- D5(첫 3분 루프): 1일째 화면에서 메뉴가 줄었다(내보내기·한 상 숨김). 가보 줄은 귀함 이상 카드에만, 나중에 이름 붙이기는 단추 하나 — 탭 수 늘지 않음.
- D6(결정성): 같은 바코드 = 같은 등급(두 uid 로 8800000770376=진귀함, 8800000773704=전설 확인).
- D7(데이터가 규칙을 든다): 자리 좌표·받침·매듭 예외는 decor_meta/props_meta 에서 읽고 코드에 좌표를 박지 않았다(플레이트 이름 대응표만 코드).
- 원칙과 다르게 한 곳: 드문 손님은 새 그림 없이 색만 돌렸다(그림 담당 그림이 오면 바꾼다 — 임시 그림은 아니고 기존 도트의 색 변주).

## 5. 자가 검수
1. 새 숫자가 화면의 무엇으로? — 가보 등급은 표식·선반 소품, 해금은 메뉴가 생기는 것 자체와 방송 한 줄.
2. 첫 3분 탭 수? — 늘지 않음. 1일째는 오히려 메뉴가 줄었다.
3. 같은 입력 같은 결과? — 등급·가보 선택지는 서버 결정. 해금 방송은 켠 날+기능 키로 한 번만.
4. 폰 가로에서 손가락 조작? — 844×390 에서 가보 단추 높이 34px(가로 모드 줄임, 그 외 40px), 바꾸기 단추 2개가 카드 안에 다 보임(s25_heir_swap_844).
5. 회귀 로그? — 1·3일째 「어디로」, 각인·걷기 그대로(ArkMove.selfTest ok), 콘솔 0, 괄호 0.

## 6. 미완·리스크
- 드문 손님 실제 방문은 서버 조건 때문에 화면 시험에서 견본 주입으로만 봤다. 서버 시험(test_s25)이 조건을 맡는다.
- 끝 매듭 받침은 아직 사슬을 끝까지 간 사람이 없어 견본 주입으로 확인. 바닥 가운데 자리(storage·power 의 floor)는 사람이 서면 가린다 — 좌표는 decor_meta 를 따랐다.
- 자리는 「지금 그 방에 선 사람」 기준이라 사람을 옮기면 물건도 따라간다(서버 seat 에 방이 없음). 끝 매듭을 방에 영구히 두려면 서버가 seat 에 slot 을 넣어 줘야 한다 → 요청함.
- 1280 에서 heirloomRow 가 한 카드에 두 번 불리는 로그가 있다(앞 것을 지우고 다시 그리므로 화면은 하나). 원인은 afterReveal 이중 호출로 보이며 해롭지 않아 남겨 둠.
- 실제 아이폰 확인은 사용자 몫(카메라 S23 그대로).

## 7. 요청
- 서버: `core.residents[rid].seat` 에 매듭을 맺은 방 `slot` 을 넣어 주면 받침을 그 방에 고정할 수 있다.
- 서버 담당께 회신: 「어디로」 얼굴·기색은 행마다 target.resident_id 로 짝 짓고 있었고 자가 검사로 확인. subtype_pick 잔여는 화면 결함이었고 카드마다 지우게 고쳤다.
