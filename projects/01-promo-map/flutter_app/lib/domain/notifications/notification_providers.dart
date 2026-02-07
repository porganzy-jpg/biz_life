import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/models/notification_item.dart';
import '../providers/providers.dart';
import '../location/location_provider.dart';

final geofenceNotificationsProvider =
    FutureProvider.autoDispose<List<NotificationItem>>((ref) async {
  final location = ref.watch(currentLocationProvider);
  final repo = ref.watch(notificationRepositoryProvider);

  return location.when(
    data: (pos) => repo.check(lat: pos.latitude, lon: pos.longitude),
    loading: () => <NotificationItem>[],
    error: (_, __) => <NotificationItem>[],
  );
});
