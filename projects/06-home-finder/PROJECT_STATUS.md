# HomeFinder v1.5 - 프로젝트 현황

**최종 업데이트**: 2026-02-17

## 개요
마지막 집 찾기 - 부동산 매물 검색 + 분석 플랫폼. 건물(아파트/빌라)과 **토지** 매물을 4차원 채점 시스템으로 평가하고, 카카오맵 시각화 + 필터 검색 + 후보 관리를 제공.

## 기술 스택
- **Backend**: Python 3.13, FastAPI (포트 8006)
- **DB**: SQLAlchemy + SQLite
- **Frontend**: Jinja2 + 카카오맵 API + Chart.js
- **스케줄러**: APScheduler (자동 데이터 수집)
- **알림**: Telegram Bot

## 실행 방법
```bash
cd projects/06-home-finder
python main.py
# -> http://localhost:8006
```

## 파일 구조
```
06-home-finder/
├── backend/
│   ├── api/v1/               # API 라우터
│   │   ├── dashboard.py      # 대시보드 API (건물/토지 분류)
│   │   ├── properties.py     # 매물 API (토지 필드 포함)
│   │   ├── search.py         # 검색 API (토지 필터 추가)
│   │   ├── candidates.py     # 후보 관리
│   │   └── analysis.py       # 지역 분석
│   ├── models/
│   │   └── property.py       # Property 모델 (토지 7개 컬럼 추가)
│   ├── schemas/
│   │   ├── common.py         # PropertyType: 아파트/빌라/오피스텔/토지
│   │   ├── property.py       # 토지 필드 포함 Pydantic 스키마
│   │   └── search.py         # 토지 검색 필터 스키마
│   ├── repositories/         # 데이터 접근
│   ├── services/             # 비즈니스 로직
│   ├── main.py               # FastAPI 앱
│   ├── database.py
│   ├── config.py
│   └── seed_data.py          # 160건 시드 데이터
├── scoring/
│   ├── __init__.py            # 스코어러 export
│   ├── composite_scorer.py    # 통합 채점 (건물/토지 분기)
│   └── land_property_scorer.py # [NEW] 토지 전용 5차원 채점
├── collectors/               # 5개 데이터 수집기
├── templates/                # 7개 Jinja2 페이지
├── static/                   # CSS, JS
├── collect_real_data.py      # 시드 데이터 생성 (건물 + 토지)
└── PROJECT_STATUS.md
```

## 페이지 (7개)

| 페이지 | 경로 | 설명 |
|--------|------|------|
| 대시보드 | `/` | 통계 (건물/토지 분리), 지도, 최근 매물 |
| 내 조건 검색 | `/search` | 10+ 필터, 건물/토지 분류별 동적 UI |
| 지도 | `/map` | 카카오맵, 건물(파란)/토지(초록) 마커 |
| 후보관리 | `/candidates` | 칸반 파이프라인 |
| 지역분석 | `/analysis` | 구별/동별 통계 |
| 매물상세 | `/property/{id}` | 건물/토지별 다른 정보 표시 |
| API 문서 | `/docs` | Swagger UI |

## API 엔드포인트 (10개+)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/dashboard/summary` | 대시보드 요약 (건물/토지 카운트) |
| GET | `/api/v1/dashboard/map-markers` | 지도 마커 (토지 필드 포함) |
| GET | `/api/v1/properties/` | 매물 목록 |
| GET | `/api/v1/properties/{id}` | 매물 상세 |
| POST | `/api/v1/search/execute` | 검색 실행 (토지 필터 포함) |
| POST | `/api/v1/search/save` | 검색 조건 저장 |
| GET | `/api/v1/candidates/` | 후보 목록 |
| POST | `/api/v1/candidates/` | 후보 추가 |
| PATCH | `/api/v1/candidates/{id}` | 후보 상태 변경 |

## 토지 매물 기능 (v1.5 신규, 2026-02-17)

### DB 모델 확장 (7개 컬럼 추가)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| `land_use` | String | 지목 (대, 전, 답, 임야, 잡종지) |
| `zoning_type` | String | 용도지역 (제1종/제2종일반주거, 준주거 등) |
| `building_coverage_ratio` | Float | 건폐율 (%) |
| `floor_area_ratio` | Float | 용적률 (%) |
| `road_frontage` | String | 접도 (맹지, 4m미만, 4~6m, 6~8m, 8m이상) |
| `topography` | String | 지형 (평지, 완경사, 경사) |

### 토지 전용 5차원 채점 (LandPropertyScorer)
| 항목 | 비중 | 기준 |
|------|------|------|
| 용도지역 적합성 | 30% | 주거지역 우수 (제2종일반 100점) |
| 건축 가능성 | 25% | 건폐율+용적률 복합 평가 |
| 접도 상태 | 20% | 8m이상(100) → 맹지(10) |
| 지형 | 15% | 평지(100) → 경사(45) |
| 면적 적정성 | 10% | 200~500m² 최적 |

### 토지 검색 필터 (Search API)
- `property_category`: 건물/토지/전체
- `land_uses`: 지목 필터 (복수 선택)
- `zoning_types`: 용도지역 필터
- `min_bcr`: 최소 건폐율
- `min_far`: 최소 용적률

### 프론트엔드
- **지도**: 토지는 초록색 "T" 마커 + 토지 전용 인포윈도우
- **검색**: 건물/토지 분류 선택 시 동적 필터 전환
- **상세**: 토지/건물별 다른 정보 테이블 + 레이더 차트

### 시드 데이터
- 건물 160건 + **토지 15건** (서울 9개구 실제 데이터 기반)

## 4차원 채점 시스템

### 건물 채점
위치(35%) + 가격(25%) + 매물(20%) + 지역(20%)

### 토지 채점
용도지역(30%) + 건축가능성(25%) + 접도(20%) + 지형(15%) + 면적(10%)

## 데이터 수집기 (5개)
1. 네이버 부동산 크롤러
2. 국토부 실거래가 (공공데이터)
3. 경매 데이터 (공공데이터)
4. 청약 데이터 (공공데이터)
5. KB 시세 지수

## 주요 기능 체크리스트
- [x] 매물 검색 + 10개 필터
- [x] 4차원 채점 시스템 (건물)
- [x] **토지 전용 5차원 채점 시스템**
- [x] **토지 DB 스키마 + API + 검색 필터**
- [x] **토지/건물 분류별 동적 UI**
- [x] 카카오맵 시각화 (건물+토지 마커)
- [x] 후보 관리 (칸반)
- [x] 조건 저장/불러오기
- [x] 시드 데이터 175건 (건물 160 + 토지 15)
- [x] 대시보드 (건물/토지 통계)

## 향후 과제
- [ ] 네이버 부동산 실제 크롤링 연동
- [ ] 토지 실거래가 수집 (국토부 API)
- [ ] 토지 경매 데이터 통합
- [ ] 매물 비교 기능 (2~3개 비교)
- [ ] 텔레그램 알림 (새 매물, 가격 변동)
- [ ] 토지 투자 수익률 시뮬레이션
- [ ] 위성 지도 오버레이 (필지 경계)

## 버전 히스토리
| 버전 | 날짜 | 주요 변경 |
|------|------|----------|
| v1.0 | 2026-02-16 | 기본 기능 완료 + 내 조건 검색 페이지 |
| **v1.5** | **2026-02-17** | **토지 매물 전체 기능 추가 (DB+API+채점+UI)** |
