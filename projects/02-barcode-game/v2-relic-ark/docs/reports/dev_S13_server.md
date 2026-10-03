# 개발(서버) S13-A 보고서 — 이해관계·수집 연결 (2026-10-03)

근거: `docs/reports/review_fun_collection_20261003.md` 추천 1~4(사용자 승인), 수치 `data/balance/stakes.json`(기획), 문장 `data/ui_moments.json`(시나리오), 사용자 결정 3건(PM 전달, 2026-10-03). 계약: **`docs/API_S13.md`**(0단계에 먼저 내고, 구현 중 바뀐 것을 반영해 갱신했다). 커밋은 하지 않았다(PM 몫).

## 1. 만든 것과 경로

| 항목 | 내용 | 위치 |
|---|---|---|
| 수치·문장 읽기 | `stakes()`/`stk()` — stakes.json 을 mtime 으로 다시 읽는다(재시작 없이 기획 값 반영). 파일·키가 없을 때만 안전값(TODO 표시). `moments()`/`moment()` — ui_moments.json, 점이 든 키(`complete.8801043`)도 받는다 | `server.py` S13 절 |
| **B-1 콘텐츠 연결** | 가문 세트(서로 다른 바코드 수, 문턱 = `family_sets.pieces_required`, 완성 시 이야기·장식·사기), 첫 만남(가문 줄 먼저), 주민 바람(condition.hint 를 판정식으로 읽음, line_after 영구 대체), 문어(2일차 등장 연출 1회, 하루 선물 1개·전날 카테고리 가중), 하루 마감(오늘 바뀐 것만, 우선순위·최대 3줄, 맺음 줄은 사실일 때만) | `/api/scan`, `/api/collection`, `/api/wishes`, `/api/octopus/name`, `/api/day_end`, `/api/ark.octopus` |
| 도감 | `/api/codex` 옛 필드 유지 + `entries` 33칸 전부(모르는 칸은 이름·태그 숨기고 `codex.category_hints` 실루엣), 최고 희귀도·변형 칸. 구버전 방주는 scans 표로 희귀도 기록 재생성 | `/api/codex` |
| 화면 문장 | 읽기 전용 `GET /api/text/moments` | 신규 |
| **2. 배치 = 생산** | `tick_production` 방마다 × `staff_mult[그 방 사람 수]` × (금 갔으면 `crack.prod_mult`). **`staffing.measure=contact_snapshot`**: 접촉(누름·밤 판정) 순간 배치가 그 틱 생산을 정한다(틱 평균 배율로 합산). 미리보기 `ark.production[slot]` (`snapshot`, `now_mult`) | `room_mult`, `take_staff_snapshot` |
| **3-금** | 금 = 실제 방 상태(`cracked_day`), 생산 ×0.7, 판정 바탕 `crack.room_base_penalty`(−0.5, 미리보기 parts 에 줄로 보임). `POST /api/ark/repair {uid, slot, use_patch?}` 재료 `crack.repair_cost` 또는 봉합 패치 1 | `/api/ark/repair`, `engine/combat.py` 6줄 |
| **3-덮개 공개** | `lid.reveal_target` + `reveal_from_stage`(silhouette)부터 대상 방 공개, 공개 뒤 이동은 `moves` 에 안 셈(design §7). `raid.lid_revealed`·`reveal_ko` | `lid_revealed()` |
| **3-밤 자동 판정** | 습격을 본 날(raid 가 생긴 날)만. 처음 본 시각 다음의 `night_judge.hour` 정각이 지났거나 날이 바뀌면 다음 상태 요청(`/api/ark`, `/api/raid/today`)에서 그 배치 그대로 판정. 상한은 데이터(`worst_result`)만 정한다. 멱등(resolved). `ark.night_judge.report` 한 번 | `night_judge()`, `day_tick()` |
| **4-중복 버그** | 이미 선반에 있는 바코드는 새 칸을 먹지 않고 닦는다(놓인 날 제외, 바코드당 하루 1회, 문턱 `scans_per_level` [3,5] 누적, 최대 3) | `polish_item()` |
| **4-변형** | `sha256("VARIANT|barcode:ISO주")` < `variant.rate` → 바다 무늬. 응답 `variant`, 카드 `sea_variant`, 선반 `variant`, 도감 변형 칸. 수치 보상 없음. 기존 `card.variant`(시간대)는 그대로 | `sea_variant()` |
| **4-카테고리 고정** | uid+바코드별 첫 카테고리(정체불명 제외) 고정, `peek?uid=` 가 `locked_category` | `st.barcodes` |
| **4-스팟** | `scan_counts` 가 서로 다른 바코드만 센다(`spot_unlock.count_distinct_barcodes`) | `scan_counts()` |
| **사용자 결정 ①** | 밤 판정 상한 없음 → `stakes.json night_judge.worst_result` 값만 `"breached"`(엔진 상실 상수), `_basis` 앞머리에 「사용자 결정 2026-10-03」 표기. 코드는 값이 결과 이름이 아니거나 null 이면 상한 없음 | `data/balance/stakes.json` |
| **사용자 결정 ②** | 잃은 방 = **물 찬 칸**: `flooded_from {id, level}` 기억, `ark.flooded_cells[]`. 되찾기 = 그 칸에 **보통 짓기**(economy.json 건설비, **Lv1**) → `reclaimed` 기록. 선택 이유: 예전 레벨을 싸게 되살리면 상실이 '잠깐 불편'이 되고, 따로 비싸게 매기려면 새 경제 수치(기획 소유)가 필요하다. 옛 저장의 물 찬 방에는 `flooded_from` 을 채운다 | `/api/ark/build`, `migrate_s13` |
| **사용자 결정 ③** | 덮개 보류 — **데이터로**: `data/balance/threats.json min_grade.lid = 6`(1막 등급은 1~5뿐), `_basis_lid` 앞머리에 결정 표기. 생물·공개 규칙은 남아 `debug_raid=lid` 로 확인 가능 | `data/balance/threats.json` |
| 저장 이전 | 선반 바코드를 card_id 앞부분에서 복원, 옛 중복 칸은 첫 칸만 남김, 카테고리 고정·첫 만남 기록을 scans 표에서 채움, 옛 `cracked` 는 이제 실제로 금 | `migrate_s13()` |
| 개발 훅 | ★ `GET /api/ark?debug_night=1` (RELIC_DEV=1 전용) | |
| 테스트 | 18묶음 109항목, 임시 DB + TestClient | `tests/test_s13_server.py` |

