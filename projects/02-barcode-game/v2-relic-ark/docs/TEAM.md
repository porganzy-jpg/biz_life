# 잔해 방주 — 에이전트 팀 체계 (2026-09-20)

## 0. 한 목적
> "각박한 어둠 속 거점을 키우고, 사람 대신 짐승을 믿으며, 인간이 들어갈 수 없는 아름다운 바깥을 발견하는 게임. 바코드 스캔은 그 세계의 유물을 읽는 행위다."
> 모든 에이전트는 이 문장과 `docs/` 성경에 복종한다. 성경과 충돌하는 산출물은 검수에서 반려된다.

## 1. 성경 (Single Source of Truth) — 읽는 순서
1. `docs/LORE_v2_원죄와_회복.md` — 세계관 전제
2. `docs/WORLD_BIBLE_v2.md` — 일곱 부족, 두 AI, 지도, 철학(적응은 분열, 구원은 재결합)
3. `docs/TRUST_AND_COMPANIONS.md` — 신뢰의 역전(사람 0, 짐승 높음)
4. `docs/GROWTH_AND_MYTH.md` — 계단식 성장(각인), 신화 층 원칙
5. `docs/MYTH_ORIGINS.md` — 신화 기원 사례집
6. `docs/CONCEPT_MALL_DINO.md`, `docs/CONCEPT_HEALING_SPOTS.md` — 무대(쇼핑몰·공룡), 힐링 스팟
7. `docs/CHARACTERS.md`, `data/roles.json` — 역할 8종
8. `docs/ART_REFERENCES.md`, `docs/refs/` — 아트 원칙(초록·아늑·45°·밀도), 레퍼런스
9. `README.md` — 현재 구현 상태와 파이프라인
10. `../../docs/02-BarcodeQuest_v2_잔해방주_게임기획서_20260919.md` — 상위 기획서(벤치마크·시스템)

## 2. 에이전트와 소유 영역 (충돌 방지의 핵심: 남의 폴더는 읽기만)
| 에이전트 | 역할 | 소유(쓰기 가능) | 산출물 형식 |
|---|---|---|---|
| **PM** | 목적 정렬, 작업 순서, 의존성 관리, **검수**, 통합 | `docs/TASKS.md`, `docs/DECISIONS.md`, `docs/reports/` | 스프린트 보드, 검수 보고서, 결정 로그 |
| **시나리오·세계관** | 부족·AI·사건·대사·플레이버 텍스트 | `docs/*.md`(성경 확장), `data/events*.json`, `data/dialogue*.json`, `data/relic_templates.json`, `data/spots.json` | JSON 데이터 + 문서. 코드 금지 |
| **개발** | 서버·클라이언트·시스템 구현, 테스트 | `server.py`, `engine/`, `static/*.js`, `static/*.css`, `static/index.html`, `static/poc3d.html`, `data/*_schema.json` | 동작하는 코드 + curl/브라우저 검증 로그 |
| **배경·그래픽 에셋** | 방·지반·지상·힐링 스팟 씬, 타일, GLB | `tools/blender_iso.py`, `tools/blender_rooms.py`, `tools/blender_export_glb.py`(rooms), `tools/gen_art.py`, `art_raw/iso`, `art_raw/world`, `static/art/iso`, `static/models/rooms` | GLB + PNG + 렌더 스크린샷 |
| **캐릭터 디자인·그래픽** | 주민·부족 의상·짐승·공룡 모델, 애니메이션, 스프라이트 | `tools/blender_chars*.py`, `tools/blender_charshow.py`, `tools/blender_export_glb.py`(chars), `art_raw/chars*`, `static/art/chars`, `static/models/chars`, `static/charshow.html` | GLB(애니 포함) + 스프라이트 + 비교 페이지 |
| **사운드** (추가 예정) | 앰비언트·SFX·힐링 스팟 음악, 방주/바깥 대비 | `audio/`, `tools/gen_audio*.py`, `static/audio` | OGG/MP3 + 큐시트 |

