# 15-dopamine-detox (가칭 고요)

- 기획: [PLAN.md](PLAN.md) · 차별화: [DIFFERENTIATION.md](DIFFERENTIATION.md)
- 대표 기능(2026-10-17 결정): **A. 한국형 숏폼 팩** — 카톡 숏폼 탭·네이버 클립·유튜브 쇼츠·인스타 릴스를 앱은 둔 채 구간만 닫는다.

## P0 Android 구조 (`android/`)
| 파일 | 역할 |
|---|---|
| `assets/shortform_rules.json` | 앱별 숏폼 감지 규칙(view id, 선택된 탭 이름). **코드 수정 없이 여기만 고친다** |
| `Rules.kt` | 규칙 JSON 로드. `filesDir/shortform_rules.override.json`이 있으면 그것을 우선 사용 |
| `Matcher.kt` | 화면 트리에서 숏폼 구간 찾기 |
| `BlockPolicy.kt` | 찾았을 때 BACK / HOME / NONE 결정(쿨다운·승격) |
| `ShortformBlockerService.kt` | 접근성 서비스 본체 |
| `NodeDumper.kt` | 덤프 모드: 화면 트리를 파일로 저장 → 새 규칙 찾기 |
| `BlockLog.kt` | 차단 기록 csv(충동 지도 원자료) |

## 규칙 검증 절차 (카톡·네이버)
1. 앱에서 **덤프 모드**를 켜고 카톡 숏폼 탭을 3초 이상 연다.
2. `adb pull /sdcard/Android/data/app.goyo.detox/files/dumps/`
3. 덤프에서 `[SELECTED]` 탭과 숏폼 플레이어 id를 찾아 `shortform_rules.json`에 넣고 `verified: true`로 바꾼다.

## 빌드 (도구 설치 후)
JDK 17 + Android SDK(platform 35, build-tools) 필요.
`cd android && gradlew assembleDebug` → `adb install -r app/build/outputs/apk/debug/app-debug.apk`
