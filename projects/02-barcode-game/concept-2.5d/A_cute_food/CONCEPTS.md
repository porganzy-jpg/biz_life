# 컨셉 A — 귀여운 계열 · 편의점 식품/과자 모티프 (2.5D)

편의점 매대의 식품·과자 바코드를 스캔하면 태어나는 몬스터들. 아트 디렉션은 **2.5D**(아이소메트릭 느낌의 게임 캐릭터 렌더, 소프트 셀 셰이딩 + 은은한 3D 볼륨, 토이 같은 질감)이며, 이 팀은 "귀여움 우선, 실루엣만 봐도 어떤 음식인지 알 수 있게"를 목표로 6종을 뽑았다.

공통 스타일 프리픽스(모든 프롬프트 앞에 동일하게 사용):

```
2.5D isometric game character render, soft cel shading with subtle 3D volume, clean outlines, vibrant colors, plain pastel background, centered full body, toy-like, high quality, no text,
```

생성: pollinations.ai (768×768, nologo, 하단 4.5% 크롭). 아래 프롬프트는 프리픽스 뒤에 이어지는 본문이다.

---

## 01. 삼각슬라임 (`01_gimbap_slime.png`)

- **모티프 상품 & 바코드 카테고리**: 삼각김밥 (EAN-13 `880` 한국 / 식품 – 즉석식품·도시락류, CU·GS25·세븐일레븐 PB 상품)
- **속성**: 음식
- **성격**: 아침마다 배고픈 사람 옆에 붙어 있는 느긋한 식탐 슬라임.
- **진화 아이디어**: 김 한 장 → 참치마요 속이 비치는 "속보이는 삼각슬라임" → 삼각김밥 3단 탑 "삼각김밥왕".
- **시그니처 동작**: 몸 가운데 김 띠를 스르륵 벗겨내며 위협 → 실제로는 밥알이 몇 알 떨어져서 귀엽게 끝남.
- **프롬프트(v2)**: `a triangular onigiri rice ball character with black seaweed band, big sparkling eyes, rosy cheeks, tiny arms` / seed ``

```
cute chubby slime monster shaped like a Korean triangle rice ball (samgak gimbap), white sticky rice body with a glossy jelly sheen, dark seaweed band wrapped around the middle like a belt, tiny stubby arms, big round sparkling eyes, small happy mouth, a few rice grains dripping off, kawaii mascot, pastel mint background
```

- **이미지 평가**: 재생성 후 일치 — 김 위에 얹힌 흰 주먹밥에 얼굴. 검증 문구(kawaii food mascot… onigiri rice ball character) seed 42. 이전 고양이 코스튬은 `_alt`

---

## 02. 우유팩냥 (`02_milk_carton_cat.png`)

- **모티프 상품 & 바코드 카테고리**: 200ml 흰 우유 (EAN-13 `880` / 식품 – 유제품·가공유, 서울우유·매일유업 등)
- **속성**: 물
- **성격**: 차갑게 굴지만 개봉(뚜껑 접힘)해 주면 금방 마음을 여는 츤데레 고양이.
- **진화 아이디어**: 200ml 팩 → 1L 대용량 팩(몸이 길어지고 목도리처럼 꼬리가 감김) → 딸기·초코 3팩 묶음 "삼색우유냥".
- **시그니처 동작**: 게이블탑(뾰족 지붕) 귀를 팔랑거리며 우유 한 방울을 코끝에서 튕겨 상대를 얼린다.
- **프롬프트(v2)**: `a white milk carton character with cat ears and a cat face, blue stripe, tiny paws` / seed ``

```
cute kitten monster whose body is a small white milk carton with a gable top, cat ears poking out of the folded carton top, fluffy striped tail, tiny paws, pale blue and white carton with a simple cow spot pattern, blushing cheeks, curious wide eyes, a drop of milk on its nose, kawaii mascot, pastel yellow background
```

- **이미지 평가**: 재생성 후 대체로 일치 — 각진 몸통 + 우유팩 접힌 윗부분을 모자처럼 쓴 고양이. seed 2202. 이전 버전 `_alt`

---

## 03. 컵라곤 (`03_cup_noodle_dragon.png`)

- **모티프 상품 & 바코드 카테고리**: 컵라면 (EAN-13 `880` / 식품 – 면류·즉석면, 농심·오뚜기·팔도 등)
- **속성**: 불
- **성격**: 3분만 기다려 주면 뭐든 해내는 성급한 열혈 아기 드래곤.
- **진화 아이디어**: 소컵 → 큰사발(몸집 2배, 뚜껑을 방패처럼) → 뚜껑이 날개로 펼쳐지는 "왕뚜껑 드래곤".
- **시그니처 동작**: 컵 안에서 끓는 김을 뿜어 "매운 김 브레스"를 쏜다.
- **프롬프트(v2)**: `a baby dragon character sitting in a red cup noodle bowl, noodle mane, steam, big eyes` / seed ``

