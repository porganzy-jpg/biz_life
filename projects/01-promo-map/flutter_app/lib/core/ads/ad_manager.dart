import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'ad_helper.dart';

/// 전면 광고(Interstitial) 관리
///
/// 사용법:
/// ```dart
/// final adManager = AdManager();
/// adManager.loadInterstitial();
/// // ... 적절한 시점에:
/// adManager.showInterstitial();
/// ```
class AdManager {
  InterstitialAd? _interstitialAd;
  bool _isInterstitialReady = false;

  /// 전면 광고 미리 로드
  void loadInterstitial() {
    InterstitialAd.load(
      adUnitId: AdHelper.interstitialAdUnitId,
      request: const AdRequest(),
      adLoadCallback: InterstitialAdLoadCallback(
        onAdLoaded: (ad) {
          _interstitialAd = ad;
          _isInterstitialReady = true;

          ad.fullScreenContentCallback = FullScreenContentCallback(
            onAdDismissedFullScreenContent: (ad) {
              ad.dispose();
              _isInterstitialReady = false;
              loadInterstitial(); // 다음 광고 미리 로드
            },
            onAdFailedToShowFullScreenContent: (ad, error) {
              ad.dispose();
              _isInterstitialReady = false;
              loadInterstitial();
            },
          );
        },
        onAdFailedToLoad: (_) {
          _isInterstitialReady = false;
        },
      ),
    );
  }

  /// 전면 광고 표시 (준비되어 있으면)
  bool showInterstitial() {
    if (_isInterstitialReady && _interstitialAd != null) {
      _interstitialAd!.show();
      return true;
    }
    return false;
  }

  /// 리소스 해제
  void dispose() {
    _interstitialAd?.dispose();
  }
}
