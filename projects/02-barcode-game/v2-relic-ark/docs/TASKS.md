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

- [개발(시스템)→PM] **소문 해금 조건 정본 결정 필요**: `server.py RUMOR_RULES`(PM 요청대로 food/medical/stationery 확장 완료) vs `data/rumors.json` 줄별 `unlock`(예: 옥상 정원 = 의약3·전자4). 현재는 **서버 표가 해금을 정하고 파일은 문장만** 쓴다(조건 못 채운 줄은 폴백으로 나올 수 있음). 데이터 주도로 바꾸려면 한 줄 작업.
- [개발(시스템)→PM] `DECISIONS.md` 등재 요청 2건: ① 각인 참여자 선별(hero > counter_room 배치 > 역할태그 > 카드태그 > 시드난수, 상한 2명, 목격자 1명) ② 가문 실명 비노출(`family_names.json` 우선, 없으면 "이름 잃은 가문 NNNN") — 코드 반영 완료.
- [개발(시스템)→시나리오] `data/dialogue_schema.json`(신규, 개발 소유) 참고: `when` enum과 `_hooks`(어느 태그가 화면 어디에 뜨는지)를 적어 뒀다. `game_start`·`spot_water_reflection` **훅 연결 완료** — 줄만 채우면 바로 뜬다. `scan_medical/electronics/apparel/tobacco/stationery/drink`도 코드 수정 없이 자동 연결된다.
- [개발(시스템)→시나리오·배경] 힐링 스팟 월드 좌표는 `server.py SPOT_POS`의 임시값(부족 방향만 맞춤). 지도상 위치가 다르면 알려 주세요 — 그 표만 고치면 됩니다.
- [개발(시스템)→개발(월드 S2-A)] 지도 표식은 `/api/rumors`의 `pos{x,y}`(m)·`unlocked`를 쓰세요(잠기면 `clue_text:null`). 대사 연출은 `window.ARK.voiceToast({who,who_ko,text})`, 소문 목록은 `window.ARK.renderRumors()` 재사용 가능.
- [개발(시스템)→사운드] 오디오 버스·트리거 연결은 S2-B 범위 밖(스프린트 3). 현재 서버가 이미 내보내는 신호: `/api/scan.voice`, `/api/event/resolve.voice|spot_voice`, `/api/ark.is_night|voice|morning_lines`.

- [배경→개발] S2-D 에셋 배치 규약(경로 / 파사드 원점=입구 바닥 중심·정면 Three +Z / 힐링 스팟 물 재질명 `Water` / `koi_1~5` 좌표 / 문간 마커 `marker_threshold` / 금붕어 빈 수면 6×4m 좌표)은 `docs/reports/bg_S2.md` §7에 정리했습니다. `static/world3d.js`는 개발 소유라 손대지 않았습니다.
- [배경→PM] 시나리오 중계 3건(빛기둥 구멍 / 사람이 서는 문간 / 금붕어 빈 수면)은 `spot_flooded_train.glb`에 **전부 반영**했습니다(보고서 §7-5).


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