## 2. 검증 방법과 결과

1. **구문·임포트**: `ast.parse` + `import server` 통과. 서버 8012(RELIC_DEV=1) 재기동 4회, 기동 로그 오류 없음(`scratchpad/s13/srv8012.log`). 8002 는 다른 에이전트가 쓰는 중이라 건드리지 않았다.
2. **새 테스트** `python tests/test_s13_server.py` → **합계 109 · 통과 109 · 실패 0**. 대표 줄:
```
OK   같은 날 재스캔(감쇠 0.5) → 같은 칸, 선반 1칸 (중복 칸 버그 수정)
OK   다른 날 3번 → Lv2 (levels=[1, 1, 2, 2, 2, 2, 2, 3, 3]) / 다른 날 8번 → Lv3 / 재스캔 20번 뒤에도 선반 1칸
OK   옛 중복 칸 정리: 3칸 → 2칸, 바코드 복원
OK   고른 카테고리 무시, 같은 유물: 따뜻한 말린 실의 부적 / peek(uid) → 고정 카테고리, 묻지 않는다
OK   바다 무늬 비율 118/4000 = 0.0295 (목표 0.03125) / 주가 바뀌면 시드가 바뀐다 (2026-W40 → 2026-W41)
OK   첫 만남: 가문 줄 먼저 / 3번째에서 완성 + 이야기·장식 / 사기 +2 / 완성 문장 = family_set.complete.<code>
OK   식량창고 food: 0명 4 / 1명 9 / 3명 14 = staff_mult 0.5/1.0/1.6 / 금 간 방 food: 6 (×0.7)
OK   접촉한 틱: 대상 방 3 = 3명 배율 1.6 (지금 배치 1.0) / 비운 방 2 = 0명 0.5 — 되돌려도 이번 틱 비용이 남는다
OK   수리 → 재료 {'cloth': 1, 'med': 1} 지불, 금 지움 / 봉합 패치로 대신 수리 / 재료 없으면 400
OK   밤 판정 = 누른 것과 같은 규칙(상한 breached): 미리보기 breached → 결과 breached capped=False
OK   멱등: 두 번째 요청에 판정 없음, raid_log 1건 / 서 있는 배치가 좋으면 막음 + 보상
OK   15시에 본 습격 → 같은 날 21시 판정 / 22시에 본 습격 → 다음 날 21시(바로 판정하지 않는다)
OK   실루엣: 대상 공개 slot=4 … / 공개 뒤(실루엣) 이동은 세지 않는다 / 덮개 아닌 생물은 예전처럼 moves 를 센다
OK   금 간 방 판정 바탕 1.0 → 0.5 (-0.5)
OK   같은 바코드 3번 → 스팟 카운트 1 / 서로 다른 둘 → 열수구 열림
OK   도감 전 칸 33/33, 아는 칸 1, 모르는 칸은 이름 없이 실루엣 / 옛 필드 유지
OK   2일차: 첫 등장 + 선물 / 같은 날 다시 열어도 선물 하나 / 요리사 바람 이룸 → line_after / 아무 일 없는 날 → quiet
OK   상실 → 물 찬 칸, 기억 {'id': 'greenhouse', 'level': 2} / 다시 짓기 → Lv1, 건설비 {'food': 7, 'cloth': 3} 지불
OK   threats.json min_grade.lid = 6 / 1~399일 × 등급 4·5 무작위 선택에서 덮개 0회
OK   사건 해결 → /base 상태 모양 그대로 / 두 번 해결 → 400
```
3. **플레이어 한 바퀴(규칙 사)** — 테스트 `t_player_loop` + 라이브 `scratchpad/s13/live_loop.py`(8012, 18/18 OK): 스캔 → 다른 날 재스캔 닦기 → 가문 진행 2/3 → 습격(큰 입, 등급 4) → 접촉 안 누름 → 밤 판정(상한 없음 → 상실) → 물 찬 칸 → 같은 칸 다시 짓기 → 온실에 1명 배치하면 다음 틱 배율 0.5 → 1.0. (결정 ① 이전 값 scarred 에서는 같은 경로가 금 → 수리로 돌았고 그것도 통과했다. 테스트는 상한 값을 데이터에서 읽어 두 경로 다 검사한다.)
4. **전투 결정성**: `scratchpad/combat_snapshot.py`(생물 14 × 관문 상황 격자, 12.6MB) 변경 전후 **`cmp` 바이트 동일**. combat.py 변경은 `room_base_adj` 키가 있을 때만 작동하는 6줄이고, 서버는 금 간 방에만 그 키를 넣는다. 덮개는 combat.py 가 아니라 서버의 `moves` 세기만 바뀌었다.
5. **기존 회귀**: `t_reg12.py`(8012 로 포트만 바꿈) 27/27 OK. `t_reg.py` 는 `/world.html` 404 하나 — 변경 전 로그(`scratchpad/t_reg.log`)에도 같은 FAIL, 경로가 원래 `/static/world.html` 이다(기존). 회귀 7항목(스캔·건설·사건·주민·도감·통계·마이그레이션) 전부 OK.
6. **실제 개발 DB 이전**: `relic_ark.db` 사본으로 216개 방주를 load → public_state → tick → day_tick → codex/collection/wishes/day_end 까지 돌림: **오류 0**, 물 찬 칸 74(기억 보강), 금 간 방 29(이제 실효).
7. **API 차집합(아)** — `base.html` 의 `<script src>` 넷(movement·m5map·base·base_collect)만 셈:
```
server routes 29
server - /base = ['/api/stats']      ← 관리용, 의도
/base - server = []
data/*.json 미사용(서버·엔진·base 스크립트): dialogue_schema.json(스키마), world_prompts.json(그림 파이프라인)
```
   화면 개발이 이미 `base_collect.js` 로 새 엔드포인트 아홉(codex·collection·day_end·event/today·event/resolve·octopus/name·rumors·text/moments·wishes)과 `/api/ark/repair` 를 부른다.
