import 'package:flutter/material.dart';

class AppColors {
  static const primary = Color(0xFFFF6B35);
  static const primaryLight = Color(0xFFFF8F65);
  static const primaryDark = Color(0xFFE55A25);
  static const secondary = Color(0xFF2D3436);
  static const background = Color(0xFFF8F9FA);
  static const surface = Color(0xFFFFFFFF);
  static const error = Color(0xFFE74C3C);
  static const success = Color(0xFF27AE60);
  static const warning = Color(0xFFF39C12);
  static const textPrimary = Color(0xFF2D3436);
  static const textSecondary = Color(0xFF636E72);
  static const textHint = Color(0xFFB2BEC3);
  static const divider = Color(0xFFDFE6E9);
  static const star = Color(0xFFF39C12);
}

class AppDefaults {
  static const double defaultLatitude = 37.5665;
  static const double defaultLongitude = 126.9780;
  static const double defaultRadius = 500.0;
  static const int defaultPageSize = 20;
  static const Duration animDuration = Duration(milliseconds: 300);
  static const Duration toastDuration = Duration(seconds: 2);
}

class AppStrings {
  static const appName = 'PromoMap';
  static const appDescription = '직장인 할인 지도';
  static const version = '1.0.0';
}
