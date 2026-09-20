# 잔해 방주 (RELIC ARK) — Phase 0 검증 프로토타입

> 기획서: `docs/02-BarcodeQuest_v2_잔해방주_게임기획서_20260919.md` · 웹 페이지: https://claude.ai/artifact/RAf3SGYtqQCP7JzudhVqYQ
> 기간: 4주 · 목표: **"스캔 → 카드 → 방 하나 짓기 → 사건 카드 1회 대항" 3분 루프가 재미있는가**를 검증

## 0. 확정 결정 (2026-09-19)

| # | 결정 | 이 프로토타입에서의 의미 |
|---|---|---|
| 1 | 부상·회복 기본, 하드코어 토글 | `ArkState.hardcore=False`. 주민은 `injured` 카운트만 증가 |
| 2 | 협동 방어 주축, PvP는 비동기 스냅샷만 | Phase 0에 PvP 없음. 사건은 모두 AI 위협 |
| 3 | 지명 없는 반도 잔해 | 텍스트에 실제 지명 금지. 880 접두어 = "반도 잔해" |
| 4 | 카드 종이수채 / 방주 도트 하이브리드 | 카드 뷰와 방주 뷰를 한 화면에 두고 공존 여부를 눈으로 검증 |
| 5 | 도서(ISBN) 포함 | 978/979 → `book` 카테고리, 최소 RARE, 서고 청사진 진행도 |

## 1. 검증 가설

| 가설 | 측정 | 성공 기준 |
|---|---|---|
| H1. 스캔이 "목적 있는 행동"이 된다 | 일 유효 스캔 수 / 유저 | ≥ 6회 (3일 평균) |
| H2. 사건 대항이 재미의 피크다 | 대항 시도율(사건 노출 대비) | ≥ 70% |
| H3. 카테고리를 옮겨 다닌다 | 유저당 스캔 카테고리 수 | 3일 안에 ≥ 4종 |
| H4. 두 아트 스타일이 공존한다 | 테스터 설문 "어색하다" 응답 | ≤ 3/10명 |
| H5. 하루 두 번 돌아온다 | 일 세션 수 | ≥ 2 |

측정은 서버 로그(scan, event_shown, counter_used, session_start)로만. 설문은 3일차에 10문항.

## 2. 범위

**포함**: 바코드 스캔(카메라), 유물 카드 생성·팩 개봉 연출, 인벤토리, 방 4종 건설, 하루 1회 사건 카드 + 대항 카드 드래그, 오프라인 생산, 도감(카테고리별), 로그 수집.
**제외**: 전투(6턴), 주민 특성, 연맹, 거래, 진화 생태계, 결제, 앱스토어 배포. 전부 Phase 1.

## 3. 기술 스택 (Phase 0 한정)

이 머신에 node/npm이 없어 v1과 같은 **Python FastAPI + 순수 브라우저 JS**로 만든다. Phaser 3 + TypeScript 전환은 Phase 1.

| 레이어 | 선택 | 메모 |
|---|---|---|
| 서버 | FastAPI (v1 `backend/` 패턴) | 엔드포인트 6개 (§6) |
| 스캔 | 브라우저 `BarcodeDetector` API, 미지원 시 `@zxing/browser` CDN 폴백 | 이미지 저장 없음, 숫자만 전송 |
| 클라이언트 | 단일 HTML + JS 모듈, PWA manifest | 카드 뷰 CSS(종이), 방주 뷰 Canvas(도트) |
| 저장 | SQLite | 유저·스캔 로그·방주 상태 |
| 배포 | 로컬 네트워크 or ngrok/Cloudflare Tunnel | 테스터 10명 휴대폰 접속 |

## 4. 화면 — 방주가 메인, 나머지는 그 위의 시트

> 2026-09-19 피드백 반영: "내가 생활하고 발전시켜가는 거점이 시각적으로 메인이어야 하고, 바코드는 그중 일부."

```
[홈 = 방주 단면도]  세로 스크롤 · 지상 스카이라인(그림) + 지하 흙 텍스처 위에 방 타일(그림)
                    B0 지상 2칸(재건) / B1~B4 지하 각 2칸(굴착) · 방마다 색 불빛·주민 초상·생산량
                    좌측 승강기 축 · 시간대(낮/저녁/밤) 톤 · 자리 비운 동안 생산 알림
[하단 도크 3버튼]   성문 해독(스캔) · 유물 카드 · 오늘의 쪽지(빨간 점)
[시트: 스캔]        카메라 + 숫자 입력 + 샘플 → 팩 개봉 오버레이 → 방주로 복귀
[시트: 건설]        빈 칸 탭 → 방 4종 썸네일·비용·설명 → 짓기 → 방주에 즉시 반영
[시트: 카드]        도감 진행도 + 손패(실제 아트)
[시트: 쪽지]        쪽지 슬라이드 인 · 카운트다운 · 대항 카드 탭 · 결과
```

