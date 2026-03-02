# BarcodeQuest - 프로젝트 현황

## 개요
바코드 스캔으로 몬스터를 생성하는 수집형 배틀 게임. EAN-13 바코드의 국가코드, 제조사코드, 상품코드를 분석하여 결정적(deterministic)으로 몬스터를 생성하는 특허 핵심 기술 기반.

## 기술 스택
- **Backend**: Python 3.13, FastAPI, SQLAlchemy + SQLite
- **Game Engine**: 순수 Python (외부 라이브러리 불필요)
- **Frontend**: 인라인 HTML 템플릿 (vanilla JS)

## 실행 방법
```bash
cd projects/02-barcode-game/backend
python main.py
# → http://localhost:8001
```

## 파일 구조
```
02-barcode-game/
├── game-engine/
│   ├── barcode_monster_generator.py  # [특허 핵심] 바코드→몬스터 변환 엔진
│   ├── battle_system.py             # 턴제 배틀 시스템 (속성 상성, 크리티컬)
│   ├── collection.py                # 도감 시스템 (수집, 완성도, 보상)
│   ├── player.py                    # 플레이어 모델 (파티, 인벤토리, 레벨)
│   ├── expedition_system.py         # 방치형 탐험 시스템
│   ├── item_system.py               # 아이템 인벤토리/상점
│   ├── evolution_system.py          # 크리처 진화
│   ├── daily_quest_system.py        # 일일 퀘스트
│   └── bus_system.py                # 버스 경영 시스템
├── backend/
│   ├── main.py                      # FastAPI 게임 서버 + HTML 클라이언트 (~170KB)
│   ├── database.py                  # DB 설정
│   └── models.py                    # PlayerModel, MonsterModel, BattleLog
├── artwork/                         # AI 아트 이미지 (110장)
│   ├── named_characters/            # 캐릭터 10장 (나비, 하루 등)
│   ├── monsters/                    # 몬스터 100장 (10몸체 × 10속성)
│   ├── image_urls.json              # pollinations.ai URL 매핑
│   ├── preview.html                 # 전체 이미지 미리보기
│   └── landscapes/                  # 배경 이미지
├── mockups/
│   ├── index.html                   # 게임 클라이언트 (수채화 아트 통합)
│   └── monster_preview.html         # 몬스터 이미지 리뷰 페이지
├── tools/
│   ├── generate_monster_images.py   # pollinations.ai URL 매핑 생성기
│   └── generate_local_art.py        # Pillow 로컬 아트 생성기
├── design-concepts/                 # 18개 SVG 디자인 에셋
├── docs/
│   └── PROJECT_PLAN.md
└── requirements.txt
```

## API 엔드포인트
| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 게임 클라이언트 (HTML) |
| GET | `/api/health` | 헬스체크 |
| GET | `/api/player` | 플레이어 상태 조회 |
| POST | `/api/scan?barcode=` | 바코드 스캔 → 몬스터 생성 |
| POST | `/api/battle` | PvE 배틀 시작 |
| GET | `/api/collection` | 도감 목록 + 통계 |
| POST | `/api/recover` | 에너지 회복 |
| GET | `/api/expedition/zones` | 탐험 지역 목록 |
| POST | `/api/expedition/start` | 탐험 시작 |
| POST | `/api/expedition/collect` | 탐험 보상 수령 |
| GET | `/api/items` | 아이템 인벤토리 |
| POST | `/api/items/use` | 아이템 사용 |
| GET/POST | `/api/shop/*` | 상점 |
| GET/POST | `/api/evolve/*` | 진화 시스템 |
| GET/POST | `/api/daily-quest/*` | 일일 퀘스트 |
| GET/POST | `/api/bus/*` | 버스 시스템 (건설/배치/수집/업그레이드) |
| GET/POST | `/api/party/*` | 파티 관리 |

## 특허 핵심 알고리즘 (barcode_monster_generator.py)
```
바코드(EAN-13) → 파싱(국가/제조사/상품)
    → GPS + 시간 결합 → SHA-256 시드 생성
    → 결정적 속성 매핑:
        - 이름: 국가별 prefix + 속성 기반 suffix
        - 타입: 10종 (Fire, Water, Earth, Wind, Food, Tech, Nature, Spirit, Dark, Light)
        - 희귀도: 5단계 (Common~Legendary) - 체크섬 기반
        - 능력치: HP, ATK, DEF, SPD, SPL
        - 외형: 체형, 색상, 장식
    → 위치 보너스 적용 → Monster 객체 조립
```

