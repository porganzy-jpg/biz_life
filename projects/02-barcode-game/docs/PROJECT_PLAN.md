# BarcodeQuest - 바코드 기반 어드벤처 게임

## 1. 프로젝트 개요

### 1.1 핵심 컨셉
상품 바코드를 스캔하면 바코드 정보(국가코드, 제조사코드, 상품코드)를 조합하여
몬스터/아이템을 생성하는 게임. 일상에서 접하는 모든 상품이 게임의 소재가 되며,
수집, 육성, 배틀의 재미를 제공한다.

### 1.2 문제 정의
- 기존 수집형 게임은 가챠(뽑기) 과금에 의존하여 사용자 피로감 유발
- 현실 세계와 게임 세계의 연결 경험 부재 (Pokemon GO 이후 혁신 부재)
- 오프라인 쇼핑 경험에 재미 요소 부족

### 1.3 타겟 사용자
- 1차: 10~30대 모바일 게이머 (수집형 게임 선호)
- 2차: 쇼핑을 자주 하는 일반 소비자
- 3차: 자녀와 함께 쇼핑하는 부모 (교육적 요소)

---

## 2. 핵심 게임 메카닉 (Core Game Mechanics)

### 2.1 바코드 스캔 -> 몬스터 생성
1. 사용자가 상품 바코드를 카메라로 스캔
2. EAN-13 바코드 정보를 파싱하여 속성값 추출
3. 속성값 조합으로 유니크한 몬스터 생성
4. 몬스터의 등급, 속성, 스탯이 바코드 정보에 의해 결정

### 2.2 도감 시스템 (Collection System)
- 전체 몬스터 도감: 바코드 조합으로 이론상 수만 종 가능
- 카테고리별 도감: 음료 몬스터, 과자 몬스터, 생활용품 몬스터 등
- 도감 완성도에 따른 보상 시스템
- 희귀 몬스터: 특정 한정판 상품 바코드에서만 등장

### 2.3 위치 기반 퀘스트 (Location-based Quests)
- 특정 매장에서 바코드 스캔 시 보너스 경험치
- 지역별 한정 퀘스트 (예: 편의점 3곳 방문 시 보스 몬스터 출현)
- 이벤트 기간 특정 장소에서 레어 몬스터 출현율 증가
- GPS 기반 탐험 보상 시스템

### 2.4 배틀 시스템 (Battle System)
- 턴제 배틀: 몬스터 속성 상성 기반
- PvP 대전: 다른 사용자와 실시간 배틀
- 레이드 보스: 여러 사용자가 협력하여 도전
- 몬스터 레벨업 및 진화 시스템

---

## 3. 바코드-몬스터 생성 알고리즘 (EAN-13 Format Breakdown)

### 3.1 EAN-13 바코드 구조

```
┌─────────┬──────────────┬───────────┬─────────┐
│ 국가코드 │  제조사코드   │  상품코드  │ 체크섬  │
│  (3자리) │   (4자리)    │  (5자리)  │ (1자리) │
│ 880      │  1234        │  56789    │ 0       │
└─────────┴──────────────┴───────────┴─────────┘
```

### 3.2 속성 결정 알고리즘

```python
class BarcodeMonsterGenerator:
    """바코드 정보를 기반으로 몬스터를 생성하는 알고리즘"""

    # 국가코드 → 몬스터 속성 (Element)
    COUNTRY_ELEMENT_MAP = {
        '880': 'FIRE',      # 한국 → 불
        '490': 'WATER',     # 일본 → 물
        '690': 'EARTH',     # 중국 → 땅
        '000': 'LIGHTNING', # 미국 → 번개
        '400': 'WIND',      # 독일 → 바람
        '300': 'ICE',       # 프랑스 → 얼음
    }

    # 제조사코드 → 몬스터 종족 (Race)
    def determine_race(self, manufacturer_code: str) -> str:
        code_num = int(manufacturer_code)
        if code_num < 2000:
            return 'BEAST'      # 야수형
        elif code_num < 4000:
            return 'DRAGON'     # 드래곤형
        elif code_num < 6000:
            return 'SPIRIT'     # 정령형
        elif code_num < 8000:
            return 'MECHANICAL' # 기계형
        else:
            return 'MYTHICAL'   # 신화형

    # 상품코드 → 스탯 분배
    def calculate_stats(self, product_code: str) -> dict:
        digits = [int(d) for d in product_code]
        return {
            'HP':      digits[0] * 10 + 50,    # 50~140
            'ATK':     digits[1] * 8 + 20,     # 20~92
            'DEF':     digits[2] * 8 + 20,     # 20~92
            'SPD':     digits[3] * 6 + 10,     # 10~64
            'SPECIAL': digits[4] * 10 + 30,    # 30~120
        }

    # 등급 결정 (체크섬 + 상품코드 조합)
    def determine_grade(self, product_code: str, checksum: str) -> str:
        total = sum(int(d) for d in product_code) + int(checksum)
        if total >= 40:
            return 'LEGENDARY'  # 레전더리 (5%)
        elif total >= 30:
            return 'EPIC'       # 에픽 (15%)
        elif total >= 20:
            return 'RARE'       # 레어 (30%)
        else:
            return 'COMMON'     # 일반 (50%)

    def generate_monster(self, barcode: str) -> dict:
        country = barcode[0:3]
        manufacturer = barcode[3:7]
        product = barcode[7:12]
        checksum = barcode[12]

        return {
            'element': self.COUNTRY_ELEMENT_MAP.get(country, 'NEUTRAL'),
            'race': self.determine_race(manufacturer),
            'stats': self.calculate_stats(product),
            'grade': self.determine_grade(product, checksum),
            'unique_id': hashlib.md5(barcode.encode()).hexdigest()[:8],
        }
```

