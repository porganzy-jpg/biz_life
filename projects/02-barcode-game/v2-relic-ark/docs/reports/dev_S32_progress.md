# S32 서버 진행 기록 — 「다음 할 일」 한 줄 · 첫 스캔 길잡이
시작 2026-10-17. 커밋 안 함. 확인 포트 8019(8002 는 사용자 플레이 중 — 건드리지 않음).

| # | 항목 | 상태 |
|---|---|---|
| 1 | /api/ark.next_step {kind, line_ko, target, hint_mode, idle_sec} 우선순위 1~7 | 코드 완료 |
| 2 | 켠 날 1~3 always, 4~ idle(30초 — 화면이 판단) | 코드 완료 |
| 3 | tutorial: core.tutorial_seen, POST /api/tutorial, /api/ark.tutorial.next_step_id | 코드 완료 |
| T | test_s32 21/21, 전 스위트 통과, 8019 curl, API §21 | 완료 |
- 걸음 이름 정렬: quick_pick → subtype_pick(시나리오·코디). 화면 별칭 받음
- next_line 은 _rot 대신 날 시드(public_state 가 여러 번 불려도 줄이 안 바뀌고 상태를 안 건드림)
