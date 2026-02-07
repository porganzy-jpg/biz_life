import '../datasources/remote/notification_api.dart';
import '../models/notification_item.dart';

class NotificationRepository {
  final NotificationApi api;

  NotificationRepository({required this.api});

  Future<List<NotificationItem>> check({
    required double lat,
    required double lon,
  }) => api.check(lat: lat, lon: lon);

  Future<void> logUsage({
    required int storeId,
    required int discountId,
    double savedAmount = 0,
  }) => api.logUsage(storeId: storeId, discountId: discountId, savedAmount: savedAmount);
}
