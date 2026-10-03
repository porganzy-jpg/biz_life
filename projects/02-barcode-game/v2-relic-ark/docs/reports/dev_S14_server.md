# 개발(서버) S14-A 보고서 — 능력치가 생산을 바꾼다 (2026-10-03)

근거: PM S14-A 지시(사용자 승인), 수치 `data/balance/stakes.json stat_production`(기획 확정: clamp 0.88~1.18, mean, injured_counts=false, room_stat 14방). 계약: `docs/API_S13.md §S14`(작성 후 main 에 알림). 커밋하지 않았다. static/·balance 파일은 이번에 고치지 않았다.

## 1. 만든 것
| 항목 | 내용 | 위치(`server.py`) |
|---|---|---|
| 생산식 | 방 산출 = (기본 + 그 방 사람의 역할 보정) × `staff_mult[n]` × `stat_mult` × 금 × 불. `stat_mult = clamp(1 + per_point × A)`, A = aggregate(mean/sum_excess/best_plus) of (방 능력치 − center). 사람 없으면 1.0 | `stat_factor`, `room_mult`, `tick_production` |
| 역할 보정은 그 방에서만 | `role_bonus_in_room_only`: 역할 effects.room_bonus + 각인 room_bonus 를 **그 방에 선 사람 것만** 합산. 끄면 예전(role_effects 합계). 다른 역할 효과는 그대로 | `resident_room_bonus`, `room_bonus_for` |
| 부상 규칙 | `injured_counts=false` → 부상자는 머릿수·능력치·역할 보정에서 빠진다(전투 판정 명단은 그대로) | `staff_people` |
| 스냅숏 | 접촉 순간 **사람 id**(`staff_snapshot.ids`)도 저장. 그 틱은 머릿수·능력치·보정 모두 그 사람들로. 옛 스냅숏(counts 만)은 능력치 1.0 으로 받아 준다 | `take_staff_snapshot`, `snapshot_people`, `room_segments` |
| 화면에 내보냄 | `stats_meta.room_stat`(정본 표), `stats_meta.stat_production`(매개변수), `production[slot]`: `stat`, `stat_mult`, `per_person[]`, `role_bonus`, 스냅숏 틱이면 `now_mult`·`now_stat_mult` | `public_state`, `production_public` |
| 드래그 미리보기 | PM 결정대로 **서버가 계산**: `move_preview[resident_id][slot\|"hall"] = {room_delta_pct, from_delta_pct, can}`. 홀은 JSON 키에 null 을 못 써서 `"hall"`. 모든 public_state 응답에 다시 계산된다 | `room_output`, `move_preview` |
| 안정성 | 기획이 stakes.json 을 쓰는 도중 잠깐 깨진 JSON 을 읽어 안전값으로 떨어지는 것을 실제로 겪었다 → 이제 **직전에 읽은 값을 지킨다**. 안전값도 확정 값에 맞췄다(polish [3,5], stat_production) | `stakes()` |
| 테스트 | 새 `tests/test_s14_server.py` 6묶음 26항목. `tests/test_s13_server.py` 의 생산 기대값 3곳을 새 식(같은 함수)으로 갱신 | |

## 2. 검증
- `python tests/test_s14_server.py` → **26/26**. 대표:
```
OK   stats_meta.room_stat = stakes 표 (14방)
OK   공방(손 9): stat_mult 1.18 (기대 1.1800) / 온실(숨 2): stat_mult 0.88 / 맞는 방 > 1 > 틀린 방 / 상한 1.18
OK   요리사가 홀에 있으면 식량창고 보정 없음 / 식량창고에 → role_bonus {'food': 1} / 옮기면 사라진다
OK   부상 기술자 → 머릿수 0, mult 0.5
OK   스냅숏 ids['4'] = 요리사 / 이번 틱 stat_mult 0.9(요리사 손 3) / 다음 틱 1.18(기술자 손 9)
OK   정산 구간 [(1, 0.63), (1, 0.826)] — 스냅숏 틱이 더 낮다
OK   홀→온실 미리보기 room_delta 76.0% = 실제 76.0% (배율 0.5→0.880) / 온실에서 홀로 from_delta -43.2%
```
- `python tests/test_s13_server.py` → **109/109**(기대값 3곳 갱신 뒤).
- 전투: `combat_snapshot.py` 결과가 S13 기준과 **바이트 동일**(engine/ 변경 없음).
- 라이브 8012(RELIC_DEV=1): `t_reg12` 27/27, S13 라이브 루프 18/18, `t_reg` 는 기존 `/world.html` 404 하나(변경 전과 같음).
- 실제 DB 사본 216방주(옛 모양 스냅숏을 일부러 끼워 넣음): 오류 0, `move_preview` 크기 평균 429B·최대 2.1KB.
- API 차집합(아, base.html 스크립트만): 서버 − /base = `['/api/stats']`, /base − 서버 = 없음. 새 엔드포인트는 없다(필드만 늘었다).
- Playwright `/base`: 콘솔 오류 0. `docs/reports/shots/dev_S14A_server_base.png`.

## 3. 교본 원칙
- **D2**: 화면은 계산하지 않는다 — 배율·사람별 몫·이동 미리보기를 서버가 내려 준다(PM 결정이 원래 제안한 "식+매개변수"보다 이쪽을 택했다).
- **D7**: 방→능력치 표와 식의 수치 전부 stakes.json. 클라이언트 사본(ROOM_STAT)은 정본이 아니게 됐다.
- **D6**: 같은 배치·같은 스탯 = 같은 배율. 미리보기와 정산이 같은 함수(`room_mult`, `room_bonus_for`)를 쓴다.
- **D1**: 새 시스템이 아니라 기존 배율의 곱 하나(stat_mult)를 더했다.

## 4. 자가 검수
1. 새 숫자가 화면에 보이나 — `production.stat_mult`·`per_person`·`move_preview` 가 서버에서 온다. 화면 연결은 화면 개발 몫.
2. 첫 3분 탭 수 — 늘지 않는다(서버 필드만).
3. 결정성 — 예(테스트로 미리보기 = 실제 정산).
4. 720px — 해당 없음.
5. 회귀 로그 — §2.

## 5. 미완·리스크·후속
- **공방 「제작 시간 ÷ stat_mult」**: 제작이 즉시라 걸 곳이 없다. 손 보정은 재료 ±1 로 이미 있다 → 후속.
- **발전실 「공급 × stat_mult」**: `power_supply` 를 쓰는 전력 예산이 아직 없다 → 생기면 `room_mult` 를 곱하면 된다.
- `move_preview` 는 "다음 틱부터" 값이다. 접촉 스냅숏이 걸린 틱의 손해는 `production.snapshot` 쪽에서 본다.
- 산출이 쌓이지 않는 방(공방·발전실·창고·에어락·홀)은 `room_delta_pct: null`. 의무실은 `heal` 을 숫자로 센다(대항 카드 생산은 비교에서 빠진다).
- 부상자를 생산에서 빼면서, 상실 때 다친 사람이 있는 방은 산출이 줄어든다(의도대로지만 첫날 체감은 기획 확인).
- 화면 요청: `static/base.js ROOM_STAT` 를 `stats_meta.room_stat` 로 교체(의무실 hand·정수실 breath·홀 eye 로 바뀜), 드래그 중 `move_preview` 표시.
