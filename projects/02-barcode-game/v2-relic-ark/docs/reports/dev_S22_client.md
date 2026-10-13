# 개발 S22 — 1단계 화면: 「이게 뭐예요?」·받은 물건·매듭 소품·흔적·찾아온 이·지난 건넴·놓친 이야기·각인 겹 (2026-10-13)

> 계약 `docs/API_S19.md` §12, 각인 겹 규약 `static/art/chars/front/p2/meta.json imprint_compose`(char_S22 §3), 그림 `props_meta.json`(by_subtype·knots)·`decor_meta.json`(traces).
> 커밋하지 않았다. 검증은 8002(S22 서버 8c3d138)에서 새 방주로, 1280·844 각각 했다. 서버는 재시작하지 않았다.

## 바꾼 것
| 항목 | 파일 | 무엇 |
|---|---|---|
| ① 「이게 뭐예요?」 | `base_core.js`·`base_cards.js`·`base.css` | `where.subtype_pick.needed`이면 「어디로」 위에 `ask_ko`와 단추 4~6개가 뜬다. `suggest`가 있으면 그 단추를 미리 골라 두고 `suggest_ko` 한 줄(「「물」, 다른 방주 8곳에서는 그렇게 부르더군요.」)을 보인다. 고르면 `POST /api/scan/subtype` → 응답 `card`로 앞면만 다시 그리고(빛 한 줄) `where`로 「어디로」를 다시 그린다. 카드 앞면 첫 줄은 「음료 · 물 · 흔함」(갈래 · 하위 종류 · 희귀도). |
| ② 받은 물건 | `base.js`·`base_core.js` | `core.residents[rid].keepsakes_recent` 셋까지를 그 사람 곁(방·홀·문간 자리 모두)에 작은 소품으로 그린다. 소품 id는 `prop` → `by_subtype[갈래][종류].prop` → 갈래 good → `unknown.any` 순서. |
| ② 매듭 소품 | `base_core.js` | `core.props`(chair_1·sprout_on_sill·warm_basin·name_tag_worn)를 그 매듭의 방(식량창고·온실·공방·거주실)에 그린다. 방이 없거나 그림이 없으면 그리지 않는다(자리표시 그림 없음). |
| ② 끝 「자리」 | — | `seat`는 이름만 오고 전용 그림이 없어 그리지 않았다(사용자 원칙). |
| ③ 흔적 | `base_core.js`·`base.css` | `decor_trace` 방 바닥 가운데 기둥 자리에 `traces` 그림(손님 종류로 고름: 방 안 손님=발자국, 창 손님=비늘, 문어=촉수, 정원사=해초, 그 밖=물무늬)을 반투명으로 그린다. 방 카드에 `line` 한 줄. |
| 찾아온 이 | `base_collect.js`·`base.css` | 도감에 「찾아온 이 n/8」 탭. 손님 도트(×2), 못 본 손님은 그림자와 「?」, 횟수, 기념품 배지, 처음 온 날·꼬리표·기념품 이름 줄. 밤사이 `kind:"souvenir"` 줄도 그린다. |
| 지난 건넴 | `base.js`·`base.css` | 카드 아래 「전에: 1일째, 다올 님께」(card.history 최근 둘, 방이면 「○○에」). |
| 놓친 이야기 | `base_core.js`·`base.css` | 떠날 때 카드에 `missed_chain.line` 한 줄(leaving 응답, 없으면 /api/ark 값). |
| 각인 겹 | `base.js` | 본체(등불색) 위에 그 사람의 각인(최대 3)만 한 장에 모으고, `rolemask`로 지운 뒤(destination-out) 같은 불빛을 입혀 얹는다. 역할 판은 `meta.json imprint_fit_result.override_files`에 있는 것만 쓴다(없는 파일을 부르지 않아 404 0). 반전은 같은 시트라 본체와 같이 된다. 화면이 체형 A·아이 A 시트만 쓰므로 `imprints/`·`kid/`만 쓴다. 그림이 없는 개인 각인은 건너뛴다. |
| 덧 | `base_core.js` | `/api/ark`에만 오는 `visitors_book`·`decor_trace`·`missed_chain`도 다른 응답이 덮어쓰지 않게 이어 쓴다. |

## 검증 (8002, `t_s22.py`, 1280·844 각각 새 방주)
- 「이게 뭐예요?」: 앞면 「음료 · 거품 음료 · 흔함」 → 「물」 고름(다른 방주 제안 미리 선택) → 「음료 · 물 · 흔함」. 로그 `subpick 6 suggest`, `subtype water 물`.
- 매듭·기억 제안을 닫고 떠날 때 → 「누리 님이 아까 뭔가 하실 말씀이 있었던 것 같습니다…」.
- 흔적: 식량창고 「따뜻한 부엌」 1/2일 때 `trace_scales` + 방 카드 줄 「식량창고 김 서린 창에 작은 동그란 코 자국이 하나 생겼습니다.」.
- 지난 건넴: 「전에: 1일째, 다올 님께」.
- 받은 물건: 요리사 곁 3점, 매듭 소품 chair_1(식량창고), 도감 찾아온 이 탭.
- 각인 겹: 서버에 각인을 가진 주민이 없어 화면 상태에 각인 둘을 얹어(★ 검수용) 그렸다 → `ARKBASE.imprints()`에 기록, 404 0.
- **콘솔 에러 0, 4xx 0, 중괄호 0, selfTest ok**(1280·844).
- **(자) 응답 필드 단위**: 일곱 필드 모두 「응답에 옴 = 화면이 씀」.
  - `where.subtype_pick`
  - `card.history`
  - `core.residents[].keepsakes_recent`
  - `core.props`
  - `decor_trace`
  - `visitors_book`
  - `missed_chain`
- 엔드포인트 차집합: `['/api/dev/advance','/api/expedition/scene','/api/prefs','/api/stats','/api/table']`. 끝의 둘(`prefs`·`table`)은 작업 트리 서버의 **S23** 새 경로라 S23 배정 때 잇는다.
- 스크린샷 `docs/reports/shots/s22_*.png`(21장):
  - 1280·844 짝: subpick, subpick_done, leave_missed, trace, history, overview, pantry_zoom, imprint_zoom, visitors_tab, leave
  - 1280만: imprint_pod

## 미완·리스크
- **각인 겹은 실서버 각인 주민으로는 못 봤다**. 도트가 작아 1280 화면 배율에서는 잘 안 보인다. 캐릭터 담당이 실제 화면에서 한 번 봐 주면 좋겠다.
- 받은 물건 소품은 「잠자리」 위치가 아니라 그 사람이 지금 서 있는 곳 곁에 그린다. 화면에 잠자리 좌표가 없어서다. 문간 자리에서는 화분과 조금 겹친다.
- 흔적 비늘(trace_scales)은 작고 옅어 거의 안 보인다. 배경 담당과 크기·위치를 맞춰야 한다.
- 「이게 뭐예요?」는 고르지 않아도 「어디로」를 쓸 수 있다. 고르기 전에 건네면 그 물건은 고르지 않은 채로 남는다(계약대로).
- 끝 「자리」(seat)는 그림이 없어 그리지 않았다.

## 남에게 요청
- 서버: 스캔 직후(아직 「어디로」를 고르기 전)의 `/api/ark`에 그 스캔이 `missed_chain`으로 잡힌다(매 찍기 때 화면이 `/api/ark`를 다시 부른다). 「고르기 전」인 마지막 스캔은 빼 달라.
- 배경: 흔적 그림 크기(비늘이 작음)와 잠자리 좌표.
- 캐릭터: 각인 겹 실화면 확인.
