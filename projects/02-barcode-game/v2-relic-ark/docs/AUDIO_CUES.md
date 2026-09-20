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
