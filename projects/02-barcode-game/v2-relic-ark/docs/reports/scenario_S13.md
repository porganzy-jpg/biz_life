# 시나리오 보고 — S13-C 재미·수집 개선 문장 (2026-10-03)

근거: `docs/reports/review_fun_collection_20261003.md` 추천 1~4(사용자 승인). 목소리: `docs/TEXT_VOICE.md`.

## 1. 만든 것
`data/ui_moments.json` (신규, 화면 문자열 63개). 커밋은 하지 않았다.

## 2. 개발용 키 목록
| 순간 | 키 | 자리표시자 |
|---|---|---|
| 재스캔으로 닦기 | `shelf.rescan` / 다 닦은 뒤 `shelf.rescan_max` | {item} |
| 닦임 단계 이름·한 줄 | `shelf.levels.1·2·3.label` / `.line` | — |
| 희귀 변형 발견 | `variant.found`, 이름표 `variant.label` | {item} |
| 가문 세트 진행 | `family_set.progress`, 하나 남음 `family_set.one_left` | {family} {n} {total} |
| 가문 세트 완성 | `family_set.complete.<가문 코드>` (18개 가문 전부), 없으면 `family_set.complete_default` | {family}(기본형만) |
| 절차 생성 가문 첫 만남 | `family_set.first_meet_generated` | {family} |
| 도감 미확인 칸 | `codex.unknown` + `codex.category_hints.<카테고리 8종>`, 힌트 없으면 `codex.unknown_no_hint` | {hint} |
| 금 | 생겼을 때 `crack.occurred` / 아침에 아직 금 `crack.still_cracked` / 고침 `crack.repaired`, 이름표 `crack.label_cracked`·`crack.label_repair` | {room} |
| 일손 없어 반만 돌아감 | `staffing.reduced`, 이름표 `staffing.label` | {room} |
| 덮개 대상 방 공개 | `lid.target_revealed` | {room} |
| 답하지 않은 습격의 아침 보고 | `night_judge.blocked` / `.passed` / `.cracked` | {creature} {room} |
| 하루 마감 요약 | `day_end.open` → (`scans` / `blocked` / `floors` 중 해당 줄, 없으면 `nothing`) → `close` | {scan_count} {blocked} {floors} |
| 문어 선물 | `octopus_gift.pop`, 이름표 `octopus_gift.label` | {item} |
| 사건 카드 띠 | `event_strip.label`(「관리실 쪽지」), `event_strip.line` | — |

- **조사 처리**: 자리표시자 바로 뒤에 을/를·이/가·은/는이 오지 않게 문장을 짰다. 「」, 쉼표, '에', '쪽', '손님', '가문'으로 이었으므로 받침 처리 코드가 필요 없다(자동 검사 0건).
- **가문 세트 개수**: `family_lore.json`의 `set_count`가 아직 3~6으로 제각각이다. DECISIONS 2026-09-27에서 3으로 통일하기로 했으니 `{total}`은 서버가 정한 값을 넣어 달라.
- **카테고리 키**: `food·drink·medical·electronics·stationery·book·apparel·tobacco`(엔진 키 그대로).

## 3. 기존 네 파일 점검 (S12-E에서 다시 쓴 것)
- `wishes.json`·`first_meet.json`·`companion_octopus.json`·`day_end.json`의 목소리는 문제없다. 고친 곳은 없다.
- 빈 곳은 셋이었고, 모두 `ui_moments.json`에 넣었다.
  - day_end에 '금'과 '밤사이 판정' 장면이 없었다 → `crack.*`, `night_judge.*`
  - first_meet는 알려진 18개 가문만 다룬다 → `family_set.first_meet_generated`
  - 문어 선물이 도착하는 순간의 알림 한 줄이 없었다 → `octopus_gift.pop`
- 위치를 이렇게 정한 이유: 기존 파일에 항목을 덧붙이면 개발 로더 구조가 바뀔 수 있어서 피했다.

## 4. 검증
- JSON 유효성: 통과.
- 가문 코드 18개가 `family_lore.json`과 정확히 일치한다.
- 금지어 0건: 탑·봉인 어휘·하늘·도시·옥상·일곱·열하나·위협·줄표·실명.
- 교본 적용: S9(한두 문장), S1(덮개 공개 줄은 규칙을 설명하지 않고 습성 한 마디로 끝낸다), TEXT_VOICE §3(버튼은 이름표, 알림은 방송).

## 5. 확인할 것
- **덮개 공개 문장**: 대상이 공개된 뒤에 사람을 옮겨도 되는지는 규칙이 아직 미정이다. 그래서 문장은 "움직이는 것 위에는 앉지 않습니다"라는 습성만 말하고, 지시는 하지 않았다. 규칙이 정해지면 한 줄을 덧붙인다.
- **다 닦은 뒤 재스캔한 물건**의 쓰임(분해 등)이 미정이라 「따로 모아 두겠습니다」로 두었다.
