# 16-life-archive — 나의 아카이브 (개인용 0단계)

나를 만든 영화·책·만화·게임·음악·장소·사건을 여러 DB에서 찾아 "그때의 나"와 함께 나이 축 위에 쌓는 개인 앱.
기획안: https://claude.ai/code/artifact/2ac0d0dc-c296-4bb2-8ddd-be18c2108f8a

## 실행
`start.bat` 또는 `python app.py` → http://localhost:8016
인증이 없어서 기본은 이 PC(127.0.0.1)에서만 열린다. 폰에서 쓰려면 `.env`에 `HOST=0.0.0.0`과 `ALLOWED_HOSTS=<이 PC의 IP>`(같은 와이파이 누구나 접근 가능).
- 다른 사이트에서 온 쓰기 요청(Origin 불일치)은 403, 등록 안 된 Host 이름은 400 (CSRF·DNS 재바인딩 방지)
- CSV 내보내기는 `= + - @`로 시작하는 칸 앞에 `'`를 붙인다 (엑셀 수식 실행 방지)

## 구조
- `sources.py` — 소스별 검색 어댑터. 모두 같은 dict 모양을 돌려준다
  - 키 없이: Wikidata(한국어 라벨 강함, 뼈대), AniList, MusicBrainz
  - 카카오 책·장소: `KAKAO_REST_API_KEY` (home-finder와 같은 JS 키 → `KA`/`Origin` 헤더 필요)
  - 선택: `TMDB_API_KEY`, `RAWG_API_KEY` — 비어 있으면 건너뜀
- `db.py` — SQLite `data/archive.db` (cards, settings). `data/`는 git 제외
- `app.py` — FastAPI: `/api/search`, `/api/cards` CRUD, 사진 업로드, `/api/export.json|csv`
- `static/` — 화면 하나(연대기 · 진열장 · 전체). 연대기는 만난 해(met_year)별로 묶고 그해 나이를 붙인다
- 메모 — 검색 없이 떠오른 걸 적는 쪽지(`kind="memo"`, 본문은 `memory`). 해를 적으면 연대기의 그해에 꽂힌다

## 백업
`data/` 폴더 통째(archive.db + photos/)가 전부다. JSON 내보내기에는 사진 파일이 들어가지 않는다.
