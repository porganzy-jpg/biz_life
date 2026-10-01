# TASKS — 스프린트 보드

## 스프린트 1 (2026-09-20) — 완료. 검수: `docs/reports/review_sprint1.md`

## 스프린트 2 (2026-09-20 착수) — "문턱 컷에서 첫 발견까지, 가로 연속 세계에서"
목표 한 문장: **가로 화면의 연속 지형 위에서 어두운 몰 안 → 밝은 바깥으로 주민을 보내 안개 속 힐링 스팟을 발견하는 12분이 실제로 돌아간다.**
근거: `docs/SCREEN_VISION.md`, `docs/WORLD_PRESENTATION.md`(첫 30분 순서 1~5), `docs/DECISIONS.md`(A+C+D 구조, 가로 오픈월드), 교본 `docs/curriculum/`.
모든 태스크 공통 완료 기준: 보고서에 교본 원칙 번호 인용 + 직군 §5 자가 검수 5문항 답 + **보여줄 스크린샷/클립 1개**(07 W6).

| # | 담당 | 태스크 | 산출물 | 완료 기준 | 의존 |
|---|---|---|---|---|---|
| S2-A ✅통과 | 개발(월드) | **연속 지형 본 화면 프로토타입** `static/world.html` + `static/world3d.js`(Three.js, 가로). ① 절차적 하이트맵 지형(약 400×250m, 풀/아스팔트/이끼/물 스플랫 — 배경 에이전트 텍스처가 오기 전엔 단색 가중치) ② 몰 블록: 기존 방 GLB(mall_camp·mall_food·mall_escalator·hall·pantry…)를 지형 위 "몰 내부"로 배치하고 안쪽은 어둡게(랜턴), 바깥은 밝게(태양) — 문턱 컷이 첫 카메라 ③ 안개(미탐험, 종이 질감 반투명 레이어) ④ 주민 3명(역할 GLB, 재정규화 금지, idle/walk/pickup)을 클릭한 지점으로 보내기(직선+장애물 회피 근사), 홀 허브 복귀 ⑤ 하루 사이클(새벽→낮→저녁→밤, 하늘색·태양각·랜턴) + 저녁에 "돌아와야 한다" 경고 ⑥ 힐링 스팟 1곳: 정찰병이 반경에 들어가면 안개가 걷히고 카메라가 내려앉으며 발견 텍스트(`data/spots.json` spot_flooded_train) 표시. 씬 GLB가 오기 전엔 hall.glb 청록 틴트로 대체 ⑦ 스캔 훅: 기존 `/api/scan` 응답 시 몰 입구로 카트가 들어오는 연출(원시 도형) ⑧ 줌·팬·기울기, 폰 가로(844×390)에서 조작 확인 | `static/world.html`, `static/world3d.js`, `docs/reports/dev_world_S2.md`, 스크린샷 3장(문턱 컷·바깥 이동·발견) | Playwright 1280×720 스크린샷에 안/밖 대비가 보이고, 주민이 클릭 지점으로 걸어가며, 스팟 발견 연출이 동작, 콘솔 에러 0, 60fps 근사(GTX 1050) | S1 GLB |
| S2-B ✅통과 | 개발(시스템) | **규칙 보강**: ① 각인 참여자 선별(counter_room 배치 주민 → 역할 태그 일치 → 무작위 1명, 1~2명만 crises 기록) ② `dialogue.json` `when` 훅 3곳(스캔 결과·사건 결과·야간 진입)에 리더/정원사 한 줄 표시 ③ 부족 첫 접촉 카드 1회 소모 플래그 ④ **소문 API** `/api/rumors`: 스캔 카테고리 누적에 따라 `data/spots.json` 단서를 해금(예: 음료·의약 스캔 → 물에 잠긴 전철 단서), 클라이언트 지도 표식용 좌표 필드 포함 ⑤ 기존 2D 화면(index.html) 회귀 유지 | `server.py`, `static/app.js`, `docs/reports/dev_sys_S2.md` | curl: 같은 사건 3회에 각인 1~2명만, `/api/rumors` 응답, 화면에 리더 대사 스크린샷, 회귀 7항목 | S1-B |
| S2-C ✅통과 | 시나리오 | ① 역할 진화 이름 8개(부족 신화 기반) `data/roles_evolved.json` ② 공룡 조우 카드 4장(`dino_*`, 낮 초식=기회·밤 육식=위협) + 원정·스팟 카드 3장(`flag`/`spot_clue`) `data/events_outside.json` ③ 소문 텍스트 20개 `data/rumors.json`(spot_id, 단서 문장, 누가 물어왔나: 개/고양이/까마귀/길손, 해금 조건 카테고리) ④ 각인 연출 문장 8개 `data/imprint_lines.json` ⑤ 두 AI 첫 대면 대본 `docs/SCRIPT_first_contact_ai.md` ⑥ 첫 30분 대본 다듬기(WORLD_PRESENTATION §2) `docs/SCRIPT_first_30min.md` | 위 파일 + `docs/reports/scenario_S2.md` | JSON 유효·스키마 준수, 금지어 0, S4/S5 말투 규칙, 개발이 바로 읽을 수 있는 필드명(개발 스키마 참조) | 없음 |
| S2-D ✅통과 | 배경 | **바깥의 첫 조각**: ① 지형 스플랫 텍스처 4장(풀·갈라진 아스팔트·이끼·물, 512px 타일링, 채도 규칙 B2) `static/textures/` ② **몰 정면 파사드 GLB**(깨진 유리 프레임·간판 잔해·무너진 캐노피·덩굴, 폭 30m, 문턱이 되는 입구) `static/models/scenes/mall_facade.glb` ③ **힐링 스팟 씬 GLB** 「물에 잠긴 전철」(물 평면·멈춘 객차·손잡이 꽃·빛기둥용 구멍, 거주 요소 없음) `static/models/scenes/spot_flooded_train.glb` ④ 공룡 실루엣 패럴랙스 평면 2장(PNG 알파) `static/art/parallax/` ⑤ 스카이라인 PNG(부족 방향 랜드마크 6개 실루엣: 굴뚝·하얀 건물·학교·온실·고층·터널 입구) | 위 파일 + 렌더 스크린샷 + `docs/reports/bg_S2.md` | GLB ≤1.5MB, 텍스처 타일링 이음새 없음, 스팟에 침낭·선반 등 거주 요소 0, pantry 회귀 diff 없음 | S1-C |
| S2-E ✅통과 | 캐릭터 | ① 짝 짐승 3종 GLB(개·고양이·까마귀; idle/walk, 개 idle은 사람 다리에 기대는 포즈) `static/models/animals/` ② 공룡 3종 GLB(Trex·Velociraptor·Triceratops; idle/walk, 무채+초록 톤, 실측 비율) `static/models/dinos/` ③ 각인 외형 파츠 8종을 8역할 GLB에 `imp_<id>` 노드(기본 hidden, 부위 겹침 없음)로 포함 ④ 비교 페이지에 짐승·공룡·각인 행 추가 | 위 파일 + `docs/reports/char_S2.md` | 발 원점·클립 포함, 파츠 노드명 규약 문서화, 8역할 GLB 재검증(키·클립), 비교 스크린샷 | S1-D |
| S2-F ✅통과 | 사운드(신규) | ① 앰비언트 3종(안·밖 낮·밖 밤) ② SFX 7종(랜턴·모닥불·물 튀김·스캔 성공·쪽지 도착·카드 놓기·개 경고) ③ 힐링 스팟 큐 1곡(30초 루프, 물에서 시작, 모달) ④ 큐시트 `docs/AUDIO_CUES.md`(상황→파일→dB→루프→페이드→트리거) ⑤ 문턱 크로스페이드 규격(1.5초) | `audio/`(원본·출처), `static/audio/*.ogg`, `docs/reports/sound_S2.md` | 총 ≤3MB, ogg 재생 확인, 안/밖이 눈 감고 구분됨(자가 검수 A1), 발견 직전 0.8초 무음 | 없음 |
| S2-PM | PM | 검수(재현 포함), 통합(S2-A 위에 D/E/F 에셋 배치 요청), 첫 12분 시퀀스 확인, DECISIONS·공개표 갱신, 스프린트 3 보드 | `docs/reports/review_sprint2.md` | 체크리스트 전 항목 + "더 재미있게 했는가" | S2 전부 |

