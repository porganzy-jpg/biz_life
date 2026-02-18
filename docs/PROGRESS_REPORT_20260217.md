# 진행 보고서 - 2026-02-17

## 요약
서버 인프라 구축 + 기존 프로젝트 환경 정비 + HomeFinder 토지 기능 대규모 업데이트

## 신규: 00-ServerMonitor (통합 서버 모니터링)

### 개요
노트북을 홈서버로 운영하기 위한 통합 관리 시스템.

### 구현 내용
1. **FastAPI 웹 대시보드** (포트 9000)
   - 시스템 리소스 실시간 모니터링 (CPU, RAM, Disk)
   - 6개 프로젝트 상태 확인 + 시작/중지/재시작 제어
   - 30초 자동 새로고침, 로그 뷰어

2. **텔레그램 관리 봇**
   - 8개 명령어 (status, system, begin, stop, restart, logs, panel)
   - 인라인 키보드 제어 패널
   - Chat ID 기반 인증

3. **인프라**
   - `startup_all.bat`: 전체 프로젝트 일괄 시작
   - `setup_firewall.bat`: Windows 방화벽 포트 개방

### 파일
- `app.py` (323줄), `bot.py` (295줄), `config.py` (45줄)

---

## 04-CryptoBot: 환경 정비

### 변경 내용
1. **requirements.txt**: 정확 버전 → 범위 버전 (`pandas>=2.0,<3.0` 등)
2. **start_bot.bat**: 경로 수정 (`user` → `itzia`), Cloudflare Tunnel 분리

---

## 05-StockBot: 실전 전환

### 변경 내용
1. **포트 변경**: 8081 → 8082 (CryptoBot과 충돌 해소)
2. **실전 모드 전환**: `paper_trading=True` → `paper_trading=False`
3. **requirements.txt**: 범위 버전으로 유연화

---

## 06-HomeFinder: 토지 매물 기능 (v1.5)

### 개요
건물(아파트/빌라)만 지원하던 HomeFinder에 **토지 매물** 전체 기능 추가.

### 구현 상세 (17개 파일, +579줄)

**Backend:**
- DB 모델에 토지 7개 컬럼 추가 (지목, 용도지역, 건폐율, 용적률, 접도, 지형 + 인덱스)
- Pydantic 스키마에 토지 필드 추가 (Create, Update, Response, Brief)
- PropertyType enum에 "토지" 추가
- 검색 API에 토지 전용 필터 5개 추가 (category, land_uses, zoning_types, min_bcr, min_far)
- 대시보드 API에 건물/토지 카운트 분리
- 매물 API에 토지 필드 포함

**Scoring:**
- `LandPropertyScorer` 신규 구현 (5차원: 용도지역 30% + 건축가능성 25% + 접도 20% + 지형 15% + 면적 10%)
- `CompositeScorer`에서 건물/토지 자동 분기

**Frontend:**
- 지도: 토지 초록색 "T" 마커, 건물/토지 필터 드롭다운
- 검색: 건물/토지 분류 선택 시 필터 동적 전환 (건물→연식/층수/향, 토지→지목/용도지역/건폐율)
- 상세: 토지/건물별 다른 정보 테이블
- 대시보드: 건물 X건 / 토지 X건 표시

**데이터:**
- 서울 9개구 실제 토지 15건 시드 데이터 추가 (마포, 용산, 성동, 광진, 영등포, 동작, 강동, 은평, 강서, 노원)

---

## 02-BarcodeQuest: 기획 확장

### 추가 문서
- `docs/midjourney-prompt-guide.md`: Midjourney 컨셉아트 프롬프트 가이드
- `tools/`: 게임 개발 도구

---

## SSH 설정
- `~/.ssh/known_hosts` 생성 (GitHub SSH 연결)

---

## 통계

| 항목 | 수치 |
|------|------|
| 변경된 파일 | 23개 |
| 새로 추가된 파일 | 8개+ |
| 코드 변경 | +579줄 / -89줄 |
| 신규 프로젝트 | 1개 (00-ServerMonitor) |
| 총 프로젝트 | 8개 (6개 사업 + 서버모니터 + 소설) |
