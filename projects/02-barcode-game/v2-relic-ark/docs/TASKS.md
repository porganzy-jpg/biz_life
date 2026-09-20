# TASKS — 스프린트 보드

## 스프린트 1 (2026-09-20) — 완료. 검수: `docs/reports/review_sprint1.md`

## 스프린트 2 (2026-09-20 착수) — "문턱 컷에서 첫 발견까지, 가로 연속 세계에서"
목표 한 문장: **가로 화면의 연속 지형 위에서 어두운 몰 안 → 밝은 바깥으로 주민을 보내 안개 속 힐링 스팟을 발견하는 12분이 실제로 돌아간다.**
근거: `docs/SCREEN_VISION.md`, `docs/WORLD_PRESENTATION.md`(첫 30분 순서 1~5), `docs/DECISIONS.md`(A+C+D 구조, 가로 오픈월드), 교본 `docs/curriculum/`.
모든 태스크 공통 완료 기준: 보고서에 교본 원칙 번호 인용 + 직군 §5 자가 검수 5문항 답 + **보여줄 스크린샷/클립 1개**(07 W6).

| # | 담당 | 태스크 | 산출물 | 완료 기준 | 의존 |
|---|---|---|---|---|---|
| S2-A | 개발(월드) | **연속 지형 본 화면 프로토타입** `static/world.html` + `static/world3d.js`(Three.js, 가로). ① 절차적 하이트맵 지형(약 400×250m, 풀/아스팔트/이끼/물 스플랫 — 배경 에이전트 텍스처가 오기 전엔 단색 가중치) ② 몰 블록: 기존 방 GLB(mall_camp·mall_food·mall_escalator·hall·pantry…)를 지형 위 "몰 내부"로 배치하고 안쪽은 어둡게(랜턴), 바깥은 밝게(태양) — 문턱 컷이 첫 카메라 ③ 안개(미탐험, 종이 질감 반투명 레이어) ④ 주민 3명(역할 GLB, 재정규화 금지, idle/walk/pickup)을 클릭한 지점으로 보내기(직선+장애물 회피 근사), 홀 허브 복귀 ⑤ 하루 사이클(새벽→낮→저녁→밤, 하늘색·태양각·랜턴) + 저녁에 "돌아와야 한다" 경고 ⑥ 힐링 스팟 1곳: 정찰병이 반경에 들어가면 안개가 걷히고 카메라가 내려앉으며 발견 텍스트(`data/spots.json` spot_flooded_train) 표시. 씬 GLB가 오기 전엔 hall.glb 청록 틴트로 대체 ⑦ 스캔 훅: 기존 `/api/scan` 응답 시 몰 입구로 카트가 들어오는 연출(원시 도형) ⑧ 줌·팬·기울기, 폰 가로(844×390)에서 조작 확인 | `static/world.html`, `static/world3d.js`, `docs/reports/dev_world_S2.md`, 스크린샷 3장(문턱 컷·바깥 이동·발견) | Playwright 1280×720 스크린샷에 안/밖 대비가 보이고, 주민이 클릭 지점으로 걸어가며, 스팟 발견 연출이 동작, 콘솔 에러 0, 60fps 근사(GTX 1050) | S1 GLB |
| S2-B | 개발(시스템) | **규칙 보강**: ① 각인 참여자 선별(counter_room 배치 주민 → 역할 태그 일치 → 무작위 1명, 1~2명만 crises 기록) ② `dialogue.json` `when` 훅 3곳(스캔 결과·사건 결과·야간 진입)에 리더/정원사 한 줄 표시 ③ 부족 첫 접촉 카드 1회 소모 플래그 ④ **소문 API** `/api/rumors`: 스캔 카테고리 누적에 따라 `data/spots.json` 단서를 해금(예: 음료·의약 스캔 → 물에 잠긴 전철 단서), 클라이언트 지도 표식용 좌표 필드 포함 ⑤ 기존 2D 화면(index.html) 회귀 유지 | `server.py`, `static/app.js`, `docs/reports/dev_sys_S2.md` | curl: 같은 사건 3회에 각인 1~2명만, `/api/rumors` 응답, 화면에 리더 대사 스크린샷, 회귀 7항목 | S1-B |
| S2-C | 시나리오 | ① 역할 진화 이름 8개(부족 신화 기반) `data/roles_evolved.json` ② 공룡 조우 카드 4장(`dino_*`, 낮 초식=기회·밤 육식=위협) + 원정·스팟 카드 3장(`flag`/`spot_clue`) `data/events_outside.json` ③ 소문 텍스트 20개 `data/rumors.json`(spot_id, 단서 문장, 누가 물어왔나: 개/고양이/까마귀/길손, 해금 조건 카테고리) ④ 각인 연출 문장 8개 `data/imprint_lines.json` ⑤ 두 AI 첫 대면 대본 `docs/SCRIPT_first_contact_ai.md` ⑥ 첫 30분 대본 다듬기(WORLD_PRESENTATION §2) `docs/SCRIPT_first_30min.md` | 위 파일 + `docs/reports/scenario_S2.md` | JSON 유효·스키마 준수, 금지어 0, S4/S5 말투 규칙, 개발이 바로 읽을 수 있는 필드명(개발 스키마 참조) | 없음 |
| S2-D | 배경 | **바깥의 첫 조각**: ① 지형 스플랫 텍스처 4장(풀·갈라진 아스팔트·이끼·물, 512px 타일링, 채도 규칙 B2) `static/textures/` ② **몰 정면 파사드 GLB**(깨진 유리 프레임·간판 잔해·무너진 캐노피·덩굴, 폭 30m, 문턱이 되는 입구) `static/models/scenes/mall_facade.glb` ③ **힐링 스팟 씬 GLB** 「물에 잠긴 전철」(물 평면·멈춘 객차·손잡이 꽃·빛기둥용 구멍, 거주 요소 없음) `static/models/scenes/spot_flooded_train.glb` ④ 공룡 실루엣 패럴랙스 평면 2장(PNG 알파) `static/art/parallax/` ⑤ 스카이라인 PNG(부족 방향 랜드마크 6개 실루엣: 굴뚝·하얀 건물·학교·온실·고층·터널 입구) | 위 파일 + 렌더 스크린샷 + `docs/reports/bg_S2.md` | GLB ≤1.5MB, 텍스처 타일링 이음새 없음, 스팟에 침낭·선반 등 거주 요소 0, pantry 회귀 diff 없음 | S1-C |
| S2-E | 캐릭터 | ① 짝 짐승 3종 GLB(개·고양이·까마귀; idle/walk, 개 idle은 사람 다리에 기대는 포즈) `static/models/animals/` ② 공룡 3종 GLB(Trex·Velociraptor·Triceratops; idle/walk, 무채+초록 톤, 실측 비율) `static/models/dinos/` ③ 각인 외형 파츠 8종을 8역할 GLB에 `imp_<id>` 노드(기본 hidden, 부위 겹침 없음)로 포함 ④ 비교 페이지에 짐승·공룡·각인 행 추가 | 위 파일 + `docs/reports/char_S2.md` | 발 원점·클립 포함, 파츠 노드명 규약 문서화, 8역할 GLB 재검증(키·클립), 비교 스크린샷 | S1-D |
| S2-F | 사운드(신규) | ① 앰비언트 3종(안·밖 낮·밖 밤) ② SFX 7종(랜턴·모닥불·물 튀김·스캔 성공·쪽지 도착·카드 놓기·개 경고) ③ 힐링 스팟 큐 1곡(30초 루프, 물에서 시작, 모달) ④ 큐시트 `docs/AUDIO_CUES.md`(상황→파일→dB→루프→페이드→트리거) ⑤ 문턱 크로스페이드 규격(1.5초) | `audio/`(원본·출처), `static/audio/*.ogg`, `docs/reports/sound_S2.md` | 총 ≤3MB, ogg 재생 확인, 안/밖이 눈 감고 구분됨(자가 검수 A1), 발견 직전 0.8초 무음 | 없음 |
| S2-PM | PM | 검수(재현 포함), 통합(S2-A 위에 D/E/F 에셋 배치 요청), 첫 12분 시퀀스 확인, DECISIONS·공개표 갱신, 스프린트 3 보드 | `docs/reports/review_sprint2.md` | 체크리스트 전 항목 + "더 재미있게 했는가" | S2 전부 |

## 요청함 (소유 영역 밖 수정 요청)
- (비어 있음)

## 스프린트 3 후보
- 개발: 노선 원정(C 심장) 노드 맵 + 6턴 3레인 대항(D 손) 통합, 자리 잡기 건설, 빛 게이지, world.html을 index로 승격.
- 배경: 부족 쉘터 외관 3종, 지하철 터널 씬, 스팟 2곳 추가.
- 캐릭터: 부족 7종 의상 파츠, 아이 성장 단계, 일하는 모션(카트 끌기).
- 시나리오: 부족 신화 낭독 전문, 엔딩 3갈래 개요, 카드 뒷면 주석 31종.
- 사운드: 부족 모티프 6종, 공룡 접근 경고, 리더/정원사 시그니처.
