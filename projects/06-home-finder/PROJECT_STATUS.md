# HomeFinder v3.0 - 프로젝트 현황

**최종 업데이트**: 2026-04-04

## 개요
마지막 집 찾기 - 부동산 매물 검색 + 분석 플랫폼.
서울 25개구 + 경기도 근교 14개 시/구의 아파트 매물을 **국토부 실거래가 API**로 수집하고,
4차원 채점 시스템 + **가격 적정성 분석**으로 평가. 카카오맵 시각화 + 필터 검색 + 후보 관리 제공.

## 기술 스택
- **Backend**: Python 3.13, FastAPI (포트 8006)
- **DB**: SQLAlchemy + SQLite
- **Frontend**: Jinja2 + 카카오맵 API + Chart.js
- **스케줄러**: APScheduler (자동 데이터 수집)
- **데이터 수집**: PublicDataReader (국토부 실거래가 API)
- **외부 접속**: Cloudflare Tunnel (핸드폰/외부 기기)
- **알림**: Telegram Bot (선택)

## 실행 방법
```bash
# 원클릭 시작 (서버 + Cloudflare Tunnel)
start.bat

# 또는 수동 실행
cd projects/06-home-finder
pip install -r requirements.txt
python main.py
# -> http://localhost:8006

# 핸드폰 접속 (별도 CMD 창에서)
cloudflared tunnel --url http://localhost:8006
# -> https://xxx.trycloudflare.com
```

### 다른 PC에서 설치
```bash
git clone git@github.com:porganzy-jpg/biz_life.git
cd biz_life/projects/06-home-finder
pip install -r requirements.txt
copy .env.example .env    # API 키 입력
start.bat                 # 서버 + 터널 시작
```

## 파일 구조
```
06-home-finder/
├── backend/
│   ├── api/v1/               # API 라우터 (15개)
│   │   ├── dashboard.py      # 대시보드 API (건물/토지/실거래 통계)
│   │   ├── properties.py     # 매물 API + 가격 적정성 분석
│   │   ├── collector.py      # [NEW] 데이터 수집 관리 API
│   │   ├── search.py         # 검색 API (토지 필터 추가)
│   │   ├── candidates.py     # 후보 관리
│   │   ├── transactions.py   # 실거래가 추이 API
│   │   └── analysis.py       # 지역 분석
│   ├── models/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   │   ├── price_analyzer.py # [NEW] 가격 적정성 분석 (3단계 매칭)
│   │   └── scoring_service.py # 채점 (실거래 데이터 우선)
│   ├── main.py               # FastAPI 앱
│   ├── database.py
│   ├── config.py
│   └── seed_data.py          # 시드 데이터 자동 로드
├── scoring/
│   ├── composite_scorer.py    # 통합 채점 (건물/토지 분기)
│   ├── price_scorer.py        # 가격 채점 (실거래 비교 통합)
│   └── land_property_scorer.py # 토지 전용 5차원 채점
├── collectors/               # 5개 데이터 수집기
│   ├── molit_collector.py    # [UPGRADED] 국토부 실거래가 (서울+경기)
│   ├── naver_collector.py    # 네이버 부동산
│   ├── auction_collector.py  # 법원 경매
│   ├── subscription_collector.py # 청약홈
│   └── kb_index_collector.py # KB 시세 지수
├── scheduler/
│   └── scheduler.py          # APScheduler 10개 작업 자동 실행
├── templates/                # 12개 Jinja2 페이지
├── static/                   # CSS, JS
├── start.bat                 # [NEW] 원클릭 시작 스크립트
├── collect_real_data.py      # 시드 데이터 생성
└── PROJECT_STATUS.md
```

## 페이지 (12개)

