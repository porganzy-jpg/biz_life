import 'package:shared_preferences/shared_preferences.dart';

class PreferencesService {
  static const _notificationsEnabledKey = 'notifications_enabled';
  static const _locationRadiusKey = 'location_radius';
  static const _lastLatKey = 'last_lat';
  static const _lastLngKey = 'last_lng';

  late SharedPreferences _prefs;

  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
  }

  bool get notificationsEnabled =>
      _prefs.getBool(_notificationsEnabledKey) ?? true;

  Future<void> setNotificationsEnabled(bool value) =>
      _prefs.setBool(_notificationsEnabledKey, value);

  double get locationRadius =>
      _prefs.getDouble(_locationRadiusKey) ?? 500.0;

  Future<void> setLocationRadius(double value) =>
      _prefs.setDouble(_locationRadiusKey, value);

  double? get lastLat => _prefs.getDouble(_lastLatKey);
  double? get lastLng => _prefs.getDouble(_lastLngKey);

  Future<void> saveLastLocation(double lat, double lng) async {
    await _prefs.setDouble(_lastLatKey, lat);
    await _prefs.setDouble(_lastLngKey, lng);
  }
}
