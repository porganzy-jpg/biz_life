# 캐릭터 S19-C — 꾸밈 손님 여덟 (2026-10-05)

`data/draft/visitors.json` 의 손님 여덟을 P2 도트로 그렸다. 손으로 찍은 도트이고 생성 AI는 쓰지 않았다. 코드는 고치지 않았다(새 생성기 하나). 커밋하지 않았다.

**한 장**: `docs/reports/char_S19_visitors.png`. 방 ×3 화면에서 주민 둘 옆에 손님을 세웠고, 아래 띠에 프레임 전부를 ×3으로 실었다.

## 스타일 — 「괴기스럽다」 피드백을 규칙으로
- 따뜻하고 둥근 실루엣, 1px 점 눈 + 작은 웃음 + 홍조, 부드러운 색(산호·살구·크림·연보라·겨자).
- 차가운 발광과 큰 반사 눈은 쓰지 않았다. 빛이라고는 등불고기 턱 밑의 따뜻한 불씨뿐이다.
- 담요게는 늘 자는 손님이라 눈을 감은 둥근 한 획으로 그렸다.

## 손님과 클립
| id | 어디 | idle | 특기 |
|---|---|---|---|
| blanket_crab 담요게 | 방 안(거주실) | 2 — 담요 속 숨, 등딱지 실밥, z | `tuck_in` 4 — 담요를 끌어 덮고 다 덮이면 z |
| lantern_fish_pair 등불고기 한 쌍 | 창밖 | 4 — 같은 박자로 깜빡임 | `circle` 4 — 서로를 돈다 |
| hermit_trader 소라게 장수 | 방 안(흥정 자리) | 2 — 병뚜껑 집, 집게에 단추 | `show_stall` 4 — 작은 천을 깔고 물건 셋을 늘어놓으며 집게를 흔든다 |
| page_shrimp 책장새우 | 창밖 | 2 — 더듬이 | `march` 4 — 한 줄로 왼쪽에서 오른쪽으로 |
| steam_eel 꼬마 장어 | 창밖 | 2 — 꿈틀 | `nose_press` 3 — 코를 대고 동그란 김 자국을 남긴다 |
| baby_jelly_drift 아기 해파리 떼 | 창밖 | 3 — 둥둥 | `bump` 3 — 둘이 부딪쳐 잠깐 따뜻하게 밝아진다 |
| glass_star 유리닦이 불가사리 | 창밖 | 2 — 웃는 얼굴 | `wipe` 4 — 돌면서 이끼 낀 유리에 맑은 동그라미가 커진다 |
| screw_crab 나사집게 | 방 안(작업대 밑) | 2 — 큰 집게에 나사 | `carry` 4 — 옆걸음질 후 나사를 내려놓는다 |

## 파일
- `static/art/visitors/<id>.png`(x1, 0행 = idle, 1행 = 특기) · `<id>_x3.png`(방 화면 판)
- `static/art/visitors/visitors_meta.json` — 손님마다 id·ko·file·where·indoor·size·cols·clips(row/frames/fps)·anchor
  - 앵커: 방 안 = 발 가운데(방 바닥 floor_y 에 맞춘다), 창밖 = 몸 가운데
  - 배율: 원화 x1 은 P2 사람 셀과 같은 배율이라 방 ×3 이면 손님도 ×3
- 생성기: `tools/gen_chars_visitors.py`(새 파일, gen_chars_p2 원시함수만 쓴다)

## 남은 것
- 창밖 손님은 둥근 창을 임시로 그려 확인했다. 실제 방 유리 위치·크기는 배경·개발 몫이다.
- 소라게 장수의 늘어놓은 물건 셋은 ×3에서 작다(손톱만 하다). 더 크게 보여야 하면 키운다.

## S19-C2 추가 — 문어 · 작은 물고기 떼 · 정원사
id 는 **서버 kind 그대로** 뒀다. `core_a.json` visit_odds(`octopus`·`small_fish`·`gardener`)와 맞췄고, `base_core.js` 가 `ART.vis[v.kind]` 로 찾는다. PM이 적은 이름(`octopus_small`·`fish_school`)은 메타의 `aliases` 에 넣었다.

| id | 어디 | 줄(row) | 메모 |
|---|---|---|---|
| octopus 문어 | 방 안·선반 | `idle_hidden`·`idle_watching`·`idle_close`·`idle_bonded`(각 4, 2fps) + `gift` 4 | 기분 넷 = companion_octopus.json moods. 색은 숨음 선반색, 지켜봄 살구, 곁 산호(기본 `default_clip`), 감음 장밋빛. 지켜봄은 팔 하나만 내놓고, 감음은 팔 고리를 만든다. 선물은 팔에 감아 와 내려놓고 색이 한 단 붉어진다. **말·글자 없음** |
| small_fish 작은 물고기 떼 | 창밖 | `idle` 4(4fps) | 둥근 물고기 다섯이 고리를 그리며 돈다. 하나는 살구색이다 |
| gardener 정원사 | 창밖 | `idle` 4(1fps) | 성경: 정원사는 떼·해류로만 말하고 돔 밖에서만 온다. 그래서 **얼굴 없이** 은빛·바다빛 떼가 흐름 → 말림 → 방향 바꿈 → 펼침으로 천천히 돈다. 외곽선은 없고, 무섭지 않게 느리고 부드럽게 그렸다 |

- 접촉 시트 `char_S19_visitors.png` 를 갱신했다(11칸: 기존 8 + 셋).
- 문어 1차 확인에서 오른쪽 아래 그늘이 얼굴을 덮어 점 눈이 묻혔다. 그늘을 가장자리로 줄였다.
- 개발 참고: 메타가 생기면 `drawOutsideExtra` 의 도형 대체(`!ART.vis[v.kind]`)는 자동으로 꺼진다. 문어는 줄 이름이 `idle_<mood>` 라서, 서버 기분 단계를 읽어 고르면 된다(없으면 `default_clip`).