아트 소스는 셋으로 나눈다(2026-09-19 테스트 결과):
- **시점 = 아이소메트릭(디아블로·폴아웃1식 사선 내려보기)**, 2026-09-19 사용자 결정. 홈은 지하 3×3 격자(중앙 = 역 홀 고정, 주변 8칸 = 슬롯 2~9) + 지상 2칸(슬롯 0,1). 타일은 `tools/blender_iso.py`가 투명 PNG로 렌더하고 `tile_meta.json`에 바닥 마름모 좌표를 기록해 클라이언트가 정확히 격자에 놓는다. 벽은 2.6m로 낮춰 뒤 칸이 가려지지 않게 한다. 후처리 `tools/post_iso.py` → `static/art/iso/`.
- **(이전) 측면 단면도 타일 = Blender 3D 디오라마 → 2.5D 프리렌더** (`tools/blender_rooms.py`, Fallout Shelter·This War of Mine 방식. 레퍼런스 정리: `docs/ART_REFERENCES.md`). 방 셸 + 방 주색 랜턴 + CC0 소품(Kenney Survival Kit, Quaternius Survival Pack → `assets3d/`) + 직교 카메라 + EEVEE + Freestyle 손그림 선. 6종 렌더 14초. 결과는 `static/art/rooms3d/<id>.jpg`, 클라이언트가 있으면 우선 사용하고 없으면 `static/rooms.js` 절차 픽셀 룸으로 대체. 무료 AI(Pollinations)는 방 단면을 흐릿한 인형집 사진으로 그려 부적합했다.
  ```bash
  "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --python tools/blender_rooms.py -- art_raw/rooms3d            # 6종 전체
  "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --python tools/blender_rooms.py -- art_raw/rooms3d pantry --level=2
  # 후처리(채도·종이·비네트) → static/art/rooms3d/  : README §5 아트 파이프라인의 post 단계
  ```
- **AI 생성 = 지상 스카이라인·주민 초상·유물 카드 아트** (`tools/gen_art.py`: 웹 AI → Pillow 후처리 → `static/art/`). 프롬프트는 주제 먼저, 스타일 뒤. 하단 8% 워터마크 크롭.
- **월드 = 줌/팬 캔버스** (2026-09-19 사용자 요청): 휠·핀치·더블탭 줌(0.45~2.6배), 드래그 팬, 우측 +/−/맞춤 버튼. 격자 아래에 Blender로 렌더한 **지반 판**(`ground_under`: 흙·뿌리·바위·물웅덩이·균류 발광 / `ground_surface`: 갈라진 아스팔트·잡초·어린 나무)을 깔아 검은 여백을 없앴다.
- **주민 = 역할 있는 캐릭터** (`data/roles.json`, `docs/CHARACTERS.md`): 8역할(정찰병·요리사·의무병·기술자·농부·학자·교섭가·아이) × 특성. 상시 효과·자동 대항·건설 할인·부상 회복·표류자 합류가 서버에 구현됨. 스프라이트는 `tools/blender_chars.py`(치비, 2방향×2프레임). 클라이언트에서 홀을 허브로 방 사이를 **실제로 걸어 다니고** 승강기로 지상에 오른다(`static/life.js`).
- **살아가는 모습 = CSS/JS 레이어** (`static/life.js`): 세계관 인트로, 일지 티커, 안개·비·까치, 랜턴 든 주민 왕래와 일 말풍선, 지상에 나타나는 오늘의 위협(누르면 쪽지).

## 4.5 실시간 2.5D (2026-09-20 채택) — `static/poc3d.html`
Three.js(jsdelivr importmap, node 불필요) + Blender GLB. 방 7종 `static/models/rooms/*.glb`(랜턴 포인트라이트 포함, `tools/blender_export_glb.py rooms`), 캐릭터 `static/models/chars/*.glb`(Quaternius, Idle/Walk/PickUp/SitDown… 클립, `… chars`). 직교 카메라 45°/45°, 우클릭으로 살짝 기울임, 휠 줌, 드래그 팬, 밤/낮, 랜턴 깜빡임, 주민이 방 사이를 걸어 다님. 증명 스크린샷: `docs/refs/poc3d_final.png`. 다음 스프린트에서 본 화면(`index.html`)으로 승격 예정. 프리렌더 아이소 타일은 폴백으로 유지.
주의: Blender GLB의 KHR 라이트는 W 단위로 커서 로더에서 45로 고정, 안개는 0.006 이하(0.03이면 전부 검게 보임), 스킨 메시 높이는 `Box3.setFromObject(root, true)`로 정규화.

## 4.6 팀 체계 — `docs/TEAM.md`, `docs/TASKS.md`, `docs/DECISIONS.md`
PM + 시나리오·개발·배경·캐릭터(+사운드 예정) 에이전트가 파일 소유권을 나눠 동시에 작업하고, PM이 체크리스트로 검수한다. 에이전트 정의: `../../.claude/agents/relic-*.md`.

## 5. 데이터 · 엔진 (이 폴더)

