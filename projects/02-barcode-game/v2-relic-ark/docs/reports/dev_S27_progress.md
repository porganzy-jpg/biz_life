# S27 서버 진행 기록 (5차 플테 원인 고침) — 끊겨도 이어 가기 위한 메모

시작: 2026-10-17. HEAD c8f7615 기준 작업 트리. 커밋 안 함.

| # | 항목 | 상태 |
|---|---|---|
| 1 | 기색: 지금 물건 칸 → 집에 있는 하위 종류 칸(home) → 역할×갈래 → 공통 | 코드 완료 |
| 2 | 「어디로」 줄 pin_rows(필요·좋아함·기억·매듭 맞는 사람 + 오늘 부탁한 사람, 첫 칸 아님) | 코드 완료 |
| 3 | 라벨 4일째 꺼짐(달력 mood_hints·notebook 3→4) | 코드 완료 |
| 4 | 첫 매듭 1일째·낮 한 상(DAYTIME_TABLE)·기억 벽(첫 칸 채움, /api/memory_wall/hang) | 코드 완료 |
| 5 | 가보: not_for_me 제외·heirloom_refused·fit_hint | 코드 완료 |
| 6 | 이름 다시 붙이기 rename(하루 한 번) | 코드 완료 |
| 7 | r5-1 solved_today·r5-3 leave_lines·r5-4 개발 시계 판정·선반 꽉 참 세션 1회 | 코드 완료 |
| 8 | /api/raid/auto_defend + raid.office | 코드 완료 |
| T | tests/test_s27.py 70/70, 전 스위트 통과, 8019 curl 확인, API §17 | 완료 |
- r5-5 _alt 규칙(announce_alt 없으면 announce, 입말 되풀이 금지) 코드 완료
- PM 첫 세션 큐 ①첫 진입판 ②가보 3일째·간직 메모 ③한 번에 고르기(peek.quick_pick + scan user_subtype) 완료
- 고른 하위 종류에 맞춘 첫 만남 줄(first_meet_sub) 완료
- Playwright 스크린샷: 다른 세션이 브라우저를 쓰는 중이라 못 찍음(서버만 바뀜, index 200 확인)