### 3.3 몬스터 외형 생성
- 속성(Element) + 종족(Race) 조합으로 기본 외형 결정
- 스탯 분배에 따라 외형 세부 요소 변경 (크기, 색상, 장식)
- AI 이미지 생성 (Stable Diffusion) 또는 사전 제작 스프라이트 조합
- 동일 바코드 = 동일 몬스터 보장 (결정론적 생성)

### 3.4 몬스터 네이밍 규칙
- 속성 접두사 + 종족 기반 이름 + 등급 접미사
- 예: 화염드래곤EX (FIRE + DRAGON + EPIC)
- 사용자가 닉네임을 부여할 수 있음

---

## 4. 기술 아키텍처 (Technical Architecture)

### 4.1 전체 시스템 구성

```
[Mobile App (Unity / Flutter)]
    |
    |--- Camera (바코드 스캔)
    |--- GPS (위치 기반 퀘스트)
    |--- AR Kit/Core (AR 몬스터 표시)
    |
[API Gateway (Kong / Nginx)]
    |
[Game Server (Node.js / Go)]
    |
    |--- MongoDB (몬스터/도감 데이터)
    |--- Redis (실시간 배틀, 랭킹)
    |--- PostgreSQL (사용자, 결제)
    |
[Matchmaking Server (Go)]
    |--- WebSocket (실시간 PvP)
```

### 4.2 모바일 앱 기술 스택
- **Game Engine**: Unity 2023 LTS (게임 렌더링, AR)
- **바코드 스캔**: ZXing / ML Kit Barcode Scanning
- **AR**: AR Foundation (ARKit + ARCore 통합)
- **네트워크**: gRPC + WebSocket
- **로컬 저장**: SQLite (도감 캐시)

### 4.3 서버 기술 스택
- **Game Logic Server**: Go (고성능 동시 처리)
- **API Server**: Node.js + Express / NestJS
- **Matchmaking**: Go + WebSocket
- **Database**: MongoDB Atlas (몬스터), Redis Cluster (랭킹/배틀), PostgreSQL (유저/결제)
- **CDN**: CloudFront (몬스터 이미지/에셋)
- **Infrastructure**: AWS EKS (Kubernetes)

---

## 5. GPS 연동 - 위치 기반 보너스 (GPS Integration)

### 5.1 위치 기반 보너스 시스템
- **매장 보너스**: 제휴 매장에서 스캔 시 경험치 1.5배
- **탐험 보너스**: 새로운 장소 방문 시 추가 보상
- **지역 한정 몬스터**: 특정 지역에서만 출현하는 몬스터
- **이벤트 존**: 기간 한정 특별 구역

### 5.2 위치 검증 (Anti-Cheat)
- GPS Spoofing 감지 알고리즘
- 이동 속도 기반 비정상 탐지
- Wi-Fi / Cell Tower 기반 위치 교차 검증
- 매장 Wi-Fi 연결 확인 (제휴 매장)

### 5.3 지역 맵 시스템
- 한국 전국을 격자(Grid)로 분할
- 격자별 출현 몬스터 풀 설정
- 사용자 탐험 기록 시각화 (히트맵)

---

## 6. 브랜드 협업 모델 (Brand Collaboration)

### 6.1 협업 유형