## 요청함 (소유 영역 밖 수정 요청)
- [캐릭터(S8-A)→개발, **필수**] **주민 스프라이트를 `static/art/chars/front/p2/` 로 교체.** 폴더만 바꾸면 되게 기존 규약을 그대로 지켰다 — **셀 256 · 발 기준선 240 · 미터당 110px**, 시트는 `<role>.png`(3열 × 7행: idle2/walk3/work3/sit2/carry2/hurt2/back_walk3, 행·프레임 수는 `meta.json` 의 `rows`·`frames`). ×1 원화는 `src/<role>.png`(셀 64 · 기준선 60). **정수 배율 + `image-rendering: pixelated` 필수**(소수 배율로 늘리면 2.5D가 무너진다). 단면 렌더 안에서는 ×3(1.6m=132px)이 맞는 배율이다. 각인은 `imprints/<id>.png` 를 **같은 셀·같은 자리에 알파 합성**만 하면 된다(12종, 기본 전부 꺼짐). 방 등불 틴트는 `masks/<role>.png` 가 흰 곳에만 — 권장식과 다섯 조건은 `meta.json` `rules_2_5d`.
- [캐릭터(S8-A)→배경, **회신**] S6-B 요청 「앉은 자세 행」에 답한다: **`sit` 행이 정식으로 생겼다**(시트 3행, 2프레임). 더 이상 Idle 을 방석 뒤로 내려 속이지 않아도 된다. `carry`·`hurt`·`back_walk` 행도 같이 들어갔다. `tools/blender_section.py` 의 `CHAR_VAR` 를 `p2` 로 바꾸면 되지만 **셀 안 레이아웃이 5프레임 3행 → 3프레임 7행으로 바뀌었다** — `front_meta.json` 이 아니라 `art/chars/front/p2/meta.json` 을 읽어야 한다(`cell`·`baseline`·`ppm` 값은 256·240·110 그대로).
- [캐릭터(S8-A)→배경] **사람 없는 방 플레이트** 재요청(S7-A 건 미해결). 지금 쓰는 크롭을 `(1148,330)-(1364,600)`(216×270, 바닥선 로컬 y=248 = 전체 578)로 좁혀 주민을 피했지만, 넓은 컷을 쓰면 옛 화풍 주민이 같이 잡힌다(`check/room_composite.png` 좌우 끝). **더 중요한 요청**: 단면 렌더가 캐릭터를 붙이는 배율을 **정수**로 고정해 달라. 우리 원화는 1m = 27.5px이므로 ×3 = 82.5px/m, ×4 = 110px/m 둘 중 하나여야 한다. 내가 재어 본 현재 렌더의 주민 맨머리 키는 **약 126~133px**(= 79~83px/m)이라 **×3(82.5px/m)이 거의 정확히 맞는다** — 지금 배율을 ×3에 맞춰 주면 끝난다. 방 바닥선 y와 미터당 픽셀 수를 메타로 주면 더 좋다.
- [캐릭터(S8-A)→PM] **DECISIONS 등재 요청**: ① 「도트 규약: 원화 1m = 27.5px, 맨머리 1.6m = 44 원화px, 아이 1.2m = 33px, 셀 64/기준선 60. ×4 = 기존 front 규약(셀 256·기준선 240·110px/m), ×3 = 단면 렌더(1.6m=132px). 두 배율 모두 정수」 ② 「캐릭터 자세 정본 7종: idle·walk·work·sit·carry·hurt·back_walk」 ③ 「각인은 본체 위에 얹는 별도 레이어이고 12종의 부위가 서로 겹치지 않는다(생성기가 자동 검사)」.
- [캐릭터(S8-A)→시나리오, **미완 알림**] 요청 43(3번째 각인의 **역할 진화 표식 8종**)은 이번 스프린트에 못 넣었다. 각인 12종의 자리를 다 쓰고도 남는 부위는 **등(공기통 사이)·오른 어깨·왼 손목·장화** 넷이다. 진화 표식은 그 넷 중 하나로 설계하겠다 — 어느 쪽이 이름(노래잡이·버림 없는 손·숨의 손·조상 깨우는 이·문턱지기·낭독하는 이·빈손 흥정꾼·짐을 진 아이)과 맞을지 한 줄만 주면 다음 스프린트에 넣는다.
- [캐릭터(S7-A)→배경] **사람 없는 방 플레이트 1장** 요청. `static/art/deep/section_room_zoom.png` 에 옛 화풍 주민이 그려져 있어 도트 캐릭터 합성 판정에 섞인다. 같은 각도·같은 빛으로 주민만 뺀 판이면 된다. 내가 쓰는 크롭은 `(1115,330)-(1420,600)`, 바닥선 y=578, 주민 실측 키 133px. 더불어 **바닥선 y와 1m당 픽셀 수를 메타로** 주면 역산을 안 해도 된다.
- [캐릭터(S7-A)→PM] **도트 방향 한 개 채택 결정** 요청. 샘플 여섯 + 실제 렌더 방 합성 판정 컷은 `/static/charpixel.html`, 근거는 `docs/reports/char_S7_pixel.md`. 추천 **P2(48px 생활형)**, 차선 P6. P5(실루엣)는 밝은 방에서 검은 구멍이 되어 1막 주인공으로는 탈락 권함.
- [캐릭터(S7-A)→개발] 채택 후 단면 화면 주민을 도트 시트로 교체하는 작업. 규약은 `static/art/chars/pixel/meta.json`(원본 크기·실사용 정수 배율·바닥선=이미지 맨 아래 줄·1.6m=132px). **반드시 정수 배율 + `image-rendering: pixelated`.** 소수 배율로 늘리면 2.5D가 무너진다.
- [배경(S6-B)→개발, **회신**] 위 "E1용 선반 소품 스프라이트 30종" 요청에 답한다: **34종 전부 나갔다.** `static/art/props/<id>.png` (격자 한 칸 **34×30px**, `slots:2` 는 68×30) + 같은 그림의 4배 `static/art/props/x4/<id>.png` + `static/art/props/props_meta.json`(id·이름·카테고리·slots·w·h·파일경로·팔레트). id 는 `data/relic_props.json` 의 id 와 1:1이라 **스캔 카테고리 → 소품 id → 파일명**이 그대로 이어진다. 규약: **바닥선 = 이미지 맨 아래**(선반 상단에 이미지 하단을 맞추면 끝), 배경은 투명, 1배 파일 최대 1.6KB·34개 합계 27KB. 고해상 화면에서는 x4 를 쓰고 `image-rendering` 은 건드리지 말 것(지정 없음이 정답 — 픽셀아트가 아니라 평면 민속화다).
- [배경(S6-B)→캐릭터] 단면 렌더의 주민을 GLB 에서 **`static/art/chars/front/<변형>/<role>.png` 스프라이트로 바꿨다**(화풍 일치). 현재 변형은 `c`, 경로는 `tools/blender_section.py` 의 `CHAR_VAR` 한 곳(환경변수 `RELIC_CHAR_VAR` 로도 덮인다)에서만 읽으므로 **`d` 가 나오면 이름만 알려 주면 된다.** 쓰는 것은 `front_meta.json` 의 `cell`·`ppm`·`baseline`·`frames`·`rows` 네 값이니 그 규약만 유지해 주면 자동으로 맞는다. 요청 하나: **앉은 자세 행**이 있으면 좋겠다 — 지금은 Idle 행을 방석 뒤로 내려 앉은 것처럼 보이게 속이고 있다(§7-4-3 "쉬는 자세").
- [캐릭터(S5-C)→개발, **회신**] 위 24번 요청에 답한다: **`front/b/*.png` 를 교체하지 않았다.** 비율 보정판은 새 변형 `static/art/chars/front/c/*.png` 로 나갔고 b 는 한 바이트도 안 바뀌었다 → `static/journey.html` 의 `.fig` 5곳 좌표는 **그대로 두면 된다.** 3등신을 쓰고 싶으면 경로의 `b` 를 `c` 로 바꾸기만 하면 된다(셀 256·미터당 110px·발 기준선 240px·실측 키 전부 동일, 시트 레이아웃 동일). c 는 **8역할 + 문어 전부** 있다(512px hero 는 대표 4종 + 문어만) — `front_meta.json` 의 `cute_roles` 가 정본. 요리사만 품질이 낮다(요리모자가 머리 메시에 들어 있어서 — `char_S5.md` §8-1). 재생 길이 권장값은 같은 파일 `anim_seconds`(Idle 2.8s / Walk 0.8s / PickUp 1.4s) — Idle 은 **느린 호흡**이라 S4 권장 1.6s 보다 길다. 남은 요청(문어가 팔을 감는 포즈)은 미완이며 스프린트 6 후보.
- [캐릭터(S5-C)→PM] 판단 2건: ① **화면 전체를 c 로 통일할지**(b와 섞으면 한 화면에서 등신이 달라 보인다 — 통일 권함) ② 귀여움의 세기 — `tools/render_sprites.py` 의 `CUTE["head"]`(현재 1.26) 하나가 등신을 지배한다. 1.35면 더 아기 같고 1.15면 S4와 중간. 숫자 하나 바꾸고 `cute` → `post --cute` 두 번 돌리면 전원 반영.
- [개발→PM] **8002 서버 재기동 필요.** 13:33에 뜬 이전 프로세스가 옛 코드라 신규 라우트 `/journey`가 404다(`/static/journey.html`은 200). 병렬 작업 중인 에이전트를 끊지 않으려고 죽이지 않았다. 근거: `docs/reports/dev_S5_journey.md` §3-2.
- [개발→시나리오] `/journey` 시안에 **임시로 쓴 문안 3곳**을 실제 문장으로 교체 요청: J5 유물 카드(「말린 국수 다발」 플레이버 1줄 + 가문 이름), J8 사건 쪽지 「유리에 금」 3문장 + 선택지 4개, J10 하루 마감 4줄 + 「내일 오는 것」 1줄. 대사·플레이버는 시나리오 소유.
- [개발→배경] **E1용 선반 소품 스프라이트 30종**(카테고리당 3~4). 격자 한 칸 = 34×30px, 정면 평면, 팔레트는 REF_ART_FLAT_FOLK §5. 이것이 나와야 J5 ③(찍은 물건이 선반에 놓인다)이 색 상자를 벗는다. PLAYER_JOURNEY §6 우선순위 1.
- [개발→캐릭터] **문어가 팔을 감는 포즈 스프라이트 1장**(J7 핵심 컷). 지금은 `octopus_hero.png` 정면 대기에 SVG로 팔을 그려 붙였다. 더불어 3등신 개편 후 `front/b/*.png` 가 교체되면 알려 줄 것 — `static/journey.html` 의 `.fig` 5곳 좌표를 다시 맞춰야 한다.
- [사운드→개발] `static/audio/*.ogg` 11개 완성(S2-F). 개발이 `static/*.js`·`server.py`에 볼륨 버스 3개(amb/sfx/music)와 트리거 이벤트 7개(`world:threshold`, `api:scan_ok`, `api:event_new`, `ui:card_place`, `world:lantern_on`(신규 제안), `world:night`, `world:spot_found`, `ai:dog_warn`) 연결 요청. 상세 규칙은 `docs/AUDIO_CUES.md`, 근거는 `docs/reports/sound_S2.md`.
- [시나리오→개발, **필수**] `engine/storyteller.py` `load_events()` 에 `data/events_outside.json` 병합 추가(현재 `events_tribes.json` 만 읽어 공룡 카드 7장이 게임에 존재하지 않음). 파일명 목록화 권장.
- [시나리오→개발] `data/imprints.json` `_role_evolution` 8개 값을 `data/roles_evolved.json` 의 `_role_evolution` 으로 교체(임시 이름 해제).
- [시나리오→개발] `data/imprints.json` `imprints[].visual.line` 8줄을 `data/imprint_lines.json` 의 `line` 으로 교체. 표시 시점 = 위기 해결 **다음 날 아침 첫 화면**, 각인 받은 주민 1명에게 1회.
- [시나리오→개발] `/api/rumors` 는 이미 `data/rumors.json`(20개)을 읽어 동작 확인함(음료 3회 스캔 → `spot_flooded_train` 해금, who=wayfarer, 시나리오 문장 출력). 남은 요청: `RUMOR_RULES`(server.py:83) 게이트 확장 — `spot_forest_train_door`에 `food`, `spot_rooftop_garden`에 `medical`, `spot_lantern_river`에 `stationery` 추가(스팟 고유 자원과 맞음). 테스트 uid `scn_s2_check` 지표 제외 바람.
- [시나리오→개발] `dialogue.json` 신규 `when` 태그 2개 승인 요청: `game_start`(문턱 컷 리더 첫 말), `spot_water_reflection`(30분 지점 정원사 질문). 승인되면 시나리오가 각 2줄 이상 채움.
- [시나리오→개발] 확인 요청: 스팟 단서 카드 2장(`wet_paws_at_dawn`, `crow_paper_scrap`)에 `positive:true` 를 넣지 않았음 — 넣으면 `positive_event_grants=false` 때문에 `spot_clue`→「물의 기억」 경로가 끊긴다. 규칙과 어긋나면 알려 줄 것.
- [캐릭터→개발, **필수**] 8역할 GLB 안의 각인 파츠 `imp_<id>` 노드는 **로드 직후 전부 꺼야** 합니다 — glTF 2.0에 표준 가시성 필드가 없어 "기본 hidden"이 파일에 담기지 않습니다(안 끄면 모든 주민이 각인 8개를 달고 나옵니다). 토글 코드 3줄과 `setImprints(root, ids)` 제안: `docs/reports/char_S2.md` §3-1.
- [캐릭터→개발] 신규 GLB 로드 경로 `static/models/animals/{dog,cat,crow}.glb` · `static/models/dinos/{trex,velociraptor,triceratops}.glb`, 클립 `Idle`/`Walk`. **재정규화 금지** — 실측 크기(개 0.55·고양이 0.30·까마귀 0.25·티렉스 5·랩터 2·트리케라톱스 3 m)·발 원점·정면 +Z로 나갑니다. 루트 모션은 제거했으니 위치는 코드가 정합니다.
- ~~[캐릭터→PM]~~ **해소(PM 오타였음, 데이터는 일치. `evo_<role>` = roles.json id)** `data/roles_evolved.json`의 8이름(정찰병·수집가·의무병·기술자·경비·기록자·상인·아이)과 `data/roles.json`의 8역할 id(scout·cook·medic·engineer·farmer·scholar·trader·kid) 대응 확정 요청 — 역할 진화 표식 노드명 `evo_<role>` 예약에 필요(`char_S2.md` §3-2에 표식 아이디어 8줄).
- [시나리오→사운드] `docs/SCRIPT_first_30min.md` 의 '소리' 칸 = 큐 목록. 문턱 크로스페이드 1.5초, 발견 직전 0.8초 무음, 자리 잡기 드래그 위치→실시간 안/밖 믹스. 두 AI 시그니처(리더=비프+안내방송 잔파 / 정원사=무음→물소리)는 `docs/SCRIPT_first_contact_ai.md`.
- [시나리오→캐릭터] 3번째 각인의 **역할 진화 표식** 8종을 확정된 이름(`data/roles_evolved.json`: 노래잡이·버림 없는 손·숨의 손·조상 깨우는 이·문턱지기·낭독하는 이·빈손 흥정꾼·짐을 진 아이)에 맞춰 설계 요청.
- [시나리오→배경] `spot_flooded_train.glb` 에 빛기둥용 구멍 + **사람이 서는 문간**이 필요(문간이 없으면 '들어가지 않는다'가 화면에 안 보임). 정원사 대면의 잉어 글자는 텍스처 금지, 인스턴스 배치 애니메이션으로.
- [시나리오→개발] `data/family_names.json`(18개 창작 가문 이름) 적용 — 화면 노출 이름은 이 파일의 `name`, 실제 제조사명은 `known_families.json` 숨김 필드 `real` 로만.
- [시나리오(S5-B)→개발, **필수**] 신규 데이터 6개 로더·API 필요(전부 시나리오 소유, 읽기 전용): `data/companion_octopus.json`(E3) · `data/wishes.json`(E5) · `data/family_lore.json`(E2) · `data/first_meet.json`(E7) · `data/day_end.json`(E6) · `data/relic_props.json`(E1). 각 파일 `_for_dev` 에 치환자·판정 힌트·권장 규칙을 적어 뒀습니다. **스키마가 필요하면 `data/*_schema.json` 으로 정해 주세요 — 필드명이 바뀌면 값은 시나리오가 다시 맞춥니다.**
- [시나리오(S5-B)→개발] E7 첫 만남은 **처음 1회만** 떠야 합니다. 세이브에 `seen_categories`(9종)·`seen_families`(18키) 플래그 두 개가 필요합니다. 같은 스캔에서 둘 다 처음이면 가문 줄 먼저, 카테고리 줄 뒤.
- [시나리오(S5-B)→개발] E3 문어: `finds[].favor_category` 는 **전날 찍은 카테고리** 가중치입니다(권장: 기본 1, 일치 시 `weight` 가산). `kind: "spot_clue"` 3줄은 `spot_hint` 의 스팟 단서 연출과 같은 날 묶어 주세요. 이름 미지정 시 `{oct_name}` 치환 대신 `naming.skip_line` 을 씁니다.
- [시나리오(S5-B)→개발] E5 바람 8개의 `condition.hint` 는 **판정 힌트일 뿐 정본이 아닙니다.** 실제 조건식은 개발이 정하고, 바뀐 조건만 알려 주면 `condition.text` 문장을 다시 씁니다. `line_after` 는 `line_before` 를 **영구 대체**(되돌아가지 않음)입니다.
- [시나리오(S5-B)→개발] E4 눈금 일지 화면 문안은 `docs/WORLD_BIBLE_DEEP.md` §9 에 있습니다(머리말 3줄 + 옛 기록 5줄 + 플레이어 줄 형식). 간격 90초 시작 · 층당 −5 · 하한 40, 하한에 닿으면 일지는 **멈춥니다**. 새 줄에 해설을 붙이지 말 것(§9-5 봉인 어휘 목록).
- [시나리오(S5-B)→배경·캐릭터] E1 창고 소품 **34종**(`data/relic_props.json`, 8카테고리 4개씩 + unknown 2) 스프라이트 요청. 전부 선반 위 물건, 바닥 가구 없음, 흙 팔레트(청록·남색은 물 전용), 정면 평면 단면이라 **옆모습 실루엣으로 구분**되게. 선반 격자 한 칸 규격이 정해지면 `slots`(1/2) 제안값을 그 규격에 맞춰 고치겠습니다.
- [시나리오(S5-B)→배경] E2 가문 장식 **18종**(`data/family_lore.json` 의 `decor`) — 전부 벽·선반에 거는 작은 물건입니다. 세트 완성 시 해당 방 벽에 하나 붙습니다.

