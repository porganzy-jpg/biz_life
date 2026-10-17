#!/usr/bin/env bash
# 사용법 (Git Bash):
#   ./phone.sh build    디버그 APK 빌드
#   ./phone.sh install  빌드 + 폰에 설치
#   ./phone.sh dumps    폰의 덤프 파일을 ./dumps/ 로 가져오기
#   ./phone.sh log      차단 서비스 로그 보기
set -e
cd "$(dirname "$0")"
export JAVA_HOME="C:\\Program Files\\Microsoft\\jdk-17.0.20.101-hotspot"
ADB=/c/Users/user/AppData/Local/Android/Sdk/platform-tools/adb.exe
APK=android/app/build/outputs/apk/debug/app-debug.apk

case "$1" in
  build)   (cd android && ./gradlew.bat assembleDebug --console=plain -q) && ls -la "$APK" ;;
  install) "$0" build && "$ADB" install -r "$APK" ;;
  dumps)   mkdir -p dumps && "$ADB" pull /sdcard/Android/data/app.goyo.detox/files/dumps/. dumps/ && ls dumps ;;
  log)     "$ADB" logcat -s AccessibilityService:* AndroidRuntime:E ;;
  *)       sed -n '2,6p' "$0" ;;
esac
