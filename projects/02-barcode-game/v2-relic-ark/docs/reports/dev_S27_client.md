# 개발 S27 화면 — 진행 메모 (2026-10-17)

- [대기] S27 화면 본작업(낮 한 상, 가보 후보 한 줄, 수첩 「이름 다시 붙이기」, 습격 「관리실이 대신 막을까요?」, tomorrow_ask 와 「오늘은 여기까지」 배치, 「선반이 꽉 찼습니다」를 세션에 한 번)은 서버 API_S19 §17 이 나온 뒤에 시작한다. 2026-10-17 현재 §17 없음.

## r5-5 「매듭 장면에 같은 문장이 겹침」 — 화면 쪽 확인·수정 (커밋하지 않음)
5차 플테: 아이 2매듭에서 「누구는 따뜻하대. 누구는 조용하대. 누구는 모른대. 다 적었어.」가 두 번 나왔다. 원인은 서버가 역할 없는 대체 줄(`_alt`)을 announce 와 line 양쪽에 실은 것이다(서버·시나리오가 고칠 일). 화면도 같은 말을 거르지 않고 그대로 두 번 보여 줬다. 화면이 겹치게 만드는 곳은 셋이었다.
1. 매듭 카드(showBeat): `broadcast(=announce)` 와 `line` 을 둘 다 그린다.
2. 반응(react): 반응 대사 아래에 `reaction.announce` 를 방송으로 다시 띄운다. 곧 뜰 매듭 카드의 문장과 같을 때도 띄운다.
3. 방송(K.say): 같은 문장이 연달아 와도 다 띄운다.

**수정** (static/base_core.js):
- 비교 함수 `sameT`: 따옴표·공백·문장부호를 뺀 글자로 비교한다.
- 매듭 카드: 방송과 대사가 같으면 대사만 보인다(로그 `beat dedupe`).
- 반응: 방송이 대사와 같거나, 매듭 카드의 announce·line 과 같으면 방송하지 않는다.
- `K.say` 감싸기: 지금 보이는 매듭 카드·반응 말풍선에 이미 있는 문장, 또는 60초 안에 띄운 같은 문장은 거른다(`ARKCORE.dupSkips`).
- 검수용 `ARKCORE.queueBeat` 를 열었다.

**검증** (scratchpad t_dup.py, 8041 별도 포트 — 8002 는 건드리지 않음, 확인 뒤 8041 껐음):
- 시험 입력은 서버 r5-5 모양을 그대로 넣었다(announce = line = 위 문장).
- 결과: 카드에는 「…다 적었어.」 한 줄만, 방송 칸은 비었다. 카드에 보이는 그 문장을 방송으로 다시 보내면 걸러졌고, 같은 방송을 두 번 보내면 두 번째가 걸러졌다(dupSkips 2).
- 844·1280 콘솔 오류 0. 스크린샷 s27_dup_card_{844,1280}.png.

**남는 것**: 서버 쪽 근본 수정(`_alt` 는 line 에만, announce 는 관리실 서술 대체)은 서버·시나리오 몫이다. 화면은 그것과 무관하게 겹침을 막는다.

## S27 화면 본작업 (API_S19 §17 + where.rename) — 2026-10-17, 커밋하지 않음
확인은 8041 별도 포트에서만 했다. 8002 는 건드리지 않았고 확인 뒤 8041 은 껐다. 시험 스크립트는 scratchpad t_s27.py.