| 페이지 | 경로 | 설명 |
|--------|------|------|
| 대시보드 | `/` | 통계 카드 + 실거래 추이 차트 + 정렬 가능 매물 테이블 |
| 내 조건 검색 | `/search` | 10+ 필터, 건물/토지 분류별 동적 UI |
| 지도 | `/map` | 카카오맵, 점수 마커 + 후보 별마커 + 실거래 요약 + 정렬 |
| 후보관리 | `/candidates` | 칸반 파이프라인 |
| 지역분석 | `/analysis` | 구별/동별 통계 + 실거래 기반 실시간 통계 |
| 매물상세 | `/property/{id}` | 프리미엄 리디자인 + 가격 적정성 분석 + 미니맵 |
| 매물등록 | `/property/new/land` | 토지/건물 등록 폼 |
| 경매 | `/auctions` | 법원 경매 물건 |
| 청약 | `/subscriptions` | 청약 정보 |
| 추천 | `/recommendations` | TOP 매칭 (선호도/알림 준비 중) |
| 스크래퍼 | `/scraper` | 데이터 수집 관리 |
| API 문서 | `/docs` | Swagger UI |

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/dashboard/summary` | 대시보드 요약 (실거래 통계 포함) |
| GET | `/api/v1/dashboard/map-markers` | 지도 마커 (매물 + 실거래 요약) |
| GET | `/api/v1/properties/` | 매물 목록 |
| GET | `/api/v1/properties/{id}` | 매물 상세 |
| GET | `/api/v1/properties/{id}/price-analysis` | **[NEW] 가격 적정성 분석** |
| GET | `/api/v1/transactions/trend` | **실거래 추이** |
| POST | `/api/v1/collector/run/{name}` | **[NEW] 수동 수집 트리거** |
| GET | `/api/v1/collector/scheduler/status` | **[NEW] 스케줄러 상태** |
| GET | `/api/v1/areas/realtime-stats` | **[NEW] 실거래 기반 지역 통계** |

## 데이터 수집 파이프라인 (v3.0)

### 국토부 실거래가 API 연동
- **API 키**: 공공데이터포털 발급 (`.env`에 설정)
- **수집 범위**: 서울 25개구 + 경기 14개 시/구 = **39개 지역**
- **현재 데이터**: 매물 419건 + 실거래 4,369건
- **자동 수집**: 매일 06:00 (APScheduler)

### 자동 수집 스케줄
| 수집기 | 주기 | 시간 |
|--------|------|------|
| 국토부 실거래가 | 매일 | 06:00 |
| 네이버 부동산 | 매 6시간 | - |
| 법원 경매 | 매일 | 08:00 |
| 청약홈 | 월/목 | 09:00 |
| KB 시세지수 | 매주 월 | 07:00 |

### 에러 처리
- 전체 API 실패 시 RuntimeError (로그에 실패로 기록)
- 500건 배치 커밋 (대량 데이터 안전)
- 파싱 에러 90%+ 시 CRITICAL 로그
- DB 커밋 실패 시 rollback + 에러 전파

## 가격 적정성 분석 (v3.0 신규)

### 3단계 매칭 시스템
| 레벨 | 비교 기준 | 정확도 |
|------|----------|--------|
| 1단계 | 같은 단지 + 비슷한 면적(±10㎡) | 최고 |
| 2단계 | 같은 동 + 비슷한 면적 | 중간 |
| 3단계 | 같은 구 + 비슷한 면적 | 참고 |

### 판정 기준
| 시세 대비 | 판정 | 점수 |
|-----------|------|------|
| -10% 이하 | 급매/저평가 | 100 |
| -5% ~ -10% | 저렴 | 85 |
| ±5% | 적정가 | 65 |
| +5% ~ +10% | 다소 비쌈 | 35 |
| +10% 이상 | 고평가 | 20 |

### 채점 시스템 개선
- 기존: 하드코딩된 지역 평균가 기반
- **v3.0**: 실거래 평균가 우선 사용 (DB에서 실시간 계산)

## 지도 기능 (v3.0 강화)

### 마커 시스템
| 마커 | 색상 | 표시 |
|------|------|------|
| 일반 매물 | 점수별 (초록/파랑/주황/빨강) | 점수 숫자 |
| 후보 매물 | 주황 + ★ | 점수 + 별 |
| 토지 | 초록 | 점수 숫자 |
| 실거래 요약 | 보라 | 거래 건수 |

### 기능
- 점수/가격/면적 기준 정렬 (오름/내림차순)
- 후보 매물만 보기 필터
- 매물 상세 → 지도 위치 자동 이동
- 대시보드 → 지도 위치 이동
- 매물 상세 미니맵

## 4차원 채점 시스템

### 건물 채점
위치(35%) + 가격(25%) + 매물(20%) + 지역(20%)

### 토지 채점
용도지역(30%) + 건축가능성(25%) + 접도(20%) + 지형(15%) + 면적(10%)

## 주요 기능 체크리스트
- [x] 매물 검색 + 10개 필터
- [x] 4차원 채점 시스템 (건물+토지)
- [x] **국토부 실거래가 API 연동 (서울+경기 39개 지역)**
- [x] **가격 적정성 분석 (3단계 매칭)**
- [x] **자동 수집 스케줄러 (10개 작업)**
- [x] **점수 표시 카카오맵 마커**
- [x] **후보 매물 지도 강조 (별 마커)**
- [x] **매물 상세 → 지도 위치 이동**
- [x] **대시보드 실거래 추이 차트**
- [x] **테이블/사이드바 정렬 기능**
- [x] **매물 상세 프리미엄 리디자인**
- [x] **서버 시작 시 시드 데이터 자동 로드**
- [x] **Cloudflare Tunnel 핸드폰 접속**
- [x] **원클릭 시작 스크립트 (start.bat)**
- [x] 카카오맵 시각화 (건물+토지+실거래 마커)
- [x] 후보 관리 (칸반)
- [x] 조건 저장/불러오기
- [x] 대시보드 (건물/토지/실거래 통계)
- [x] 토지 등록/수정 CRUD UI

## 향후 과제
- [ ] 네이버 부동산 실시간 매물 크롤링
- [ ] 텔레그램 알림 (새 매물, 가격 변동)
- [ ] 매물 비교 기능 (2~3개 나란히)
- [ ] 추천/선호도 학습 기능 구현
- [ ] 토지 투자 수익률 시뮬레이션
- [ ] 위성 지도 오버레이 (필지 경계)
- [ ] Cloudflare Named Tunnel (고정 URL)

## 버전 히스토리
| 버전 | 날짜 | 주요 변경 |
|------|------|----------|
| v1.0 | 2026-02-16 | 기본 기능 완료 + 내 조건 검색 페이지 |
| v1.5 | 2026-02-17 | 토지 매물 전체 기능 추가 (DB+API+채점+UI) |
| v2.0 | 2026-02-18 | 토지 등록/수정 CRUD UI + 검색필터 강화 |
| **v3.0** | **2026-04-04** | **국토부 실거래 API 연동, 가격 적정성 분석, 점수 마커 지도, 서울+경기 확장, 매물 상세 리디자인, 자동 수집 스케줄러, Cloudflare Tunnel** |