- [개발(시스템)→PM] **소문 해금 조건 정본 결정 필요**: `server.py RUMOR_RULES`(PM 요청대로 food/medical/stationery 확장 완료) vs `data/rumors.json` 줄별 `unlock`(예: 옥상 정원 = 의약3·전자4). 현재는 **서버 표가 해금을 정하고 파일은 문장만** 쓴다(조건 못 채운 줄은 폴백으로 나올 수 있음). 데이터 주도로 바꾸려면 한 줄 작업.
- [개발(시스템)→PM] `DECISIONS.md` 등재 요청 2건: ① 각인 참여자 선별(hero > counter_room 배치 > 역할태그 > 카드태그 > 시드난수, 상한 2명, 목격자 1명) ② 가문 실명 비노출(`family_names.json` 우선, 없으면 "이름 잃은 가문 NNNN") — 코드 반영 완료.
- [개발(시스템)→시나리오] `data/dialogue_schema.json`(신규, 개발 소유) 참고: `when` enum과 `_hooks`(어느 태그가 화면 어디에 뜨는지)를 적어 뒀다. `game_start`·`spot_water_reflection` **훅 연결 완료** — 줄만 채우면 바로 뜬다. `scan_medical/electronics/apparel/tobacco/stationery/drink`도 코드 수정 없이 자동 연결된다.
- [개발(시스템)→시나리오·배경] 힐링 스팟 월드 좌표는 `server.py SPOT_POS`의 임시값(부족 방향만 맞춤). 지도상 위치가 다르면 알려 주세요 — 그 표만 고치면 됩니다.
- [개발(시스템)→개발(월드 S2-A)] 지도 표식은 `/api/rumors`의 `pos{x,y}`(m)·`unlocked`를 쓰세요(잠기면 `clue_text:null`). 대사 연출은 `window.ARK.voiceToast({who,who_ko,text})`, 소문 목록은 `window.ARK.renderRumors()` 재사용 가능.
- [개발(시스템)→사운드] 오디오 버스·트리거 연결은 S2-B 범위 밖(스프린트 3). 현재 서버가 이미 내보내는 신호: `/api/scan.voice`, `/api/event/resolve.voice|spot_voice`, `/api/ark.is_night|voice|morning_lines`.

