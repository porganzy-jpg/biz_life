# 오디오 큐시트 (docs/AUDIO_CUES.md)

> 소유: relic-sound. 개발(server.py·static/*.js)이 트리거 이벤트를 실제로 발생시키는 지점은 개발 담당이 정한다.
> 여기 적은 이벤트 이름은 **제안**이다(교본 05_SOUND §4, TASKS.md S2-F). 볼륨 버스 3개(amb/sfx/music) 신설을 개발에 요청한다(하단 §4).

## 1. 상황 → 파일 → 재생 규칙

| 상황 | 파일 | 권장 dB(버스 기준) | 루프 | 페이드 | 트리거 조건(제안 이벤트명) |
|---|---|---|---|---|---|
| 문턱 넘기(안→밖, 밖→안) | `amb_inside.ogg` ↔ `amb_outside_day.ogg` | amb 버스 -12dB | 예(둘 다 배경 루프) | **크로스페이드 1.5초**(A1) | `world:threshold` (payload: `{to: "inside"\|"outside"}`) |
| 스캔 성공 | `sfx_scan_ok.ogg` | sfx 버스 -6dB | 아니오 | 없음(즉시 원샷) | `api:scan_ok` |
| 쪽지 도착 | `sfx_note_arrive.ogg` | sfx 버스 -8dB | 아니오 | 없음 | `api:event_new` |
| 카드 내기(대항 카드) | `sfx_card_place.ogg` | sfx 버스 -10dB | 아니오 | 없음 | `ui:card_place` |
| 랜턴 켜짐 | `sfx_lantern_on.ogg` | sfx 버스 -8dB | 아니오 | 없음 | `world:lantern_on` **(신규 제안, 기존 목록에 없어 추가함 — §3 참고)** |
| 밤 진입(낮→밤 앰비언트 전환) | `amb_outside_day.ogg` → `amb_outside_night.ogg` | amb 버스 -14dB | 예 | 크로스페이드 **3.0초**(문턱보다 느리게 — 노을처럼 서서히) | `world:night` |
| 힐링 스팟 발견 | `cue_spot_found.ogg` | music 버스 -6dB (평소 음악 버스는 0 볼륨, 이 순간만 페이드인 — A2) | 예(30초 반복) | 파일 자체에 **0.8초 무음 선행**(A10) + 재생 시작 시 amb 버스 -6dB로 덕킹, fade-in 0.3초 | `world:spot_found` |
| 개 경고(위협 접근) | `sfx_dog_warn.ogg` | sfx 버스 -4dB(경고는 크게, A5) | 아니오 | 없음. **위협 연출(랩터 실루엣·저역 임팩트)보다 최소 0.3~0.5초 먼저 트리거**(A5: 개가 먼저 짖는다=신뢰의 역전) | `ai:dog_warn` |

## 2. 안/밖 상시 배경 루프 (문턱·밤 전환 이벤트가 없을 때 기본값)

| 위치·시간대 | 파일 | 기본 볼륨 |
|---|---|---|
| 안(거점) | `amb_inside.ogg` | amb 버스 -12dB |
| 밖·낮 | `amb_outside_day.ogg` | amb 버스 -10dB |
| 밖·밤 | `amb_outside_night.ogg` | amb 버스 -13dB |

## 3. 개발에게 요청 (소유 영역 밖이라 직접 못 고침 — `docs/TASKS.md` 요청함에도 기재)

1. **볼륨 버스 3개 신설**: `amb`(앰비언트) / `sfx`(효과음) / `music`(힐링 스팟 큐 등 드문 음악). 설정 화면 슬라이더 3개 대응 가능하도록. 기본값 예: amb 70%, sfx 85%, music 90%.
2. **이벤트 이름 확정**: 위 표의 7개 트리거 중 `world:lantern_on`은 이번 스프린트에서 새로 제안한 이름이다(기존 6개는 태스크 지시에 있던 이름 그대로 사용: `world:threshold`, `api:scan_ok`, `api:event_new`, `ui:card_place`, `world:night`, `world:spot_found`, `ai:dog_warn`). 개발이 실제 코드 이벤트명과 맞춰 확정해 달라.
3. **문턱 크로스페이드 1.5초 / 밤 전환 3.0초**는 오디오 레이어(예: Web Audio GainNode 2개를 겹쳐 재생하며 gain을 반대로 램프)로 구현 필요. 두 앰비언트를 항상 같은 재생위치(phase)로 유지할 필요는 없음(둘 다 루프이므로 위상이 달라도 크로스페이드 자연스러움).
4. **cue_spot_found 재생 방식**: 발견 시 1회는 파일 그대로(0.8초 무음 포함) 재생하고, 플레이어가 스팟에 머무는 동안 반복하려면 무음 0.8초를 건너뛴 30초 지점부터 루프하는 것을 권장(오디오 스프라이트처럼 `loopStart=0.8s, loopEnd=30.8s` 처리하면 매 반복마다 무음이 끼지 않음). 다만 "발견마다 짧은 침묵 후 다시 시작"하는 느낌을 원한다면 파일 전체를 그냥 반복해도 무방(A10 침묵을 오히려 리듬으로 씀).

## 4. 파일 목록 (static/audio/)

`amb_inside.ogg`, `amb_outside_day.ogg`, `amb_outside_night.ogg`, `sfx_lantern_on.ogg`, `sfx_campfire.ogg`,
`sfx_water_splash.ogg`, `sfx_scan_ok.ogg`, `sfx_note_arrive.ogg`, `sfx_card_place.ogg`, `sfx_dog_warn.ogg`,
`cue_spot_found.ogg`. 검증 수치는 `docs/reports/sound_S2.md` 참고.

---

## 5. 심해 1막 (스프린트 4-D, 2026-09-26) — 이벤트명 확정판

> 근거: `docs/SCRIPT_first_10min_deep.md`(비트 2:30/3:00/3:40), `docs/WORLD_BIBLE_DEEP.md` §5-1
> ("문 안에서는 리더가 들리고, 문 밖에서는 정원사가 온다"). 이번 절의 이벤트명은 **제안이 아니라 확정**이다
> — 개발이 그대로 코드에 붙이면 된다. 검증·수치 근거는 `docs/reports/sound_S4.md`.

### 5-1. 상황 → 파일 → 재생 규칙

| 상황 | 파일 | 버스·dB | 루프 | 페이드 | 트리거 이벤트명(확정) |
|---|---|---|---|---|---|
| 돔 안 상시 배경 | `amb_dome_inside.ogg` | amb -12dB | 예 | — | (기본값, 이벤트 없이 상시 재생) |
| 바깥(박광/무광층) 상시 배경 | `amb_outside_deep.ogg` | amb -10dB | 예 | — | (기본값) |
| 해구 상시 배경 | `amb_trench.ogg` | amb -11dB | 예 | — | (기본값) |
| **에어락으로 나감(안→밖)** | `sfx_airlock_cycle.ogg` 1회 + 리더 버스 완전 차단 + amb 크로스페이드 | 아래 §5-2 참고 | — | 아래 §5-2 | `world:airlock_exit` |
| **에어락으로 들어옴(밖→안)** | `sfx_airlock_cycle.ogg` 1회 + 리더 버스 복귀 + amb 크로스페이드 | 아래 §5-2 참고 | — | 아래 §5-2 | `world:airlock_enter` |
| 무광층 → 해구 하강 | `amb_outside_deep.ogg` → `amb_trench.ogg` | amb 버스 | 예(둘 다) | 크로스페이드 **2.5초**(문턱 1.5초보다 느리게 — 경계가 아니라 서서히 짙어지는 하강이므로) | `world:depth_enter_trench` |
| 해구 → 무광층 상승 | `amb_trench.ogg` → `amb_outside_deep.ogg` | amb 버스 | 예(둘 다) | 크로스페이드 2.5초 | `world:depth_leave_trench` |
| 유리에 금이 감(사건 카드 진행 중) | `sfx_glass_crack.ogg` | sfx -6dB | 아니오 | 없음(즉시 원샷) | `world:glass_crack` (payload `{room_id}`) |
| 긴목이 창을 두드림(8:40 비트) | `sfx_knock_glass.ogg` | sfx -5dB | 아니오 | 없음. **실루엣 등장(창에 얼굴 붙임)과 동시 또는 최대 0.2초 뒤**(소리가 먼저 오고 실루엣이 온다는 A5 원칙은 대형 생물 기준 — 긴목은 이미 코앞이라 소리·실루엣 거의 동시) | `world:knock_glass` |
| 공기 게이지가 낮음 구간 진입(예: 20% 미만) | `sfx_air_low.ogg` | sfx -7dB, 이 순간 amb 버스를 -4dB 덕킹(숨소리를 더 잘 들리게) | 아니오(구간 진입 시 1회, 이후 게이지가 더 낮아지면 재생 간격을 좁혀 재트리거 가능) | 없음 | `world:air_low` |
| 해저에서 조각 줍기(첫 채집, 3:00 비트) | `sfx_collect.ogg` | sfx -8dB | 아니오 | 없음 | `world:collect_deep` (payload `{item_id}`) |
| 격벽이 닫히고 방이 잠김(8:00~8:40 비트) | `sfx_room_flood.ogg` | sfx -3dB(임팩트라 크게) | 아니오 | 없음. **재생 종료 직후 그 room_id의 로컬 앰비언트 emitter를 영구 mute**(아래 §5-3 참고) | `world:room_flood` (payload `{room_id}`) |
| 열수구 정원 발견 | `cue_vent_garden.ogg` | music -6dB(평소 0, 이 순간만 페이드인) | 예(30초 반복) | 파일 자체 **0.8초 무음 선행**(A10) + fade-in 0.3초 + amb 버스 -6dB 덕킹 | `world:spot_found` (payload `{spot_id: "spot_vent_garden", cue: "cue_vent_garden.ogg"}` — 기존 서프이스 스팟과 이벤트명을 통일하고 `cue` 필드로 파일만 바꿔 끼운다. 향후 스팟 5개도 같은 이벤트로 확장) |
| 「먼 울음」(해구, 정체 비공개) | `amb_far_call.ogg` | amb -9dB(가끔 들리되 묻히지 않게) | 아니오(원샷, 게임이 간격을 두고 반복 트리거) | 없음. **간격 커브는 PM이 확정**(`docs/reports/review_sprint4.md`): 기본 90초 → 방주 층수(깊이)가 늘 때마다 5초씩 감소 → 하한 40초. 내려갈수록 가까워진다는 뜻과 성장 방향(아래)이 맞물린다. 해구에 있을 때만 재생 후보 | `world:far_call` |

### 5-2. 에어락 크로스페이드 규격 — **이 스프린트의 핵심 연출**

> "끊긴다는 사실 자체가 대사다." 단순 볼륨 감소가 아니라 **저역통과 필터로 먹먹해지다 사라지는** 것이 핵심(리더가
> 갑자기 뚝 끊기면 버그처럼 들리고, 서서히 먹먹해지며 사라지면 "막힌 문 저편으로 멀어진다"는 물리적 사실이 된다).
> `sfx_airlock_cycle.ogg`(4.00초) 내부 타임라인: 0.0s 걸쇠 풀림 → 0.30~1.80s 바퀴 돌아감 → 1.00~3.00s 물 차오름
> → 3.00~4.00s 정착. 아래 수치는 이 타임라인에 맞춰져 있다.

**나갈 때(`world:airlock_exit`, 안→밖)**
1. t=0.00s: `sfx_airlock_cycle.ogg` 재생 시작.
2. t=0.00s~0.90s: **리더 버스**에 걸린 로우패스 필터 cutoff를 20000Hz → **400Hz**로 로그 스케일 스윕, 동시에 게인을 0dB → **-80dB**로 램프(사실상 무음). 0.90초에 완료.
3. t=0.30s~1.80s: **amb 버스** 크로스페이드 시작 — `amb_dome_inside.ogg` → `amb_outside_deep.ogg`, 지속 **1.5초**(기존 문턱 크로스페이드 규격과 통일, A1). 바퀴가 도는 동안 시작해 물이 차오르기 전에 절반쯤 진행되게 한다.
4. 결과: t≈0.9s에 리더는 완전히 사라지고(먹먹해지다 무음), amb는 t≈1.8s에 완전히 바깥 소리로 전환된다. **리더가 먼저 없어지고 그다음 세계가 바뀐다** — "끊긴다는 사실"이 전환 연출보다 먼저 온다.

**들어올 때(`world:airlock_enter`, 밖→안)**
1. t=0.00s: `sfx_airlock_cycle.ogg` 재생 시작(같은 파일 재사용).
2. t=0.00s~1.50s: **amb 버스** 크로스페이드 `amb_outside_deep.ogg` → `amb_dome_inside.ogg`, 1.5초.
3. t=1.50s~2.40s(물이 빠지고 방 소리가 들리기 시작한 뒤): **리더 버스** 로우패스 cutoff를 400Hz → 20000Hz로 스윕, 게인을 -80dB → 0dB로 램프. 0.90초 소요.
4. 결과: 물 빠지는 소리 → 방 안 소리(amb 전환, t≈1.5s) → **리더 목소리 복귀**(t≈1.5~2.4s) 순서가 그대로 재현된다(`SCRIPT_first_10min_deep.md` 3:40 비트의 "물 빠지는 소리 → 방 안 소리 → 리더 목소리 복귀"와 일치).

구현 메모(개발 요청, §5-4 참고): 리더 버스에 상시 걸린 `BiquadFilterNode`(lowpass) 하나 + `GainNode` 하나를 두고, 위 cutoff·게인 값을 `AudioParam.exponentialRampToValueAtTime`(게인은 0 근처로 못 가므로 -80dB≈0.0001 선형값을 사용하거나 `setTargetAtTime`)으로 스케줄하면 두 이벤트만으로 충분하다.

### 5-3. 방이 잠긴 뒤의 정적(§ `world:room_flood`)

`sfx_room_flood.ogg` 재생이 끝나면(약 2.2초 뒤) 그 `room_id`에 연결된 앰비언트 발생원(있다면 방별 로컬 emitter,
없다면 해당 방을 화면에 표시할 때 amb 레이어에 얹던 보정치)을 **영구 mute**로 표시한다. 이후 그 방을 다시 봐도
소리가 없는 상태가 유지되어야 한다(`WORLD_BIBLE_DEEP.md` §6: "닫힌 방은 그대로 남아 창 너머로 보인다" — 시각은
남고 청각만 사라진다). 이 mute는 세이브 데이터에 방 상태(`flooded: true`)로 저장되는 것이 자연스럽다(개발 결정).

### 5-4. 개발에게 요청 (소유 영역 밖 — `docs/TASKS.md` 요청함에도 등재)

1. 리더 버스에 로우패스 필터 + 게인 노드 상시 배치, §5-2의 cutoff·게인·타이밍 값 그대로 구현.
2. 이벤트 9개 연결: `world:airlock_exit`, `world:airlock_enter`, `world:depth_enter_trench`,
   `world:depth_leave_trench`, `world:glass_crack`, `world:knock_glass`, `world:air_low`,
   `world:collect_deep`, `world:room_flood`. 그리고 기존 `world:spot_found`에 `cue` 페이로드 필드 추가(§5-1 표).
3. `world:far_call`은 게임 쪽 타이머가 호출한다. 간격 커브는 **PM이 확정**(`docs/reports/review_sprint4.md`,
   2026-09-26): 기본 90초 → 방주 층수(깊이)가 늘 때마다 5초씩 감소 → 하한 40초.
4. `world:room_flood` 처리 후 room 상태에 `flooded: true` 저장(§5-3).

### 5-5. 파일 목록 (심해분, static/audio/)

`amb_dome_inside.ogg`, `amb_outside_deep.ogg`, `amb_trench.ogg`, `sfx_airlock_cycle.ogg`, `sfx_glass_crack.ogg`,
`sfx_knock_glass.ogg`, `sfx_air_low.ogg`, `sfx_collect.ogg`, `sfx_room_flood.ogg`, `cue_vent_garden.ogg`,
`amb_far_call.ogg`. 총 11개, 검증 수치는 `docs/reports/sound_S4.md` 참고(총 0.78MB, 예산 2MB).

---

## 6. 전투(배치 방어) — 스프린트 10-A, 2026-10-01

> 근거: `docs/COMBAT_AND_DEFENSE.md` §3(소리→실루엣→접촉), `data/creatures.json`(각 생물 `sound`/
> `silhouette`/`contact` 플레이버), `engine/combat.py` `CREATURES[*].audio`(실제 스키마), `docs/TASKS.md`
> 요청함의 두 건(시나리오 S9-B 예고음 다섯 · 개발 S8-B 큐 넷). 검증·수치 근거는 `docs/reports/sound_S10.md`.
> **「그늘」·「먼 울음」은 건드리지 않는다**(각각 무음 설계·봉인 소재). **문지기·손톱 무리·덮개의 '소리' 단계도
> 자산이 없다** — 이 셋은 "다른 소리가 없어지는 것"이 신호라서, 새 파일이 아니라 **덕킹 스펙**으로만 존재한다.

### 6-1. `engine/combat.py` `CREATURES[*]["audio"]` 제안값 (개발이 그대로 덮어쓰면 끝)

현재 코드값(placeholder)은 생물끼리 소리를 돌려 쓰고 있다 — 특히 **문지기의 `sound`가 `amb_far_call.ogg`를
재사용 중인데, 이는 「먼 울음」(해구의 봉인 소재)과 「문지기」(막을 수 있는 위협)를 같은 소리로 섞어
혼동을 만든다.** 아래 표가 그 치환값이다.

| 생물 | 현재 `audio`(placeholder) | 제안 `audio` | 비고 |
|---|---|---|---|
| swarm(작은 떼) | `sound: sfx_water_splash.ogg` | `sound: sfx_warn_swarm.ogg` | `contact: sfx_glass_crack.ogg` 유지 |
| longneck(긴목) | `sound: sfx_knock_glass.ogg`(접촉용 재사용) | `sound: sfx_warn_longneck.ogg` | `contact: sfx_knock_glass.ogg`로 교체(그 파일은 원래 '코앞까지 온' 접촉음, 소리 단계엔 멀고 먹먹한 새 파일이 맞다). `contact: sfx_glass_crack.ogg`는 유리에 금이 가는 결과음이라 §6-3으로 분리 |
| warden(문지기) | `sound: amb_far_call.ogg` ⚠ | `sound: null`(§6-2 덕킹만) · `silhouette: sfx_warden_press.ogg` | **먼 울음과의 혼동 해소가 이번 스프린트의 목적 중 하나** |
| claws(손톱 무리) | `sound: amb_outside_deep.ogg` | `sound: null`(§6-2 덕킹만) · `silhouette: sfx_warn_claws.ogg` | 소리 단계는 '없음'이 신호(creatures.json), 실루엣 단계에서 처음 긁는 소리가 들린다 |
| octopus(동거 문어) | `sound: sfx_water_splash.ogg` | `sound: sfx_octopus_enter.ogg` | `contact: sfx_collect.ogg` 유지(무언가를 물고 들어오는 결과와 맞음) |
| mirror_eye(거울눈) | 없음(엔진 미배선) | `sound: sfx_warn_mirroreye.ogg` | 관문·need 확정되면 `CREATURES`에 항목 추가 시 같이 붙임 |
| straight_one(곧은치) | 없음 | `sound: sfx_warn_straight.ogg` | 파일 자체에 긴장음 + 2초 정적이 들어 있다. 추가 타이머 불필요 |
| lid(덮개) | 없음 | `sound: null`(§6-2 덕킹만) | '소리가 아니라 무게'(creatures.json) — 자산 없음이 설계 |
| needle(바늘) | 없음 | `sound: sfx_warn_needle.ogg` | 16초, 명단에서 가장 긴 큐(시나리오 S9-B 요청 그대로) |
| big_maw(큰 입) | 없음 | `sound: sfx_warn_bigmaw.ogg` | 7.6초, 느린 스웰 2회 |
| follower(따라온 것) | 없음 | `sound: sfx_warn_follower.ogg` | 5.6초, 부름(0.1s)과 답(2.6s) 사이 정적 포함 |
| upper_child(윗물 아이) | 없음 | `sound: sfx_warn_upperchild.ogg` | 긴목과 같은 음색 계열, 더 빠르고 겁먹은 떨림 |
| shade(그늘) | — | **자산 없음.** §6-2 | 위협 아님. 이미 creatures.json 자체가 "없음"으로 설계 |
| far_cry(먼 울음) | `amb_far_call.ogg` | **변경 없음** | 건드리지 않음(DECISIONS 2026-09-22 봉인) |

### 6-2. 무음·덕킹 스펙 (자산이 없는 것이 설계인 생물들)

| 생물 | 구간 | 덕킹 스펙 |
|---|---|---|
| warden(문지기) | 소리 단계 전체 | 그 구역 amb 버스를 **2.5초에 걸쳐 -24dB까지** 램프(선형이 아니라 `setTargetAtTime` 류로 서서히). 다른 생물 트리거음(swarm/claws 등)도 이 구간엔 섞이지 않게 억제 — "다른 소리가 전부 사라진다"가 글자 그대로 되어야 한다 |
| claws(손톱 무리) | 소리 단계 2초 | 바닥/해저 쪽 로컬 앰비언트(있다면)를 **2초에 걸쳐 -18dB**. 완전 무음이 아니라 "빠져나가는" 쪽(creatures.json: "바닥 잡음이 천천히 빠져나간다") — 다 죽이면 '실수로 음소거된 버그'처럼 들린다 |
| lid(덮개) | 소리+실루엣 단계 내내 | 그 방 **천장 쪽 로컬 앰비언트만** -20dB(방 전체 앰비언트는 유지 — "그 방 천장 쪽 물소리가 먼저 멎는다"는 국소적 현상이다) |
| shade(그늘) | 통과하는 동안 | 돔 전체 amb 버스를 **3~4초에 걸쳐 -10dB**, 지나가면 같은 시간으로 복귀. 기존 다른 위협 생성 억제(이미 engine 쪽 "조용한 날" 설계와 자연히 맞음) |

### 6-3. 결과음 셋 (접촉 이후)

| 결과 | 파일 | 비고 |
|---|---|---|
| `held`(막았다) | **`sfx_defend_held.ogg`**(신규) | 승리 팡파르 아님. 물러가는 소리 + 안도의 숨(완전5도 공명 두 음) |
| `scarred`(유리에 금이 갔다) | `sfx_glass_crack.ogg`(기존 재사용) | 이미 "손톱 긁기→균열"로 설계되어 있어 그대로 맞는다. 신규 자산 불필요 |
| `breached`(방을 잃었다) | `sfx_room_flood.ogg`(기존 재사용) + **영구 로컬 mute** | §5-3에 이미 명시된 "그 방 로컬 앰비언트 영구 mute"를 **이 라이드 시스템의 `breached` 결과에도 그대로 적용**. 상실을 소리의 부재로 표현하는 장치가 이미 있었다 — 새로 만들 것은 raid 시스템과의 연결뿐 |

### 6-4. 접촉 직전 무음(A10) — 라이드 전용 적용

습격의 `stage`가 `silhouette → contact`로 넘어가 `resolve_raid`가 돌기 **0.8초 전부터** amb+sfx 버스를
`-20dB`까지 덕킹했다가, 접촉음(위 생물별 `contact` 파일 또는 §6-3 결과음)과 동시에 복귀시킨다. 기존
`cue_spot_found`·`cue_vent_garden`의 0.8초 선행 무음(A10)과 같은 원칙을 "발견"이 아니라 "접촉"에 쓰는
것 — 놀래키지 않는다는 COMBAT_AND_DEFENSE §6의 요구와, 침묵이 곧 긴장이라는 A10을 결합한다.

### 6-5. 조작음 (아주 작고 짧게)

| 조작 | 파일 | 트리거(추정 — 개발이 실제 핸들러에 맞춰 확정) |
|---|---|---|
| 사람 집어 들기 | **`sfx_pickup_person.ogg`**(신규) | 드래그 시작/탭-집기(`base.js` pointerdown→carry 진입) |
| 사람 내려놓기 | **`sfx_place_person.ogg`**(신규) | `POST /api/ark/station` 성공 |
| 조명 끄기 | **`sfx_light_off.ogg`**(신규) | `POST /api/ark/light` (on:false) |
| 조명 켜기 | **`sfx_light_on.ogg`**(신규) | `POST /api/ark/light` (on:true) — 기존 `sfx_lantern_on.ogg`(장식 랜턴 점화)와는 다른 맥락(방 전기 스위치)이라 분리했다 |
| 전원 내리기 | **`sfx_power_down.ogg`**(신규) | `POST /api/ark/power` (on:false) |
| 도구 설치 | **`sfx_tool_install.ogg`**(신규) | `POST /api/ark/install` 성공 |

전원 **올리기**는 이번 스프린트 범위에 없다(지시 원문이 "전원 내리기"만 요청). 필요하면 `sfx_power_down`의
역재생이나 짧은 변형으로 다음 스프린트에 추가 가능 — 지금은 최소 범위를 지켰다.

### 6-6. 측정 방법 교정 — 500Hz 하이패스 (PM 지적 반영)

지난 스프린트(S4)의 교훈 재적용: 광대역 RMS·중심주파수는 저역 에너지가 90% 이상을 차지하는 신호에서
"디테일"(리듬·질감 차이)을 가린다. 이번 검증(`tools/gen_audio_combat_verify.py`)은 **500Hz 하이패스
후** 중심주파수·리듬(온셋 간격)을 다시 쟀다. 수치와 판정 전부는 `docs/reports/sound_S10.md` §3 참고.

### 6-7. 파일 목록 (전투분, static/audio/, 신규 18개)

`sfx_warn_longneck.ogg`, `sfx_warden_press.ogg`, `sfx_warn_swarm.ogg`, `sfx_warn_claws.ogg`,
`sfx_warn_mirroreye.ogg`, `sfx_warn_straight.ogg`, `sfx_warn_needle.ogg`, `sfx_warn_bigmaw.ogg`,
`sfx_warn_follower.ogg`, `sfx_warn_upperchild.ogg`, `sfx_octopus_enter.ogg`, `sfx_defend_held.ogg`,
`sfx_pickup_person.ogg`, `sfx_place_person.ogg`, `sfx_light_off.ogg`, `sfx_light_on.ogg`,
`sfx_power_down.ogg`, `sfx_tool_install.ogg`. 신규 합계 0.137MB(예산 1MB), `static/audio` 전체 2.059MB
(Phase 0 예산 3MB). 검증 수치는 `docs/reports/sound_S10.md` 참고.
