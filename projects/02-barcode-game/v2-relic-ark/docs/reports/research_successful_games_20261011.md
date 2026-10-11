# 레퍼런스 리서치 — 성공·실패 게임에서 질랜디아가 배울 것

- 작성: 2026-10-11. 조사: WebSearch(standard) 후 원문은 WebFetch로 확인. 기사·위키·개발자 인터뷰·GDC 기록·실적 보도를 썼다.
- 숫자(판매·다운로드·매출·리텐션·종료일)에는 옆에 출처 URL을 붙였다. 출처를 못 찾은 숫자는 "미확인"으로 적었다.
- 게임마다 7개 항목: ① 코어 루프 한 줄 ② 재미를 만드는 메커닉 ③ 매일 돌아오는 이유 ④ 30일 이상 장기 목표 ⑤ 칭찬과 불만 ⑥ 결과 ⑦ 질랜디아가 할 일.
- 게임 안 콘텐츠에는 실제 상표·지명을 쓰지 않는다. 아래 제안도 일반 명사로 적었다. 실제 이름은 리서치 본문의 레퍼런스 게임에만 쓴다.

## 0. 3차 플레이테스트 문제와 레퍼런스 지도

| 3차 플테 문제 | 가장 직접적인 레퍼런스 | 한 줄 처방 |
|---|---|---|
| 저녁 세션이 약함(같은 날 감쇠) | Pokémon Sleep 식사 3칸 · Stardew 하루 1개/주 2개/생일 · Finch 저녁 귀환 · ACNH 밤 손님 · Pokémon GO 저녁 1시간 | 감쇠 대신 "시간대 칸"과 "저녁에만 오는 것" |
| 꾸밈 → 손님 루프가 1주 안에 안 닫힘 | Neko Atsume · Stardew 꾸러미 · 스티커 앨범 심리 | 몇 시간 안에 첫 손님, 흔적으로 예고, 빈칸이 보이는 묶음 |
| 첫 제안이 곧 정답(60~100%) | Strange Horticulture · Coffee Talk · Papers, Please · Potionomics · Stardew 선물 기록 | 가치 순 정렬 대신 단서, "좋은 답 둘, 대가는 다르게" |
| 주 후반 새것 고갈 | Papers, Please(매일 규칙 추가) · Koster · Pokémon Sleep 주간 교체 · TCG Pocket MAU 하락 · BMJ 걸음 연구 | 주 후반엔 새 규칙, 같은 물건의 새 의미, 바코드 없는 날의 대안 |
| 재미 4.1 → 4.5 | SDT/PENS · LeBlanc · Project Horseshoe · Tomodachi Life 반응 연출 | 발견·표현·관계를 키우고, 정답 순간을 크게 연출 |

- 참고: 2026-10-11 커밋 10b9b8b(S21)이 감쇠 완화(×0.8), 꾸밈 칸 3, 첫 꼬리표 다음 날 손님 확정, warm 1순위 금지, 주 후반 novelty 실마리를 이미 넣었다(커밋 메시지 기준). 아래 교훈은 그다음 단계인 구조 쪽에 무게를 둔다.
- 주의: 3차 플테는 LLM 페르소나다. "현실에서 바코드를 찾아 움직이는 비용"과 "신기함이 꺼지는 속도"는 시뮬레이션으로 잴 수 없다(1-4의 BMJ 연구 참고). 실제 사람 5~10명이 실기기로 하는 테스트를 한 번은 섞는 게 좋다.

---

## 1. 현실 행동·사물 → 게임 (최우선)