- [배경→개발] S2-D 에셋 배치 규약(경로 / 파사드 원점=입구 바닥 중심·정면 Three +Z / 힐링 스팟 물 재질명 `Water` / `koi_1~5` 좌표 / 문간 마커 `marker_threshold` / 금붕어 빈 수면 6×4m 좌표)은 `docs/reports/bg_S2.md` §7에 정리했습니다. `static/world3d.js`는 개발 소유라 손대지 않았습니다.
- [캐릭터(S4-C)→PM·사용자] **판단 요청 2건**: ① `static/charshow2d.html` §1 대표 캐릭터 다섯(정찰병·의무병·아이·기술자·동거 문어)이 이 게임의 얼굴로 맞는가 ② §2 팔레트 7계열 중 바꾸고 싶은 색. 화풍 판정은 §6(70px)만 보면 됩니다. 캐릭터 담당 추천은 **B안 = 평면 민속화풍**(`REF_ART_FLAT_FOLK` §1 적용) — 근거는 `docs/reports/char_S4.md` §7. A안(렌더 그대로)은 아이소(2·3막)용으로 남깁니다.
- [캐릭터(S4-C)→PM] **DECISIONS 후보**: 「1막 캐릭터 화풍 = 평면 민속화풍(팔레트 7계열·음영 2단·역할별 반복 무늬·흔들리는 선). 청록·남색은 물 전용, 사람에게 금지」. 채택되면 배경·UI도 같은 팔레트를 써야 화면이 한 덩어리가 됩니다.
- [캐릭터(S4-C)→배경·UI] 팔레트를 공유 자산으로 쓰시려면 `static/art/chars/front/front_meta.json` 의 `palette` 키에 7계열 (밝은 면, 그림자) 쌍과 선 색이 들어 있습니다. 방 색을 이 팔레트 안으로 옮기면 인물과 방이 같은 그림이 됩니다.
- [캐릭터(S4-C)→개발] 정면 단면용 스프라이트 시트 규약: `static/art/chars/front/<a|b>/<role>.png` (셀 256px · 가로=프레임 5 · 세로=클립 Idle/Walk/PickUp). 메타는 `static/art/chars/front/front_meta.json`. **미터당 110px 고정 · 발 기준선 = 셀 위에서 240px**. 클라이언트는 `scale = 원하는1.6m높이 / 176` 하나만 쓰면 8역할 키 비율이 자동으로 맞습니다(아이 1.21m는 실제로 작게 나옵니다). 셀을 세로로 잘라 바닥에 맞추지 말고, 셀 바닥을 바닥선보다 `16*scale` px 아래에 두세요.
- [캐릭터(S4-C)→배경] `section_hero.png` 의 방 뒷벽(#e4ce9a)·바닥(#5f5953)·어두운 구석(#1a180d) 색을 그대로 써서 검증했습니다. **요청**: 방 안 벽과 바닥의 명도 차가 지금처럼 크면(0.89 ↔ 0.10) 한 인물의 상반신과 다리가 정반대 대비 환경에 놓입니다. 사람이 서는 띠(바닥에서 위로 약 1.7m)만이라도 명도 폭을 0.35~0.65로 좁혀 주시면 캐릭터 가독성이 크게 올라갑니다.
- [캐릭터(S4-C)→PM·시나리오] **정면 단면의 제약 발견**: 깊이 방향(카메라 쪽으로 숙이는) 동작은 읽히지 않습니다. `PickUp` 을 전 구간 쓰면 얼굴이 사라지고 덩어리가 됩니다(비교 페이지 §5 '실패 컷'). 1막 거점의 일하는 동작은 **좌우·상하 동작으로 다시 설계**해야 합니다(팔을 옆으로 뻗기, 쭈그려 앉기, 물건을 옆으로 옮기기). 사건·대사에서 "몸을 숙여 ~을 줍는다" 류의 묘사를 화면으로 보여줄 계획이라면 미리 알려 주세요.
- [배경→PM] 시나리오 중계 3건(빛기둥 구멍 / 사람이 서는 문간 / 금붕어 빈 수면)은 `spot_flooded_train.glb`에 **전부 반영**했습니다(보고서 §7-5).

- [시나리오(S3-A)→개발] `data/events_deep.json`(16장) 신규. 서버 EVENTS 병합 목록에 추가해 주세요(현재 `events.json`+`events_tribes.json`+`events_outside.json`만 읽는지 확인 필요). 스키마·id 유일성은 검증 완료(보고서 `scenario_S3.md` §3).
- [시나리오(S3-A)→개발] `data/events_schema.json` `faction` enum에 심해 무리용 값이 없습니다. 낯선 돔 카드는 임시로 `faction:"tribe"` + `tribe` 필드 비움으로 처리했습니다. `tribe` enum에 `gauge`(눈금)·`anchor`(닻)·`net`(그물)·`guest`(손님) 4개 추가를 요청합니다. 클라이언트 `FAC_KO`/부족 한국어 표기도 함께.
- [시나리오(S3-A)→개발] `data/imprints.json` 각인 3종 신설 요청: 「아낀 숨」(공기 부족, id_prefixes `deep_air`), 「금을 본 자」(유리 균열, `deep_glass`), 「깊이의 자국」(해구 하강, `deep_trench`/`deep_ballast`). 표는 `docs/WORLD_BIBLE_DEEP.md` §7. 현재 이 3계열 카드는 각인이 안 붙습니다.
- [시나리오(S3-A)→PM] 「발자국」 각인이 육상 이름입니다. 심해 대형 생물 카드는 `flag:"dino_escaped"`로 같은 각인에 연결해 두었습니다 — 이름을 「지나간 것의 자국」 계열로 일반화할지 결정 필요(DECISIONS 후보).
- [시나리오(S3-A)→PM·개발] 심해 힐링 스팟 6곳 본문을 `docs/WORLD_BIBLE_DEEP.md` §4에 `spots.json` 필드 형식 그대로 써 두었습니다. `data/spots.json`에 바로 넣으면 S3-C(`/api/spots`·`SPOT_POS` 교체)와 충돌할 수 있어 **대기 중**입니다. 넣을 시점과 파일(기존 `spots.json` vs 신규 `spots_deep.json`)을 지정해 주세요. 사건 카드가 참조하는 id: `spot_vent_garden`, `spot_whale_fall`, `spot_kelp_ceiling`(나머지 3곳은 아직 단서 카드 없음).
- [시나리오(S3-A)→사운드] 1막의 핵심 연출 하나: **에어락을 나가면 리더의 목소리가 완전히 끊기고, 들어오면 돌아온다.** 안=리더(스피커) / 밖=정원사(물·떼·해류). 오디오 버스를 안/밖으로 분리해 주세요(`docs/SCRIPT_first_10min_deep.md` 2:30·3:40 비트, `WORLD_BIBLE_DEEP.md` §5-1).
- [시나리오(S3-A)→배경·캐릭터] 첫 10분이 요구하는 것 표는 `docs/SCRIPT_first_10min_deep.md` §4에 있습니다(돔 단면 첫 화면 / 에어락 문턱 2방향 / 목만 들어오는 긴목 / 문어 / 은빛 떼 글자 / 물 찬 방).
- [시나리오(S3-A)→개발] 공기 게이지는 **숫자가 아니라 줄어드는 띠**로 요청합니다(각박함을 수치로 읽지 않게. 육상 빛 게이지와 같은 자리).

- [개발(S3-C)→시나리오, **필수**] 「두드림을 들은 자」(`knock_heard`) 각인의 **외형·연출문·대가 한 줄**이 없습니다 — `WORLD_BIBLE_DEEP.md` §7 표에 1행 추가해 주세요. 판정·연결은 끝났고(심해 `dino_escaped`→`beast_left` 매핑) 지금은 자리표시라 서버가 `pending` 플래그로 화면 노출을 막고 있습니다. `data/imprints.json` 에 id `knock_heard` 정식 항목을 넣으면 코드의 자리표시가 자동으로 밀려납니다(파일 우선 병합).
- [개발(S3-C)→시나리오] `data/rumors.json` 줄별 `unlock` 수치 확인 요청: 4개 스팟(`spot_goldfish_canal`·`spot_forest_train_door`·`spot_rooftop_garden`·`spot_lantern_river`)이 **열리는 순간 읽을 수 있는 소문 줄이 0줄**입니다(가장 싼 줄이 서버 문턱보다 높음). 지금은 `spots.json` 의 `clue_text` 로 물러나게 고쳐 두었으니 동작은 정상이지만, 첫 소문을 시나리오 문장으로 읽히려면 각 스팟에 서버 문턱 이하 조건의 줄이 한 줄씩 필요합니다. 대조표는 `docs/reports/dev_S3.md` §5.
- [개발(S3-C)→시나리오] `data/spots_deep.json` 신설 대기 중 — `/api/spots` 목록 병합 로더 완료(파일이 없어도 정상). 필드는 `spots.json` 과 동일(`id`·`name`·`discovery_text`·`clue_text`·`resource`·`danger_note`·`tribe_hint`), 줄마다 `unlock:{category,count}` 를 넣으면 서버 표에 없는 동안 임시 게이트로 씁니다. 파일이 들어오면 개발이 `SPOT_POS`(심해 좌표)와 `RUMOR_RULES` 6줄을 붙입니다.
- [개발(S3-C)→시나리오] `data/events_deep.json` 16장의 `tribe` 필드가 비어 있습니다 — 스키마 enum 에 `gauge`·`anchor`·`net`·`guest` 를 넣고 클라이언트 표기(눈금/닻/그물/손님 **무리**)까지 붙였으니, 낯선 돔 카드에 `tribe` 를 채우면 화면에 무리 이름이 바로 뜹니다(`faction:"tribe"` 는 그대로).
- [개발(S3-C)→PM] `?debug_force_event=` 는 이제 **`RELIC_DEV=1` 에서만** 동작합니다(기본 404). 개발·검수 시 서버를 `RELIC_DEV=1 python server.py` 로 띄워 주세요. 02_DEV §4-4 '배포 전 제거 목록'에서 이 항목은 닫힌 것으로 봐 주십시오.
- [사운드(S4-D)→개발, **필수**] 심해 오디오 11개(`static/audio/amb_dome_inside.ogg` 등) 완성. **에어락 크로스페이드 규격**(리더 버스 로우패스 20000→400Hz + 게인 0→-80dB, 0.9초, amb 1.5초 크로스페이드)과 이벤트명 9개(`world:airlock_exit`·`world:airlock_enter`·`world:depth_enter_trench`·`world:depth_leave_trench`·`world:glass_crack`·`world:knock_glass`·`world:air_low`·`world:collect_deep`·`world:room_flood`) 연결 요청. 기존 `world:spot_found`에 `cue` 페이로드 필드 추가도 필요(스팟마다 다른 큐 파일 지정). 전체 수치·순서·구현 메모는 `docs/AUDIO_CUES.md` §5, 근거는 `docs/reports/sound_S4.md`.
- [사운드(S4-D)→개발] `world:room_flood` 처리 후 해당 `room_id`를 `flooded:true`로 저장해 그 방의 로컬 앰비언트를 영구 mute해 주세요(시각은 남고 청각만 사라지는 것이 `WORLD_BIBLE_DEEP.md` §6 요구). 저장 위치는 개발 판단.
- [사운드(S4-D)→개발·PM] `world:far_call`(먼 울음, `amb_far_call.ogg`) 간격 커브 요청은 **PM이 해결함**(`docs/reports/review_sprint4.md`): 기본 90초 → 방주 층수(깊이)가 늘 때마다 5초씩 감소 → 하한 40초. 개발은 이 값 그대로 구현하면 됩니다(`docs/AUDIO_CUES.md` §5-4에도 반영).


- [시나리오(S4-C)→개발] `acts` **60장 전량 기입 완료**(DECISIONS 2026-09-23). 작업 중에 개발이 `events_schema.json` `acts` 속성과 `storyteller.acts_of()`·`events_for_act()` 를 이미 붙여 둔 것을 확인해, 임시 분류표(`ACT_BY_ID`/`ACT_BY_PREFIX`)는 이제 **전부 파일에 밀려납니다** — 표를 지워도 됩니다(`_UNCLASSIFIED` 경고 0건). 실측 분포: **1막 26장**(sev 0/1/2/3 = 9/7/9/1, positive 2) · 2막 4장 · 3막 38장. `events_for_act(1)` 이 26장을 돌려주는 것까지 확인했습니다.
- [시나리오(S4-C)→개발, **필수**] `data/imprints.json` 에 「두드림을 들은 자」(`knock_heard`) 정식 항목 등재 요청. 외형·대가 문구는 `docs/WORLD_BIBLE_DEEP.md` §7 표(1행 추가 완료), 연출문은 `data/imprint_lines.json` 의 `knock_heard` 줄. `server.py DEEP_IMPRINTS` 의 `_pending_text` 자리표시를 해제해도 됩니다. 대가는 **야간 생산 −**(밤에 두드리는 소리가 더 자주 들려 손이 느려진다) — 수치는 개발 몫.
- [시나리오(S4-C)→개발] `data/dialogue.json` 에 1막 줄 12개 추가(`game_start`·`surface_trip`·`spot_deep`·`spot_water_reflection`·`night`·`first_ally`·`scan_unknown`·`event_fail`). **결함 하나**: 대사 줄에 막 구분이 없어 1막에서도 육상 소재 줄(비단잉어·숲·바람·일곱 물줄기)이 같은 태그에서 뽑힙니다. ① 줄별 `acts` 허용(`dialogue_schema.json` 도 `additionalProperties:false`) 또는 ② 서버가 막으로 거르기 중 하나를 골라 주세요. 그리고 `when` enum에 **`airlock_in`**(에어락을 다시 넘어 들어온 순간, 리더 목소리 복귀) 추가 요청 — 지금은 밖(`surface_trip`)만 있고 귀환 자리가 없어 첫 10분 3:40 비트의 "값은… 0입니다" 줄을 넣지 못했습니다.
- [시나리오(S4-C)→개발] `data/spots_deep.json` 6곳 반영 확인함 — `/api/spots` 12곳, `spot_gate` 전부 `source=rules`, `rumor_rule_audit()` **결함 0**. 스팟의 `unlock` 은 서버 `RUMOR_RULES_DEEP` 과 값이 같으니 이제 **표가 정본**입니다(파일 쪽은 표가 비었을 때의 폴백으로만 남김). 좌표는 개발 표(`SPOT_POS_DEEP`)가 성경 §4의 구역과 맞습니다 — 시나리오 이견 없음.
- [시나리오(S4-C)→캐릭터] 심해 각인 4종의 외형 파츠 `imp_<id>` 요청: `imp_saved_breath`(짧아진 문장 — 다문 입·좁아진 어깨), `imp_crack_seen`(늘 창을 만지는 손 — 장갑 손끝만 닳음), `imp_depth_mark`(귀·코의 눌린 자국), **`imp_knock_heard`**(만지기 전에 두 번 두드리는 버릇 — 손가락 마디에 굳은살, 귀가 소리 쪽으로 돌아간 각도). 외형 근거는 `docs/WORLD_BIBLE_DEEP.md` §7.
- [시나리오(S4-C)→PM] 1막 풀 26장 중 **4장이 육상 파일(`events.json`)** 입니다: `famine`·`drought`·`confusion`·`relic_cache`. 근거는 "장소를 타지 않는 것만 전 막 공용"(DECISIONS 2026-09-23) — 항아리가 빈다/물이 샌다/성문을 잘못 읽는다/봉인된 상자가 나온다는 돔에서도 그대로 성립합니다. 나머지 6장은 지하 강·철길·빛의 사원·회색 개·까치·밤 기온이 나와 [3]으로 뒀습니다. 다르게 보시면 알려 주세요.

- [개발(S4-B)→시나리오] **2막(터널) 사건 풀이 4장뿐입니다**(1막 26 · 3막 38). `acts:[2]` 카드 12장 이상 필요 — 지금 2막으로 가면 같은 카드가 계속 돕니다. 수치는 `docs/reports/dev_S4.md` §2.
- [개발(S4-B)→시나리오] `data/dialogue.json` 줄에 **`acts` 배열** 기입 요청. 스키마(`data/dialogue_schema.json`)와 필터(`voice_for(..., act=)`)는 완료했고 **값만** 채우면 됩니다. acts 없는 줄은 전 막 공용이라 지금 동작은 그대로입니다. 1막에서 금지: 숲·비단잉어·'일곱'(DECISIONS 2026-09-22).
- [개발(S4-B)→시나리오] `when` enum 에 `airlock_in`·`airlock_out`·`far_call` 추가 완료. **호출부는 아직 없습니다**(원정·에어락 시스템 전). 줄을 미리 채워 두면 그날 코드 수정 없이 뜹니다.
- [개발(S4-B)→시나리오·PM] `room.flooded`(물 찬 방, 첫 10분 8:00 비트) **그리는 쪽은 준비됐고 만드는 규칙이 없습니다.** 어느 카드가 실패하면 그 방이 닫히는지 정해 주세요(예: `deep_glass_*` on_fail 에 `flood_room`).
- [개발(S4-B)→PM] 판단 3건: ① 캐릭터 A/B 기본값(`/base` 는 지금 b→a→색 사각형 순, `?chars=` 로 비교 가능) ② 슬롯 10칸 확장 여부 — 현재 최대 깊이 180m 라 해구(210m)에 닿지 못합니다 ③ 2막 풀 최소선(1막은 24장으로 박혀 있음).
- [개발(S4-B)→PM·사운드] 사운드 3건(리더 버스 로우패스·이벤트 9개·`room_flood` mute)은 **다음 스프린트로 미룹니다** — 클라이언트에 오디오 계층 자체가 없어 이번 스프린트에 넣으면 검증 없는 코드가 됩니다. 다만 「먼 울음」 간격 커브는 지금 심었습니다: `/api/ark.gauges.far_call_sec`(90초 − 층당 5초, 하한 40. 4층 방주 = 80초). 정체를 알리는 이름·설명은 응답에 없습니다.
- [개발(S4-B)→시나리오] 신규 자원 key 6종(`vent_heat`·`glow`·`relic_tile`·`bone_feast`·`brine`·`kelp`)으로 **분기하는 코드는 없습니다** — 표시용 꼬리표로만 쓰이고 실제 증감은 `gain` 의 기존 키로 들어옵니다. 그대로 두셔도 됩니다.
- [개발(S4-B)→전원] 1막 거점 화면이 섰습니다: **`http://127.0.0.1:8002/base`** (index 와 같은 방주). 막 전환 검증은 `RELIC_DEV=1` 에서 `?debug_act=1|2|3`. 보고서 `docs/reports/dev_S4.md`.

## 스프린트 3 (2026-09-22 착수) — "심해 유리돔이 첫 화면이 된다"
목표 한 문장: **검은 물속 유리돔 단면 한 장으로 이 게임이 설명되게 한다.** 근거 `docs/CONCEPT_DEEP_SEA.md`, 결정 `DECISIONS.md` 2026-09-22.

| 태스크 | 담당 | 내용 | 산출물 | 완료 기준 |
|---|---|---|---|---|
| S3-A | 시나리오 | 심해 1막 성경: `LORE_v3_바다가_보관한_것.md`, `WORLD_BIBLE_DEEP.md`(돔 문화 3~4·깊이 4구역·해양 생물 3~4·힐링 스팟 6·두 AI의 수중 언어), `data/events_deep.json`(12~16장), `SCRIPT_first_10min_deep.md` | 위 파일 + `docs/reports/scenario_S3.md` | JSON 유효·기존 스키마 준수, 금지어 0, 기존 성경과 모순 0, 사건이 전부 질문 형태(S3) |
| S3-B | 배경 | **유리돔 단면 비주얼 테스트**: `tools/blender_dome.py`, 렌더 3장(첫 화면·에어락·깊이감), 가능하면 `dome_core.glb` | `art_raw/deep/*.png` + `docs/reports/bg_S3.md` | 설명 없이 "물속 유리돔"으로 읽힘, 유리가 반사+투과(D4), 주색 2개만(D1), 빈 물 40%+(D2), 생성 AI 0 |
| S3-C | 개발 | **필수** `/api/spots` 신설(`spots.json`이 브라우저에 못 닿아 발견 텍스트가 JS 상수 — D7 위반). `SPOT_POS`를 `dev_world_S2.md` §3-3 표로 교체. `data/rumors.json` `unlock` ↔ `RUMOR_RULES` 동기화. `?debug_force_event=` 제거 스위치 | `server.py`, `docs/reports/dev_S3.md` | curl 로그 + 월드 화면 회귀 |
| S3-D | 캐릭터 | (S3-B 판정 후 착수) 잠수복 주민·대형 해양 생물 | — | — |
| S3-E | 사운드 | (S3-B 판정 후 착수) 수중 앰비언트: 압력·먼 울음·에어락 | — | — |
| S3-PM | PM | S3-A/B 검수, 사용자에게 첫 화면 후보 제시, 2막(터널) 연결 설계, 기존 육상 에셋의 2·3막 재배치 표 | `docs/reports/review_sprint3.md` | 사용자가 첫 화면을 보고 판단할 수 있는 상태 |

기존 육상 자산의 재배치(폐기 0): 몰 파사드·물에 잠긴 전철·일곱 부족·공룡·`world.html` 지형 → **3막 지상**. 침수 지하철 터널 → **2막 연결부**(신규).


## 스프린트 4 (2026-09-26 착수) — S4-C 시나리오 ✅통과 · S4-D 사운드 ⚠️조건부

## 스프린트 4 (2026-09-26 착수) — "심해 1막이 목표 화풍으로 보이고, 막이 갈린다"
목표 한 문장: **평면 단면 거점 화면을 목표 화풍(평면 민속화풍)으로 세우고, 1막 카드 풀을 분리한다.**
근거: `docs/refs/REF_ART_FLAT_FOLK.md`, `docs/refs/REF_CROSS_SECTION.md`, `DECISIONS.md` 2026-09-23.

| 태스크 | 담당 | 내용 | 산출물 | 완료 기준 |
|---|---|---|---|---|
| S4-A | 배경 | 평면 단면 렌더 완성. sRGB/선형 버그 수정 + HANDOFF §3.5 지적 5건 + **목표 화풍 적용**(음영 2단·흙 팔레트·장식 무늬·손그림 선·단색 면 배경) | `tools/blender_section.py`, `section_hero/zoom/palette.png`, `docs/reports/bg_S4.md` | 거점 전체가 한 장에, 방이 색과 무늬로 구분, 위→아래 어두워짐, 우주로 안 보임, 가장 밝은 것은 방 등불 |
| S4-B | 개발 | **`acts` 막 구분**(1심해/2터널/3지상/[1,2,3]공용) + **`static/base.html` 평면 단면 화면 뼈대** + 공기 게이지 자리 + spots_deep 자동 연결 준비 | `server.py`, `engine/`, `static/base.html`·`base.js`, `docs/reports/dev_S4.md` | 회귀 7항목, 1막 풀 24장 이상 확인, 폰 세로·데스크톱 스크린샷, 콘솔 에러 0 |
| S4-C | 시나리오 | `data/spots_deep.json` 신설(6곳) + 소문 결함 4스팟 수정 + 「두드림을 들은 자」 각인 완성 + 심해 카드 `tribe`·`acts` 기입 | 위 파일 + `docs/reports/scenario_S4.md` | JSON 유효·금지어 0·스팟마다 즉시 읽히는 줄 1개 이상·1막 24장 |
| S4-D | 사운드 | 심해 앰비언트 3 + **에어락에서 리더 목소리가 끊기는 전환** + SFX 5 + 발견 큐 + 「먼 울음」(정체 봉인) | `static/audio/*.ogg`, `AUDIO_CUES.md` 심해 절, `docs/reports/sound_S4.md` | 심해분 ≤2MB, 스펙트럼 중심 돔 안 < 바깥 < 해구 |
| S4-E | 캐릭터 | 정면 2D 스프라이트 화풍 확정(A/B/덩어리 비교, 70·110px 가독성) → **대표 캐릭터 4종 쇼케이스** | `tools/render_sprites.py`, `static/charshow2d.html`, `docs/reports/char_S4.md` | 70px에서 역할 구분, 어두운 방 배경에서 안 묻힘, 팔레트 띠 포함 |
| S4-PM | PM | 검수(재현), 화풍 일관성 판정(배경과 캐릭터가 같은 팔레트인가), 통합, 사용자에게 대표 캐릭터·단면 화면 제시 | `docs/reports/review_sprint4.md` | 체크리스트 + "더 재미있게 했는가" |

병렬 안전성: 소유 파일이 겹치지 않는다. 배경=`blender_section.py`·`art/deep`, 캐릭터=`render_sprites.py`·`art/chars`, 개발=`server.py`·`engine`·`base.html`·`*_schema.json`, 시나리오=`data/` 내용 파일, 사운드=`audio/`. 개발은 내용 파일을 런타임 병합으로만 건드린다.

## 스프린트 5 (2026-09-27 착수) — "왜 내일 또 켜는가"
| 태스크 | 담당 | 내용 |
|---|---|---|
| S5-A | 개발 | `static/journey.html` — 여정 14단계 화면 시안 |
| S5-B | 시나리오 | E1~E7이 필요로 하는 텍스트·데이터 7종(문어·바람·가문 도감·첫 만남·마감 컷·일지·소품 이름) |
| S5-C | 캐릭터 | 대표 캐릭터 3등신으로 — 귀여움은 비율·실루엣·동작에서만 |
| S5-PM | PM | 검수, 기획안 통합, Phase 1 보드 |

## 스프린트 7 후보
- [배경, **필수**] 합성용 **사람 없는 방 플레이트** 렌더(현재 플레이트에 옛 화풍 주민이 박혀 있다)
- [캐릭터] 채택된 도트 방향 하나로 8역할·각인·뒷모습 확장, 키 ±12% 오차 보정
- [개발] 주민 배치 시스템 + 습격 3단계 예고 + 방어 판정(`COMBAT_AND_DEFENSE.md` §8)
- [배경] `soft_mat()` Mapping 순서 버그 수정 + **바깥 룩 재검수를 한 묶음으로**(물 부유물·해파리·빛기둥이 같은 함수를 쓴다)
- [캐릭터] 앉은/기댄/누운 자세 행 추가(현재 Idle을 내린 속임수)
- [배경·캐릭터] 컨셉 선정 후 `section_warm.png` 재렌더(`CHAR_VAR` 문자 하나)
- [개발] 소품 34종을 창고 선반에 실제로 붙이기(E1 완성)

## 스프린트 3 후보(미배정)
- [개발, **필수**] `/api/spots` 신설 — `data/spots.json`이 브라우저에 닿지 못해 발견 텍스트가 world3d.js 상수로 박혀 있다(D7 위반). 데이터는 API로만.
- [개발] `SPOT_POS`를 dev_world_S2.md §3-3 제안표(지형 좌표계)로 교체.
- [캐릭터] 역할 진화 표식 `evo_<role>` 8종 모델링(char_S2.md §3-2 아이디어 표), 각인 파츠 대비 개선(이빨 목걸이·등 뒤 파츠).
- [배경] 스카이라인 양끝 페이드 또는 반복 타일화, 파사드 담쟁이 밀도 상향(초록 비율 ≥ 절반, ART_REFERENCES §2.7), 유리 알파 Three 검증.
- [개발] `data/rumors.json` `unlock` ↔ `RUMOR_RULES` 동기화, `?debug_force_event=` 배포 전 제거, 주민 자리 배치(`station`) UI — 참여자 규칙 ②가 살아난다.
- [시나리오·PM] `cold_snap`→「지킨 자」 오매칭: 각인 표를 9종으로 확장(「견딘 자」 후보) → GROWTH_AND_MYTH 개정. DECISIONS 필요.
- [사운드] 리더/정원사 시그니처(A4)·부족 모티프 6개(A7), 사용자 청취 피드백 반영.
- 개발: 노선 원정(C 심장) 노드 맵 + 6턴 3레인 대항(D 손) 통합, 자리 잡기 건설, 빛 게이지, world.html을 index로 승격.
- 배경: 부족 쉘터 외관 3종, 지하철 터널 씬, 스팟 2곳 추가.
- 캐릭터: 부족 7종 의상 파츠, 아이 성장 단계, 일하는 모션(카트 끌기).
- 시나리오: 부족 신화 낭독 전문, 엔딩 3갈래 개요, 카드 뒷면 주석 31종.
- 사운드: 부족 모티프 6종, 공룡 접근 경고, 리더/정원사 시그니처.
- [배경(S8-C)→캐릭터, **회신**] 「사람 없는 방 플레이트」 두 건(S7-A·S8-A) 모두 처리했다. ①전체 컷 `static/art/deep/section_warm_noppl.png`·방 2칸 확대 `section_room_zoom_noppl.png` — **사람이 한 명도 없다**(`RELIC_CHAR_VAR=none` 스위치). ②더 쓸모 있는 것은 방 종류별 단독 플레이트 12장 `static/art/plates/room_plate_<방>_{dark,lit}.png`(6종 × 빈 방/등불 켜짐). ③**배율 요청대로 ×3 = 82.5px/m 로 고정**했다 — `front/p2/meta.json` 의 `src_ppm 27.5 × room_scale 3` 을 그대로 가져왔다(84px/m 로 잡았다가 1.8% 어긋나서 다시 냈다). ④요청한 메타를 `static/art/plates/plates_meta.json` 에 전부 넣었다: `floor_y`(=315, 캔버스 위에서의 바닥선) · `px_per_m`(82.5) · `stand_x`(사람이 설 수 있는 x 범위) · `lamp`(등불 좌표) · `inner_rect`/`outer_rect`. `src/<role>.png` 를 NEAREST ×3 으로 키우고 셀 안 `baseline(180)` 을 `floor_y` 에 맞추면 끝이고, 그 합성을 실제로 해 본 증거가 `art_raw/plates/plate_char_test.png` 다.
- [배경(S8-C)→개발] 전투 예고·피해 재료 납품. ①생물 실루엣 8장 `static/art/threats/threat_<생물>_{far,near}.png`(990×495 RGBA, **플레이트와 같은 82.5px/m**, 오른쪽이 거점 쪽 — 반대면 좌우 반전) + `threats_meta.json`. ②유리 피해 3단계 `static/art/plates/damage_crack{1,2,3}.png` 와 물 찬 방 `room_flood.png` — 전부 **플레이트와 같은 672×378 RGBA 오버레이**라 좌표 계산 없이 그대로 얹으면 된다. 세 단계는 **같은 자리에서 누적**되고, `room_flood.png` 의 구멍은 `damage_crack3.png` 의 구멍과 같은 좌표다. ③방 6종은 거주·창고·공방·의무실·발전실·온실이고 `COMBAT_AND_DEFENSE.md` §5-1 의 기능과 1:1이다(`plates_meta.json` 의 `rooms[].note`).
- [배경(S8-C)→PM] 판단 2건: ①플레이트 6종에 **의무실·발전실이 새로 생겼다** — `layout()`(전체 단면)에는 아직 없고 라운지·서고·목욕탕·에어락이 플레이트 세트에는 없다. 전체 단면의 방 구성을 COMBAT §5-1 에 맞춰 바꿀지 결정이 필요하다. ②`soft_mat()` Mapping 순서 버그는 이번에도 **고치지 않았다**(S6 §8-4 와 같은 이유 — 물이 그 함수를 쓴다). 스프린트 7 후보에 묶인 채로 둔다.
