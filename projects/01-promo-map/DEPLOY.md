# PromoMap 배포 가이드

## 목차
1. [Docker Compose 로컬 테스트](#1-docker-compose-로컬-테스트)
2. [Railway.app 배포](#2-railwayapp-배포)
3. [Fly.io 배포](#3-flyio-배포)
4. [환경 변수](#4-환경-변수)
5. [도메인 + HTTPS 설정](#5-도메인--https-설정)
6. [Flutter 앱 프로덕션 설정](#6-flutter-앱-프로덕션-설정)

---

## 1. Docker Compose 로컬 테스트

PostgreSQL + PromoMap API를 로컬에서 한번에 실행합니다.

### 사전 준비
- Docker Desktop 설치 (Windows/Mac)
- 프로젝트 루트: `biz_life/`

### 실행

```bash
# biz_life/ 루트에서 실행
cd C:\Users\user\Desktop\biz_life

# 빌드 및 실행
docker compose up --build

# 백그라운드 실행
docker compose up --build -d

# 로그 확인
docker compose logs -f promomap-api

# 종료
docker compose down

# DB 볼륨까지 삭제 (초기화)
docker compose down -v
```

### 접속 확인
- API: http://localhost:8000
- Health check: http://localhost:8000/api/health
- PostgreSQL: localhost:5432 (user: promomap / password: promomap_dev_2024)

### 환경 변수 오버라이드

`.env` 파일을 `biz_life/` 루트에 생성:

```env
DB_PASSWORD=my_secure_password
JWT_SECRET_KEY=my-jwt-secret-key-production
ADMIN_SESSION_SECRET=my-admin-session-secret
CORS_ORIGINS=http://localhost:8000
LOG_LEVEL=DEBUG
```

---

## 2. Railway.app 배포

Railway는 GitHub 레포 연결로 자동 배포를 지원합니다.

### 사전 준비
- GitHub에 `biz_life/` 전체를 push
- Railway 계정 생성 (https://railway.app)

### 단계별 배포

#### A. PostgreSQL 추가
1. Railway 대시보드 > New Project > Provision PostgreSQL
2. PostgreSQL 서비스 생성 후 `DATABASE_URL` 자동 생성됨

#### B. 백엔드 서비스 추가
1. New Service > GitHub Repo 연결
2. Settings에서 설정:
   - **Root Directory**: (비워둠 - biz_life 루트 사용)
   - **Dockerfile Path**: `Dockerfile.promomap`
   - **Watch Paths**: `shared/**`, `projects/01-promo-map/**`

#### C. 환경 변수 설정
Railway 대시보드 > Variables 탭:

```
DATABASE_URL        = (PostgreSQL 서비스에서 자동 참조: ${{Postgres.DATABASE_URL}})
JWT_SECRET_KEY      = (랜덤 문자열 생성: openssl rand -hex 32)
ADMIN_SESSION_SECRET = (랜덤 문자열 생성: openssl rand -hex 32)
CORS_ORIGINS        = https://your-domain.railway.app
LOG_LEVEL           = INFO
PORT                = 8000
```

#### D. 배포 확인
- Railway가 자동으로 빌드 및 배포
- Deploy Logs에서 진행 상황 확인
- 생성된 URL로 접속: `https://your-project.up.railway.app`

### Railway CLI 사용 (선택)

```bash
npm install -g @railway/cli
railway login
railway link
railway up
```

---

## 3. Fly.io 배포

### 사전 준비

```bash
# Fly CLI 설치
# Windows: powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
# Mac: brew install flyctl

fly auth login
```

### 단계별 배포

#### A. 앱 생성

```bash
cd C:\Users\user\Desktop\biz_life
fly launch --dockerfile Dockerfile.promomap --name promomap-api --region nrt --no-deploy
```
- `nrt`: 도쿄 리전 (한국에서 가장 가까움)
- `--no-deploy`: 설정만 하고 배포는 나중에

#### B. PostgreSQL 추가

```bash
fly postgres create --name promomap-db --region nrt
fly postgres attach promomap-db --app promomap-api
```
- attach 시 `DATABASE_URL`이 자동으로 환경 변수에 추가됨

#### C. 환경 변수 설정

```bash
fly secrets set \
  JWT_SECRET_KEY="$(openssl rand -hex 32)" \
  ADMIN_SESSION_SECRET="$(openssl rand -hex 32)" \
  CORS_ORIGINS="https://promomap-api.fly.dev" \
  LOG_LEVEL="INFO" \
  --app promomap-api
```

#### D. 배포

```bash
fly deploy --app promomap-api
```

#### E. 상태 확인

```bash
fly status --app promomap-api
fly logs --app promomap-api

# Health check
curl https://promomap-api.fly.dev/api/health
```

---

## 4. 환경 변수

| 변수명 | 필수 | 기본값 | 설명 |
|--------|------|--------|------|
| `DATABASE_URL` | O (프로덕션) | SQLite (로컬) | PostgreSQL 연결 문자열 |
| `JWT_SECRET_KEY` | O | - | JWT 토큰 서명 키 |
| `ADMIN_SESSION_SECRET` | O | - | 관리자 세션 암호화 키 |
| `CORS_ORIGINS` | X | localhost | 허용할 Origin (콤마 구분) |
| `LOG_LEVEL` | X | INFO | 로깅 레벨 (DEBUG/INFO/WARNING/ERROR) |
| `PORT` | X | 8000 | 서버 포트 (Railway가 자동 설정) |

### 시크릿 생성 예시

```bash
# Linux/Mac
openssl rand -hex 32

# PowerShell
-join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) })

# Python
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 5. 도메인 + HTTPS 설정

### Railway 커스텀 도메인
1. Railway 대시보드 > Settings > Domains
2. "Add Custom Domain" 클릭
3. DNS에 CNAME 레코드 추가:
   ```
   Type: CNAME
   Name: api (또는 promomap)
   Value: your-project.up.railway.app
   ```
4. Railway가 자동으로 SSL 인증서 발급

### Fly.io 커스텀 도메인

```bash
fly certs create api.your-domain.com --app promomap-api
```

DNS 설정:
```
Type: CNAME
Name: api
Value: promomap-api.fly.dev
```

### CORS 업데이트 (중요)

커스텀 도메인 설정 후 환경 변수를 반드시 업데이트:

```bash
# Railway: 대시보드 Variables에서 수정
CORS_ORIGINS=https://api.your-domain.com,https://your-domain.com

# Fly.io
fly secrets set CORS_ORIGINS="https://api.your-domain.com,https://your-domain.com"
```

---

## 6. Flutter 앱 프로덕션 설정

Flutter 앱의 API 엔드포인트를 프로덕션 서버로 변경해야 합니다.

### .env.prod 파일 생성

`flutter_app/.env.prod`:
```env
API_BASE_URL=https://api.your-domain.com
# 또는 Railway/Fly.io 기본 도메인:
# API_BASE_URL=https://your-project.up.railway.app
# API_BASE_URL=https://promomap-api.fly.dev
```

### 프로덕션 빌드

```bash
cd flutter_app

# Android APK
flutter build apk --dart-define-from-file=.env.prod

# iOS
flutter build ios --dart-define-from-file=.env.prod

# Web
flutter build web --dart-define-from-file=.env.prod
```

### 주의사항
- 프로덕션 API URL에는 반드시 HTTPS 사용
- Flutter 앱에서 HTTP를 사용하면 Android/iOS에서 기본 차단됨
- CORS_ORIGINS에 Flutter Web 빌드가 호스팅되는 도메인도 추가 필요
