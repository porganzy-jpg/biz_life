# 잔해 방주 — 다른 컴퓨터에서 이어서 작업하기 (2026-09-23 기준)

## 1. 지금 어디까지 왔나

| 단계 | 상태 |
|---|---|
| 스프린트 1 | 완료 — 아이소 거점 화면, 바코드→유물, 사건·각인, 방/캐릭터 GLB |
| 스프린트 2 | **6태스크 전원 통과** — 연속 지형 본 화면(`static/world.html`), 각인 참여자 선별, 소문 API, 몰 파사드·힐링 스팟 GLB, 짐승·공룡, 오디오 11종 |
| **1막 심해 전환**(2026-09-22) | 결정 완료. 3막 구조 = 심해 유리돔 → 침수 지하철 터널 → 지상. 육상 자산은 폐기 0, 3막으로 승격 |
| 스프린트 3 | 시나리오(심해 성경·사건 16장·첫 10분) 통과 / 개발(`/api/spots`·사건 54장·각인 12종) 통과 / 배경(유리돔 단면 렌더 3장·`dome_core.glb`) 검수 중 |

**읽는 순서**: `docs/CONCEPT_DEEP_SEA.md` → `docs/DECISIONS.md`(최신이 위) → `docs/TASKS.md` → `docs/reports/review_sprint3.md` → `docs/TEAM.md`.

## 2. 새 컴퓨터에서 준비할 것

```bash
git clone https://github.com/porganzy-jpg/biz_life.git
cd biz_life/projects/02-barcode-game/v2-relic-ark
pip install -r requirements.txt
python server.py            # http://localhost:8002
python server.py --https    # https://…:8444 (폰 카메라 스캔용, 자체 서명)
```

검수·디버그용으로 사건을 강제로 뽑으려면 `RELIC_DEV=1 python server.py` 로 띄운다(기본 모드에서는 404).

**필요한 외부 도구**
- **Blender 5.2** — 3D·렌더 파이프라인 전부가 이것으로 돈다. 스크립트가 쓰는 경로는 `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` 이고, 다른 경로에 깔면 `docs/TEAM.md` §5와 각 에이전트 정의의 경로를 같이 고쳐야 한다.
- **ffmpeg** — 오디오 합성·인코딩.
- node/npm은 **필요 없다**(웹은 순수 JS + CDN importmap).

## 3. 깃에 없는 것과 복구 방법 (중요)

| 빠진 것 | 왜 | 복구 |
|---|---|---|
| `assets3d/` | CC0 에셋 원본 팩(수백 MB) | `assets3d/README.md`에 출처 URL이 전부 있다. Kenney Survival Kit / Blocky Characters / Prototype, Quaternius Survival·Ultimate Animated Characters·Animated Dinosaurs를 같은 폴더명으로 내려받으면 `tools/blender_*.py`가 그대로 돈다 |
| `art_raw/` | 중간 렌더 원본 | 도구로 재생성. 보여줄 컷은 `docs/reports/*.png`에 복사해 두었다(심해 돔 3장 포함) |
| `certs/` | 자체 서명 키(비밀) | `python tools/make_cert.py` |
| `*.db` | 플레이 저장 상태 | 첫 실행 시 자동 생성. 구버전 DB는 서버가 마이그레이션한다 |

즉 **코드·데이터·문서·게임에 실제로 쓰이는 GLB와 오디오는 전부 깃에 있다.** 새 컴퓨터에서 없는 것은 원본 팩과 중간 산출물뿐이고 둘 다 복구 가능하다.

## 4. 바로 다음에 할 일 (스프린트 4 1순위)

1. **막 구분 `acts` 도입** — 1막이 심해인데 육상 공룡·부족 카드가 같은 풀에서 섞여 나온다. 개발이 스키마와 방주 `act` 상태를 먼저, 시나리오가 카드에 값을 기입. 1막 풀 최소 24장(결정 2026-09-23).
2. **각인 「두드림을 들은 자」 문구** — 자리는 코드에 있고 문구가 없다. 시나리오가 외형·대가 1행.
3. **`data/spots_deep.json`** — 심해 힐링 스팟 6곳. 본문은 `WORLD_BIBLE_DEEP.md`에 완성돼 있고 로더(`SPOT_FILES`)도 준비됐다.
4. **공기·깊이 게이지** — 첫 10분 대본의 핵심 장치. 숫자가 아니라 줄어드는 띠.
5. **심해 월드 화면** — 지금 `world.html`은 육상(3막)이다. 돔 단면을 실시간 화면으로 올리는 것이 스프린트 4의 본 과제. `dome_core.glb`와 `tools/blender_dome.py`가 준비돼 있다.

## 5. 에이전트로 이어서 일하기
`.claude/agents/relic-*.md` 6종(pm·scenario·dev·bg·char·sound)이 저장소에 들어 있어 새 컴퓨터에서도 그대로 쓸 수 있다. 각 에이전트는 `docs/curriculum/` 교본과 성경을 먼저 읽게 되어 있다. PM이 `docs/TASKS.md`에 보드를 쓰고, 담당들이 **파일 소유권으로 병렬 작업**하고, PM이 재현으로 검수하는 방식이 두 스프린트 연속으로 잘 작동했다.

## 6. 알려진 함정
- glTF에는 노드 가시성 필드가 없다 → 각인 파츠 `imp_*`는 클라이언트가 로드 직후 꺼야 한다.
- Blender에서 NLA 트랙을 푸시하면 GLB 기본 포즈가 망가진다 → `export_animation_mode='ACTIONS'`만 쓴다.
- Playwright는 `localhost` 연결을 거부한다 → `127.0.0.1` 사용.
- Pollinations 무료 이미지 API는 요청 제한이 심하다(429 시 5분 대기). 대량 생성은 Colab 노트북으로.
