# 진행 보고서 - 2026-02-19

## 요약
BarcodeQuest 메인 화면 전면 리디자인: 측면 뷰 → 항공 조감도(Aerial Bird's-Eye View) + 전체 에셋 픽셀아트 전환

---

## 02-BarcodeQuest: 항공 조감도 + 픽셀아트 리디자인

### 배경
- 기존: 측면 뷰 (하늘+산+도로+버스 옆모습)
- 변경: 위에서 내려다보는 항공/조감도 (구불구불한 길 + 픽셀아트 풍경)
- 컨셉: 현실에서 힘들었던 동물들이 천국에서 그리웠던 곳으로 여행하는 애잔하고 아름다운 여정

### 1단계: 항공 조감도 기본 구현
- 측면 뷰 CSS/HTML/JS 전량 삭제 (sky-layer, clouds, mountains, road, bus-exterior 등)
- 새 aerial scene 레이어 시스템 구축:
  - `.aerial-scenery` (z:1) — 정적 풍경 SVG
  - `.aerial-river` (z:2) — 강
  - `.aerial-road-layer` (z:3) — S커브 도로
  - `.aerial-bridge` (z:4) — 나무 다리
  - `.aerial-animals` (z:6) — 동물 스프라이트
  - `.aerial-bus` (z:10) — 버스
  - `.aerial-petals` (z:14) — 벚꽃잎
  - `.aerial-fireflies` (z:13) — 반딧불
  - `.aerial-atmosphere` (z:15) — 황금빛 오버레이
  - `.aerial-mist` (z:16) — 비네트
- 120초 주야간 사이클 (brightness/saturate 필터)
- 마우스/디바이스 패럴랙스 효과

### 2단계: 버스 개선
- 아이소메트릭 3/4 뷰 버스 SVG (3층 구조, 창문, 옥상정원, 굴뚝)
- 버스 도로 위 정확한 배치 (SVG path getPointAtLength 45% 지점)
- 바퀴 회전 애니메이션 (CSS isoWheelSpin)
- 버스 클릭 → 글로우+줌블러 트랜지션 → 내부 단면도

### 3단계: 전체 픽셀아트 전환
- **풍경**: viewBox 120×180 축소 → rect 기반 픽셀 나무, 숲, 벚꽃, 꽃밭, 해바라기, 라벤더, 돌, 벤치
- **강**: 계단식 픽셀 물길 + 하이라이트
- **도로**: S커브 path (여전히 곡선이지만 crispEdges로 선명)
- **다리**: 목재 판자 + 난간 (rect 기반)
- **버스**: 36×40 viewBox 픽셀아트 (3층 창문, 옥상정원, 굴뚝, 전조등, BQ 간판, 스트링 라이트)
- **동물 6종**: 고양이(오렌지 태비), 강아지(갈색), 토끼(흰색), 새(파랑), 사슴(갈색+뿔), 햄스터(금색)
- **벚꽃잎**: border-radius:0 사각형 픽셀
- **반딧불**: 사각형 글로우
- **전역**: `shape-rendering: crispEdges` 적용

### 기술 결정
| 항목 | 선택 | 이유 |
|------|------|------|
| SVG viewBox | 120×180 | 모바일 세로 최적화, xMidYMid slice |
| 버스 배치 | getPointAtLength() | CSS offset-path 대비 브라우저 호환성 우수 |
| 주야간 | filter: brightness/saturate | 전체 씬 일괄 변조, 코드 단순 |
| 동물 이동 | CSS transition + setInterval 8s | 프레임 비용 거의 없음 |
| 픽셀 스타일 | SVG rect + crispEdges | 실제 비트맵 불필요, 벡터 확장성 유지 |

### 색상 팔레트
- 대지: #B8D8A0 (세이지 그린)
- 도로: #C4A87C (모래색)
- 벚꽃: #FFB5C2, #FFC4D0
- 강: #7EC8E3
- 숲: #4A7A4A, #5A8A5A
- 버스: #E8734A
- 꽃: #D4A0C0 (라벤더), #FFE066 (해바라기), #FFB380 (들꽃)

---

## 파일 변경
| 파일 | 변경 내용 |
|------|----------|
| `backend/main.py` | CSS: ~170줄 교체 (aerial 스타일), HTML: ~120줄 교체 (픽셀아트 SVG), JS: ~200줄 교체 (aerial 함수) |
| `PROJECT_STATUS.md` | 항공 조감도 + 픽셀아트 섹션 추가, 향후과제 업데이트 |

---

## 테스트 결과
- 서버 기동: http://localhost:8001 정상 (200 OK)
- API 헬스체크: 정상
- 픽셀아트 렌더링: image-rendering:pixelated + crispEdges 8개소 확인
- 버스 도로 배치: path 좌표 계산 정상
- 주야간 사이클: 120초 루프 정상
- 벚꽃잎 드리프트: 18개 랜덤 파라미터 정상
- 반딧불: 밤 구간 표시/숨김 정상
- 동물 이동: 8초 주기 부드러운 전환 정상
- 버스 클릭 → 내부 전환: 글로우+줌 트랜지션 정상
- Exit → 조감도 복귀: 정상

---

## 통계
| 항목 | 수치 |
|------|------|
| 변경된 파일 | 3개 (main.py, PROJECT_STATUS.md, PROGRESS_REPORT) |
| CSS 변경 | ~170줄 (aerial 스타일 + 픽셀아트) |
| HTML 변경 | ~120줄 (픽셀아트 SVG 풍경/버스) |
| JS 변경 | ~200줄 (aerial 초기화 함수 6개) |
| 픽셀아트 에셋 | 풍경 1세트, 버스 1개, 동물 6종, 강/도로/다리 각 1개 |
