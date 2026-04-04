# PromoMap - 종합 기획서 & 진행 현황

> 최종 업데이트: 2026-02-07
> 프로젝트 경로: `C:\Users\user\Desktop\biz_life\projects\01-promo-map\`

---

## 1. 프로젝트 개요

**PromoMap**은 직장인을 위한 위치 기반 할인 매장 탐색 서비스입니다.

```
"점심시간에 회사 주변을 걸어가는데,
 내 회사와 제휴된 30% 할인 매장이 바로 옆에 있다면?"
 → PromoMap이 GPS로 자동 감지해서 알려줍니다
```

### 핵심 가치
- 직장인이 모르고 지나치는 복지 할인 혜택을 실시간으로 알려줌
- 회사별 제휴 매장 + 위치 기반 자동 탐색
- 리뷰/평점으로 동료들의 솔직한 후기 확인

### 수익 모델
- 광고 수익 (AdMob 배너/전면/보상형)
- 매장 제휴 수수료
- 기업 B2B 구독
- 프리미엄 구독 (광고 제거)

---

## 2. 전체 시스템 구성

```
┌──────────────────────────────────────────────────────────────┐
│                    사용자 (직장인)                              │
│              Android 앱 / Web 브라우저                         │
└───────────────────────┬──────────────────────────────────────┘
                        │ HTTPS
┌───────────────────────▼──────────────────────────────────────┐
│               Flutter 모바일 앱 (Android/Web)                 │
│  Google Maps + Riverpod + Dio + GoRouter + AdMob             │
│  78개 Dart 파일 | 4,000줄+                                   │
└───────────────────────┬──────────────────────────────────────┘
                        │ REST API (JWT)
┌───────────────────────▼──────────────────────────────────────┐
│               FastAPI 백엔드 서버                             │
│  20+ API 엔드포인트 | 52개 Python 파일                        │
│  SQLite(로컬) / PostgreSQL(프로덕션)                          │
├──────────────────────────────────────────────────────────────┤
│  관리자 웹 대시보드 (Jinja2 HTML)                             │
│  매장/할인/기업/회원 CRUD | 통계 대시보드                      │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. 진행 현황 (Phase별)

### Phase 0: 개발 환경 ✅ 완료

| 항목 | 위치 | 버전 | 상태 |
|------|------|------|------|
| Flutter SDK | `D:\dev\flutter` | 3.38.9 (Dart 3.10.8) | ✅ |
| Android SDK | `D:\dev\android-sdk` | Platform 34, 35, 36 | ✅ |
| OpenJDK | `D:\dev\jdk17` | 17.0.13 | ✅ |
| 백엔드 (FastAPI) | `backend/` | Python 3.13 | ✅ 이미 완성 |
| 관리자 대시보드 | `templates/admin/` | Jinja2 HTML | ✅ 이미 완성 |

### Phase 1: Flutter 앱 코어 ✅ 완료

| 카테고리 | 파일 수 | 내용 |
|----------|---------|------|
| 앱 설정 | 4개 | constants, theme, routes, app |
| 데이터 모델 | 12개 | 백엔드 스키마 1:1 매칭 |
| 네트워크 | 3개 | Dio + JWT 인터셉터 + 에러 처리 |
| API 클래스 | 7개 | auth, store, discount, favorite, review, user, notification |
| 리포지토리 | 7개 | API를 감싸는 중간 관리자 |
| 저장소/유틸 | 5개 | SecureStorage, Preferences, Validators, Formatters, Debouncer |

### Phase 2: 상태 관리 (Riverpod) ✅ 완료

| Provider | 역할 |
|----------|------|
| AuthProvider | 로그인/회원가입/로그아웃/토큰 자동 갱신 |
| StoreProviders | 주변 매장, 검색, 상세, 카테고리 필터 |
| FavoritesProvider | 즐겨찾기 토글 (낙관적 업데이트) |
| ReviewProviders | 리뷰 목록, 리뷰 작성 |
| UserProviders | 프로필, 사용 내역 |
| LocationProvider | GPS 위치 + 권한 관리 |
| DiscountProviders | 활성 할인 목록 |
| NotificationProviders | 지오펜스 알림 확인 |

### Phase 3: UI 화면 + 위젯 ✅ 완료

**화면 10개:**

| # | 화면 | 설명 |
|---|------|------|
| 1 | SplashScreen | 로고 + 자동 로그인 체크 |
| 2 | ShellScreen | 4탭 하단 네비게이션 (지도/검색/즐겨찾기/MY) |
| 3 | MapScreen | Google Maps + 매장 마커 + 드래그 시트 |
| 4 | SearchScreen | 키워드 검색 + 결과 리스트 + 배너 광고 |
| 5 | FavoritesScreen | 즐겨찾기 목록 + 배너 광고 |
| 6 | MypageScreen | 프로필 + 통계 + 메뉴 + 로그아웃 |
| 7 | StoreDetailScreen | 매장 상세 + 할인 + 리뷰 + 전면/배너 광고 |
| 8 | EditProfileScreen | 이름/전화번호 수정 |
| 9 | UsageHistoryScreen | 할인 사용 이력 리스트 |
| 10 | SettingsScreen | 알림 ON/OFF + 검색 반경 슬라이더 |

**위젯 21개:**