| 항목 | 화면 | 파일 |
|---|---|---|
| 한 번에 고르기(peek.quick_pick) | 갈래를 모르는 바코드: 그림 8개(props x4) + 「기타」. 고르면 `/api/scan {user_category, user_subtype}` 한 번이고 「이게 뭐예요?」를 다시 묻지 않는다. 「기타」 → 예전 갈래 8개 → 하위 종류 | base.js showPicker·handleCode |
| 고른 뒤 첫 만남 줄(first_meet kind=subtype, replaces) | 갈래 짐작 줄을 지우고 「처음 보는 우유입니다.」 | base_core subtypePick |
| 이름 다시 붙이기(where.rename) | 이미 이름을 붙인 바코드를 다시 찍으면 「이름 다시 붙이기 ▸」 한 줄. 누르면 rename_confirm 문장과 이름 단추가 나오고, 지금 이름은 눌리지 않는다. 바꾸면 그림·이름·첫 만남 줄을 다시 그리고 done_ko 를 띄운다. 하루 한 번이라 두 번째는 「오늘은 한 번 바꾸셨습니다」 단추가 눌리지 않는다 | base_core renameRow |
| 간직 메모(keep_note) | 가보 칸이 열리기 전에 들어온 귀함 이상 카드에 단추 없는 한 줄. 같은 물건은 세션에 한 번 | base_core keepNote |
| 가보 후보 한 줄(hint_ko) | 「가보로 · 온새」 아래 「부엌에서 쓰던 손때 묻은 물건을 아끼시는 분입니다.」. 접힌 줄이 이미 묻고 있어서 펼쳤을 때 같은 물음이 한 번 더 나오지 않게 했다. heirloom_refused 면 결과 한 줄만 | base_core heirloomRow |
| 떠날 때 순서(order/leave_order) + 내일의 부탁 합치기(r5-3) | 서버 순서대로 그리고, 빠진 블록은 뒤에 붙인다. next_visit.kind=tomorrow_ask 면 「다음에 켜시면」 아래 그 사람 얼굴 + 부탁 한 줄. 「오늘은 여기까지」 문장은 없다 | base_core leaveCard |
| 낮 한 상(evening_table.daytime) | 카드 제목 「낮 상」, 문장은 서버 open_ko·table_prompt(daytime_table) | base_core openTable |
| 관리실이 대신 막기(raid.office) | 습격 카드에 물음과 [관리실에 맡기기][직접 하기]. 맡기면 `/api/raid/auto_defend` → 결과 글자·office.line 방송. 「직접 하기」를 누르면 그 습격 동안 접는다 | base.js renderRaid·autoDefend |
| 선반 꽉 참(세션에 한 번) | 처음 한 번만 바꾸기를 묻는다. 그 뒤로는 서버 `stored.quiet_ko` 한 줄(흐린 색) | base.js showReveal |
| 첫 진입(overnight.first_entry) | 「어서 오십시오」 판(morning.first_entry). 하루 소비 줄은 그사이 창 맨 앞으로 옮겼다 | base_collect morning |
| 덤 | 습격 카드를 펼치면 문어 「어디로」 카드를 잠시 숨긴다(844 에서 둘이 겹쳐 단추를 가리던 것). 이름을 묻는 중에는 짐작한 하위 종류 그림 대신 갈래 그림 | base_core·base.js |

**검증 (844·1280)**
- (자) 13개 필드가 모두 응답에 오고 화면에서 쓰인다(seen=used): quick_pick, first_meet.subtype, keep_note, where.rename, rename.done_ko, heirloom.hint_ko, leave.order, next_visit.tomorrow_ask, evening_table.daytime, raid.office, auto_defend.office, stored.quiet_ko, overnight.first_entry.
- 관리실 맡기기 결과: held(plan 있음).
- 콘솔 오류 0. 이름 두 번째 바꾸기 400 은 시험에서 일부러 피했고, 그 밖에 400 이상 응답은 0. braces 0.
- 스크린샷(s27_*_{844,1280}): first_entry, quick_pick, quick_card, keep_note, rename_open, renamed, leave_order, heir_hints, shelf_quiet, daytime_table, raid_office, raid_office_done.

**남은 것**
- 기억 벽(memory_wall)과 「어디로」의 pinned 표시는 이번 지시 목록에 없어서 하지 않았다(서버는 준비됨).
- t_s28 시험은 한 번에 고르기 때문에 고르는 길이 바뀌어 고쳐야 한다(화면 결함은 아님).

## 남은 화면 작업 — 기억 벽 · pinned 확인 · S28 시험 고침 (2026-10-17, 커밋하지 않음)
확인은 8041 별도 포트에서만 했다(8002 6차 진행 중이라 건드리지 않음). 확인 뒤 8041 은 껐다.

**기억 벽(/api/ark.memory_wall, POST /api/memory_wall/hang)** — base_core.js·base.css
- 방 카드(식량창고): 「식량창고 · 기억 벽 1/4 · 「첫 물건」」 한 줄과 [여기 걸기](다 차면 단추 없음). 문장 키는 `memory_wall.hang_label`, 없으면 기본값.
- 작은 패널:
  - 고리 넷을 보여 준다. 첫 칸은 「○○ 님께 처음 드린 것」 또는 「처음 찍은 것」.
  - prefilled_ko 와 hang_prompt_ko 를 쓴다.
  - 선반·창고 물건을 단추로 보여 주고, 누르면 hang 을 보낸 뒤 서버 line 을 띄운다.