### 1-1. Barcode Battler (에포크, 1991)
- ① 바코드 카드나 식품 바코드를 긁는다 → 전사·아이템 수치가 생긴다 → 난수가 섞인 자동 전투 → 더 센 바코드를 찾는다. (https://en.wikipedia.org/wiki/Barcode_Battler)
- ② 일상 사물이 복권이 된다. 위키 표현으로는 "어떤 바코드가 무엇이 될지 실험하고 모으는 생각이 많은 사람의 상상력에 불을 붙였다". (같은 URL)
- ③ 기기에 약속이나 보상 장치는 없다. 새 상품을 볼 때마다 긁어 보는 발견 욕구가 전부였다.
- ④ 센 카드 모으기, 후속기 Barcode Battler II(1992)의 패미컴·슈퍼패미컴 연동, 닌텐도가 라이선스한 마리오·젤다 카드. (위키)
- ⑤ 칭찬: 일본에서는 바코드 실험·수집이 놀이 문화가 됐다. 불만: 서구에서는 그래픽·소리·조작이 없고 반복적이라 금방 잊혔다. 스캐너가 까다롭고 다시 할 이유가 적었다. (위키, https://www.superjumpmagazine.com/once-upon-a-time-grocery-barcodes-unlocked-an-rpg-world/)
- ⑥ 일본에서 히트해 아이들이 특별한 바코드가 있다고 믿은 상품 일부가 품절됐다. 서구에서는 실패. 1991~1995년 판매. 판매 대수는 미확인. 1993년 아일랜드 슈퍼마켓이 1만 대를 경품으로 풀었다. (https://retrohandhelds.gg/game-over-the-history-of-barcode-gaming/, 위키)
- ⑦ 할 일: 바코드 → 유물 대응에 "찾아낼 수 있는 규칙"을 몇 개 숨긴다(끝자리, 숫자 반복 같은 패턴 → 특정 가문·등급 확률 상승). 결과를 숫자에서 끝내지 말고 바로 사람의 반응(「어디로」)으로 잇는다. 바코드 배틀러에 없던 "찍은 뒤 할 일"이 질랜디아의 무기다. 인식 실패에 대비해 재시도와 수동 입력 UX를 둔다.

### 1-2. Monster Rancher (테크모, 1997 · CD → 몬스터)
- ① 아무 CD나 넣는다 → CD 메타데이터로 몬스터가 나온다 → 게임 속 몇 년 동안 훈련·대회 → 은퇴·냉동·합체. (https://en.wikipedia.org/wiki/Monster_Rancher_(video_game))
- ② "우리 집 CD장에 뭐가 숨어 있나"라는 발견. 크리스마스 앨범에서는 산타 계열, 자사 게임 디스크에서는 그 게임의 악당이 나오는 식의 의미 있는 숨은 대응. (위키)
- ③ 키우는 몬스터의 주간 훈련·대회 일정(게임 속 주 단위)과, 새 CD가 손에 들어올 때마다 해 보는 시험.
- ④ 대회 랭크, 희귀종 해금, 정해진 수명 안에 최대로 키우기, 냉동·합체로 다음 세대 만들기. (수명·냉동·합체는 시리즈 공통: https://legendcup.com/faq-mrds-lifespan-info.php)
- ⑤ 칭찬: "넣는 CD마다 다른 몬스터"(IGN 등, 위키). 문화: "소문, 잡지 게재, CD 빌려주기의 조합이 이 게임을 특별하게 만들었다". 친구가 영화 사운드트랙을 빌려 와 특별한 몬스터를 얻은 기억, 부모님 CD 더미를 뒤지던 아이들. (https://cogconnected.com/review/monster-rancher-1-2-dx-review/, https://www.nettosgameroom.com/2024/12/a-brief-history-of-monster-rancher.html) 불만: 메뉴 위주라 박진감이 없다(GamePro, 위키).
- ⑥ 일본에서 1997년 12월 초까지 50만 장 이상, 1999년까지 전 세계 100만 장. (위키) 2021년 DX판은 CD 드라이브 없는 기기를 위해 앨범·곡 검색 DB로 바꿨다(커뮤니티 보고로 약 75만 항목). (https://www.gematsu.com/2021/08/monster-rancher-1-2-dx-announced-for-switch-pc-and-ios, https://steamcommunity.com/app/1716120/discussions/0/603017372668863737) 리뷰어는 "가장 센 몬스터를 인터넷에서 찾지 말고 친구와 좋아하는 앨범으로 하라"고 권했다. 마법은 최적화가 아니라 발견에 있었다는 뜻이다. (cogconnected)
- ⑦ 할 일: (1) 게임 안 소문 방송으로 "어떤 종류의 물건에서 무엇이 나왔다더라"를 주 1~2개 흘려 공유 문화를 만든다. 상표 없이 "줄무늬 봉지 국수"처럼 묘사한다. (2) 집 물건이 바닥나는 날을 위해 DX식 대체 입력을 둔다. "기억 속 물건" 일반 범주 목록에서 하루 1개 고르기(값은 실물 스캔보다 낮게). (3) 떠나는 주민이나 유물이 냉동·합체처럼 다음 세대에 흔적을 남기게 한다(머리맡 물건 상속).

### 1-3. Skylanders · amiibo (toys-to-life)
- ① 피규어를 포털에 올린다 → 캐릭터가 등장한다 → 레벨·업그레이드가 피규어 칩에 저장돼 다른 집, 다음 작품에서도 그대로. (https://en.wikipedia.org/wiki/Skylanders)
- ② 손에 쥔 장난감이 곧 내 캐릭터라는 소유감. 속성 문(Elemental Gate)은 같은 속성 피규어가 있어야 열려 수집 압박이 된다. (https://en.wikipedia.org/wiki/Skylanders:_Spyro%27s_Adventure)
- ③ 매일 장치는 약하다. 매년 새 작품·새 피규어 출시가 귀환 동기였다.
- ④ 속성별 수집 완성, 다음 작품으로 이월.
- ⑤ 칭찬: 2011년에 장르를 열었다. 불만: 대형 경쟁작 셋이 진열대를 채워 공급 과잉(액티비전 퍼블리싱 CEO "수백 피트의 진열대"), 부모 지갑의 피로. amiibo는 품귀, 매장 독점, 콘텐츠 잠금("비싼 DLC") 반발. (https://www.nintendolife.com/news/2017/07/activision_ceo_on_the_state_of_the_skylanders_series_and_toys-to-life, https://www.huffingtonpost.co.uk/entry/amiibo_b_7555842)
- ⑥ Skylanders는 2015년 6월 기준 장난감 2억 5천만 개, 매출 30억 달러. (https://gameluster.com/skylanders-franchise-has-sold-250-million-toys-generated-3-billion-for-activision/) 쇠퇴는 2-4 참고. amiibo는 2016년 2월까지 피규어 3,100만, 카드 2,150만 출하. (https://www.gamedeveloper.com/business/amiibo-shipments-reach-31-million)
- ⑦ 할 일: 특정 범주의 물건이 없으면 막히는 콘텐츠(속성 문)는 만들지 않는다. 언제나 다른 길을 둔다. 대신 소유감은 빌린다. 유물 카드에 "누가 언제 받았는지"가 각인처럼 쌓이게 한다(받은 주민 이름, 날짜).

### 1-4. Pokémon GO (나이언틱, 2016)
- ① 걷는다 → 근처 포켓몬·포켓스톱 → 잡고 모은다 → 레이드·교환·커뮤니티 데이.
- ② 현실 장소가 게임 장소가 된다. 걸음이 알 부화와 버디 보상으로 바뀐다.
- ③ 하루 첫 포획·첫 스톱 연속 보너스. 리서치 도장은 하루 1개, 7개를 모으면(연속 아님) "리서치 돌파" 보상. 매주 화요일 18~19시 스포트라이트 아워, 수요일 18~19시 레이드 아워(현지 시각, 2023년 기준). 매달 커뮤니티 데이. (https://www.imore.com/pokemon-go-research-breakthrough-rewards, https://afkgaming.com/gaming/general/pokmon-go-raid-hours-spotlight-hours-explained-october-2023)
- ④ 도감 완성, 레벨, 이로치·개체값, 친구 레벨.
- ⑤ 칭찬: 사람을 밖으로 나가게 한다. 불만: 시골에는 스톱·출현이 적다(인구와 전작 Ingress 기준 배치). 2023년 리모트 레이드 가격 인상과 하루 5회 제한에 큰 반발. (https://www.thegamer.com/pokemon-go-help-rural-players/, https://videogames.si.com/news/pokemon-go-niantic-remote-raid-nerfs-open-letter)
- ⑥ 결과
  - 신기함의 붕괴: 2016년 7월 중순 하루 이용자 약 4,500만으로 정점, 이후 감소. 미국 이용자는 연말까지 약 80% 빠졌다. (https://www.androidpolice.com/2016/08/24/pokemon-go-usage-peaked-now-steady-decline/, https://www.bgr.com/2017/04/03/pokemon-go-popularity-2016-users/)
  - 현실 행동의 감쇠: BMJ 연구에서 설치 첫 주 하루 +955걸음, 6주째에는 설치 전 수준으로 돌아감. (https://pmc.ncbi.nlm.nih.gov/articles/PMC5154977) 반면 열심인 이용자는 하루 +1,473걸음(25% 이상). (https://www.jmir.org/2016/12/e315)
  - 회복: 레이드(2017)와 커뮤니티 데이·친구·교환(2018)으로 돌아와 2018년 매출 7억 9,500만 달러. (https://gameluster.com/look-pokemon-go-two-years-later/, https://mobilesyrup.com/2019/01/03/pokemon-gos-revenue-was-just-shy-of-800-million-in-2018/)
  - 장기: 2026년 7월까지 누적 매출 90억 달러 이상, 다운로드 8억 이상(Sensor Tower). (https://wnhub.io/news/analytics/item-51864) 2025년 나이언틱 게임 사업 전체가 Scopely에 35억 달러로 팔렸다. (https://www.nintendolife.com/news/2025/03/niantic-sells-pokemon-go-and-entire-gaming-division-for-usd3-5-billion)
- ⑦ 할 일: (1) "현실 행동의 신기함은 6주 안에 꺼진다"를 전제로 14일 이후 콘텐츠는 약속·관계 쪽으로 짠다. (2) 연속 출석 대신 "도장 7개(연속 아님) → 큰 보상"을 14일 달력에 두 번 둔다. (3) 매주 고정된 저녁 1시간을 만든다(예: 수요일 저녁 「등불 시간」, 그 시간엔 손님·원정 귀환 확정). (4) 집마다 바코드 공급이 다르다. 시골 스톱 문제와 같은 구조이므로 찍을 게 없는 날에도 할 일이 있어야 한다.

### 1-5. Pikmin Bloom (나이언틱·닌텐도, 2021)
- ① 걷는다 → 피크민 묘목을 줍고 키운다 → 꽃을 심으며 걷는다 → 원정을 보내 열매를 받는다 → 하루 기록.
- ② 걸음이 꽃길로 남는다. 카페·빵집·우체국 같은 장소 종류에 따라 피크민이 다른 장식 옷을 입고 나온다. 내 생활 동선이 곧 수집 축이다. (https://pikminwiki.com/Decor)
- ③ 하루를 마치면 걸음과 경로를 돌아보고 메모·사진을 남기는 "추억", 친구에게 보내는 엽서. (https://www.fastcompany.com/90689136/nintendo-niantic-pikmin-bloom)
- ④ 장식 피크민 도감, 친밀도, 이벤트용 큰 꽃.
- ⑤ 칭찬: 게이머가 아닌 사람도 하는 걷기 일기(UX 디렉터 카타야마, fastcompany). 불만: 출시 초 성적은 "그럭저럭"이었다.
- ⑥ 결과
  - 느린 출발: 출시 2주에 200만 다운로드, 47만 3천 달러(Sensor Tower). (https://www.pocketgamer.biz/pikmin-bloom-two-million-downloads/)
  - 해마다 성장: 2022년 840만 → 2023년 2,090만 → 2024년 3,340만 달러, 2025년 12월 1일 누적 1억 달러(AppMagic). 계기는 본편 신작 출시, 이벤트 패스, 유료 현장 행사. (http://www.pocketgamer.biz/pikmin-bloom-hits-100m-after-four-years-as-2025-becomes-its-best-year-yet/)
  - 최근: 2025년 3,810만, 2026년 상반기 3,570만 달러. 대만이 902% 늘었고 계기는 현장 행사였다. (https://www.pocketgamer.biz/pikmin-bloom-skyrockets-to-record-revenue-as-taiwanese-spending-surges-902/)
- ⑦ 할 일: 바코드의 범주(식품, 문구, 세면 등)에 따라 같은 손님이나 유물이 다른 장식으로 나오게 해서 "같은 물건이지만 새 변형"이라는 축을 만든다. 떠날 때 카드 옆에 "오늘의 일지" 한 장(오늘 건넨 것, 들은 말)을 둔다. 첫 성적보다 오래 완만하게 크는 운영을 계획한다.

### 1-6. Finch (셀프케어 펫, 2021~)
- ① 물 마시기·일기 같은 작은 자기 돌봄을 체크한다 → 에너지가 찬다 → 새가 모험을 떠난다 → 저녁에 이야기를 들고 돌아온다 → 무지개 돌로 옷·가구를 산다. (https://dishabhatia.substack.com/p/the-self-care-bird-app-finch, https://foxdata.com/en/blogs/finch-as-app-store-editors-choice-a-self-care-companion/)
- ② "펫을 돌보는 일이 곧 나를 돌보는 일". 창업자들이 제인 맥고니걸에게서 착안했다. (https://www.pastemagazine.com/article/finch-app-mental-health-virtual-pet-self-care)
- ③ 아침에 보내고 저녁에 받는 하루 리듬, 계절 이벤트.
- ④ 새의 성장 단계(아기 → 어른), 여행사 해금, 성격 공개. (Paste)
- ⑤ 칭찬: 하루를 빠져도 새가 죽지 않고 꾸짖지 않는다. "죄책감이 아니라 기분이 좋아지는 습관 앱". 불만: 1주차의 기쁨이 3개월째엔 "돌볼 것 하나 더"가 된다. 구독 전환이 갑작스럽다. (https://habitbox.app/blog/finch-app-review)
- ⑥ 초기 인터뷰 때 약 8만 명(Paste)에서 2025년 7월 1,000만 다운로드 이상으로. (https://android-developers.googleblog.com/2025/07/weareplay-app-game-founders-across-the-us.html) 매출은 미확인.
- ⑦ 할 일: 저녁 세션을 "받는 시간"으로 고정한다. 아침에 원정이나 심부름을 보내면 저녁에 주민이 이야기와 물건을 들고 돌아온다. 빠진 날 벌점은 계속 0으로 둔다(습격 손실도 결석과 묶지 않는다). 3개월째 피로에 대비해 계절 테마를 일찍 설계한다.

### 1-7. Pokémon Sleep (2023)
- ① 폰을 베개 옆에 두고 잔다 → 아침에 수면 유형(꾸벅·새근·쿨쿨)에 맞는 포켓몬이 자는 모습으로 모여 있다 → 기록하고 친해진다 → 낮에는 요리로 잠만보를 키운다. (https://www.pokemon.com/us/pokemon-news/pokemon-sleep-and-pokemon-go-plus-coming-summer-2023)
- ② 이미 매일 하는 행동(잠)을 수집 결과로 바꾼다. 잠은 하루 한 번이라 자연스러운 상한이 있다.
- ③ 아침 결과 확인. 요리는 하루 3번(아침 4~12시, 점심 12~18시, 저녁 18~4시). (https://www.dexerto.com/pokemon/how-to-cook-dishes-in-pokemon-sleep-application-2221762)
- ④ 매주 월~일요일 한 연구지에서 새 잠만보를 키우고 월요일에 장소를 바꾼다. 주간 미션 8개(월요일 4시 리셋). (https://bulbapedia.bulbagarden.net/wiki/Professor_Neroli, https://bulbapedia.bulbagarden.net/wiki/Mission_(Sleep)) 잠자는 모습 도감.
- ⑤ 칭찬: 생활 습관 동반자. 불만: 밤새 화면을 켜 둬 배터리가 약 15% 든다, 낮 플레이가 수동적이다, 친해지는 재료가 하루 몇 개뿐이다. (https://gosugamers.net/entertainment/features/69058-pokemon-sleep-impressions-why-catch-pokemon-when-you-can-catch-some-zs)
- ⑥ 첫해 매출 약 1억 달러(일본 7,300만, 미국 1,500만, AppMagic). (https://gamingbolt.com/pokemon-sleep-reportedly-earned-over-100-million-in-revenue-in-its-first-year) 1주년에 2,000만 다운로드, 2025년 7월 2,800만과 수면 기록 10억 회, 2026년 4월 3,000만. (https://www.gamedeveloper.com/press-release/pok-mon-sleep-celebrates-one-year-anniversary-and-twenty-million-downloads, https://en.wikipedia.org/wiki/Pok%C3%A9mon_Sleep)
- ⑦ 할 일: 같은 날 감쇠를 "시간대 칸"으로 바꾼다. 아침·낮·저녁 칸마다 주민별로 신선한 선물 한 번을 주고, 칸이 바뀌면 리셋한다. 매주 월요일에 "물때"가 바뀌어 손님 풀, 사슬 갈래, 소문이 교체되는 주간 리듬을 만든다(7일째 일지 비트와 맞물린다).

---

## 2. 실패·쇠퇴 사례

### 2-1. Harry Potter: Wizards Unite (2019 출시, 2022 종료)
- ① 걸으며 "파운더블"을 찾아 주문을 그려 회수한다 → 등록부(스티커북)를 채운다 → 요새 전투.
- ② 지식재산은 강했지만 핵심 동작이 약했다. 전문가 평: 주문마다 패턴이 다르지만 "의미 있는 선택이 아니다". (https://www.pocketgamer.biz/mobile-mavens/71270/whatever-happened-to-harry-potter-wizards-unite/)
- ③ 에너지, 포션, 요새 등 시스템이 많아 매일 할 일이 흐렸다.
- ④ 등록부 완성, 직업 트리.
- ⑤ 전문가 평(2019-07-25): "스티커북 메커닉은 마법사가 되는 판타지와 상관없다", "너무 많은 걸 너무 빨리 배워야 한다", "사회적 메커닉이 사실상 없다", "사람을 매일 밖으로 나가게 하는 건 아주 높은 장벽이다". (위 URL)
- ⑥ 첫 주 약 300만 달러(위 URL), 첫 2주 1,240만 다운로드와 약 800만 달러. (https://www.pocketgamer.biz/pikmin-bloom-two-million-downloads/) 누적 3,940만 달러, 2,030만 다운로드, 2021년 1~11월은 470만 달러(Sensor Tower). (https://wnhub.io/news/vr/item-19430) 2021-12-06 스토어에서 내려가고 2022-01-31 서버 종료. (https://www.pocketgamer.biz/news/77466/harry-potter-wizards-unite-shutting-down-on-31-january-2022/)
- ⑦ 할 일: 모으는 이유가 판타지와 맞물려야 한다. 질랜디아는 "건네기"가 이유라서 이미 맞다. 그러니 첫 주에 보이는 동사는 셋 이하(찍기, 「어디로」, 떠날 때)로 두고 원정·습격·잔치는 날짜에 맞춰 천천히 연다. 가벼운 사회 장치 하나(비동기 소문 공유)를 로드맵에 넣는다.

### 2-2. Minecraft Earth (2019 출시, 2021 종료)
- ① 걸으며 "탭퍼블" 블록·동물을 모은다 → AR 빌드플레이트에 짓는다 → 어드벤처.
- ② 마인크래프트를 현실 위에 놓는 판타지. ③ 탭퍼블 갱신과 챌린지. ④ 건축 완성과 수집.
- ⑤ 분석: "희귀도가 의미를 잃었고, 플레이어를 늦추는 방법을 끝내 찾지 못했다." 양 768마리와 다이아 178개가 힘들이지 않고 쌓였고, 돈을 쓸 이유가 없었다. 공격적인 시간 제한과 홍보한 기능의 누락도 지적됐다. (https://blog.patientrock.com/the-end-of-minecraft-earth/, https://www.windowscentral.com/minecraft-earth-ends-why-microsoft-mobile-games-failing)
- ⑥ 다운로드 1,800만, 누적 매출 약 49만 8천 달러(Sensor Tower, 2021-01). (https://pocketgamer.biz/comment-and-opinion/75451/minecraft-earth-failed-to-cross-500k-in-lifetime-revenue-are-location-based-games-off-the-map/) 2021-06-30 종료. 공식 사유는 코로나로 이동과 협동이 막힌 것. 구매자에게는 마인크래프트 본편을 줬다. (https://www.geekwire.com/2021/microsoft-owned-mojang-studios-shutting-ar-powered-minecraft-earth-game-june/)
- ⑦ 할 일: 전설 유물이 창고에 의미 없이 쌓이지 않게 한다. 등급의 가치는 "누구에게 줄 때 무엇이 열리는가"로만 커지게 한다(예: 전설은 사슬 매듭을 두 칸 움직임). 넘치는 자원은 지금처럼 다른 가치로 바꾸되 상한이 보이게 한다.

### 2-3. Barcode Kanojo (사이버드, 2010~)
- ① 아무 1D 바코드나 찍는다 → "7조 가지" 조합의 가상 여자친구가 생긴다 → 데이트, 호감도.
- ② 외모가 찍은 위치(위도·경도)와 바코드 국가 코드에 따라 달라진다. 같은 바코드(같은 상품)를 찍은 사람끼리는 여자친구들이 서로 친구가 된다. (https://asiajin.com/blog/2010/10/barcode-kanojo-barcode-battler-reincarnated-with-otaku-flavour/)
- ③·④ 매일 장치와 장기 구조는 공개 자료로 미확인.
- ⑤ 당시 평: 무료인 이유는 "사용자 주변 상품과 위치 정보"일 거라는 추정. 기사 시점까지 여자친구 2만 4천 명 이상이 생성됐다. (위 URL)
- ⑥ 서비스 종료(공식 사이트·앱 없음). 종료일은 미확인. (https://alternativeto.net/software/barcode-kanojo/about)
- ⑦ 할 일: "바코드 → 캐릭터 생성"만으로는 첫날 재미뿐이다. 생성 뒤의 관계 루프가 본체다. 같은 물건을 찍은 다른 방주와 이어지는 비동기 장치(같은 범주 물건을 찍은 이웃 방주의 소문 한 줄)는 가볍게 빌릴 만하다. 위치 정보는 쓰지 않는다(개인정보, 실제 지명 금지 원칙).

### 2-4. Skylanders의 쇠퇴 (1-3에서 이어짐)
- ⑥ 30억 달러(2015) 뒤 Imaginators(2016)는 미국 출시 달 6만 6천 장에 그쳤고, 2017년에는 신작이 없었다(개발팀은 Destiny로 이동). (https://www.mcvuk.com/business/no-new-skylanders-this-year-but-toy-to-life-franchise-isnt-dead-yet) 액티비전 CEO: 장르 과밀과 수요·공급 불균형, Wii의 퇴장도 원인. (https://nintendoeverything.com/activision-thinking-about-how-to-continue-investing-in-skylanders-says-wiis-death-contributed-to-series-struggles) Disney Infinity는 2016년 종료, LEGO Dimensions는 2017년 10월에 한 해 일찍 끝났다. (https://www.thesixthaxis.com/2017/10/23/lego-dimensions-wont-receive-any-further-expansions/)
- ⑦ 할 일: 새로움을 "새 물건을 들여와야 생긴다"에 묶지 않는다. 같은 물건이 날, 주민, 계절에 따라 다른 이야기를 여는 재해석이 신선함의 엔진이다(3차 플테에서 재스캔 가치 0을 선물로 바꾼 것을 넓힌다).

---

## 3. 선물과 관계

### 3-1. Animal Crossing: New Horizons (2020)
- ① 섬에서 채집·제작·꾸미기 → 주민과 대화·선물 → 박물관 기증 → 섬 평가.
- ② 준 옷을 주민이 입고, 준 가구를 집에 진열한다(친밀도와 물건 값에 따라). (https://www.gfinityesports.com/article/animal-crossing-new-horizons-best-villager-gifts-guide) 주민 부탁(물고기·벌레·가구 가져오기, 배달)을 들어주면 작은 보상과 친밀도 1~3점. (https://nookipedia.com/wiki/Favor) 관장 부엉이가 기증품마다 길게 해설한다. (https://nookipedia.com/wiki/Blathers) 박물관은 실제 자연사 박물관처럼 설계됐다는 큐레이터들의 평. (https://kotaku.com/museum-experts-weigh-in-on-animal-crossing-new-horizons-1843613946)
- ③ 실시간 시계, 매일 바뀌는 상점·화석·부탁. 밤 19~4시에만 오는 셀레스트와 별똥별, 다음 날 아침 해변의 별 조각. (https://nookipedia.com/wiki/Wishing_Star)
- ④ 박물관 완성, 섬 별점, 계절 이벤트.
- ⑤ 칭찬: 2020년의 안식처. 불만: 주민 대사가 금방 되풀이된다, 엔드게임이 부족하다. (https://www.looper.com/205372/big-problems-animal-crossing-new-horizons-needs-to-fix)
- ⑥ 2026-06-30 기준 5,029만 장(닌텐도 실적). (https://www.shacknews.com/article/150276/animal-crossing-new-horizons-50-million-units-sold)
- ⑦ 할 일: (1) 준 유물이 보이는 곳에서 쓰이는 장면을 만든다. 머리맡 물건의 다음 단계로, 주민이 그 물건을 실제로 쓰는 모습(덮고 자기, 국자로 젓기). (2) 유물 도감에 관리실의 짧은 해설 한 줄. (3) 19시 이후에만 오는 손님과 다음 날 아침에 남는 흔적이 저녁 세션의 존재 이유가 된다. (4) 반응 대사 풀은 7일 안 반복 0을 목표로 한다.

### 3-2. Stardew Valley (2016)
- ① 농사·채광·낚시로 돈과 물건 → 주민에게 선물 → 하트 → 하트 이벤트(컷신).
- ② 선물 규칙이 분명하다. 주민마다 하루 1개, 주 2개. 생일에는 ×8이고 주 2개를 넘겨도 줄 수 있다. 주 2개를 주면 일요일 아침 보너스, 만나지 않으면 친밀도가 조금씩 준다. 알게 된 취향은 "선물 기록"에 쌓인다(대화와 비밀 쪽지로 배움). 하트 1개는 250점. (https://stardewvalleywiki.com/Friendship)
- ③ 계절 작물, 주민 생일, 축제 달력.
- ④ 커뮤니티 센터 꾸러미. 개발자는 "노가다가 아니라 게임의 여러 면을 탐험하게 하려는 것"이라고 했다(2014-08-01). 꾸러미를 채우면 마을 일부가 영구히 복원된다. (https://stardewvalley.net/dev-update-19/, https://stardewvalleywiki.com/Bundles)
- ⑤ 칭찬: 관계의 깊이와 자유. 불만: 힌트가 적은데 "틀린 선물"에 벌을 받는다, 선물 취향이 캐릭터 설정과 연결되지 않아 무작위처럼 느껴진다(스팀 토론 요약). (https://steamcommunity.com/app/413150/discussions/0/142261027583519022)
- ⑥ 2025년 1월 기준 4,100만 장 이상(PC 2,600만, 스위치 790만). (https://www.pocketgamer.biz/stardew-valley-sells-over-41-million-copies/)
- ⑦ 할 일: 숨은 감쇠 배율 대신 보이는 규칙을 쓴다("주민마다 하루 한 번 마음에 남는 선물, 그 뒤로는 덤 대사"). 주민 기념일 ×N을 14일 달력에 배치해 그날은 그 사람에게 주고 싶게 만든다. 취향은 캐릭터 설정에서 추론할 수 있게 만든다(스타듀 불만의 반대). 꾸밈 꼬리표는 꾸러미처럼 빈칸이 보이는 목록으로 만들고, 완성하면 방주가 영구히 바뀌게 한다(통로 개방, 새 손님 자리).

### 3-3. Spiritfarer (Thunder Lotus, 2020)
- ① 배를 몰며 자원 모으기·요리·건설 → 영혼 승객의 필요(음식, 부탁)를 채운다 → 이야기가 진행된다 → 준비되면 "에버도어"로 배웅한다. (https://en.wikipedia.org/wiki/Spiritfarer)
- ② 영혼마다 좋아하는 것·싫어하는 것과 최애 요리 하나가 있다. 같은 요리를 연달아 두 번은 줄 수 없다(가이드 기준). 포옹, 그리고 떠날 때 "영혼의 꽃"을 남긴다. (위키, https://www.gameskinny.com/ov491/spiritfarer-favorite-foods-guide-passenger-likes-and-dislikes)
- ③ 승객의 기분 유지(배고픔), 부탁, 배 위 미니게임.
- ④ 모든 영혼 배웅(엔딩), 배 확장. 디렉터 게랭은 임종 돌봄 시설에서 환자와 돌봄 노동자를 만나며 자료를 모았다. (https://www.gameskinny.com/culture/thunder-lotus-on-spiritfarer-death-hugs-and-legacies/)
- ⑤ 칭찬: 감정의 깊이, 애니메이션, 음악. 불만: 후반에는 자원 미니게임이 반복적이고 이동·되돌아가기가 지루하다(IGN은 9/10을 주면서도 지적). (위키, https://www.gamereactor.eu/spiritfarer-review/)
- ⑥ 2021년 12월까지 100만 장. (위키)
- ⑦ 할 일: 11개 사슬의 끝을 배웅 장면과 기념 물건 하나(그 사람 자리에 남는 유물)로 만들어 30일 목표로 쓴다. "같은 거 연달아는 싫어요"를 숫자 감쇠 대신 대사로 말하게 한다. 후반 매듭일수록 물건 요구량은 줄이고 장면 밀도는 높인다(후반 노가다 경고).

### 3-4. Cozy Grove (Spry Fox, 2021)
- ① 매일 유령 곰들의 부탁(채집·제작)을 들어준다 → 섬에 색이 돌아오고 이야기 한 토막이 열린다 → 정해진 분량이 끝나면 "내일 또".
- ② 하루치 이야기를 정해 몇 달에 걸쳐 나눠 주는 에피소드식 진행. 공동 창업자 에더리: "플레이어를 제한한다기보다, 몇 달에 걸친 즐거운 에피소드 경험이 되도록 이야기 분량을 나누는 것". (https://www.vice.com/en/article/bvx9vw/cozy-grove-is-ok-telling-players-to-log-off-its-delightful)
- ③ 매일 새 과제. 실시간으로 흐르고 시간을 건너뛸 수 없다. (https://en.wikipedia.org/wiki/Cozy_Grove) 기자 체험으로는 약 20분 뒤 "이제 꺼도 괜찮다"는 신호가 온다. (Vice)
- ④ 곰 모두 떠나보내기, 섬 복원, 꾸미기 수집.
- ⑤ 칭찬: 그만해도 된다고 허락하는 다정함. 불만: 하루 할 일이 끝나면 기다리는 것뿐이다, 퀘스트 물건을 며칠씩 모아야 해서 숙제가 된다, 인벤토리가 불편하다, 얕다. 메타크리틱 71~72. (https://www.keengamer.com/articles/reviews/switch-reviews/cozy-grove-review-a-game-i-slowly-ghosted-switch, https://thepinknews.com/2021/04/14/cozy-grove-review-spry-fox-animal-crossing-playstation-xbox-pc-apple-arcade, 위키)
- ⑥ 판매는 미확인. D.I.C.E. 올해의 가족 게임 후보. 스프라이 폭스는 2022-10-31 넷플릭스에 인수됐다가 2025년 12월 창업자들이 다시 사들였다. 후속작 Camp Spirit(2024)은 넷플릭스 모바일 독점. (https://www.geekwire.com/2022/netflix-acquires-seattle-game-studio-spry-fox/, https://gameworldobserver.com/2025/12/04/spry-fox-will-become-independent-again-as-the-studios-founders-buy-it-back-from-netflix)
- ⑦ 할 일: 하루 이야기 분량을 정하고 "오늘 매듭은 여기까지"를 정직하게 말한다. 대신 저녁 세션은 이야기를 소비하는 시간이 아니라 다른 동사(꾸밈 마무리, 도감, 사이드 모드, 밤 손님)로 채워 "기다림만 남는다"는 불만을 피한다. 비트는 실제 날짜가 아니라 플레이한 날 기준으로 센다. 3차 플테에서 5일 쉰 uid가 3~7일째 비트를 통째로 건너뛰었다(보고서 기록).

### 3-5. Tomodachi Life (닌텐도, 2013 · 2026)
- ① 아는 사람을 닮은 Mii를 들인다 → Mii끼리 알아서 친해지고 싸우고 사귄다 → Mii의 고민(음식, 옷, 연애 상담, 미니게임)을 해결한다 → 행복도가 오르면 선물. (https://en.wikipedia.org/wiki/Tomodachi_Life_(series))
- ② 지켜보는 재미(예상 못 한 조합의 상황 코미디)와 취향 발견. Mii마다 최애 음식 2개, 최악 음식 2개가 있고, 최애를 먹으면 춤을 추거나 우주로 날아가는 과장된 반응을 한다. (https://tomodachi.fandom.com/wiki/Food)
- ③ 매일 새 고민과 사건, 바뀌는 상점 물건. ④ 결혼·아이, 섬 확장, 모든 Mii 행복.
- ⑤ 칭찬: 엉뚱한 유머. 불만: 반복적이다, 누가 사귈지 정할 수 없어 개입이 부족하다, 참여보다 지켜보는 시간이 길다. (위키, https://www.trustedreviews.com/tomodachi-life-review)
- ⑥ 3DS판 672만 장. 2026-04-16 출시한 Living the Dream은 2026년 8월 기준 800만 장 이상, 시리즈 합계 1,849만 장. (위키 시리즈 문서)
- ⑦ 할 일: "최애 발견" 순간을 크게 연출한다(평소와 확 다른 동작, 소리, 관리실 방송). 내가 준 유물을 두고 주민끼리 주고받는 장면(지켜보는 재미)을 저녁 세션에 둔다. 같은 요청과 사건이 7일 안에 되풀이되지 않게 한다.

---

## 4. 비운 사이 보상과 기지 운영

### 4-1. Neko Atsume (Hit-Point, 2014)
- ① 마당에 밥과 장난감을 놓는다 → 앱을 닫는다 → 고양이가 와서 놀다 간다 → 사진첩에 기록, 멸치(화폐)와 기념품. (https://en.wikipedia.org/wiki/Neko_Atsume)
- ② 놓은 물건이 누가 올지를 정한다. 희귀 고양이 26마리는 특정 물건·먹이를 놓아야만 온다. 여러 번 방문하면 기념품을 남긴다. (위키) 게임이 직접 "잠시 앱을 닫았다가 다시 열어 보라"고 안내한다. 떠나 있는 동안 일이 생긴다. (https://www.killscreen.com/cats-finally-take-over-the-world-with-mobile-game-neko-atsume/)
- ③ 밥이 떨어지기 전에 채우기. 몇 분에서 몇 시간 단위로 짧게 자주 확인한다.
- ④ 사진첩(고양이 도감) 완성, 기념품 전부 모으기.
- ⑤ 칭찬: 시간과 실력 부담 없이 보는 위안(제작자 "아이도 즐길 수 있게"). 2015-08-20 CEDEC 게임 디자인상. 불만: 단순하고 내용이 적다(VR판 리뷰). (위키, https://www.cgmagonline.com/review/game/neko-atsume-purrfect-kitty-collector)
- ⑥ 2015년 5월 400만, 2015-12-04 1,000만 다운로드(위키). 시리즈 3,000만(2023-12). (https://www.meta.com/blog/neko-atsume-interview/) 10주년작 Neko Atsume 2(2024-10-20)는 친구 마당 방문과 장난감 고장·수리를 더했다. (https://www.siliconera.com/?p=1057093)
- ⑦ 할 일: 꾸밈 결과를 "하루 확률 0.35"가 아니라 "닫았다 열면" 단위로 준다. 꼬리표가 붙은 뒤 첫 손님은 같은 날 다음 세션에 확정한다(S21의 "다음 날 확정"보다 빠르게). 손님이 오기 전에는 흔적(발자국, 물 자국)으로 "이 꼬리표를 좋아하는 누군가"를 예고한다. 같은 손님이 N번 오면 기념품 유물. 손님 도감은 빈칸 실루엣으로 보인다.

### 4-2. Fallout Shelter (Bethesda, 2015)
- ① 지하 볼트에 방을 짓는다 → 주민을 S.P.E.C.I.A.L. 능력치에 맞는 방에 배치한다 → 전력·식량·물 생산 → 인구 증가 → 황무지 탐험·퀘스트. (https://en.wikipedia.org/wiki/Fallout_Shelter)
- ② 단면도 기지의 장난감 같은 손맛, 능력치와 방의 매칭, "서두르기"(빨리 생산하지만 화재·벌레 사고 위험). 타이머와 페이월이 없고 과금은 런치박스(카드 팩)뿐인데 플레이로도 얻는다. (https://www.deconstructoroffun.com/blog//2015/07/why-fallout-shelter-popped-and-dropped.html)
- ③ 생산 수거, 탐험 귀환, 플레이로 가끔 얻는 런치박스. 2016-07-14 퀘스트 추가, 명절 테마 퀘스트로 정기 귀환을 만들었다. (위키, https://www.pocketgamer.biz/four-years-on-bethesda-on-the-evolution-of-fallout-shelter/)
- ④ 인구 200, 전설 주민, 퀘스트 라인.
- ⑤ 칭찬: 비주얼, 관대한 과금. 불만: 깊이가 없고 엔딩이 없다, "주말이면 다 끝낸다", 사회 요소가 0이다, 인구가 늘어 열리는 새 방이 새로운 걸 더하지 않는다. 출시 3주 뒤 매출 순위가 급락했다. 베데스다도 "플레이어가 예상보다 훨씬 빨리 콘텐츠를 소진한다"고 인정했다. (Deconstructor of Fun, pocketgamer.biz 위 URL)
- ⑥ 첫 2주 510만 달러(SuperData). (https://www.gamespot.com/articles/fallout-shelter-makes-51-million-in-first-two-week/1100-6428950/) 2019년 플레이어 1억 5천만, 누적 매출 1억 달러. (pocketgamer.biz 위 URL, 위키) 7일·30일 리텐션 수치는 미확인(공개 자료를 찾지 못함).
- ⑦ 할 일: 방(시설) 해금은 수치가 아니라 새 동사를 열어야 한다(새 방 = 새 손님 종류, 새 사슬 갈래). 습격은 처벌이 아니라 사건이어야 하고, 서두르기처럼 플레이어가 위험을 고르는 구조가 좋다. 1주차에 다 보여 주지 말고 7·14·30일째에 새 층(구역)을 연다.

---

## 5. 추리·매칭 (맞는 것을 맞는 사람에게)

### 5-1. Strange Horticulture (Bad Viking, 2022)
- 루프와 장치: 손님의 요청(증상, 용도) → 식물 도감의 묘사·스케치·냄새·잎 모양 단서로 이름 모를 화분을 알아낸다 → 건넨다. 개발자: "찾는 식물을 다른 것과 구별해 주는 정보가 항상 하나는 있다." 무엇을 주느냐에 따라 뒤의 사건이 갈린다. (https://www.gamedeveloper.com/design/strange-horticulture---bad-viking, https://en.wikipedia.org/wiki/Strange_Horticulture)
- 평가와 결과: IGF 디자인 부문 후보, PC Gamer 2022 최고의 퍼즐 게임. 불만: 진열·물주기 루프가 지루하다는 평. 판매는 미확인. (위키)
- 할 일: 「어디로」의 정답을 시스템이 1순위로 알려 주지 않는다. 주민의 오늘 한마디(단서)와 유물 카드의 특징(재질, 온기, 냄새 — 바코드 범주에서 파생)으로 플레이어가 맞히게 한다. 결정적 단서 하나는 늘 보장한다.

### 5-2. Coffee Talk (Toge Productions, 2020)
- 손님의 모호한 주문 → 베이스·주재료·부재료를 고른다 → 정확히 맞히면 손님이 자기 이야기를 더 꺼낸다. 게임 속 14일로 구성된다. (https://en.wikipedia.org/wiki/Coffee_Talk_(video_game))
- 평가와 결과: 픽셀 아트와 로파이 음악은 호평, 사회 문제를 얕게 다룬다는 비판. 출시 첫 달 약 76억 루피아(약 55만 달러). (위키)
- 할 일: 14일 비트를 짤 때 바로 참고할 모델이다. 하루마다 주민 한 명의 이야기가 한 칸 깊어진다. 주민의 요청을 "따뜻하고 오래 두고 볼 수 있는 것"처럼 모호하게 말하게 하고, 정확히 맞히면 속마음 대사가 열린다.

### 5-3. Potionomics (Voracious Games, 2022)
- 물약 제작 → 손님과의 흥정을 카드 대결로(오프너·클로저, 인내심, 스트레스) → 번 돈으로 선물 → 관계 단계마다 새 카드. 개발자: "관계 단계마다 카드를 줘서 캐릭터에 투자할 이유를 하나 더 만들었다." (https://www.gamedeveloper.com/road-to-igf-2023/how-potionomics-turned-price-haggling-into-a-card-game)
- 결과: 판매 미확인.
- 할 일: 사슬 매듭이 진척될 때마다 원정·습격에서 쓰는 "주민 카드"(그 사람의 기술)를 준다. 선물 루프와 양념(습격, 원정)을 잇는 다리가 된다.

### 5-4. Papers, Please (Lucas Pope, 2013)
- 서류의 모순을 찾아 입국을 허가하거나 거부한다 → 하루 처리량이 가족 생계 → 규칙이 날마다 늘어난다. 루카스 포프: 대사를 줄이고 모호하게 남겨 상상에 맡겼다. (https://www.gamedeveloper.com/design/designing-the-bleak-genius-of-i-papers-please-i-)
- 결과: 10년 동안 500만 장. (https://gamedeveloper.com/business/papers-please-has-sold-5-million-copies-in-a-decade)
- 할 일: 주 후반(4~7일째)에 날마다 새 규칙을 하나씩 더한다. 예: "정찰병은 밤에 소리 나는 물건을 싫어한다", "젖은 물건은 창고 칸을 하나 더 먹는다". 규칙이 쌓이면 같은 물건의 정답이 날마다 달라진다. 효율과 마음(주민)이 부딪치는 선택을 가끔 넣는다.

### 5-5. Unpacking (Witch Beam, 2021)
- 상자에서 물건을 꺼내 새 집에 놓는다 → 등장인물도 대사도 없이 물건만으로 한 사람의 삶을 추리한다. GDC 2022 발표: 물건 약 1,000개, 모든 물건이 이야기에 보탬이 되게 골랐다. 남자친구 집에서 졸업장이 화장실 위에 걸렸다가 침대 밑으로 간다(둘 곳이 없음 = 관계의 갈등). (https://www.gamedeveloper.com/gdc2022/gdc-2022-unpacking-a-narrative-through-1-000-household-items)
- 결과: 10일 만에 10만 장, 2022년 11월 100만 장 이상. (https://www.nintendolife.com/news/2021/12/indie-hit-unpacking-sold-over-100k-units-in-just-10-days, https://www.nintendolife.com/news/2022/11/cosy-indie-darling-unpacking-has-sold-over-1-million-copies-since-launch)
- 할 일: 주민 방(머리맡 물건 배열)을 들여다보는 화면을 만든다. 받은 유물의 배치만으로 그 사람의 변화가 읽히게 한다. "둘 곳이 없는 물건" 장면으로 갈등을 보여 준다(선반이 꽉 찬 것도 이야기가 된다).

---

## 6. 수집

### 6-1. Pokémon TCG Pocket (Creatures·DeNA, 2024)
- ① 하루 무료 팩을 연다 → 카드 수집, 덱 → 짧은 대전.
- ② 팩 개봉 연출(카드를 문질러 공개, 움직이는 이머시브 카드)과 원더 픽(남이 연 팩의 5장을 뒤집어 섞은 뒤 1장 고르기, 확률 1/5). (https://www.shacknews.com/article/142323/pokemon-tcg-pocket-review-score)
- ③ 24시간마다 무료 팩 2개, 팩 모래시계로 대기 단축, 미션. ④ 확장팩 수집, 엠블럼 이벤트.
- ⑤ 칭찬: 후한 뽑기, 짧은 대전. 불만: 2025-01-28 교환 기능의 교환 토큰이 "약탈적이고 노가다"라는 반발이 나왔고, 결국 1,000토큰을 지급하고 2025년 가을에 토큰을 없애기로 했다. "같은 월간 사이클이 너무 오래 반복돼 지루하다", "원더 픽이 반복적이다", "이젠 대부분의 날 앱도 안 연다". (https://www.theouterhaven.net/2025/02/pokemon-tcg-pocket-backlash-leads-to-shifts-in-trading-feature/, https://pokemongohub.net/post/tcg-pocket/massive-pokemon-tcg-pocket-player-base-decline-dena-promises-improvements/)
- ⑥ 출시 약 4개월에 1억 다운로드(Sensor Tower), 1주년 1억 5천만. (https://sensortower.com/blog/pokemon-tcg-pocket-100-million-downloads, https://www.pocketgamer.biz/pokmon-tcg-pocket-surpasses-150m-downloads-in-under-a-year) 첫해 매출 13억 달러(AppMagic). (https://wnhub.io/news/analytics/item-49183) 그러나 MAU는 2025년 4~6월 3,900만에서 2026년 4~6월 2,300만으로 41% 줄었다(DeNA 실적). (https://www.wargamer.com/pokemon-trading-card-game/pocket-losing-players)
- ⑦ 할 일: 등급 공개 연출(문지르기, 빛)은 "찍기" 순간에 그대로 쓴다. 전설은 카드가 다르게 떨어진다. 다만 반복되는 신기함은 꺼진다(-41%). 매주 "새 카드"보다 "새 규칙, 새 쓰임"을 내야 한다. 교환이나 공유에 별도 화폐와 시간 제한을 걸지 않는다.

### 6-2. 스티커·카드 앨범 심리 (빈칸을 채우려는 욕구)
- 빈칸 효과: 미완성 세트는 가진 것보다 빠진 것을 떠올리게 한다. 통제 욕구가 큰 사람일수록, 수집 구조가 뚜렷하고 완성에 가까울수록 수집에 몰입한다. (https://www.ebsco.com/articles/sports-and-leisure/79943fea-265d-5b99-b50c-88c3f35f50db/seeking-structure-in-collections-desire-for-control-motivates-engagement-in-collecting)
- 진행 부여 효과(Nunes & Drèze 2006): 세차 쿠폰 8칸을 빈칸으로 받은 그룹은 19%, 10칸 중 2칸이 찍힌 쿠폰을 받은 그룹은 34%가 끝까지 채웠다. 필요한 구매 횟수는 둘 다 8번. (https://en.wikipedia.org/wiki/Goal_pursuit)
- 목표 경사 효과(Kivetz 외 2006): 커피 쿠폰 회원 948명은 무료 잔에 가까워질수록 구매 간격이 짧아졌다. (https://business.columbia.edu/sites/default/files-efs/pubfiles/1200/goalgradient.pdf)
- 쿠폰 수집 문제: 2018 월드컵 앨범 682장을 교환 없이 채우면 평균 약 773파운드(카디프대 수학자 계산). 마지막 몇 칸이 급격히 비싸진다. (https://www.itv.com/news/2018-03-29/773-to-fill-this-years-panini-world-cup-sticker-book)
- 할 일: 유물·손님 도감은 빈칸 실루엣으로 보이고, 처음부터 2칸을 채운 채 시작한다. 마지막 칸의 고통은 중복 유물 교환(문어 상인 등)과 소문 힌트로 줄인다. 꾸밈 꼬리표 진척은 "2/3"처럼 늘 보이게 한다.

---

## 7. 가벼운 로그라이트 사이드 모드

- **Balatro (LocalThunk, 2024)**: 포커 족보에 조커(수동 효과)의 시너지를 쌓아 점수 배율을 터뜨린다. 제작자의 조커 원칙: 테마가 그림·이름·효과와 맞물린다, 강한 효과는 조건부로 한다, 강한 단점은 결정을 흥미롭게 하고 다른 메커닉과 시너지를 만든다. 출시 첫 달 100만, 2025년 1월 500만 장 이상. (https://www.reddit.com/r/balatro/comments/1czo9g0/guidelines_for_joker_design/, https://www.pocketgamer.biz/balatro-exceeds-5-million-in-sales-on-all-platforms)
- **Slay the Spire (Mega Crit, 2017 앞서해보기)**: 전투 뒤 카드 3장 중 1장을 골라 덱을 쌓는 런. 개발 초기부터 지표 서버로 카드 채택률·승률을 모아 밸런스를 잡았다(GDC 2019). 2019년 150만 장, 후속작은 2026년 3월 앞서해보기 첫 주 300만 장. (https://gdcvault.com/play/1025731, https://www.gamedeveloper.com/business/after-a-worrisome-start-i-slay-the-spire-i-has-sold-more-than-1-5-million-copies, https://fullcleared.com/news/slay-the-spire-2-confirms-3m-sold-in-first-week/)
- **Dredge (Black Salt Games, 2023)**: 낮에는 평화로운 낚시, 밤에는 안개와 공포 미터 상승과 환각. 개발진은 낮을 일부러 아주 평화롭게 만들어 안심시킨 뒤 더 오래 머물도록 유혹했다. 첫해 10만 장을 바랐는데 100만 장 이상을 팔았다. (https://www.gamedeveloper.com/production/leveraging-the-unseen-to-turn-players-worst-fears-against-them-in-dredge, https://80.lv/articles/an-indie-game-dredge-has-sold-over-1-million-copies/)
- **Loop Hero (Four Quarters, 2021)**: 영웅은 자동으로 고리를 돌고, 플레이어는 지형·적 카드를 놓아 난이도를 스스로 정한다. 영웅이 죽어도 자원 일부는 캠프로 가져가 건물을 올린다. "실험을 두려워하지 않게" 하려는 설계. 첫 주 50만, 2021년 12월 100만 장. (https://www.windowscentral.com/loop-hero-interview, https://www.rpgsite.net/news/10867-loop-hero-sells-500-000-copies-in-first-week-of-sale, https://www.gamingonlinux.com/2021/12/loop-hero-from-four-quarters-hits-a-million-sales)
- **모은 유물이 사이드 모드에서 의미를 갖게 하는 법 (할 일)**
  1. 덱은 내가 찍은 유물 중 N장을 골라 짠다(Slay the Spire식). 등급은 "세기"가 아니라 "조건이 얼마나 까다로운가"로 나눈다(Balatro 원칙). 흔한 유물도 쓸모가 생긴다.
  2. 주민 사슬 매듭이 특수 카드를 연다(Potionomics). 본편 선물이 사이드 모드 실력이 된다.
  3. 런 결과는 본편으로 돌아온다(Loop Hero의 캠프). 실패해도 꾸밈 재료나 소문 하나는 챙긴다.
  4. 유물은 런에서 소모되거나 잃지 않는다. 본편 수집을 빼앗는 느낌을 주면 안 된다.
  5. 공포는 사이드 모드 안에만 둔다(Dredge의 밤). 본편 방주는 늘 안전한 창 안쪽이다(8절 Project Horseshoe).
  6. 밸런스는 처음부터 지표(카드 채택률, 승률)를 모아 잡는다(Slay the Spire GDC 2019).

---

## 8. 프레임워크 (짧게)

- **MDA (Hunicke·LeBlanc·Zubek, 2004)**: 메커닉 → 다이내믹 → 미학. 디자이너는 메커닉부터 만들고 플레이어는 미학부터 겪는다. 질랜디아 점검: 목표 미학(발견, 이야기, 표현)이 감쇠 배율 같은 메커닉 때문에 "선반에 놓는 노동"이라는 다이내믹으로 변하지 않았나. (https://users.cs.northwestern.edu/~hunicke/MDA.pdf)
- **LeBlanc의 8가지 재미**: 감각, 판타지, 서사, 도전, 동료애, 발견, 표현, 복종(시간 때우기). 질랜디아의 주력은 발견(바코드), 서사(사슬), 표현(꾸밈), 판타지(심해 방주). 약한 곳은 도전(추리)과 동료애(사회). (같은 PDF)
- **자기결정성 이론·PENS (Ryan·Rigby·Przybylski 2006, Motivation and Emotion 30권 4호)**: 자율성, 유능감, 관계성이 각각 따로 즐거움과 다시 할 의향을 예측한다. 첫 제안을 그대로 누르면 자율성이 낮고, 정답이 뻔하면 유능감이 낮다. 단서 추리로 둘을 함께 올리고, 관계성은 주민이 내 선물을 기억하는 장면으로 채운다. (https://selfdeterminationtheory.org/player-experience-of-needs-satisfaction-pens/)
- **Quantic Foundry 동기 모델**: 6개 군 12개 동기. 액션(파괴·흥분), 사회(경쟁·공동체), 숙달(도전·전략), 성취(완성·힘), 몰입(판타지·이야기), 창의(디자인·발견). 질랜디아가 노릴 곳은 몰입, 창의, 성취(완성). (https://quanticfoundry.com/2015/07/20/how-we-developed-the-gamer-motivation-profile-v2/)
- **Project Horseshoe 2017 아늑함 보고서 (Daniel Cook 등)**: 아늑함 = 안전(위험과 손실이 없음), 풍요(기본 욕구가 채워짐), 부드러움(낮은 각성 상태에서도 몰입). 바깥이 있다면 그 불편과 위험이 안쪽을 더 아늑하게 만든다("창을 때리는 찬비는 독서 구석의 온기를 강조한다"). 아늑함을 깨는 것: 외적 보상이 만드는 급한 필요, 강제 돌봄과 필수 유지보수, 끼어드는 알림. (https://www.projecthorseshoe.com/reports/featured/ph17r3.htm) 질랜디아: 습격은 창밖의 비로, 같은 날 감쇠와 결핍 표시는 의무처럼 느껴지지 않게.
- **Raph Koster, A Theory of Fun**: 재미는 패턴을 배우는 것이고, 패턴을 다 익히면 지루해진다. 주 후반 고갈은 패턴이 다 소진됐다는 신호이므로 새 패턴(규칙)을 넣어야 한다. (https://www.oreilly.com/library/view/theory-of-fun/9781449363208/)

---

## 9. 가로질러 보이는 것

1. **현실 행동 게임의 생존 공식**: 신기함(1~6주)이 꺼지기 전에 약속·관계·행사로 넘어간다. Pokémon GO는 레이드·커뮤니티 데이·친구로, Pikmin Bloom은 이벤트 패스와 현장 행사로, Pokémon Sleep은 주간 리듬으로 넘어갔다. 실패작(Wizards Unite, Minecraft Earth)은 넘어가기 전에 핵심 동기부터 비어 있었다.
2. **매일 오게 하는 장치는 벌이 아니라 창(시간 창)이다**: 식사 3칸(Sleep), 생일 ×8(Stardew), 저녁 1시간(GO), 밤 손님(ACNH), 저녁 귀환(Finch). 질랜디아의 같은 날 감쇠는 그 반대(벌) 방향이었다.
3. **비운 사이 보상은 짧은 부재부터 보상해야 루프가 닫힌다**: 네코아츠메는 몇 분, Finch는 반나절, Sleep은 하룻밤. 질랜디아의 꾸밈 손님은 하루 확률이라 1주일에 0번도 가능했다.
4. **정답을 숨기는 게임은 맞힌 순간을 연출한다**(Strange Horticulture, Coffee Talk, Stardew 선물 기록, Tomodachi 최애). 단, 스타듀 불만처럼 취향이 캐릭터와 무관하면 그냥 찍기가 된다. 취향은 캐릭터 설정에서 추론할 수 있어야 한다.
5. **수집만으로는 붙잡지 못한다**(Wizards Unite 스티커북, Minecraft Earth 희귀도 붕괴, TCG Pocket MAU -41%). 모은 것의 쓰임이 계속 바뀌어야 오래 간다. 질랜디아의 「어디로」가 바로 그 쓰임 장치이므로, 제안 정렬이 그 고민을 없애지 않게 지켜야 한다.
6. **현실 공급이 마를 때의 해법 셋**: (a) 대체 입력(Monster Rancher DX의 검색 DB), (b) 같은 입력의 새 의미(Pikmin Bloom의 장소별 장식, 질랜디아의 재스캔 선물), (c) 사회적 공급(Monster Rancher의 CD 빌리기, Barcode Kanojo의 같은 바코드 친구).

---

## 9-2. 미확인으로 남은 것과 조사의 한계

- 판매·매출 미확인: Barcode Battler 판매 대수, Barcode Kanojo 종료일, Cozy Grove·Strange Horticulture·Potionomics 판매량, Finch 매출, Coffee Talk 누적 판매(첫 달만 확인).
- 리텐션 미확인: Fallout Shelter 7일·30일 리텐션은 공개 자료가 없다. 이번에 다룬 게임 대부분이 D1/D7/D30을 공개하지 않는다. 리텐션 근거는 MAU·DAU 추이(Pokémon GO, TCG Pocket)와 개발사 발언(Fallout Shelter)으로 대신했다.
- 원문 미열람(검색 요약 기준): Spiritfarer "같은 요리 연달아 금지"(가이드 사이트 403), Monster Rancher 수명 FAQ, Stardew 스팀 토론 불만 요약.
- 위 항목의 숫자는 문서 어디에서도 추정치로 채우지 않았다.

---

## 10. 질랜디아에 바로 쓸 교훈 TOP 12

### 1. 저녁 세션을 "받는 시간"으로 바꾼다 [저녁]
- 근거: Finch(아침에 떠난 새가 저녁에 이야기를 들고 돌아옴), Neko Atsume(떠나 있는 사이 손님이 옴), ACNH(19~4시에만 오는 셀레스트와 다음 날 아침 별 조각).
- 적용: 아침에 보낸 원정·심부름이 저녁 첫 화면에 "돌아온 것" 카드로 온다. 19시 이후에만 오는 밤 손님 1종을 두고 다음 날 아침 흔적을 남긴다. 저녁 세션의 시작은 「어디로」가 아니라 "받기"다.
- 출처: https://foxdata.com/en/blogs/finch-as-app-store-editors-choice-a-self-care-companion/ · https://nookipedia.com/wiki/Wishing_Star

### 2. 같은 날 감쇠를 시간대 칸과 특별한 날로 바꾼다 [저녁]
- 근거: Pokémon Sleep(요리 3칸: 4~12시, 12~18시, 18~4시), Stardew(주민마다 하루 1개, 주 2개, 생일 ×8).
- 적용: 주민별 선물 신선도를 아침·낮·저녁 칸마다 리셋하고, 같은 칸 안의 두 번째부터는 값 대신 덤 대사를 준다. 14일 달력에 주민 기념일 4~5개를 배치한다(그날 그 사람 ×3과 전용 대사).
- 출처: https://www.dexerto.com/pokemon/how-to-cook-dishes-in-pokemon-sleep-application-2221762 · https://stardewvalleywiki.com/Friendship

### 3. 반복 제한은 숫자가 아니라 사람이 말하게 한다 [저녁·첫 제안]
- 근거: Spiritfarer(같은 요리는 연달아 두 번 줄 수 없음), Tomodachi Life(최악 음식에는 배를 움켜쥐는 반응).
- 적용: "×0.5" 같은 배율 표시를 없애고 주민이 "어제 그거 또요? 그럼 저 친구한테 주세요"처럼 다른 사람을 가리키게 한다. 감쇠가 벌이 아니라 다음 「어디로」의 단서가 된다.
- 출처: https://en.wikipedia.org/wiki/Spiritfarer · https://tomodachi.fandom.com/wiki/Food

### 4. 꾸밈 손님은 "닫았다 열면" 오게 한다 [꾸밈 루프]
- 근거: Neko Atsume(앱을 잠시 닫았다 열면 고양이가 와 있음, 희귀 26종은 특정 물건이 필요, 여러 번 오면 기념품).
- 적용: 꼬리표를 완성하면 같은 날이라도 다음 세션에 첫 손님을 확정한다. 희귀 손님은 꼬리표 2개 조합. 손님이 오기 전 흔적(발자국, 비늘)으로 예고하고, 3번 오면 기념품 유물을 남긴다.
- 출처: https://en.wikipedia.org/wiki/Neko_Atsume · https://www.killscreen.com/cats-finally-take-over-the-world-with-mobile-game-neko-atsume/

### 5. 꾸밈 묶음은 빈칸이 보이는 체크리스트로, 1칸을 채운 채 시작한다 [꾸밈 루프]
- 근거: Stardew 꾸러미(채우면 마을이 영구히 바뀜), Nunes & Drèze(2칸이 미리 찍힌 쿠폰 34% 대 빈 쿠폰 19% 완주).
- 적용: 꼬리표마다 필요한 범주 칸을 아이콘으로 보이고, 방을 지을 때 1칸을 미리 채워 준다. 완성하면 방주가 영구히 바뀐다(통로, 불빛, 손님 자리).
- 출처: https://stardewvalleywiki.com/Bundles · https://en.wikipedia.org/wiki/Goal_pursuit

### 6. 가치 순 정렬을 버리고 단서와 수첩을 준다 [첫 제안]
- 근거: Strange Horticulture("결정적 단서는 늘 하나 있다"), Coffee Talk(모호한 주문을 맞히면 속마음이 열림), Stardew 선물 기록.
- 적용: 제안 순서를 가치 순이 아닌 고정 순(사람 → 방 → 선반)으로 하고, 주민 옆에 오늘의 단서 한 줄("손이 시리다고 하셨습니다")을 둔다. 건넨 뒤에는 "취향 수첩"에 남긴다. 지표: 첫 제안 그대로 비율 60~100% → 40% 미만.
- 출처: https://www.gamedeveloper.com/design/strange-horticulture---bad-viking · https://en.wikipedia.org/wiki/Coffee_Talk_(video_game)

### 7. 좋은 답을 둘 만들고 대가는 다르게 한다 [첫 제안·재미]
- 근거: Papers, Please(처리량 대 양심), Potionomics(돈 대 관계 카드), Strange Horticulture(고른 것에 따라 뒷날 사건이 갈림).
- 적용: 매 「어디로」에 각자 다른 이득(사슬 진척 / 꾸밈 완성 / 오늘 필요)을 가진 선택지를 둘 이상 두고, 고르지 않은 쪽 주민이 다음 날 한마디 한다.
- 출처: https://www.gamedeveloper.com/design/designing-the-bleak-genius-of-i-papers-please-i- · https://www.gamedeveloper.com/road-to-igf-2023/how-potionomics-turned-price-haggling-into-a-card-game

### 8. 주 후반에는 새 규칙을 하나씩 더한다 [주 후반]
- 근거: Papers, Please(날마다 규칙 추가), Koster(패턴을 다 익히면 지루해짐), Pokémon Sleep(매주 월요일 장소 교체), TCG Pocket(같은 월간 사이클 반복 → MAU -41%).
- 적용: 4~7일째에 매일 규칙 하나(예: 정찰병은 밤에 소리 나는 물건을 싫어함, 물때엔 젖은 것의 가치가 오름). 같은 집 물건의 정답이 날마다 달라진다. 8일째에 "물때"를 바꿔 2주차 규칙 세트를 연다.
- 출처: https://bulbapedia.bulbagarden.net/wiki/Professor_Neroli · https://www.wargamer.com/pokemon-trading-card-game/pocket-losing-players

### 9. 현실 공급이 마르는 날을 설계한다 [주 후반·장기]
- 근거: BMJ 연구(Pokémon GO 걸음 증가가 6주째 사라짐), Monster Rancher DX(CD 대신 검색 DB), Pikmin Bloom(장소 종류별 장식).
- 적용: (a) 같은 바코드에 새 의미(범주별 변형, 주민 맥락별 반응), (b) 찍을 게 없는 날 "기억 속 물건" 하루 1개(일반 범주 목록, 실물보다 약하게), (c) 떠날 때 카드로 장보기 목록을 예고.
- 출처: https://pmc.ncbi.nlm.nih.gov/articles/PMC5154977 · https://pikminwiki.com/Decor

### 10. 소문과 숨은 규칙으로 찾는 재미를 만든다 [주 후반·장기]
- 근거: Monster Rancher(소문, 잡지, CD 빌려주기), Barcode Battler(특별한 바코드 소문에 상품 품절), Barcode Kanojo(같은 바코드를 찍은 사람끼리 친구).
- 적용: 바코드 숫자 패턴에 찾아낼 수 있는 규칙 3~5개를 심고, 소문 방송으로 주 1개씩 힌트를 준다(상표 없이 묘사). 찾으면 관리실 일지에 남는다. 나중에 이웃 방주 소문(비동기)으로 넓힌다.
- 출처: https://cogconnected.com/review/monster-rancher-1-2-dx-review/ · https://retrohandhelds.gg/game-over-the-history-of-barcode-gaming/

### 11. 30일 뼈대는 배웅, 도감, 복원으로 짠다 [장기]
- 근거: Spiritfarer(배웅과 영혼의 꽃), ACNH(박물관과 관장 해설), Stardew(꾸러미로 마을 복원), Fallout Shelter("주말이면 다 끝낸다"는 경고).
- 적용: 11개 사슬마다 끝 장면(떠날지 머물지 고름)과 그 사람이 남기는 유물 하나를 둔다. 유물 도감에 관리실 해설을 붙인다. 7·14·30일째에 방주의 새 층을 연다.
- 출처: https://en.wikipedia.org/wiki/Spiritfarer · https://www.deconstructoroffun.com/blog//2015/07/why-fallout-shelter-popped-and-dropped.html

### 12. 습격·원정은 창밖의 비로, 사이드 모드는 "유물 = 조커"로 [재미·장기]
- 근거: Project Horseshoe(바깥의 위험이 안쪽을 더 아늑하게 함), Dredge(평화로운 낮과 무서운 밤), Loop Hero(죽어도 자원은 캠프로), Balatro(강한 효과는 조건부).
- 적용: 습격은 결석과 무관하게 하고 손실 상한을 작게 두며, 결과는 이야기와 흔적으로 남긴다. 사이드 모드 덱은 찍은 유물 중 N장, 등급은 조건의 까다로움, 런 보상은 본편 꾸밈 재료로 돌아오고 유물은 소모되지 않는다.
- 출처: https://www.projecthorseshoe.com/reports/featured/ph17r3.htm · https://www.windowscentral.com/loop-hero-interview
