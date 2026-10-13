# 개발 S26 — 화면(물 빼기 비용·잠긴 칸 문장·끝 매듭 자리 고정) 보고 (2026-10-13)

서버 S26(API_S19 §16, 커밋 전 작업 트리)을 8002 에 다시 띄워(RELIC_DEV=1) 확인했다. 시험 스위트는 TestClient 라 8002 재시작과 무관. **커밋하지 않음.**

## 1. 만든 것 (static/base.js · base.css · base_core.js)
- **물 빼기 한 줄**: 빈 칸·물 찬 칸 카드와 방 고르기 패널에 방 비용과 따로 「물 빼기 · 전력 2 · 부품 1 · 식량 4」(`/api/ark.drain_cells[slot].drain_cost`). 되찾기 칸(`reclaim`)은 「다시 물 빼기 · 절반 · …」. 0m 칸·문간은 줄 없음.
- **모자랄 때**: 모자란 항목만 흐리게(`.ci.dim`, 투명도), 한 줄 「전력이 2 모자랍니다. 전자 물건을 찍으면 모입니다.」(`material_sources[k].scan`, 괄호 설명은 뺌, 줄표 없음). 물 빼기 단추는 `disabled` 만. 빨간색 없음 — 옛 `.bopt.lack small` 의 oxblood 도 회갈색으로 바꿨다.
- **방 단추**: `build_options[room].by_slot[slot]` 의 `missing`(방+물 빼기 합)·`can` 으로 판정. 방 비용 항목 중 모자란 것만 흐리게, 그 방 몫 모자람 한 줄. `cond_missing`(학자 1명 등)은 작은 한 줄.
- **잠긴 칸**: 맵 위 글자 = `ui_moments.sealed.{tower,rock}.label`, 카드 = `.line`(시나리오). 기본값도 새 문장. 180m 아래는 그대로 tower_lore.below_limit.
- **끝 매듭 자리 고정**: `core.residents[rid].seat.slot` 이 있으면 그 방의 keepsake_spots 첫 자리에 받침+물건을 고정(사람이 옮겨도 남는다). slot 이 없는 옛 값만 그 사람이 선 방.

## 2. 검증 (scratchpad t_drain.py, t_s25spots_slot.py)
| 항목 | 844×390 | 1280×800 |
|---|---|---|
| 0m 칸(slot 3) 카드: 물 빼기 줄 없음 | 예 | 예 |
| 60m 칸(slot 4) 전력 0: 「물 빼기 · 전력 2 · 부품 1 · 식량 4」, 전력 2 만 흐림, 「전력이 2 모자랍니다. 전자 물건을 찍으면 모입니다.」, 단추 눌리지 않음, 빨간 글자 없음 | 예 | 예 |
| 전자 2장 찍은 뒤: 흐림 없음·단추 눌림 → 패널 방 목록(모자란 항목만 흐림) → 정수실 짓기, 자원 식량 4→0·전력 4→2·부품 5→3·물 5→3(방 물2·부품1 + 물 빼기 전력2·부품1·식량4) | 예 | 예 |
| 되찾기 줄(서버 모양 견본 주입) 「다시 물 빼기 · 절반 · …」 | 예 | 예 |
| ui_moments.sealed 읽힘(「잠긴 칸」 / 「이 칸은 문이 안쪽에서 굳게 잠겨 있습니다…」) | 예 | 예 |
| seat.slot=2 견본 → 식량창고 첫 자리 받침 고정(fixed), slot=99 인 사람은 이 방에 받침 없이 가보 | — | 예 |
| 콘솔 오류 / 400 이상 / braces | 0 / 0 / 0 | 0 / 0 / 0 |

스크린샷: docs/reports/shots/s26_{card_0m,card_short,card_ok,panel,built,card_reclaim}_{844,1280}.png, s26_seatslot_1280.png

## 3. 교본
- D2(숫자는 화면의 무엇으로): 물 빼기 값은 카드 한 줄, 모자람은 그 항목의 흐림과 「어디서 모이나」 한 줄.
- D4: 모자람은 막힘이 아니라 다음 할 일(찍기)로 말한다.
- D5: 새 탭 없음(기존 카드·패널에 줄만).

## 4. 남은 것
- `consumption`·`consumed_while_away`(하루 소비)는 아직 화면에 안 그렸다 → 다음 작업(밤사이 한 줄·자원 띠).
- 짓기 400 의 `missing_ko` 는 지금 토스트(detail)로만 보인다(카드가 미리 막으므로 보통 안 나온다).

## 5. 후속 (PM 2차 지시) — 별도 포트 8041 에서 확인
- **8002 관련 알림**: 첫 S26 확인 때(라운드 5 공지 전) 8002 를 작업 트리 서버로 한 번 다시 띄웠다(RELIC_DEV=1). 공지 이후로는 8002 를 건드리지 않았고, 확인은 `uvicorn server:app --port 8041` 로만 했다. 확인이 끝난 뒤 8041 은 껐다.
- **모자람 문장**: `ui_moments.shortage.line`(「{res} 쪽이 {n} 모자랍니다.」) + `material_hint.<재료>` 로 조립한다. 예) 「전력 쪽이 2 모자랍니다. 전자 물건을 찍거나, 발전실을 두시면 모입니다.」 material_sources 조립은 키가 없을 때만 쓴다.
- **하루 소비**:
  - 그사이 창에 한 줄을 넣었다(`consumed_while_away` → `overnight.consumed.both|food_only|water_only`, 사기가 내려갔으면 `hungry` 를 덧붙인다). 확인한 문장: 「그사이 식량 1, 물 1 정도를 다들 나눠 드셨습니다.」
  - 자원 띠의 칩을 누르면 칩 아래에 작은 줄이 뜬다(6초 뒤나 다른 곳을 누르면 닫힘). 식량·물이면 `consumption.tip` 「지금 3분이 하루에 식량 1.8, 물 1.8 정도를 드십니다.」 + material_hint, 그 밖의 칩은 material_hint 만 보인다. 칩이 눌리지 않던 문제(topbar pointer-events)도 고쳤다.
- **844 타이틀**: 배경 담당이 phone 로고를 y=140 으로 옮겼다. 글 상자 높이를 재서, 로고 아래에 들어가면 아래에 둔다. 844 와 1280 모두 로고 → 문장 → 단추 순서이고 글자는 어둡게 한 자리 위에 온다(title_d1_844.png).
- **검증**(t_cons.py, 844·1280):
  - 콘솔 오류 0, 400 이상 0, braces 0.
  - (자) consumed_while_away·consumption: 응답에 오고 화면에 쓰인다.
  - 굶은 경우(hungry)는 이번 시험에서 식량이 바닥나지 않아 문장 조립만 확인했다.
- 스크린샷: s26_overnight_d1_*, s26_respop_*, title_d1_*, title_hungry_*.
