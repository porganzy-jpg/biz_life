import 'dart:io';

/// AdMob 광고 단위 ID 관리
/// 프로덕션 배포 시 실제 ID로 교체 필요
class AdHelper {
  // ── 테스트 광고 ID (개발용) ──
  // Google에서 제공하는 공식 테스트 ID
  static String get bannerAdUnitId {
    if (Platform.isAndroid) {
      return 'ca-app-pub-3940256099942544/6300978111'; // Android 테스트
    }
    return 'ca-app-pub-3940256099942544/2934735716'; // iOS 테스트
  }

  static String get interstitialAdUnitId {
    if (Platform.isAndroid) {
      return 'ca-app-pub-3940256099942544/1033173712'; // Android 테스트
    }
    return 'ca-app-pub-3940256099942544/4411468910'; // iOS 테스트
  }

  static String get rewardedAdUnitId {
    if (Platform.isAndroid) {
      return 'ca-app-pub-3940256099942544/5224354917'; // Android 테스트
    }
    return 'ca-app-pub-3940256099942544/1712485313'; // iOS 테스트
  }

  // ── AdMob 앱 ID ──
  // AndroidManifest.xml에도 같은 값 설정 필요
  static const String androidAppId = 'ca-app-pub-3940256099942544~3347511713'; // 테스트

  // ── 프로덕션 ID (실제 배포 시 교체) ──
  // 아래 주석을 해제하고 실제 AdMob ID로 교체하세요:
  //
  // static String get bannerAdUnitId => 'ca-app-pub-XXXXXXX/YYYYYYY';
  // static String get interstitialAdUnitId => 'ca-app-pub-XXXXXXX/YYYYYYY';
  // static String get rewardedAdUnitId => 'ca-app-pub-XXXXXXX/YYYYYYY';
  // static const String androidAppId = 'ca-app-pub-XXXXXXX~YYYYYYY';
}
