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
│   ├── main.py                      # FastAPI 게임 서버 + HTML 클라이언트 (~103KB)
│   ├── database.py                  # DB 설정
│   └── models.py                    # PlayerModel, MonsterModel, BattleLog
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
- [x] 웹 클라이언트 (스캔/배틀/도감/탐험/상점/버스 탭)

### UI/그래픽 (2026-02-18 업그레이드)
- [x] 가챠 스캔 3단계 애니메이션 (파티클→에너지 수렴→카드 플립 리빌)
- [x] 레어도별 카드 비주얼 (Common~Legendary 그라디언트, 홀로그래픽, 무지개 쉰)
- [x] SVG 인라인 몬스터 스프라이트 10종 (Dragon, Fox, Bear, Bird, Slime, Golem, Ghost, Cat, Wolf, Turtle)
- [x] 몬스터 컬러 동적 변경 (20종 색상 맵)
- [x] 버스 룸 비주얼 개선 (호버 글로우, 플로팅 애니메이션, S등급 효과)
- [x] 전체 UI 폴리시 (Poppins 폰트, 애니메이션 그라디언트 배경, 스티키 헤더, 버튼 샤인 스윕)
- [x] 에너지 바 쉬머 애니메이션

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
- [ ] 도트/픽셀 아트 에셋 전환 (현재 SVG → 향후 도트 아트)
- [ ] 캐릭터 재회 시스템 (감동적 재회 컷씬)
- [ ] 풍경 수집 시스템 (여행 루트별 고유 풍경)
- [ ] 사운드/BGM 추가