```
cute baby dragon monster hatching from a cup of instant ramen noodles, the paper cup is its round belly, curly noodle mane and noodle tail, steam wisps rising from the top, tiny red chili horns, small flapping wings, round cheeks, fiery orange and cream colors, kawaii mascot, pastel peach background
```

- **이미지 평가**: 일치 — 빨간 컵라면 용기 안에 불꽃 머리 아기 용. 날개·수염은 없지만 컨셉이 바로 읽힘

---

## 04. 바나나오리 (`04_banana_milk_duck.png`)

- **모티프 상품 & 바코드 카테고리**: 항아리형 바나나맛 우유 (EAN-13 `880` / 식품 – 가공유·가향우유, 빙그레)
- **속성**: 바람
- **성격**: 배가 볼록해서 뒤뚱거리지만 물 위에서는 누구보다 잘 뜨는 낙천주의자.
- **진화 아이디어**: 항아리 한 병 → 4개 묶음이 등에 새끼처럼 올라탄 "바나나 가족" → 빨대가 왕관이 되는 "바나나 여왕".
- **시그니처 동작**: 머리 위 빨대로 바람을 불어 상대를 둥실 밀어낸다.
- **프롬프트(v2)**: `a yellow banana milk bottle character with a duck beak and orange duck feet, big eyes` / seed ``

```
cute duckling monster shaped like a chubby pot-bellied yellow banana milk bottle, wide round body with a narrow neck, orange beak, small wings, soft yellow plastic sheen, a straw sticking out of its head like a feather, waddling pose, sleepy happy eyes, kawaii mascot, pastel sky blue background
```

- **이미지 평가**: 대체로 일치 — 통통한 노란 몸 + 주황 부리. 병 실루엣보다 병아리에 가까움

---

## 05. 초코파곰 (`05_choco_pie_bear.png`)

- **모티프 상품 & 바코드 카테고리**: 초코파이 (EAN-13 `880` / 식품 – 과자·파이류, 오리온·롯데)
- **속성**: 대지
- **성격**: 겉은 단단해 보이지만 속은 마시멜로처럼 물렁한, 情(정) 많은 곰.
- **진화 아이디어**: 낱개 1개 → 12개입 박스를 갑옷처럼 입은 "박스곰" → 바나나·딸기맛 코팅이 섞인 "믹스파이 곰".
- **시그니처 동작**: 몸을 반으로 살짝 벌려 마시멜로 층을 보여주며 상대를 홀린다(방어 버프).
- **프롬프트(v2)**: `a round chocolate pie character with bear ears and a sleepy bear face, marshmallow belly` / seed ``

```
cute round teddy bear monster whose body is a chocolate-coated snack pie, puffy brown chocolate shell with a fluffy white marshmallow layer peeking out at the seam, round bear ears, tiny paws, glossy chocolate sheen, sweet gentle smile, kawaii mascot, pastel pink background
```

- **이미지 평가**: 일치 — 초콜릿 컵 속 분홍 곰 얼굴. 초코파이 곰으로 충분히 읽힘

---

## 06. 젤리파리 (`06_jelly_jellyfish.png`)

- **모티프 상품 & 바코드 카테고리**: 구미 젤리 (EAN-13 `880` / 식품 – 캔디·젤리류, 하리보 수입품은 EAN `400`대 독일)
- **속성**: 빛
- **성격**: 빛을 받으면 몸 색이 바뀌는, 변덕스럽지만 해롭지 않은 장난꾸러기.
- **진화 아이디어**: 단색 젤리 → 무지개 그라데이션 → 촉수가 곰젤리 군단이 되어 함께 다니는 "젤리 군체".
- **시그니처 동작**: 투명한 몸으로 빛을 굴절시켜 무지개 섬광(눈부심 디버프)을 뿜는다.
- **프롬프트(v2)**: `a translucent gummy candy jellyfish character, rainbow gradient, glossy, sweet smile` / seed ``

```
cute jellyfish monster made of translucent gummy candy, round glossy dome head in rainbow gradient colors, wobbly gummy bear shaped tentacles dangling below, sugar crystal sparkles on the surface, big sparkling eyes, floating pose, kawaii mascot, pastel lavender background
```

- **이미지 평가**: 일치 — 반투명 무지개 젤리 몸체에 작은 얼굴. 젤리 질감 표현 좋음