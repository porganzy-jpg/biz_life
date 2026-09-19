
## 게임 클라이언트 적용 (2026-09-19 저녁)
- `backend/main.py`: `/artwork`, `/media` 정적 마운트 추가. 이전엔 서버로 띄우면 상대경로 `../artwork`가 404라 **모든 그림이 이모지로 대체**되던 문제를 함께 해결.
- `mockups/index.html`:
  - `ART_BASE`/`MEDIA_BASE`가 서버(`/artwork`)와 파일 열기(`../artwork`) 양쪽에서 동작
  - 버스 화면에 `<model-viewer>`로 **3D GLB 버스**(자동 회전, 드래그 회전) 표시. "내부 보기 ↔ 3D 외관" 버튼으로 기존 캔버스 내부 뷰와 전환
  - 몬스터 이미지 우선순위: `artwork/monsters/<body>_concept.png`(AI 컨셉아트 10종) → `<body>_<elem>.png`(기존 Pillow 도형) → 이모지
  - `?view=bus` 같은 딥링크로 화면 바로 열기(검증용)
- `tools/gen_body_concepts.py`: 몸체 10종 다크판타지 컨셉아트 생성기
- 실행: `cd backend && python main.py` → http://localhost:8001 (버스 탭에서 3D 확인)