8. **브라우저**: Playwright 로 `http://localhost:8012/base`(밤 판정으로 식량창고를 잃은 방주) — 콘솔 오류 0. 물 찬 칸 오버레이가 그대로 그려진다. `docs/reports/shots/dev_S13A_server_base.png`.

## 3. 적용한 교본 원칙
- **D6 결정성**: 변형 = 바코드+ISO주 해시, 문어 선물 `uid|day|octopus_gift`, 하루 마감 `uid|day|day_end|상황`. 카테고리 고정으로 "같은 바코드 = 같은 유물"을 되살렸다(이 방주 기준).
- **D2 모든 숫자는 화면의 무엇으로**: 생산 배율·금·스냅숏·물 찬 칸을 서버가 계산해 `production`/`flooded_cells`/`repair` 로 내려 준다. 화면은 계산하지 않는다(Slay the Spire 사례 — 정보를 숨기지 않는다).
- **D7 데이터가 규칙을 든다**: 수치 전부 stakes.json, 문장 전부 ui_moments/first_meet/day_end/wishes/companion 파일. 사용자 결정 ①③도 코드 분기 없이 값만 바꿨다.
- **D4 실패는 서사, 막힘은 버그**: 상실이 물 찬 칸 + 되찾기가 되어 이야기(하루 마감 room_lost)로 남고 막다른 길이 없어졌다.
- **D1 규칙은 적게**: 되찾기에 새 경로를 만들지 않고 기존 짓기 하나로 처리했다.
- **D3**: 문어 선물·바람·밤 판정은 "돌아왔을 때의 장면"(아침 방송·등장 연출)으로 한 번만 온다. 타이머 없음.
- 공통 §3 판단 순서: 덮개 공개의 `moves` 규칙은 성경(stakes `_note`·design §7)에 답이 있어 그대로 따랐다.
- **이탈**: ① stakes.json·threats.json 은 기획 소유인데 사용자 결정을 넣으려고 **값과 `_basis` 앞머리만** 고쳤다(PM 지시). ② 문어 기분 단계는 수치가 없어 임시 규칙(TODO)을 코드에 두었다 — 기획 요청함.