- 다 차면 complete_ko(관리실) + story 세 줄 장면 카드(scenecard). 문어 카드가 떠 있어도 기다리지 않는다.
- 열림 방송 open_ko: 처음 받을 때 한 번만 띄운다(로컬 저장).
- 그림:
  - 식량창고(storage 플레이트) 왼쪽 빈 벽에 가로 막대와 고리 넷(칸 좌표 (150~300, 128)). 선반 줄·꾸밈 받침·탁자와 겹치지 않는 자리를 실화면에서 골랐다.
  - 건 물건은 서버 prop(없으면 by_subtype)을 끈에 매달아 그린다. 빈 고리는 고리 모양만 보인다.
- `memory_wall`·`leave_order` 는 /api/ark 에만 오므로 다른 응답 뒤에도 이어 쓴다.
- 덤: 방 카드를 열면 문어 「어디로」 카드를 잠시 숨긴다(844 에서 「여기 걸기」를 가리던 것).
- 검증(844·1280): 7일째 열림 → 방 카드 줄 → 패널(고리 4, 물건 10) → 세 번 걸어 4/4 → 장면 카드(complete + story 3). 벽 그림 `ARKCORE.wall()` = 4개. 콘솔 오류 0, 400 이상 0, braces 0.
- 스크린샷: s27_wall_{room,card,panel,complete,full,zoom}_{844,1280}.png

**pinned 「어디로」 줄**: 표시는 바꾸지 않았다(지시대로 구분 없음). 1일째 떠날 때 내일의 부탁을 받은 사람(asked)이 2일째 「어디로」 줄에 남는지 세 번 확인했다.
- 결과: 3/3 남음. scout asked·warm 두 번, cook fit·chain_beat 한 번.
- 화면은 행마다 target.resident_id 로 그리므로 빠지지 않는다(selfTest 그대로 ok).

**S28 시험 고침**: t_s28.py·t_s28d3.py 가 한 번에 고르기 화면에서 「기타」 → 갈래 길로 간다. 844 우유 그림 prop_white_carton, 1280 가보 접기 펼침이 동작하고 콘솔 오류는 0.

## S29 서버 변경 대응 (같은 날, 커밋하지 않음)
- 가보 후보 `second:true` 행(후보가 한 명뿐일 때 서버가 덧붙인 사람)은 접어 둔다. `more_ko` 「다른 분도 보여 드릴까요?」를 눌러야 보인다.
- 확인: 8041, 844, 서버 모양 견본. 누르기 전에는 「가보로 · 첫째」와 「다른 분도…」만 보이고, 누른 뒤에는 「가보로 · 둘째」가 보인다. 콘솔 오류 0. 검수용 `ARKCORE.heirRow`.
- 이름 다시 붙이기가 바코드마다 하루 한 번으로 바뀐 것: 화면은 이미 `where.rename.can_today` 를 그대로 따르므로 바꿀 것이 없다.
- first_reason 표시(선택), expedition_return 자동 지움, quick_pick 기본 8 교체, 습격 3일째: 화면 변경 없음.

## S30 서버 변경 대응 (같은 날, 커밋하지 않음)
- 스캔 응답 `unlock_new[]`(가보 칸 해금 방송): 켠 날 해금과 같은 열쇠(기능|켠 날)로 한 번만 띄운다. 처음에는 /api/ark 의 unlocked.new 와 스캔의 unlock_new 가 같은 방송을 두 번 띄워서 열쇠를 맞췄다. 확인: 8041, 3일째 진귀함 스캔에서 로그 `unlock heirloom` 1회.
- `raid.hint_action_ko`: 습격 카드 미리보기 문장(#rwould) 아래에 한 줄로 붙인다(.rhintact). 시험 방주의 소리 단계에서는 미리보기 자체가 숨어 있어 화면에서는 아직 못 봤다. 금·방 잃음 미리보기가 뜨는 단계에서 다시 확인해야 한다.
- 밤사이 `guaranteed_rare`: 그사이 줄은 서버 ko 를 그대로 쓰므로 바꿀 것이 없다. 약·담배·술 반응 상한, first_reason story, 꾸밈 제안 한 줄도 화면 변경이 없다.
- 844 콘솔 오류 0. 8002 는 건드리지 않았다.
