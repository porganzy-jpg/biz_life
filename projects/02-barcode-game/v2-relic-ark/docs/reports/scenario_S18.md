# 시나리오 보고 — S18-S 플레이테스트 반영 문장 (2026-10-04)

근거: `docs/reports/playtest_7day_20261004.md`. 목소리: `docs/TEXT_VOICE.md`. 커밋하지 않았다.

## 1. 유물 이름 — `data/relic_templates.json`
**줄기 수**(전 → 후): 식품 4→15, 음료 4→14, 의약 4→12, 전자 4→12, 문구 4→13, 서적 4→12, 의류 4→12, 담배·주류 3→12, 모름 2→6. 형용사는 10→16개다.
**기존 구조는 그대로다.** 카테고리 배열과 각 항목의 `name`·`flavor`·`tags`가 그대로이고, 기존 줄기는 배열 앞쪽에 순서 그대로 있다. 그래서 지금 서버 코드도 바꾸지 않고 돌아간다(다양성만 는다). 새 tags는 기존 어휘 안에서만 골랐다.
**새로 생긴 것**(서버 개발용):
| 키 | 뜻 |
|---|---|
| 항목마다 `subtype` | 하위 종류. 예: 음료는 water·soda·coffee·tea·milk·juice·alcohol, 문구는 pen·paper·sticky·toy·tape·tool·document |
| `_subtypes.<카테고리>.<subtype>` | 화면 이름(하위 종류를 고르는 화면이 생기면 쓴다) |
| `_family_subtypes.<가문 7자리>` | 알려진 18개 가문의 하위 종류 목록. 예: 커피 가문 → coffee·tea, 펜 가문 → pen, 주류 가문 → liquor·beer |
| `_family_only.drink = ["alcohol"]` | 모르는 음료 가문에는 술 문장을 내지 않는다 |

**고르는 법**(제안, `_for_dev`에도 적어 두었다): 가문 목록이 있으면 그 subtype만 남긴다 → 없으면 `_family_only`를 뺀다 → 플레이어가 하위 종류를 고르면 그것만 남긴다 → 남은 pool에서 지금처럼 `(seed + 희귀도×3) % len`.
이렇게 하면 커피 바코드가 술 문장을 받거나 볼펜이 붙이는 메모 문장을 받는 일이 없어진다. 단, **모르는 가문**은 같은 카테고리 안에서 하위 종류가 시드로 정해진다. 예를 들어 모르는 우유 바코드가 커피 문장을 받을 수 있다. 이것까지 막으려면 카테고리를 고를 때 하위 종류도 함께 고르게 해야 한다(개발·PM 판단).
- 줄기끼리 서로의 끝부분이 되지 않는 것을 확인했다(`stem_of`의 끝맺음 매칭이 안전하다). 배열 길이가 바뀌었으므로 **같은 바코드라도 예전과 다른 줄기가 나올 수 있다.** 출시 전이라 허용했다.

## 2. 깊이 문턱 방송 — `data/ui_moments.json`
`depth.first_60` · `depth.first_120` · `depth.first_180`. 처음 넘을 때 한 번만 나간다. 180은 "벽이 끝나는 층, 그 아래 어둠이 해구"를 알리고, 「먼 울음」은 건드리지 않는다.

## 3. 아침 「밤사이」 패널 — `ui_moments.morning`
`title`(「밤사이」) · `open` · `production`({food} {water} {morale}) · `raid`(그 뒤에 `night_judge.*` 한 줄) · `imprint`({name}) · `expedition_back`({name}) · `guest` · `octopus` · `box_opened`({pattern}) · `rumor`({rumor}) · `nothing` · `close`. 순서는 `morning._order`에 있다.

## 4. 값이 0이 된 재스캔 — `ui_moments.shelf.rescan_zero[]` (7줄, 무작위로 하나)

