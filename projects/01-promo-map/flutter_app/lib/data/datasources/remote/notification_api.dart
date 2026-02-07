import 'package:dio/dio.dart';
import '../../models/notification_item.dart';

class NotificationApi {
  final Dio dio;

  NotificationApi(this.dio);

  Future<List<NotificationItem>> check({
    required double lat,
    required double lon,
  }) async {
    final response = await dio.get('/api/v1/notifications/check',
        queryParameters: {
          'lat': lat,
          'lon': lon,
        });
    final notifications = (response.data['notifications'] as List<dynamic>)
        .map((e) => NotificationItem.fromJson(e as Map<String, dynamic>))
        .toList();
    return notifications;
  }

  Future<void> logUsage({
    required int storeId,
    required int discountId,
    double savedAmount = 0,
  }) async {
    await dio.post('/api/v1/notifications/use', queryParameters: {
      'store_id': storeId,
      'discount_id': discountId,
      'saved_amount': savedAmount,
    });
  }
}
