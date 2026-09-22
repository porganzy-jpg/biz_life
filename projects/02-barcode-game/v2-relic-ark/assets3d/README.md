# assets3d — CC0 3D 소스 팩 (git에는 이 README만 올라간다)

렌더·GLB 파이프라인(`tools/blender_*.py`)이 여기서 소품·캐릭터·공룡을 읽는다. 용량(약 140MB) 때문에 저장소에서 제외했다. 아래대로 내려받아 같은 폴더 구조로 풀면 된다. 전부 **CC0(퍼블릭 도메인)**, 상업 이용 가능.

| 폴더 | 팩 | 출처 | 용도 |
|---|---|---|---|
| `kenney/` | Kenney Survival Kit 2.0 (80 모델, GLB) | https://kenney.nl/assets/survival-kit | 통·상자·병·침낭·작업대·도구·바위·풀 |
| `quaternius/Survival Pack - Sept 2020/` | Quaternius LowPoly Survival Pack (.blend) | https://opengameart.org/content/lowpoly-survival-pack | 캔·물병·구급함·붕대·배터리·라디오·물탱크 |
| `quaternius_chars/Ultimate Animated Character Pack - Nov 2019/` | Quaternius Ultimate Animated Characters (.blend/FBX/glTF) | https://quaternius.com/packs/ultimatedanimatedcharacter.html (Google Drive 폴더) | 8역할 캐릭터 베이스 + Idle/Walk/PickUp… 액션 |
| `quaternius_dinos/Dinosaur Animated Pack - Dec 2018/` | Quaternius Animated Dinosaurs (FBX) | https://quaternius.com/packs/animateddinosaurs.html (Google Drive 폴더) | 공룡 6종(Trex·Velociraptor·Triceratops·Stegosaurus…) |
| `kenney_blocky/` | Kenney Blocky Characters | https://kenney.nl/assets/blocky-characters | 캐릭터 후보 비교(B행) |
| `kenney_prot/` | Kenney Animated Characters Protagonists | https://kenney.nl/assets/animated-characters-protagonists | 캐릭터 후보 비교(C행) |

Google Drive 폴더는 `python -m pip install gdown` 후 `python -m gdown --folder <드라이브 URL>` 로 받는다.

기대 경로 예:
```
assets3d/kenney/Models/GLB format/barrel.glb
assets3d/quaternius/Survival Pack - Sept 2020/Blends/Can_Red.blend
assets3d/quaternius_chars/Ultimate Animated Character Pack - Nov 2019/Blends/Chef_Male.blend
assets3d/quaternius_dinos/Dinosaur Animated Pack - Dec 2018/FBX/Trex.fbx
```
