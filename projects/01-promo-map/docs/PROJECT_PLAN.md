# PromoMap - 위치 기반 임직원 할인 프로모션 앱

## 1. 프로젝트 개요

### 1.1 핵심 컨셉
GPS 기반으로 사용자 위치 반경 100m 이내 임직원 할인 가능 매장을 알림 푸시하는 앱.
직장인이 점심시간이나 퇴근 후 주변을 지나갈 때, 본인이 소속된 기업과 제휴된 할인 매장 정보를
실시간으로 받아볼 수 있다.

### 1.2 문제 정의
- 대부분의 임직원은 자사 복지 할인 혜택의 10~20%만 인지하고 있음
- 할인 가능 매장이 있어도 모르고 지나치는 경우가 대다수
- 기존 복지몰은 온라인 위주이며, 오프라인 매장 연동이 미흡

### 1.3 타겟 사용자
- 1차: 대기업 및 중견기업 임직원 (복지 제도 운영 기업)
- 2차: 프랜차이즈 매장 (제휴 파트너)
- 3차: 중소기업 (복지 서비스 외주 수요)

---

## 2. 핵심 기능 (Core Features)

### 2.1 지오펜싱 (Geofencing)
- 사용자 위치 기반 반경 100m 가상 울타리 설정
- 지오펜스 진입/퇴장 이벤트 감지
- Background Location Tracking 최적화 (배터리 소모 최소화)
- 지오펜스 최대 동시 모니터링: 100개 (Android), 20개 (iOS)

### 2.2 푸시 알림 (Push Notification)
- 지오펜스 진입 시 해당 매장 할인 정보 즉시 푸시
- 알림 빈도 제어: 동일 매장 1일 1회 제한
- 시간대별 알림 설정 (점심시간, 퇴근시간 등)
- Rich Notification: 매장 이미지, 할인율, 거리 정보 포함

### 2.3 할인 정보 DB
- 기업별 제휴 매장 데이터베이스
- 할인 종류: 정률 할인, 정액 할인, 1+1, 포인트 적립 등
- 할인 유효기간 관리
- 실시간 할인 정보 업데이트

### 2.4 사용자 위치 추적
- Foreground / Background 위치 추적
- 배터리 효율을 위한 Significant Location Change 활용
- 위치 정확도 레벨 조절 (High / Balanced / Low)

---

## 3. 기술 아키텍처 (Technical Architecture)

### 3.1 전체 시스템 구성

```
[Mobile App (Flutter)]
    |
    |--- Kakao Map API / Google Maps API
    |--- FCM (Firebase Cloud Messaging)
    |
[API Gateway (Nginx)]
    |
[Backend Server (FastAPI / Django)]
    |
    |--- PostgreSQL (메인 DB)
    |--- Redis (캐시 / 세션)
    |--- Elasticsearch (매장 검색)
    |
[Admin Dashboard (React)]
```

### 3.2 지도 API 선택

| 항목 | Kakao Map API | Google Maps API |
|------|--------------|-----------------|
| 국내 정확도 | 매우 높음 | 높음 |
| 무료 한도 | 일 300,000건 | 월 $200 크레딧 |
| 지오코딩 | 한국 주소 최적화 | 글로벌 |
| SDK 지원 | Android/iOS/Web | Android/iOS/Web/Flutter |
| 비용 | 상대적 저렴 | 트래픽 증가 시 고비용 |

**결정**: 국내 서비스 우선이므로 Kakao Map API를 메인으로 사용하되,
해외 확장 시 Google Maps API로 전환할 수 있는 추상화 레이어 설계.

### 3.3 모바일 앱 기술 스택
- **Framework**: Flutter 3.x (크로스 플랫폼)
- **상태 관리**: Riverpod
- **로컬 DB**: Hive / SQLite
- **지도**: kakao_map_plugin / google_maps_flutter
- **위치**: geolocator, geofencing_api
- **푸시**: firebase_messaging