| 카테고리 | 위젯 |
|----------|------|
| 공통 (7개) | AppLoading, AppError, AppEmpty, AppToast, SkeletonLoading, PrimaryButton, BannerAdWidget |
| 매장 (4개) | StoreCard, StoreMarkerInfo, DiscountBadge, CategoryChip+Bar |
| 리뷰 (3개) | ReviewCard, StarRating, ReviewForm |
| 인증 (3개) | AuthModal, LoginForm, RegisterForm |
| 즐겨찾기 (2개) | FavoriteCard, FavoriteToggle |
| 광고 (2개) | BannerAdWidget, (AdManager - 전면 광고) |

### Phase 4: 플랫폼 설정 ✅ 완료

| 항목 | 상태 |
|------|------|
| AndroidManifest.xml (위치 권한, Maps키, AdMob ID) | ✅ |
| build.gradle.kts (com.promomap.app, minSdk 21) | ✅ |
| 백엔드 CORS (Android 에뮬레이터 10.0.2.2) | ✅ |
| 개인정보처리방침 HTML | ✅ |
| 스토어 등록 메타데이터 | ✅ |

### Phase 5: 서버 배포 설정 ✅ 완료

| 항목 | 상태 |
|------|------|
| Dockerfile.promomap (Python 3.13 + Gunicorn) | ✅ |
| docker-compose.yml (PostgreSQL + API) | ✅ |
| database.py (SQLite/PostgreSQL 자동 전환) | ✅ |
| requirements.txt (psycopg2 + gunicorn 추가) | ✅ |
| DEPLOY.md (Railway/Fly.io 배포 가이드) | ✅ |

### Phase 6: 광고 수익화 (AdMob) ✅ 완료

| 항목 | 상태 |
|------|------|
| google_mobile_ads 패키지 설치 | ✅ |
| AdHelper (광고 ID 관리) | ✅ |
| AdManager (전면 광고 관리) | ✅ |
| BannerAdWidget (재사용 배너) | ✅ |
| 검색/즐겨찾기/상세 화면 배너 광고 | ✅ |
| 매장 상세 3회 조회 시 전면 광고 | ✅ |
| MobileAds 초기화 (main.dart) | ✅ |

### 코드 품질 ✅

```
flutter analyze 결과: 에러 0개, 경고 0개
백엔드 API 테스트: 20개 엔드포인트 전부 통과
웹 서버 모드 테스트: 정상 실행 확인
```

---

## 4. 코드 통계

| 구분 | 파일 수 | 코드 라인 |
|------|---------|----------|
| Flutter 앱 (Dart) | ~78개 | ~4,000줄 |
| 백엔드 (Python) | ~52개 | ~3,500줄 |
| 웹 프론트엔드 (HTML/JS/CSS) | ~17개 | ~2,000줄 |
| 설정/문서 | ~15개 | - |
| **합계** | **~162개** | **~9,500줄** |

---

## 5. 남은 작업 (사용자 액션 필요)

### 즉시 해야 하는 것 (출시 전)

| # | 작업 | 비용 | 소요 시간 |
|---|------|------|----------|
| 1 | Google Maps API 키 발급 | 무료 | 30분 |
| 2 | Google AdMob 가입 + 광고 ID 발급 | 무료 | 30분 |
| 3 | Google Play 개발자 계정 | $25 일회성 | 30분 |
| 4 | 앱 아이콘 이미지 준비 (512x512) | 무료~5만원 | 1시간 |
| 5 | 백엔드 서버 배포 (Railway/Fly.io) | 월 $5~ | 2시간 |
| 6 | 도메인 + HTTPS | 연 $10~15 | 1시간 |
| 7 | 에뮬레이터/실기기 테스트 | 무료 | 2시간 |
| 8 | keystore 생성 + AAB 빌드 | 무료 | 30분 |
| 9 | Play Console 등록 + 스크린샷 | 무료 | 2시간 |

**최소 비용: 초기 ~$40 + 월 $5~**

### 나중에 하면 좋은 것 (성장 단계)

| # | 작업 | 설명 |
|---|------|------|
| 1 | Firebase FCM 푸시 알림 | 주변 할인 실시간 알림 |
| 2 | 위치기반서비스 사업자 신고 | 방통위 (한국 법률) |
| 3 | Sentry/Crashlytics 에러 모니터링 | 앱 오류 추적 |
| 4 | iOS 출시 | Apple Developer $99/년 |
| 5 | 다국어 지원 | 영어/일어 |
| 6 | 오프라인 모드 | 매장 정보 로컬 캐시 |

---

## 6. 문서 목록

| 문서 | 위치 | 설명 |
|------|------|------|
| 종합 기획서 (이 문서) | `PROJECT_STATUS.md` | 전체 진행 현황 |
| 구조 설명서 | `ARCHITECTURE.md` | 쉽게 이해하는 앱 구조 |
| 향후 계획서 | `ROADMAP.md` | 출시 + 수익화 로드맵 |
| 배포 가이드 | `DEPLOY.md` | Docker/Railway/Fly.io 배포 |
| 원본 기획서 | `docs/PROJECT_PLAN.md` | 초기 사업 기획 |
| 스토어 메타데이터 | `flutter_app/store_metadata.md` | Play Store 등록 정보 |
| 개인정보처리방침 | `flutter_app/assets/privacy_policy.html` | 법적 문서 |




## 국토교통부_토지 매매 실거래가 자료
일반 인증키 : ee0c43d647676d21bfea7d2751d0820592206d7dfe7c35d8b5e11ea3d13618f8