| 유형 | 설명 | 수익 모델 |
|------|------|----------|
| 브랜드 몬스터 | 특정 브랜드 상품에서만 나오는 한정 몬스터 | 브랜드 제휴 비용 |
| 이벤트 퀘스트 | 신제품 출시 연계 한정 퀘스트 | 캠페인 비용 |
| 콜라보 스킨 | 브랜드 로고/캐릭터 기반 몬스터 스킨 | 라이선스 비용 |
| 쿠폰 보상 | 게임 내 보상으로 실제 할인 쿠폰 제공 | 수수료 |

### 6.2 브랜드 대시보드
- 캠페인별 바코드 스캔 횟수 분석
- 사용자 인구통계 및 행동 데이터 제공
- ROI 측정 도구
- 실시간 캠페인 성과 모니터링

### 6.3 예상 협업 파트너
- 대형 식품 제조사: CJ, 오뚜기, 농심, 롯데제과
- 편의점 체인: CU, GS25, 세븐일레븐
- 생활용품: LG생활건강, 아모레퍼시픽
- 음료: 코카콜라, 롯데칠성

---

## 7. 게임 경제 시스템

### 7.1 재화 종류
- **골드**: 기본 재화 (몬스터 강화, 아이템 구매)
- **크리스탈**: 프리미엄 재화 (인앱 결제 / 업적 보상)
- **에너지**: 바코드 스캔 횟수 제한 (시간 경과로 회복)
- **도감 포인트**: 새로운 몬스터 등록 시 획득

### 7.2 과금 설계
- 에너지 충전 (일 3회 무료, 추가 구매 가능)
- 몬스터 보관함 확장
- 프리미엄 도감 스킨
- 배틀 패스 (시즌제)

### 7.3 밸런스 원칙
- Pay-to-Win 방지: 과금 아이템은 편의성 위주
- 바코드 스캔 자체가 핵심 재미이므로 과도한 에너지 제한 지양
- 무과금 사용자도 도감 완성 가능하도록 설계

---

## 8. 특허 전략 (Patent Strategy)

### 8.1 출원 대상
**발명의 명칭**: "상품 바코드 정보 기반 게임 캐릭터 생성 시스템 및 방법"

### 8.2 청구항 핵심 구성
1. 사용자 단말의 카메라를 통해 상품 바코드를 인식하는 단계
2. 인식된 바코드의 국가코드, 제조사코드, 상품코드를 파싱하는 단계
3. 파싱된 각 코드를 기 설정된 변환 규칙에 따라 게임 캐릭터의 속성, 종족, 능력치로 변환하는 단계
4. 변환된 정보를 조합하여 고유한 게임 캐릭터를 생성하는 단계
5. 생성된 캐릭터를 사용자의 도감에 등록하고 관리하는 단계
6. 사용자 단말의 위치 정보를 기반으로 추가 보너스를 적용하는 단계

### 8.3 특허 차별점
- 실제 상품 바코드를 게임 요소 생성의 시드(seed)로 활용
- 바코드 구성 요소별 게임 속성 매핑의 체계적 방법론
- 결정론적 생성으로 동일 바코드 = 동일 캐릭터 보장
- 위치 정보와 결합한 보너스 시스템

### 8.4 선행 기술 차별화
- Pokemon GO: GPS 기반이지만 바코드 활용 없음
- 바코드 스캐너 앱: 상품 정보만 제공, 게임 요소 없음
- 기존 수집형 게임: 랜덤 가챠 방식, 현실 연계 없음

---

## 9. 개발 로드맵

### Phase 1: 프로토타입 (10주)
- 바코드 스캔 및 몬스터 생성 핵심 로직
- 기본 도감 시스템
- 몬스터 외형 생성 (스프라이트 조합 방식)
- 로컬 플레이 가능 (서버 없이)

### Phase 2: 소셜 기능 (10주)
- 서버 구축 및 사용자 계정 시스템
- PvP 배틀 시스템
- 랭킹 시스템
- 친구 시스템 및 몬스터 교환

### Phase 3: 수익화 (8주)
- 인앱 결제 시스템
- 브랜드 협업 플랫폼
- 위치 기반 퀘스트 시스템
- 시즌 배틀 패스

---

## 10. KPI 및 성과 지표

- **DAU** (일간 활성 사용자): 출시 3개월 내 100,000명
- **일 평균 바코드 스캔 수**: 사용자당 5회 이상
- **도감 등록률**: 사용자 평균 50종 이상 수집
- **PvP 참여율**: DAU 대비 30% 이상
- **ARPU** (사용자당 평균 매출): 월 3,000원
- **Retention D7**: 40% 이상
- **Retention D30**: 20% 이상