### 3.4 백엔드 기술 스택
- **API Server**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15 + PostGIS (공간 데이터)
- **Cache**: Redis 7.x
- **Search**: Elasticsearch 8.x
- **Message Queue**: RabbitMQ / Celery
- **Container**: Docker + Docker Compose
- **CI/CD**: GitHub Actions

---

## 4. 데이터베이스 스키마 (Database Schema)

### 4.1 사용자 테이블 (users)

```sql
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    name            VARCHAR(100) NOT NULL,
    phone           VARCHAR(20),
    company_id      BIGINT REFERENCES companies(id),
    employee_id     VARCHAR(50),
    is_verified     BOOLEAN DEFAULT FALSE,
    fcm_token       VARCHAR(500),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
```

### 4.2 기업 테이블 (companies)

```sql
CREATE TABLE companies (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    business_number VARCHAR(20) UNIQUE NOT NULL,
    industry        VARCHAR(100),
    employee_count  INTEGER,
    contract_start  DATE,
    contract_end    DATE,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### 4.3 매장 테이블 (stores)

```sql
CREATE TABLE stores (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    brand_id        BIGINT REFERENCES brands(id),
    address         VARCHAR(500) NOT NULL,
    latitude        DECIMAL(10, 8) NOT NULL,
    longitude       DECIMAL(11, 8) NOT NULL,
    location        GEOGRAPHY(POINT, 4326),
    phone           VARCHAR(20),
    category        VARCHAR(50),
    operating_hours JSONB,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_stores_location ON stores USING GIST(location);
```

### 4.4 할인 정보 테이블 (discounts)

```sql
CREATE TABLE discounts (
    id              BIGSERIAL PRIMARY KEY,
    store_id        BIGINT REFERENCES stores(id),
    company_id      BIGINT REFERENCES companies(id),
    discount_type   VARCHAR(20) NOT NULL,  -- 'PERCENT', 'FIXED', 'BOGO', 'POINT'
    discount_value  DECIMAL(10, 2) NOT NULL,
    description     TEXT,
    conditions      JSONB,
    valid_from      DATE NOT NULL,
    valid_until     DATE NOT NULL,
    max_usage       INTEGER,
    current_usage   INTEGER DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### 4.5 사용 이력 테이블 (usage_logs)

```sql
CREATE TABLE usage_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(id),
    discount_id     BIGINT REFERENCES discounts(id),
    store_id        BIGINT REFERENCES stores(id),
    used_at         TIMESTAMP DEFAULT NOW(),
    saved_amount    DECIMAL(10, 2),
    verification    VARCHAR(50)  -- 'BARCODE', 'QR', 'MANUAL'
);
```

---

## 5. API 엔드포인트 설계 (API Endpoint Design)

### 5.1 인증 API

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/v1/auth/register` | 회원가입 |
| POST | `/api/v1/auth/login` | 로그인 (JWT 발급) |
| POST | `/api/v1/auth/refresh` | 토큰 갱신 |
| POST | `/api/v1/auth/verify-employee` | 임직원 인증 |

### 5.2 매장/할인 API

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/stores/nearby?lat={}&lng={}&radius=100` | 주변 매장 조회 |
| GET | `/api/v1/stores/{id}` | 매장 상세 정보 |
| GET | `/api/v1/stores/{id}/discounts` | 매장 할인 정보 |
| GET | `/api/v1/discounts/my` | 내 기업 할인 목록 |

### 5.3 알림 API

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/v1/notifications/geofence-trigger` | 지오펜스 진입 트리거 |
| GET | `/api/v1/notifications/history` | 알림 이력 |
| PUT | `/api/v1/notifications/settings` | 알림 설정 변경 |

### 5.4 사용자 API

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/users/me` | 내 정보 조회 |
| PUT | `/api/v1/users/me` | 내 정보 수정 |
| GET | `/api/v1/users/me/usage-history` | 사용 이력 |
| GET | `/api/v1/users/me/savings` | 절약 금액 통계 |

---

## 6. 개발 단계 (Development Phases)

### Phase 1: MVP (8주)
- **목표**: 핵심 기능 구현 및 사내 테스트
- 사용자 인증 및 임직원 인증 시스템
- Kakao Map 연동 및 주변 매장 표시
- 기본 지오펜싱 (100m 반경)
- 푸시 알림 (FCM)
- 매장/할인 정보 CRUD (Admin)
- 테스트 기업 1~2곳 확보

### Phase 2: 고도화 (8주)
- **목표**: 사용자 경험 개선 및 기능 확장
- 할인 쿠폰 QR 코드 / 바코드 생성
- 사용 이력 및 절약 금액 대시보드
- 매장 리뷰 및 평점 시스템
- 알림 개인화 (시간대, 카테고리 선호)
- 관리자 대시보드 (React) 구축
- 성능 최적화 및 배터리 소모 개선

### Phase 3: 확장 (12주)
- **목표**: 수익화 및 시장 확대
- B2B 프랜차이즈 광고 플랫폼 구축
- 기업 복지 담당자 전용 포털
- 데이터 분석 및 인사이트 리포트
- 제휴 매장 자가 등록 시스템
- 타 복지몰 연동 API
- 해외 확장 준비 (Google Maps 전환)

---

## 7. 수익 모델 (Monetization)

### 7.1 B2B 프랜차이즈 광고 수수료
- **프리미엄 노출**: 매장 검색 결과 상위 노출 월 구독료
- **프로모션 배너**: 앱 내 배너 광고 (CPM / CPC)
- **타겟 푸시**: 특정 사용자 세그먼트 대상 프로모션 푸시 (건당 과금)

### 7.2 기업 구독 모델
- **Basic**: 월 50만원 - 매장 50개까지, 기본 분석
- **Standard**: 월 150만원 - 매장 200개까지, 상세 분석, 맞춤 알림
- **Enterprise**: 월 300만원+ - 무제한 매장, 전용 API, 커스텀 기능

### 7.3 수수료 모델
- 할인 쿠폰 사용 시 거래 금액의 1~3% 수수료
- 신규 제휴 매장 등록 수수료

---

## 8. 특허 전략 (Patent Strategy)

### 8.1 출원 대상
**발명의 명칭**: "위치 기반 복지 할인 매칭 시스템 및 방법"

### 8.2 청구항 핵심 구성
1. 사용자 단말의 GPS 위치 정보를 수신하는 단계
2. 수신된 위치 정보를 기반으로 기 설정된 반경 내 제휴 매장을 검색하는 단계
3. 사용자의 소속 기업 정보와 제휴 매장의 할인 정보를 매칭하는 단계
4. 매칭된 할인 정보를 사용자 단말에 푸시 알림으로 전송하는 단계
5. 사용자의 할인 사용 이력을 기록 및 분석하는 단계

### 8.3 특허 차별점
- 기업 복지와 위치 기반 서비스의 결합
- 지오펜싱 기반의 실시간 할인 매칭 알고리즘
- 임직원 인증 연동 할인 검증 시스템

### 8.4 출원 일정
- 선행 기술 조사: 2주
- 명세서 초안 작성: 3주
- 변리사 검토 및 보정: 2주
- 특허청 출원: 1주

---

## 9. 리스크 및 대응 방안

| 리스크 | 영향도 | 대응 방안 |
|--------|--------|----------|
| 위치 정보 수집 동의 이슈 | 높음 | 명확한 동의 절차, 개인정보 처리방침 |
| 배터리 과다 소모 | 중간 | Significant Location Change 활용 |
| 매장 데이터 정확도 | 높음 | 정기적 데이터 검증, 사용자 신고 시스템 |
| 프랜차이즈 제휴 거부 | 중간 | 초기 무료 제공 후 성과 기반 전환 |
| 경쟁 서비스 등장 | 중간 | 특허 확보, 선점 효과, 데이터 장벽 |

---

## 10. KPI 및 성과 지표

- **MAU** (월간 활성 사용자): 출시 6개월 내 50,000명
- **매장 등록 수**: 1,000개 이상
- **제휴 기업 수**: 50개 이상
- **쿠폰 사용률**: 푸시 수신 대비 15% 이상
- **사용자 절약 금액**: 인당 월 평균 30,000원 이상
- **NPS** (순추천지수): 40 이상
