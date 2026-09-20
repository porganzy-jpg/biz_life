# TASKS — 스프린트 보드

## 스프린트 1 (2026-09-20) — 완료. 검수: `docs/reports/review_sprint1.md`
S1-A 시나리오 통과 · S1-B 개발 통과(조건부) · S1-C 배경 통과 · S1-D 캐릭터 통과.
스프린트 1 요청함 접수분(부족 표기·스키마·사건 병합·mall 등록·GLB 역할 로드·높이 재정규화 제거·각인 파츠)은 모두 아래 S2에 반영했다.

## 스프린트 2 (착수 대기) — "실시간 2.5D 본 화면 + 살아 있는 세계"
목표: poc3d를 본 게임 화면으로 승격해 스프린트 1의 GLB(방 10종·캐릭터 8종)가 실제 게임에서 보이게 한다. 각인의 개별 서사를 살리고, 바깥(공룡·힐링 스팟)의 첫 조각을 넣는다. 사운드 에이전트 가동.

| # | 담당 | 태스크 | 산출물 | 완료 기준 | 의존 |
|---|---|---|---|---|---|
| S2-A | 개발 | **poc3d → 본 화면 승격**: `index.html`의 월드를 Three.js 씬으로 교체(격자 3×3+지상 3칸, 방 GLB 배치, 빈 칸=rock/lot, 클릭→건설 시트, 줌·팬·기울기, 밤/낮, 랜턴). 주민을 역할별 GLB(`static/models/chars/<role>.glb`)로 로드, **높이 재정규화 제거**(GLB가 발 z=0·맨머리 1.6m로 이미 정규화), 홀 허브 이동 + idle/walk/pickup 클립(소문자). 매장층 mall_* 등록(자체 랜턴 있음 → 보조 라이트 제외). 2D 아이소 타일은 WebGL 불가 시 폴백 | `static/index.html`, `static/world3d.js`(신규 권장), `static/app.js`, `docs/reports/dev_S2.md` | Playwright 스크린샷: 방 5종 이상 + 주민 3명 GLB가 보임, 건설·스캔·사건·홀 명단 기존 기능 동작, 콘솔 에러 0, 폰 폭(480) 확인 | S1 전부 |
| S2-B | 개발 | **각인 참여자 선별**: 사건마다 관여 주민 1~2명(counter_room 배치 주민 우선 → 역할 태그 일치 → 무작위 1명). 선정된 주민만 crises 기록·각인. `dialogue.json` `when` 훅 3곳(스캔 결과·사건 결과·야간 진입)에 리더/정원사 한 줄. 첫 접촉 카드(tribe_*) 1회 소모 플래그 | `server.py`, `static/app.js`, `docs/reports/dev_S2.md` | curl: 같은 사건 3회에 각인이 1~2명에게만. 리더 대사 표시 스크린샷 | S1-B |
| S2-C | 시나리오 | 역할 진화 이름 8개(부족 신화 기반, 개발 임시값 교체), 공룡 조우 카드 4장(`dino_*`, 낮 초식=기회·밤 육식=위협), 원정·힐링 스팟 카드 3장(`flag: expedition_returned` / `spot_clue: <spots.json id>`), 두 AI 첫 대면 대본 초안(정원사 = 비단잉어가 글자를 이루는 장면), 각인 연출 문장 8개 톤 다듬기 | `data/roles_evolved.json`, `data/events_outside.json`, `data/imprint_lines.json`, `docs/SCRIPT_first_contact_ai.md`, `docs/reports/scenario_S2.md` | JSON 유효·`data/events_schema.json` 준수, 금지어 0, 리더/정원사 말투 규칙 | 없음 |
| S2-D | 배경 | **바깥의 첫 조각**: 지상 지반 실시간 GLB(`ground_surface.glb`, 24m), 채광창 너머 **공룡 실루엣 패럴랙스 레이어**(반투명 평면 2장), 힐링 스팟 「물에 잠긴 전철」 실시간 씬(물 평면·잉어 마커·꽃) GLB. `mall_food` 우측 시선 유도 보정, 텐트 모델 변주 | `tools/blender_iso.py`, `tools/blender_export_glb.py`(rooms), `static/models/rooms/ground_surface.glb`, `static/models/scenes/spot_flooded_train.glb`, `docs/reports/bg_S2.md` | GLB ≤1.5MB, 렌더 스크린샷, pantry 회귀 diff 없음 | S1-C |
| S2-E | 캐릭터 | **짝 짐승 + 공룡 + 각인 파츠**: 개·고양이·까마귀 GLB(idle/walk; Quaternius 동물 팩 확보 가능하면 사용, 아니면 원시 도형), 공룡 3종(Trex/Velociraptor/Triceratops, walk/idle, 색 재질, 실측 비율), 각인 외형 파츠 8종을 역할 GLB에 `imp_<id>` 노드로 포함(기본 hidden, 부위 겹침 없이 목/허리/얼굴/팔/손목/머리) | `tools/blender_animals.py`, `tools/blender_chars_v2.py`, `static/models/animals/*.glb`, `static/models/dinos/*.glb`, `static/models/chars/*.glb` 갱신, `docs/reports/char_S2.md` | GLB 존재·클립·발 원점, 파츠 노드명 규약 문서화, 8역할 GLB 재검증(높이·클립) | S1-D |
| S2-F | 사운드(신규) | 앰비언트 2종(안: 물방울·랜턴 지글·먼 터빈 / 밖: 바람·새·잎), SFX 5종(랜턴 켜짐·모닥불·물 튀김·스캔 성공·쪽지 도착), 힐링 스팟 진입 큐 1곡(30초 루프). CC0 소스 또는 로컬 합성(python numpy/ffmpeg). 큐시트: 상황→파일→볼륨→루프 | `audio/` 원본, `static/audio/*.ogg`, `docs/AUDIO_CUES.md`, `docs/reports/sound_S2.md` | 파일 존재·재생 가능·총 ≤3MB, 큐시트 완비, 안/밖 대비가 들림 | 없음 |
| S2-PM | PM | 검수, 통합 확인(S2-A 위에 S2-D/E 에셋 배치), DECISIONS 갱신, 스프린트 3 보드 | `docs/reports/review_sprint2.md` | 체크리스트 전 항목 | S2 전부 |

## 요청함 (소유 영역 밖 수정 요청)
- (비어 있음 — 스프린트 1 접수분은 S2 태스크에 반영)

## 스프린트 3 후보
- 개발: 지하철 노선도 화면 + 구간 이동 사건 시퀀스(길손 고용), 빛 게이지, 전기 빚.
- 배경: 다른 부족 쉘터 외관 3종(발전소·병원·도서관), 노선도 아트.
- 캐릭터: 부족별 의상 파츠(7부족), 아이 성장 단계.
- 시나리오: 부족 신화 낭독 이벤트 전문, 엔딩 3갈래 개요.
- 사운드: 부족별 테마 모티프, 공룡 접근 경고음.