## 배틀 시스템
- 10종 속성 상성 매트릭스 (삼각 상성 구조)
- 턴제 배틀 (최대 10턴, 공격/스페셜/방어)
- 데미지 = (ATK * 타입배율 * 크리티컬 - DEF * 0.5) * 랜덤
- 승리 시 EXP + Gold 보상

## 테스트 결과
- 2025-02-07 전체 API 엔드포인트 테스트 통과
- 2026-02-18 UI/그래픽 업그레이드 + 도감/캐릭터 시스템 강화 완료
- 2026-02-19 항공 조감도 + 픽셀아트 전환 완료 (풍경/버스/동물/꽃잎/반딧불)
- 2026-03-03 수채화 판타지 아트 업그레이드 완료 (110장 이미지 생성)
- 몬스터 생성: `8801234567890` → "Silver Golem" (Common, Food)
- 배틀: 자동 10턴 진행, 승패 판정 정상
- 도감: 수집/완성도/보상 시스템 정상
- 가챠 스캔 애니메이션: 3단계 연출 정상 (파티클→에너지 수렴→카드 리빌)
- 몬스터 상세 모달: 스캔/도감/배틀 등 다양한 곳에서 접근 가능

## 주요 기능

### 핵심 시스템
- [x] 바코드 → 몬스터 결정적 생성 (특허 핵심)
- [x] 10종 속성 상성 배틀 시스템
- [x] 도감 수집 + 완성도 보상
- [x] 플레이어 레벨/에너지/골드 시스템
- [x] 파티(3체) + 보관함(50체) 관리
- [x] 웹 클라이언트 (풍경+버스 메인 화면 → 기능 오버레이)

### UI/그래픽 (2026-02-18 업그레이드)
- [x] 가챠 스캔 3단계 애니메이션 (파티클→에너지 수렴→카드 플립 리빌)
- [x] 레어도별 카드 비주얼 (Common~Legendary 그라디언트, 홀로그래픽, 무지개 쉰)
- [x] SVG 인라인 몬스터 스프라이트 10종 (Dragon, Fox, Bear, Bird, Slime, Golem, Ghost, Cat, Wolf, Turtle)
- [x] 몬스터 컬러 동적 변경 (20종 색상 맵)
- [x] 버스 룸 비주얼 개선 (호버 글로우, 플로팅 애니메이션, S등급 효과)
- [x] 전체 UI 폴리시 (Poppins 폰트, 애니메이션 그라디언트 배경, 스티키 헤더, 버튼 샤인 스윕)
- [x] 에너지 바 쉬머 애니메이션
- [x] **첫 화면 대폭 개선**: 히어로 섹션 (애니메이션 로고 + 태그라인 + 플로팅 크리처)
- [x] 퀵 스탯 대시보드 (Level/Collected/Gold/Energy)
- [x] Recent Catches 캐러셀 (최근 획득 크리처 10마리 미니카드)
- [x] 스캔 포탈 비주얼 (회전 링 3중 + 펄스 파티클)
- [x] 샘플 바코드 그리드 카드 (국기 + 상품명 + 코드)
- [x] 웰컴 팁 배너 (닫기 가능)

### 풍경+버스 메인 화면 리디자인 (2026-02-18)
- [x] 풍경 메인 뷰 (하늘/구름/산/도로/나무/꽃/별 - 패럴랙스 레이어)
- [x] 3층 버스 외형 SVG (창문, 바퀴, 굴뚝, 간판)
- [x] 하늘 주야간 사이클 애니메이션 (120초 루프: 낮→석양→밤→새벽)
- [x] 버스 클릭 → 줌인 트랜지션 → 버스 내부 단면도
- [x] Fallout Shelter 스타일 버스 내부 단면도 (3층 × 3슬롯)
- [x] 방 타입별 배경 그라디언트, 크리처 미니 SVG 표시
- [x] 하단 네비게이션 바 (Scan/Battle/Explore/Dex/Quest)
- [x] 기능 슬라이드업 오버레이 (기존 패널을 오버레이로 표시)
- [x] 뷰 상태 머신 (LANDSCAPE → BUS_INTERIOR → FEATURE)
- [x] USE_NEW_UI 플래그로 구/신 UI 토글 가능
- [x] 패럴랙스 이펙트 (마우스/deviceorientation)
- [x] 기존 모든 API/기능 100% 호환 (버스 건설, 배치, 수령 등)