## 4. 자가 검수(02_DEV §5)
1. 새 숫자가 화면의 무엇으로 보이나 — 배율은 방의 「일손 없음」 표시·생산 방울, 금은 「금 감」·수리 버튼, 닦기는 선반 테두리 레벨, 변형은 바다 무늬, 세트는 장식(`decor`). 서버가 라벨까지 내려 준다.
2. 첫 3분 루프 탭 수 — 서버는 탭을 늘리지 않는다. 오히려 `peek?uid` 로 고정된 바코드의 카테고리 질문이 사라진다(화면이 uid 를 붙이면).
3. 같은 입력이면 같은 결과인가 — 예. 전투 스냅숏 바이트 동일, 변형·선물·마감 문장 시드 고정, 밤 판정 멱등.
4. 폰 가로 720px — 화면 소관. 서버 변경은 레이아웃에 영향 없음.
5. 회귀 로그 — 위 2장 5항.

## 5. 미완·리스크
- **staffing 이 첫날을 반으로 깎는다**: 시작 3인이 홀에 있으면 식량창고가 ×0.5 로 돈다(stakes 의도: 빈 방 0.5). 화면이 첫날 한 명을 식량창고에 세우게 안내하지 않으면 첫날 식량이 준다 — 기획·화면 확인 필요.
- **밤 판정 상한 없음**: 이제 접속해서 습격을 보고 21시까지 두면 상실이 날 수 있다(되찾을 수는 있다). stakes `_consequence` 의 "동의 없는 영구 상실은 없다"는 이제 "영구 상실은 없다(물 찬 칸 → 다시 짓기)"로 바뀐 셈이다.
- **밤 판정 시각 = 서버 시계**(기존 `is_night` 와 같은 방식). 폰 시각대가 서버와 다르면 어긋난다. 습격을 21시 이후에 처음 봤으면 다음 날 21시이고, 그 전에 게임 날이 바뀌면 다음 요청에서 판정된다.
- **덮개 공개 규칙**: 공개 뒤 이동을 세지 않으면 "실루엣에서 전원을 대상 방에 넣기"가 정답이 된다(소리 단계에서만 움직이지 않으면 됨). design §7 대로 했지만 덮개의 성격(움직이면 진다)은 약해졌다. 지금은 덮개가 보류라 실전 영향은 없다.
- **문어 선물은 선반에 놓지 않는다**(소품 그림 없음) — `octopus_gift.pop` 문장과 어긋난다(시나리오 요청함).
- **절차 생성 가문**(stakes `family_sets.procedural_families`)은 이름 조각 표가 없어 미구현. 알려진 18가문만 세트가 된다.
- `tools/audit_combat.py` A2-추가는 `ensure_raid` 를 직접 불러 밤 판정을 거치지 않으므로 옛 결과("누르지 않으면 0")를 계속 출력한다(감사 도구 쪽 문제, 기획 요청함).
- 바람 판정은 condition.hint 를 읽는 근사다(예: 학자 바람 = 서고 + 손패에 책, 아이 바람 = 단 알갱이 가문을 찍었거나 사기 태그 식품이 손패에). 1막 3인이면 요리사·기술자·정찰병 셋만 해당.

## 6. 남에게 요청할 것 (`docs/TASKS.md` 요청함에 남김)
- **시나리오**: `ui_moments.night_judge.lost` 새 키, 되찾은 날 문장, `creatures.json big_maw.lines.breached` 의 박힌 「온실」→`{room}`, `crack.occurred`「반만」(실제 0.7), `octopus_gift.pop`「선반에 올려」.
- **기획**: 문어 기분 단계 수치, lid 되돌리는 시점, 되찾기 전용 비용이 필요한지, 감사 도구의 `day_tick` 경유.
- **화면 개발**: `/api/peek` 에 `&uid=`, 물 찬 칸 「손댈 수 없다」 문구 → `flooded_cells` 로 짓기(되찾기) 버튼, 습격 띠가 상실·자동 판정 뒤 「지나감」으로 나오는 것(`raid.result`·`raid.auto`), `production.snapshot`/`now_mult`.
- **PM**: DECISIONS 에 사용자 결정 3건(밤 판정 상한 없음 / 상실 = 물 찬 칸·보통 짓기 Lv1 / 덮개 보류 = threats.json min_grade.lid 6) 기록.