규칙
- 남의 소유 파일을 고쳐야 하면 **직접 고치지 말고** `docs/TASKS.md`에 요청을 남긴다. PM이 배정한다.
- 데이터 스키마(필드명)는 개발이 `data/*_schema.json`로 정하고, 시나리오는 그 스키마에 맞춰 내용을 채운다.
- 새 결정(예: "치비 계열 F 채택")은 `docs/DECISIONS.md`에 날짜·이유와 함께 한 줄로 남긴다. 성경과 결정 로그가 충돌하면 결정 로그가 최신이다.

## 3. 작업 흐름 (스프린트 = 반나절~하루)
1. **PM**이 `docs/TASKS.md`에 스프린트 목표와 태스크를 쓴다. 태스크마다 담당·산출물 경로·**완료 기준(acceptance)**·의존성.
2. 전문 에이전트들이 **동시에** 작업한다. 각자 끝나면 `docs/reports/<agent>_<날짜>.md`에 보고: 무엇을 만들었나, 어디에 있나, 검증 방법, 미완·리스크, 남에게 요청할 것.
3. **PM 검수**(아래 체크리스트). 통과 → 통합·결정 로그 갱신. 반려 → 사유와 수정 요구를 보고서에 답글로.
4. 스프린트 회고 3줄: 잘된 것, 막힌 것, 다음 순서.

## 4. PM 검수 체크리스트 (구체적으로)
공통
- [ ] 성경과 충돌 없음(부족 특성·두 AI·신뢰 역전·계단식 성장·아트 원칙). 충돌 시 어느 문장과 충돌하는지 지목.
- [ ] 소유 영역 밖 파일을 수정하지 않았음.
- [ ] 산출물 경로가 보고서에 정확히 적혀 있고 실제로 존재함.
- [ ] 완료 기준을 하나씩 대조.
시나리오
- [ ] 실제 종교·경전·인물·지명 이름이 없음(우회 원칙).
- [ ] 사건 카드 JSON이 스키마 검증 통과(`python -c "import json;json.load(...)"` + 필수 필드).
- [ ] 각 부족의 말투·가치관이 성경 표와 일치. 사람 간 신뢰 0·짐승 신뢰 높음의 규칙이 대사에 반영.
개발
- [ ] 서버 구문 검사·기동·curl 시나리오 통과 로그 첨부.
- [ ] 브라우저에서 화면 확인(Playwright 스크린샷 첨부). 콘솔 에러 0.
- [ ] 기존 기능 회귀 없음(스캔·건설·사건·주민).
배경
- [ ] 아트 원칙: 초록·아늑·소품 밀도·랜턴 1 = 주색 1. 카메라 45°/45°.
- [ ] 격자 좌표 메타(`tile_meta.json`) 갱신, GLB는 6m 격자 원점 기준.
- [ ] 렌더 스크린샷 첨부, 파일 크기 1MB 이하/타일.
캐릭터
- [ ] 8역할 실루엣이 3초 안에 구분됨(비교 페이지 스크린샷).
- [ ] GLB에 Idle/Walk/PickUp 클립 포함, 발 위치 원점, 높이 정규화.
- [ ] 창백한 피부·큰 눈·부족 표식 등 성경의 적응 묘사 반영.
사운드(예정)
- [ ] 안(어둡고 따뜻)과 밖(밝고 차가움)의 음향 대비. 힐링 스팟 진입 시 전환.

## 5. 지금 사용하는 도구 제약 (모든 에이전트 숙지)
- 로컬 GPU(GTX 1050 2GB)로 이미지 생성 불가. 3D 렌더는 Blender 5.2(`C:\Program Files\Blender Foundation\Blender 5.2\blender.exe -b --python …`).
- node/npm 없음. 웹은 순수 JS + CDN(Three.js는 jsdelivr importmap).
- Pollinations 무료 API는 요청 제한이 심함(429). 429 시 최소 5분 대기, 요청 간 15초. 대량 생성은 Colab 노트북(`tools/colab_world_images.ipynb`)으로.
- 서버: `python server.py`(8002) / `--https`(8444). 정적 파일 캐시 없음.
- 브라우저 확인: Playwright MCP 또는 헤드리스 Edge. WebGL은 Playwright(실 GPU)로만 확인.