### 수채화 판타지 아트 업그레이드 (2026-03-03)
- [x] Pillow 기반 수채화풍 이미지 자동 생성 시스템 구축
- [x] 캐릭터 10장: 나비(나비), 하루(강아지), 포리(앵무새), 미루(고양이), 꼬미(토끼), 랑이(여우), 별이(햄스터), 구름(고양이), 달이(부엉이), 솔이(고슴도치)
- [x] 몬스터 100장: 10 몸체(드래곤/슬라임/고블린/페어리/골렘/유니콘/피닉스/스프라이트/키메라/위스프) × 10 속성(불/물/자연/바람/영혼/빛/어둠/대지/기계/음식)
- [x] `makePixelArtSVG()` → `makeMonsterImage()` 전면 교체 (컬렉션, 상세, 발견팝업, 버스방, 도감)
- [x] CSS 색상 변형: `hue-rotate` 10단계 (바코드 기반 자동 할당)
- [x] CSS 희귀도 효과: Common~Legendary 글로우 + Epic 이상 홀로그래픽 오버레이
- [x] 버스 캔버스 스프라이트: 이미지 기반 64px 캐시 + 픽셀아트 폴백
- [x] 이미지 로드 실패 시 이모지 자동 폴백 (onerror)
- [x] pollinations.ai URL 매핑 + Pillow 로컬 생성 이중 파이프라인
- [x] 미리보기 페이지: artwork/preview.html (전체 110장 그리드 리뷰)

### 항공 조감도(Aerial Bird's-Eye) + 픽셀아트 전환 (2026-02-19)
- [x] 측면 뷰 → 항공/조감도(위에서 내려다보기) 전면 리디자인
- [x] SVG viewBox 120×180 픽셀아트 풍경 (나무, 숲, 벚꽃, 꽃밭, 해바라기, 돌, 벤치)
- [x] 픽셀아트 강 (계단식 물길 + 하이라이트)
- [x] S커브 도로 (모래색 #C4A87C, 중앙 대시선, getPointAtLength 위치 계산)
- [x] 목재 다리 (도로와 강 교차 지점)
- [x] 픽셀아트 아이소메트릭 버스 (3층 구조, 창문, 옥상정원, 굴뚝, 전조등, BQ 간판)
- [x] 버스 바퀴 회전 애니메이션 (CSS isoWheelSpin)
- [x] 버스 도로 위 정확한 배치 (path 45% 지점 좌표 + 각도 계산, 리사이즈 대응)
- [x] 픽셀아트 동물 6종 (고양이/강아지/토끼/새/사슴/햄스터) 8초 주기 이동
- [x] 벚꽃잎 18개 드리프트 (CSS custom property, 사각형 픽셀 스타일)
- [x] 반딧불 12개 (밤 45-75초 구간에만 표시, 사각형 글로우)
- [x] 120초 주야간 사이클 (brightness/saturate 필터 변조)
- [x] 마우스/디바이스 패럴랙스 (전체 씬 미세 이동)
- [x] 버스 클릭 → 글로우+줌블러 트랜지션 → 내부 단면도
- [x] shape-rendering: crispEdges 전역 적용 (선명한 픽셀 에지)
- [x] 반응형 버스 크기 (모바일 64px / 태블릿 80px / 데스크탑 96px)
- [x] 자막 텍스트 "A Journey to Remembered Places" + 그림자 가독성 개선

### 캐릭터/도감 시스템 (2026-02-18 추가)
- [x] 몬스터 상세 모달 (풀스크린, SVG 대형 표시, 능력치 바, 정보 그리드)
- [x] 감성 몬스터 스토리 30종 (체형별 3개, 아련하고 귀여운 감정)
- [x] 바코드 상품 정보 조회 (Open Food Facts API 연동)
- [x] EAN-13 바코드 파싱 (국가코드 ~100개국, 제조사, 상품코드, 체크디짓)
- [x] 도감 그리드 뷰 + 레어도 필터 (All/Legendary/Epic/Rare/Uncommon/Common)
- [x] 스캔/도감/배틀/버스 등 다양한 곳에서 캐릭터 상세 접근 가능
- [x] 카드에 스토리 미리보기 + 출신 국가 표시

## 향후 과제
- [ ] 실제 바코드 카메라 스캔 연동 (QuaggaJS / ZXing)
- [ ] PvP 대전 시스템
- [ ] 이벤트/시즌 시스템
- [ ] 리더보드
- [x] ~~도트/픽셀 아트 에셋 전환~~ → 2026-02-19 풍경/버스/동물 픽셀아트 완료
- [x] ~~몬스터 스프라이트 픽셀아트 전환~~ → 2026-03-03 수채화 판타지 아트 110장 완료
- [ ] AI 이미지 서비스 연동 (pollinations.ai 복구 시 고품질 교체)
- [ ] 캐릭터 재회 시스템 (감동적 재회 컷씬)
- [ ] 풍경 수집 시스템 (여행 루트별 고유 풍경)
- [ ] 사운드/BGM 추가