## 5. 고친 것
- **습격 미리 보기 시제**: 「지금 맞서시면 유리에 금이 갔습니다」가 과거형인 것은 서버가 결과용 과거형(`combat.RESULT_KO`)을 미리 보기에도 쓰기 때문이다. 미래형 키를 새로 만들었다: `ui_moments.raid_preview.{held,scarred,breached,passed}`(「막을 수 있습니다」·「유리에 금이 갈 겁니다」·「방을 잃게 됩니다」·「그냥 지나갈 겁니다」). 서버가 `would_ko`를 이 키에서 읽어야 한다.
- **자리표시자 바로 뒤의 조사**
  - 데이터: `imprints.json`에서 「{name}은」 셋을 「{name}의 ~」 꼴로 고쳤다(외형 문장 9·12·14).
  - 다른 데이터 파일을 전수 검사했다. 남은 것은 「{name}의」 뿐인데, 「의」는 받침과 상관없이 붙어서 안전하다.
- **코드 문자열**(개발 소유): `docs/text/ui_rewrite_s18.tsv`(file / old / new)
  - `base_expedition.js` 「을 지키고 계십니다」 → 「 쪽을 지키고 계십니다」(플레이테스트의 「식량창고을」)
  - 같은 줄의 줄표 조각 → 「. 나가시면 그 방이 그만큼 약해집니다」
  - 「…부품 1이 듭니다」 → 「… 정도 듭니다」(숫자 뒤 조사 문제)
  - `server.py` 「「{gone_card}」을(를)」 → 「「{gone_card}」 하나를」

## 6. 선반이 찼을 때 — `ui_moments.shelf.full`
`prompt`({item}) · `swap_label`(「바꿔 놓기」) · `keep_label`(「그대로 두기」) · `moved`(창고 안쪽으로 옮겼고, 도감에는 남는다) · `placed` · `kept` · `storage_label`(「창고 안쪽」)

## 7. 추가 요청(PM)
- **(a) 생물 버릇** — `creatures.json`의 위협 열하나에 `habit`을 넣었다(텍스트만, 다른 필드는 그대로이고 CRLF 서식도 지켰다). 막는 법을 직접 말하지 않고 습성으로 짐작하게 했다. 첫 주 생물인 긴목이 가장 직접적이다: 「저 녀석은 불빛을 보면 다가와 유리에 얼굴을 붙입니다. 불 꺼진 창 앞에는 오래 있지 않습니다.」
  - 덮개 버릇 「아래에서 움직임이 느껴지면 그 자리에 눌러앉습니다. 아무것도 움직이지 않으면 돌인 줄 알고 떠납니다.」는 관문(가만히 있기)에 맞췄다. 사건 카드 `deep_lid_settles`의 "움직이는 것 위에는 앉지 않는다"는 사람들이 믿어 온 **틀린 수**라서 일부러 반대로 두었다.
- **(b) 재료 출처** — `ui_moments.material_hint.<재료>`. 키는 `economy.json material_sources`와 같다(food·water·med·parts·cloth·knowledge·trade·scrap). 「모자랍니다」 옆에 붙이는 한 줄이다.

## 8. 검증
- JSON 유효성: relic_templates·ui_moments·creatures·imprints 모두 통과.
- 새 문장의 금지어 0건: 탑·봉인 어휘·하늘·도시·거리·옥상·일곱·열하나·위협·줄표.
- 자리표시자 바로 뒤 조사: 0건.

## 9. 플레이테스트에서 본, 범위 밖의 것(제안)
- 각인 「빈 자리」의 문장(검은 띠, 상복 같은 톤)이 사건(성문 오독)과 맞지 않는다. 각인 문장을 사건별로 다시 볼 필요가 있다.
- 하루 마감 문장이 사실과 다르게 나온다(나가지 않은 사람의 말수, 되찾은 층 수). 문장 문제가 아니라 서버가 주는 값의 문제로 보인다.
- 문어 문장이 「아이」를 가정한다(아이가 없는 방주도 있다). `{kid}`가 없을 때 쓸 대체 줄이 필요하다. 다음 스프린트에 쓰겠다.
