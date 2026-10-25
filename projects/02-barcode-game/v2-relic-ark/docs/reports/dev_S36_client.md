# 개발 S36 화면 — 건넨 물건이 방에서 쓰인다 (2026-10-25, 커밋하지 않음)

서버 API_S19 §25, 배경 decor_meta.json `use_spots`(docs/reports/bg_S36.md), C_PLAN §5 대로 했다. 확인은 8041 에서만 했다(8002 는 건드리지 않음, 확인 뒤 8041 껐음).

## 만든 것 (base_core.js · base.js)
- **쓰는 자리 둘**:
  - `core.rooms[slot].use_spots[spot 0·1]` 의 물건(item.prop, 없으면 by_subtype)을 그 방 플레이트의 `decor_meta.use_spots.by_plate[...][spot].item` 좌표(칸 564×317, 소품 아래 가운데, 1배)에 그린다. 플레이트는 use_spots.room_to_plate 를 따른다.
  - 서버 공지는 「keepsake_spots 앞 두 자리」였다. 배경 담당이 겹침 0 으로 따로 잡은 use_spots 를 썼다. 머리맡·자리 소품(keepsake_spots)은 그대로다.
  - 오늘 쓴 물건(today_used)은 모서리에 작은 반짝이 하나 붙는다.
  - 물건은 사람보다 먼저 그린다(사람 뒤). 쓰는 사람이 앞에 선다. 배경 담당이 물은 「사람 앞/뒤」를 이렇게 정했다.
- **쓰는 모습**(`/api/ark.use_news[]`, 사람마다 하루 한 번):
  - 관리실 한 줄 「○○ 님이 「물건」, 한 모금 드시고 숨을 고르셨습니다.」를 방송한다.
  - 그 사람이 4.5초 동안 동작에 맞는 자세를 한다. eat·drink → 앉음(sit), read → 쉼(rest_lounge), write·tinker·wrap·bandage → 그 방 일 자세, look → 고개 돌림.
  - 지금 시트에 먹기·마시기 전용 행이 없어 가까운 행을 썼다. 전용 동작 8가지는 캐릭터 담당 몫이다.
- 숫자·자원은 없다(장면만).

## 확인 (scratchpad t_s36.py, 새 방주, 요리사를 식량창고에 두고 두 번 건넴)
- 서버 use_spots: spot0 「단단한 흰 물 상자」(drink) · spot1 「작은 부푼 공기 봉지」(eat), 둘 다 오늘 씀.
- 화면 그림(ARKCORE.useSpots): 2:0 prop_white_carton, 2:1 prop_crisp_bundle. 1280 확대에서 벽 선반 아래 칸·짐 더미 꼭대기에 보인다(s36_use_1280.png).
- 쓰는 모습 소식: 실제 소식은 확인용 API 요청이 먼저 받아 가서, 같은 모양의 소식을 한 번 흘려 확인했다(로그 「use … eat」, 앉은 자세, 방송).
- 844·1280 콘솔 오류 0.

## 남은 것
- 기둥 안에 놓이는 물건(workshop 1번, quarters 1번, infirmary 2번)은 사람 뒤로 그렸다. 실화면에서 가려 보이면 앞으로 바꾼다.
- 쓰는 사람이 stand 좌표로 걸어가 서는 연출은 하지 않았다(지금 자리에서 자세만 바꾼다). 필요하면 다음에 이동 경로로 붙인다.