```
v2-relic-ark/
├── README.md                     ← 이 문서
├── server.py                     FastAPI 서버 (API 6개 + 정적 파일 + SQLite)
├── static/  index.html · app.js · style.css   4화면 클라이언트
├── tools/make_cert.py            휴대폰 카메라용 HTTPS 인증서
├── engine/
│   ├── relic_generator.py        바코드 → 유물 카드 (v1 특허 로직 승계, 결정적)
│   └── storyteller.py            방주 상태 → 사건 카드 선택 · 결과 적용
└── data/
    ├── relic_templates.json      카테고리 9종 × 이름/플레이버 템플릿 31개
    ├── known_families.json       제조 가문 18개 (크라우드소싱 시드)
    ├── rooms.json                방 4종 (식량창고·정수실·의무실·서고)
    └── events.json               사건 10종 (부정 8 · 긍정 2)
```

```bash
python server.py                 # 데스크톱: http://localhost:8002  (localhost는 카메라 허용)
python tools/make_cert.py        # 최초 1회: 자체 서명 인증서 → certs/
python server.py --https         # 휴대폰:   https://<이 PC의 IP>:8444  (경고 1회 통과 후 카메라 허용)

python engine/relic_generator.py 8801043015097 9791162241905   # 카드 JSON 출력
python engine/storyteller.py                                   # 7일 시뮬레이션
curl localhost:8002/api/stats                                  # H1~H5 원자료
```

브라우저 바코드 인식은 `BarcodeDetector` API를 쓴다(Android Chrome, 데스크톱 Chrome/Edge). iOS Safari는 미지원이므로 Phase 0에서는 숫자 입력 또는 샘플 버튼으로 테스트하고, Phase 1에서 ZXing 폴백을 넣는다. 화면의 샘플 바코드 6개는 체크섬만 유효한 테스트 코드다.

### 카테고리 판정 우선순위 (상품 DB 없이)
1. ISBN 접두어 978/979 → `book`
2. `known_families.json`의 접두어+제조사 코드 → 해당 카테고리
3. 유저가 스캔 직후 고른 카테고리 → 그 카테고리 (그리고 가문 테이블에 후보로 기록)
4. 없으면 `unknown` = "정체불명 유물" (커뮤니티 명명권의 씨앗)

### 스캔 경제
- 같은 바코드 n번째 스캔 배율 `[1.0, 0.5, 0.1, 0…]` (`rescan_multiplier`), 주 1회 리셋
- 일일 유효 스캔 상한 20회
- 카드 정체는 바코드만으로 결정, 시각은 `variant`(dawn/day/dusk/night) 표시에만 사용

## 6. API (FastAPI)

| Method | Path | 역할 |
|---|---|---|
| POST | `/api/scan` | `{barcode, user_category?}` → 카드 + 재스캔 배율 + 남은 상한 |
| GET | `/api/ark` | 방주 상태(자원·방·주민·부상) + 오프라인 생산 정산 |
| POST | `/api/ark/build` | `{room_id, slot}` → 자원 차감, 방 추가 |
| GET | `/api/event/today` | 오늘의 사건 카드 (없으면 생성, 스토리텔러) |
| POST | `/api/event/resolve` | `{event_id, counter_card_id?}` → 태그 매칭 판정, 결과 적용 |
| GET | `/api/codex` | 도감 (카테고리별 발견/미발견) |

대항 판정: 제출 카드의 `tags` ∩ 사건의 `counter_tags` ≠ ∅ 이면 성공. 사건에 `counter_room`이 있고 그 방이 있으면 카드 없이도 50% 자동 대항.

## 7. 4주 일정

| 주 | 산출 |
|---|---|
| 1 | FastAPI 서버 + `/api/scan` + 카메라 스캔 화면 + 팩 개봉 연출. **첫 주 끝에 내 휴대폰으로 집 물건 20개 스캔** |
| 2 | 방주 Canvas 뷰 + 건설 + 오프라인 생산. 카드 종이 CSS. 두 스타일 한 화면 검증 |
| 3 | 사건 카드 + 3초 대항 UX + 도감. 로그 수집. 아트: 카드 아트 30장 웹 생성 → Pillow 후처리 파이프라인 1차 |
| 4 | 테스터 10명 3일 플레이 → 지표 집계 → H1~H5 판정 → Phase 1 착수/피벗 결정 |

## 8. 설계 훅 (직접 손댈 곳)

`engine/storyteller.py`의 `weight_for(event, ark)`가 게임의 성격을 정한다. 현재 기본 규칙: 대항할 방이 없으면 그 사건 ×1.8, 결핍 자원을 치는 사건 ×1.4, 사기 ≤2면 긍정 사건 ×3, 최근 2일 반복 ×0.15, 하드코어면 심각 사건 ×1.5, 첫 3일 심각 사건 ×0.3. 7일 시뮬레이션(`python engine/storyteller.py`)으로 결과를 바로 볼 수 있다.

## 9. Phase 1로 넘기는 것
6턴 3레인 전투, 주민 특성·사연, 서버 메타 반응 진화, 연맹 협동 방어, 비동기 스냅샷 PvP, 교역, Phaser 3 + TS 전환, Capacitor 스토어 배포.
