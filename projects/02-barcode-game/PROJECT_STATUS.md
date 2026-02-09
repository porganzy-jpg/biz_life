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
│   ├── barcode_monster_generator.py  # [특허 핵심] 바코드→몬스터 변환 엔진 (487줄)
│   ├── battle_system.py             # 턴제 배틀 시스템 (속성 상성, 크리티컬)
│   ├── collection.py                # 도감 시스템 (수집, 완성도, 보상)
│   └── player.py                    # 플레이어 모델 (파티, 인벤토리, 레벨)
├── backend/
│   ├── main.py                      # FastAPI 게임 서버 + HTML 클라이언트
│   ├── database.py                  # DB 설정
│   └── models.py                    # PlayerModel, MonsterModel, BattleLog
├── docs/
│   └── PROJECT_PLAN.md
└── requirements.txt
```

## API 엔드포인트 (7개)
| Method | Path | 설명 | 테스트 결과 |
|--------|------|------|-------------|
| GET | `/` | 게임 클라이언트 (HTML) | OK - 14,002 bytes |
| GET | `/api/health` | 헬스체크 | OK |
| GET | `/api/player` | 플레이어 상태 조회 | OK |
| POST | `/api/scan?barcode=` | 바코드 스캔 → 몬스터 생성 | OK |
| POST | `/api/battle` | PvE 배틀 시작 (자동 10턴) | OK |
| GET | `/api/collection` | 도감 목록 + 통계 | OK |
| POST | `/api/recover` | 에너지 회복 | OK |

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
- 몬스터 생성: `8801234567890` → "Silver Golem" (Common, Food)
- 배틀: 자동 10턴 진행, 승패 판정 정상
- 도감: 수집/완성도/보상 시스템 정상

## 주요 기능
- [x] 바코드 → 몬스터 결정적 생성 (특허 핵심)
- [x] 10종 속성 상성 배틀 시스템
- [x] 도감 수집 + 완성도 보상
- [x] 플레이어 레벨/에너지/골드 시스템
- [x] 파티(3체) + 보관함(50체) 관리
- [x] 웹 클라이언트 (스캔/배틀/도감 탭)

## 향후 과제
- [ ] 실제 바코드 카메라 스캔 연동 (QuaggaJS / ZXing)
- [ ] PvP 대전 시스템
- [ ] 몬스터 진화/합성
- [ ] 이벤트/시즌 시스템
- [ ] 리더보드
