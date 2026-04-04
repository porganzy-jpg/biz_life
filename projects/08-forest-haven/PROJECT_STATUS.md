# Forest Haven (숲의 안식처)

## Overview
바코드 스캔 수집 + 카드 시스템 + 숲속 오두막 기지 빌딩 + 세계 자연경관 탐험을 결합한 모바일 게임.
BarcodeQuest(02-barcode-game)의 검증된 패턴을 활용하며 실제 고퀄리티 이미지를 사용합니다.

## Status: Phase 1 - HTML Mockup (Complete)

### Game Concept
- **Theme**: 따뜻한 숲속 오두막, 자연 판타지
- **Colors**: 포레스트 그린, 따뜻한 우드 브라운, 골드, 자연 톤
- **Core Loop**: 바코드 스캔 → 생명체 카드 발견 → 오두막 배치 → 자원 생산 → 크래프팅 → 세계 탐험

### 11 Screens
1. 홈 - 숲 풍경 실사 배경 + 자원 바 + 퀵 액션 그리드
2. 바코드 스캐너 - 카메라 뷰포트 + 스캔 애니메이션
3. 카드 발견 (오버레이) - 3D 카드 플립 + 홀로그래픽 효과
4. 카드북 (컬렉션) - 생명체/아이템/랜드마크/자원 탭별 그리드
5. 카드 상세 (모달) - 풀사이즈 카드 + 스탯 + 로어
6. 숲속 오두막 - Canvas 기반 사이드컷 뷰
7. 방 상세 (모달) - 실사 배경 + 배치된 생명체 + 업그레이드
8. 세계 지도 - 10개 랜드마크 카드 리스트
9. 지역 방문 (풀스크린) - 실사 배경 + 탐험 UI
10. 인벤토리/크래프팅 - 자원 + 아이템 + 레시피
11. 프로필/설정 - 레벨, 통계, 업적

### Card System
- **Types**: 생명체, 아이템, 랜드마크, 자원
- **Grades**: 일반 → 고급 → 희귀 → 영웅 → 전설 → 신화 (6단계)

### Cabin System (10 Rooms)
| Room | Resource | Floor | Unlock |
|------|----------|-------|--------|
| 거실 | comfort | 1F | 기본 |
| 부엌 | food | 1F | 기본 |
| 약초원 | herb | 1F | 기본 |
| 공방 | wood | 2F | 기본 |
| 서재 | wisdom | 2F | Lv.3 |
| 전망대 | starDust | 3F | Lv.5 |
| 온천 | water | B1 | Lv.4 |
| 수정동굴 | crystal | B1 | Lv.7 |
| 나무집 | honey | 3F | Lv.6 |
| 양봉장 | honey | 1F | Lv.8 |

### 10 World Landmarks
1. 스위스 알프스 (마터호른)
2. 일본 벚꽃길 (후지산)
3. 노르웨이 피오르 (오로라)
4. 그랜드 캐니언
5. 아마존 열대우림
6. 그레이트 배리어 리프
7. 아이슬란드 (간헐천/빙하)
8. 제주도 (한라산)
9. 파타고니아
10. 캐나디안 로키 (밴프)

### Tech Stack
- Single HTML file (Vanilla JS, no build tools)
- Canvas 2D (cabin rendering)
- localStorage (game state)
- CSS Variables (theme system)
- Unsplash (real photos) + pollinations.ai (AI creature art)

### How to Run
```bash
# Open in browser
open projects/08-forest-haven/mockups/index.html
```

## Next Steps (Phase 2+)
- FastAPI backend + SQLite persistence
- Real barcode scanner (WebRTC camera)
- Push notifications for resource production
- Social features (friend cabins, trading)
- Kakao/Google login
