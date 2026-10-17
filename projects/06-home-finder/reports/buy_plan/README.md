# 내 집 매수 계획 페이지 (buy_plan)

2026-10-01에 만든 매수 후보 정리 페이지의 빌드 소스입니다.
게시본: https://claude.ai/artifact/MarSf7gvZrWLbubZHrYq4Q (비공개)

## 기준 프로필

1인 · 84년생 · 연소득 약 1.4억 · 현금 8억 · 생애최초 · 재택 · 월세 10만 원(자동 연장).
총비용 8억 이하 / 8~10억 두 단계로 보고, 세 낀 매물을 우선한다(토허구역 실거주 유예, 2026-10-01 시행).

## 파이프라인

| 단계 | 방법 | 결과 |
|---|---|---|
| 1. 실거래 수집 | `python ../../fetch_recent_trades.py` (국토부, 12개월) | `data/cache/molit/*.csv` (git 제외) |
| 2. 후보 선정 | `python ../../rank_for_me.py stage1 [8억\|10억]` | `data/cache/apt_shortlist*.json` |
| 3. 현재 호가 | 브라우저(Playwright)로 fin.land.naver.com을 연 뒤 페이지 안에서 front-api 호출 | `.playwright-mcp/naver_*.json` (git 제외) |
| 4. 점수 | `python ../../rank_for_me.py stage2 [8억\|10억]` (카카오 생활환경 포함) | `data/cache/final_apartments*.json` |
| 5. 주변 세대수 | 브라우저에서 `complex/complexClusters` 호출, 반경 500m 100세대 이상 합산 | `apts.json`의 `hh`, `hh500`, `scale` |
| 6. 개발 호재 | 웹 검색으로 상태 확인 후 직접 정리, 카카오로 역·부지 좌표 | `hojae.json` |
| 7. 땅 | 국토부 토지 실거래, 지목 '대'·중개거래·시세 40% 미만 제외, 40평 신축비 합산 | `land.json` |
| 8. 마포·하남 추가 | `python add_mapo_hanam.py` | `apts.json`에 추가 |
| 10. 관심 권역 (2026-10-17) | `zones/`: `fetch_recent.py`·`fetch_zone_regions.py`(최근 3개월 재수집, 작업폴더 인자) → `stage1.py` → `living.py` → 브라우저로 네이버 호가·전세(`naver_zone_*.json`) → `merge.py` | `zone.json` (판단 문구는 `build.py`의 `ZONE_NOTES`). 효율·세 낀 매물은 브라우저에서 `GET /complex?complexNumber=`(용적률·세대수)와 `GET /article/basicInfo?articleNumber=&realEstateType=A01&tradeType=A1`(`priceInfo.previousDeposit`, `movingInInfo.movingInDate`)을 받아 `naver_eff_*.json`으로 저장 |
| 11. 세 갈래 후보 (2026-10-17) | 브라우저에서 `complexClusters`를 3km 칸 69개로 호출(`naver_universe.json`, 단지별 세대수·용적률·준공·평당 호가) → `zones/universe.py`(300세대·2000년 이후·카카오 이름/구/생활환경) → `zones/routes.py`(가격대 추정·점수) → 상위 62곳 매물 조회(`naver_routes_*.json`) → `zones/routes_verify.py` | `routes.json` |
| 12. 정비사업·효율 보강 | `zones/redev.py <엑셀>`: 서울시 정비사업 추진현황(열린데이터광장 OA-22856, 분기 갱신, `data/cache/seoul_jungbi_2606.xlsx`) → 카카오 좌표 → `redev.json`. 브라우저로 단지 정보·세 낀 매물 상세(`naver_routes_eff.json`) → `zones/enrich.py`가 건폐율·주차·전용률·전용 평당가·주변 1.5km 정비사업·점수 재계산 | `routes.json`, `zone.json` 갱신 |
| 9. 페이지 | `python fetch_tiles.py` → `python build.py` | `home.html` → Artifact 게시 |

`apts.json`, `land.json`, `hojae.json`은 2026-10-01, `zone.json`은 2026-10-17 시점 스냅샷이라 3·5단계 없이도 페이지를 다시 만들 수 있습니다.
추천 문구·매수 조건(목표가 등)은 `build.py`의 `RECS`, `STRAT`, `STRAT_HTML`, `LAND_HTML`에 있습니다.

## 알아둘 한계

- 네이버: 0.4초 간격 100건쯤에서 500 페이지로 차단됩니다. 1.5초 간격, 한 번에 30~40건이 안전했습니다.
  토지(E03)·단독/다가구(C03) 목록 `article/boundedArticles`는 화면이 붙이는 인증 헤더가 필요해 403이 납니다.
- 국토부 단독/다가구 실거래는 data.go.kr 활용신청 전이라 403입니다.
- 카카오 키는 JavaScript 키라 서버 호출 때 `KA: sdk/1.0 os/javascript origin/http://localhost:8006`과 `Origin` 헤더가 필요합니다.
- 세입자 여부·입주 시점은 매물 설명 문구로 추정합니다(`rank_for_me.tenancy`).
- 네이버는 하루 약 100건을 넘기면 500 페이지로 막힙니다(2026-10-17에 약 140건에서 차단, 1시간 안에 풀림). 국토부 아파트 전월세 API도 403이라 전세가는 네이버 전세 호가로 대신합니다.
